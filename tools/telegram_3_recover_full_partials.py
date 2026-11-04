"""Bounded recovery of five complete .part files; no media transfer.

Verification is independent of download queue, V2 modes and S9 contract.
Default is offline preflight. --verify contacts Telegram for hash-only read.
--commit verifies first, then recovers five files in local SQLite (no new attempt).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from telegram_courses.auth import AuthState
from telegram_courses.config import load_telegram_credentials
from telegram_courses.download_repository import _process_is_alive
from telegram_courses.downloads import _reject_reparse_path
from telegram_courses.telethon_gateway import TelethonGateway

CHANNEL = -1002758699600
MODULE = 46
EXPECTED_TOTAL = 73071671
MAX_BYTES_PER_FILE = 134217728
MAX_HASH_CALLS = 640
HASH_BLOCK = 131072
ROOT = Path(os.environ["LOCALAPPDATA"]) / "telegram_courses_product"
DB = ROOT / "db" / "catalog.sqlite3"
DOWNLOADS = ROOT / "downloads"
REPORT_ROOT = Path(__file__).parents[1] / "docs/reports/TELEGRAM_3_BATCH_RESUME_PILOT_01"


@dataclass(frozen=True)
class Target:
    db_id: int
    message_id: int
    media_id: str
    size: int
    attempts: int
    owner_pid: int | None
    partial: Path
    final: Path


@dataclass(frozen=True)
class Verified:
    target: Target
    sha256: str
    source_is_final: bool = False


def now() -> str:
    return datetime.now(UTC).isoformat()


def connection(*, readonly: bool) -> sqlite3.Connection:
    uri = DB.as_uri() + ("?mode=ro" if readonly else "?mode=rw")
    db = sqlite3.connect(uri, uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    if readonly:
        db.execute("PRAGMA query_only=ON")
    return db


def select_targets() -> tuple[Target, ...]:
    db = connection(readonly=True)
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("DB_INTEGRITY")
        module = db.execute(
            "SELECT title,parent_id,kind FROM catalog_nodes WHERE id=? AND channel_id=?",
            (MODULE, CHANNEL),
        ).fetchone()
        if module is None or module["kind"] != "module" or module["title"] != "Contagem Regressiva":
            raise ValueError("MODULE_INVALID")
        course = db.execute(
            "SELECT title,kind FROM catalog_nodes WHERE id=? AND channel_id=?",
            (module["parent_id"], CHANNEL),
        ).fetchone()
        if course is None or course["kind"] != "course" or not course["title"].startswith("Candidato de Ouro "):
            raise ValueError("COURSE_INVALID")
        rows = db.execute(
            "SELECT m.id,m.telegram_message_id,m.media_ordinal,m.telegram_media_id,"
            "m.file_size_bytes,m.remote_observation_state,d.state,d.final_path,"
            "d.partial_path,d.attempts,d.owner_pid,d.downloaded_bytes,"
            "d.remote_identity_media_id,d.remote_identity_kind,d.remote_identity_size,"
            "d.remote_identity_provenance "
            "FROM media_items m JOIN catalog_nodes n ON n.id=m.catalog_node_id "
            "JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=? AND n.parent_id=? AND n.kind='lesson' "
            "ORDER BY m.telegram_message_id,m.media_ordinal",
            (CHANNEL, MODULE),
        ).fetchall()
        if len(rows) != 5:
            raise ValueError("EXPECTED_FIVE_ITEMS")
        result = []
        for row in rows:
            size = row["file_size_bytes"]
            final = Path(row["final_path"]) if row["final_path"] else None
            partial = Path(row["partial_path"]) if row["partial_path"] else None
            pid = row["owner_pid"]
            if (
                row["state"] != "FAILED_RETRYABLE"
                or row["remote_observation_state"] != "OBSERVED"
                or row["remote_identity_provenance"] != "CAPTURED_AT_START"
                or row["remote_identity_media_id"] != row["telegram_media_id"]
                or row["remote_identity_kind"] != "DOCUMENT"
                or row["remote_identity_size"] != size
                or type(size) is not int or not 0 < size <= MAX_BYTES_PER_FILE
                or type(row["downloaded_bytes"]) is not int or row["downloaded_bytes"] != size
                or type(row["attempts"]) is not int or row["attempts"] != 1
                or row["media_ordinal"] != 0 or not row["telegram_media_id"]
                or final is None or partial is None or final.exists()
                or not partial.is_file() or partial.is_symlink()
                or str(partial) != str(final) + ".part"
                or not partial.is_relative_to(DOWNLOADS)
                or not final.is_relative_to(DOWNLOADS)
                or partial.stat().st_size != size
                or (pid is not None and _process_is_alive(pid) is not False)
            ):
                raise ValueError("PILOT_ROW_OR_FILE_STATE_INVALID")
            _reject_reparse_path(DOWNLOADS.absolute(), final)
            _reject_reparse_path(DOWNLOADS.absolute(), partial)
            result.append(Target(
                row["id"], row["telegram_message_id"], str(row["telegram_media_id"]),
                size, row["attempts"], pid, partial, final,
            ))
        if sum(target.size for target in result) != EXPECTED_TOTAL:
            raise ValueError("AGGREGATE_BUDGET_MISMATCH")
        return tuple(result)
    finally:
        db.close()


class RPCBudget:
    def __init__(self, gateway, limit: int = MAX_HASH_CALLS):
        self.gateway = gateway
        self.limit = limit
        self.calls = 0

    async def hashes(self, target: Target, offset: int):
        if self.calls >= self.limit:
            raise RuntimeError("HASH_RPC_BUDGET_EXHAUSTED")
        self.calls += 1
        return await asyncio.wait_for(
            self.gateway.get_file_hashes(
                CHANNEL, target.message_id, 0,
                telegram_media_id=target.media_id,
                expected_bytes=target.size, offset=offset,
            ),
            timeout=30,
        )


async def verify_one(target: Target, gateway, budget: RPCBudget) -> Verified:
    if await asyncio.wait_for(
        gateway.validate_media_identity(
            CHANNEL, target.message_id, 0,
            telegram_media_id=target.media_id, expected_bytes=target.size,
        ),
        timeout=30,
    ) is not True:
        raise ValueError("REMOTE_IDENTITY_INVALID")
    expected = target.size
    cursor = 0
    total_hasher = hashlib.sha256()
    with target.partial.open("rb") as stream:
        initial = os.fstat(stream.fileno())
        if not stat.S_ISREG(initial.st_mode) or initial.st_size != expected:
            raise ValueError("LOCAL_FILE_UNSAFE")
        signature = (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns)
        while cursor < expected:
            original_cursor = cursor
            ranges = await budget.hashes(target, cursor)
            if not isinstance(ranges, (list, tuple)) or not 0 < len(ranges) <= 32:
                raise ValueError("HASH_PAGE_INVALID")
            last_start = -1
            for remote in ranges:
                offset = getattr(remote, "offset", None)
                limit = getattr(remote, "limit", None)
                digest = getattr(remote, "sha256", None)
                if (
                    type(offset) is not int or type(limit) is not int
                    or type(digest) is not bytes or len(digest) != 32
                    or offset < 0 or offset <= last_start or limit <= 0
                ):
                    raise ValueError("HASH_RANGE_INVALID")
                last_start = offset
                reported_end = offset + limit
                if reported_end > expected and not (
                    offset < expected and limit == HASH_BLOCK
                    and offset % HASH_BLOCK == 0
                    and 0 < reported_end - expected < HASH_BLOCK
                ):
                    raise ValueError("HASH_EOF_GEOMETRY_INVALID")
                effective_end = min(reported_end, expected)
                if offset > cursor or (offset < cursor and effective_end > cursor):
                    raise ValueError("HASH_COVERAGE_GAP_OR_OVERLAP")
                stream.seek(offset)
                local_bytes = stream.read(effective_end - offset)
                if len(local_bytes) != effective_end - offset:
                    raise ValueError("LOCAL_READ_INCOMPLETE")
                if hashlib.sha256(local_bytes).digest() != digest:
                    raise ValueError("REMOTE_HASH_DIVERGENT")
                if offset == cursor:
                    total_hasher.update(local_bytes)
                    cursor = effective_end
            if cursor <= original_cursor:
                raise ValueError("HASH_PAGE_NO_PROGRESS")
        end = os.fstat(stream.fileno())
        end_signature = (end.st_dev, end.st_ino, end.st_size, end.st_mtime_ns)
        if end_signature != signature or target.partial.is_symlink():
            raise ValueError("LOCAL_FILE_CHANGED")
    return Verified(target, total_hasher.hexdigest())


def _file_sha256(path: Path, expected: int) -> str:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while data := f.read(262144):
            digest.update(data)
            size += len(data)
    if size != expected or path.is_symlink():
        raise ValueError("FILE_SIZE_OR_SYMLINK")
    return digest.hexdigest()


def finalize_one(verified: Verified) -> None:
    item = verified.target
    if item.final.exists() or not item.partial.is_file():
        raise ValueError("FINAL_OR_PARTIAL_CHANGED")
    _reject_reparse_path(DOWNLOADS.absolute(), item.partial)
    _reject_reparse_path(DOWNLOADS.absolute(), item.final)
    if _file_sha256(item.partial, item.size) != verified.sha256:
        raise ValueError("PARTIAL_CHANGED_AFTER_REMOTE_PROOF")
    conn = connection(readonly=False)
    renamed = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT d.*,m.telegram_media_id,m.kind,m.file_size_bytes,m.remote_observation_state "
            "FROM downloads d JOIN media_items m ON m.id=d.media_item_id "
            "WHERE d.media_item_id=?", (item.db_id,),
        ).fetchone()
        if (
            row is None or row["state"] != "FAILED_RETRYABLE"
            or row["attempts"] != item.attempts or row["owner_pid"] != item.owner_pid
            or row["remote_identity_media_id"] != row["telegram_media_id"]
            or row["remote_identity_kind"] != "DOCUMENT" or row["kind"] != "DOCUMENT"
            or row["remote_identity_size"] != row["file_size_bytes"]
            or row["remote_observation_state"] != "OBSERVED"
            or row["remote_identity_provenance"] != "CAPTURED_AT_START"
            or row["expected_bytes"] != item.size or row["downloaded_bytes"] != item.size
            or row["final_path"] != str(item.final)
            or row["partial_path"] != str(item.partial)
            or (item.owner_pid is not None and _process_is_alive(item.owner_pid) is not False)
        ):
            raise ValueError("COMMIT_IDENTITY_OR_STATE_CHANGED")
        timestamp = now()
        cursor = conn.execute(
            "UPDATE downloads SET state='VALIDATED', sha256=?,validated_at=?,"
            "failure_category=NULL,error_details='PILOT_REMOTE_HASH_FULL_RECOVERY',"
            "owner_pid=?,updated_at=? WHERE media_item_id=? AND state='FAILED_RETRYABLE' "
            "AND attempts=?",
            (verified.sha256, timestamp, os.getpid(), timestamp, item.db_id, item.attempts),
        )
        if cursor.rowcount != 1:
            raise ValueError("RECOVERY_CLAIM_FAILED")
        conn.execute(
            "UPDATE downloads SET state='FINALIZATION_PENDING',updated_at=? "
            "WHERE media_item_id=? AND state='VALIDATED' AND owner_pid=?",
            (timestamp, item.db_id, os.getpid()),
        )
        # Windows same-volume rename never overwrites an existing target.
        if item.final.exists():
            raise ValueError("TARGET_COLLISION")
        os.rename(item.partial, item.final)
        renamed = True
        if _file_sha256(item.final, item.size) != verified.sha256:
            raise ValueError("POST_RENAME_HASH_MISMATCH")
        completed = conn.execute(
            "UPDATE downloads SET state='DOWNLOADED',sha256=?,downloaded_bytes=?,"
            "owner_pid=NULL,failure_category=NULL,"
            "error_details='PILOT_REMOTE_HASH_FULL_RECOVERY',updated_at=? "
            "WHERE media_item_id=? AND state='FINALIZATION_PENDING' AND owner_pid=?",
            (verified.sha256, item.size, now(), item.db_id, os.getpid()),
        )
        if completed.rowcount != 1:
            raise ValueError("RECOVERY_COMPLETION_FAILED")
        conn.commit()
    except Exception:
        conn.rollback()
        if renamed:
            # Preserve the verified data even if SQLite commit fails.
            # A separate, separately-tested reconciliation is then needed.
            raise RuntimeError("RECOVERY_POST_RENAME_RECONCILIATION_REQUIRED") from None
        raise
    finally:
        conn.close()


def backup_catalog_once() -> None:
    """Keep a private SQLite snapshot before any recovery changes."""
    backup = ROOT / "db" / "catalog.pre_telegram3_recovery.sqlite3"
    if backup.exists() or backup.is_symlink():
        raise ValueError("RECOVERY_BACKUP_ALREADY_EXISTS")
    source = connection(readonly=True)
    destination = None
    try:
        destination = sqlite3.connect(backup)
        source.backup(destination)
        if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("RECOVERY_BACKUP_INVALID")
    finally:
        source.close()
        if destination is not None:
            destination.close()


async def run(*, commit: bool):
    items = select_targets()
    gateway = TelethonGateway(
        load_telegram_credentials(),
        bounded_metadata_channel_id=CHANNEL,
        receive_updates=False, catch_up=False,
        request_retries=0, connection_retries=0,
    )
    budget = RPCBudget(gateway)
    proofs = []
    try:
        if await asyncio.wait_for(gateway.restore(), timeout=30) is not AuthState.AUTHENTICATED:
            raise ValueError("SESSION_NOT_AUTHENTICATED")
        for index, target in enumerate(items, 1):
            proof = await verify_one(target, gateway, budget)
            proofs.append(proof)
            print(f"MEDIA_{index}_FULL_REMOTE_HASH=PASS CALLS_TOTAL={budget.calls}", flush=True)
    finally:
        await gateway.close()
    if len(proofs) != len(items):
        raise ValueError("INCOMPLETE_PROOF_SET")
    if commit:
        backup_catalog_once()
        for index, proof in enumerate(proofs, 1):
            finalize_one(proof)
            print(f"MEDIA_{index}_LOCAL_RECOVERY=COMPLETED", flush=True)
    return {
        "status": "COMPLETED" if commit else "REMOTE_FULL_HASH_VERIFIED",
        "files": len(proofs), "hash_requests": budget.calls,
        "payload_download_bytes": 0, "original_attempts_preserved": True,
        "finalized": len(proofs) if commit else 0,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--commit", action="store_true")
    args=parser.parse_args()
    if args.verify == args.commit:
        # No live RPC by default; exactly one explicit action required.
        print("USE_EXPLICIT_VERIFY_OR_COMMIT")
        return 2
    lock_file = ROOT / "pilot_recovery_running.lock"
    lock_fd = None
    locked = False
    try:
        lock_fd = os.open(lock_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        locked = True
        os.close(lock_fd)
        lock_fd = None
        result = asyncio.run(asyncio.wait_for(run(commit=args.commit), timeout=3600))
        REPORT_ROOT.joinpath(
            "RECOVERY_RESULT.json" if args.commit else "RECOVERY_VERIFICATION.json"
        ).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        error_class = type(exc).__name__
        print("RECOVERY_BLOCKED="+(error_class if error_class.isascii() else "Unknown"))
        return 3
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        if locked:
            try:
                lock_file.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
