"""SQLite boundary for eligible lesson media and download state."""

from __future__ import annotations

import ctypes
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import aiosqlite

from telegram_courses.catalog_repository import SQLiteCatalogRepository


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _assert_media_identity(
    db: aiosqlite.Connection,
    candidate: DownloadCandidate,
    *,
    require_download: bool = False,
) -> None:
    media_columns = {
        row["name"] for row in await (await db.execute("PRAGMA table_info(media_items)")).fetchall()
    }
    if "remote_observation_state" not in media_columns:
        raise DownloadMediaNotObserved
    download_columns = {
        row["name"] for row in await (await db.execute("PRAGMA table_info(downloads)")).fetchall()
    }
    if "remote_identity_provenance" not in download_columns:
        raise ValueError("RESUME_IDENTITY_MISMATCH")
    current = await (await db.execute(
        "SELECT telegram_media_id, kind, file_size_bytes, remote_observation_state FROM media_items "
        "WHERE id=? AND channel_id=? AND telegram_message_id=? AND media_ordinal=?",
        (candidate.media_item_id, candidate.channel_id,
         candidate.telegram_message_id, candidate.media_ordinal),
    )).fetchone()
    if current is None or (
        current["telegram_media_id"] != candidate.telegram_media_id
        or current["kind"] != "DOCUMENT"
        or current["file_size_bytes"] != candidate.expected_bytes
    ):
        raise ValueError("current remote media identity changed")
    if current["remote_observation_state"] != "OBSERVED":
        raise DownloadMediaNotObserved
    download = await (await db.execute(
        "SELECT remote_identity_media_id, remote_identity_kind, remote_identity_size, "
        "remote_identity_provenance "
        "FROM downloads WHERE media_item_id=?",
        (candidate.media_item_id,),
    )).fetchone()
    if download is None:
        if require_download:
            raise ValueError("RESUME_IDENTITY_MISMATCH")
        return
    if download["remote_identity_provenance"] != "CAPTURED_AT_START":
        raise ValueError("RESUME_IDENTITY_MISMATCH")
    if (
        download["remote_identity_media_id"] != current["telegram_media_id"]
        or download["remote_identity_kind"] != current["kind"]
        or download["remote_identity_size"] != current["file_size_bytes"]
    ):
        raise ValueError("download remote media identity changed; blocked")


@dataclass(frozen=True)
class DownloadCandidate:
    media_item_id: int
    channel_id: int
    telegram_message_id: int
    media_ordinal: int
    telegram_media_id: str
    expected_bytes: int
    original_filename: str | None
    lineage: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class DownloadRecord:
    media_item_id: int
    state: str
    final_path: str | None
    partial_path: str | None
    expected_bytes: int
    downloaded_bytes: int
    sha256: str | None
    failure_category: str | None
    owner_pid: int | None
    contract_version: int | None = None
    evidence_version: int | None = None
    remote_identity_provenance: str | None = None


class DownloadInProgress(Exception):
    """A different process already owns this media transfer."""


class DownloadMediaNotObserved(ValueError):
    """The media ordinal was absent from the latest observation."""


def _require_s6_v2_schema(row: aiosqlite.Row | dict[str, object] | None) -> None:
    if row is not None and (
        row["schema_version"] != 1
        or row["contract_version"] != 2
        or row["evidence_version"] != 1
    ):
        raise ValueError("unsupported S6 V2 record schema")


def _process_is_alive(pid: int | None) -> bool | None:
    if type(pid) is not int or pid <= 0:
        return None
    if os.name == "nt":
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:  # ERROR_INVALID_PARAMETER is positive evidence of absence
                return False
            if error == 5:  # ERROR_ACCESS_DENIED means the process may still be alive
                return True
            return None
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


class DownloadRepository:
    """Owns download SQL; catalog SQL remains with its existing repository."""

    def __init__(self, database_path: str | Path, *, busy_timeout_ms: int = 5000) -> None:
        if type(busy_timeout_ms) is not int or busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        self.database_path = Path(database_path)
        self.busy_timeout_ms = busy_timeout_ms

    async def _connect(self) -> aiosqlite.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self.database_path, timeout=self.busy_timeout_ms / 1000)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        await db.execute("PRAGMA journal_mode = WAL")
        return db

    async def migrate(self) -> None:
        await SQLiteCatalogRepository(self.database_path, busy_timeout_ms=self.busy_timeout_ms).migrate()
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            applied = await (await db.execute(
                "SELECT 1 FROM schema_migrations WHERE version=4"
            )).fetchone()
            if applied is None:
                sql = files("telegram_courses").joinpath("migrations/004_downloads.sql").read_text(encoding="utf-8")
                for statement in sql.split(";"):
                    if statement.strip():
                        await db.execute(statement)
                await db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(4, ?)",
                    (_now(),),
                )
            applied_v2 = await (await db.execute(
                "SELECT 1 FROM schema_migrations WHERE version=5"
            )).fetchone()
            if applied_v2 is None:
                sql = files("telegram_courses").joinpath(
                    "migrations/005_s6_integrity_v2.sql"
                ).read_text(encoding="utf-8")
                for statement in sql.split(";"):
                    if statement.strip():
                        await db.execute(statement)
                await db.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(5, ?)",
                    (_now(),),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def select_candidate(
        self, channel_id: int, message_id: int, media_ordinal: int
    ) -> DownloadCandidate | None:
        db = await self._connect()
        try:
            rows = await (await db.execute(
                "WITH RECURSIVE lineage(id, parent_id, kind, title, depth) AS ("
                " SELECT n.id, n.parent_id, n.kind, n.title, 0 FROM media_items m "
                " JOIN catalog_nodes n ON n.id=m.catalog_node_id AND n.channel_id=m.channel_id "
                " WHERE m.channel_id=? AND m.telegram_message_id=? AND m.media_ordinal=? "
                " AND n.kind='lesson' AND n.is_active=1 "
                " UNION ALL SELECT p.id, p.parent_id, p.kind, p.title, l.depth+1 "
                " FROM catalog_nodes p JOIN lineage l ON p.id=l.parent_id "
                " WHERE p.is_active=1 AND l.depth<4) "
                "SELECT m.id AS media_item_id, m.channel_id, m.telegram_message_id, "
                "m.media_ordinal, m.telegram_media_id, m.file_size_bytes, m.original_filename, "
                "l.kind, l.title, l.depth "
                "FROM media_items m JOIN messages msg ON msg.channel_id=m.channel_id "
                "AND msg.telegram_message_id=m.telegram_message_id "
                "JOIN channels c ON c.telegram_chat_id=m.channel_id "
                "JOIN lineage l ON l.id=m.catalog_node_id "
                "WHERE m.channel_id=? AND m.telegram_message_id=? AND m.media_ordinal=? "
                "AND m.kind='DOCUMENT' AND m.file_size_bytes IS NOT NULL "
                "AND m.file_size_bytes>=0 AND m.telegram_media_id IS NOT NULL "
                "ORDER BY l.depth DESC",
                (channel_id, message_id, media_ordinal, channel_id, message_id, media_ordinal),
            )).fetchall()
            if not rows:
                return None
            first = rows[0]
            lineage = tuple((row["kind"], row["title"]) for row in rows)
            if not any(kind == "lesson" for kind, _ in lineage):
                return None
            if any(kind not in {"lesson", "module", "course", "track"} for kind, _ in lineage):
                return None
            kinds = tuple(kind for kind, _ in lineage)
            if kinds not in {
                ("lesson",),
                ("course", "lesson"),
                ("module", "lesson"),
                ("course", "module", "lesson"),
                ("track", "course", "lesson"),
                ("track", "course", "module", "lesson"),
            }:
                return None
            return DownloadCandidate(
                media_item_id=first["media_item_id"], channel_id=first["channel_id"],
                telegram_message_id=first["telegram_message_id"], media_ordinal=first["media_ordinal"],
                telegram_media_id=first["telegram_media_id"], expected_bytes=first["file_size_bytes"],
                original_filename=first["original_filename"], lineage=lineage,
            )
        finally:
            await db.close()

    async def get_record(self, media_item_id: int) -> DownloadRecord | None:
        db = await self._connect()
        try:
            row = await (await db.execute(
                "SELECT media_item_id, state, final_path, partial_path, expected_bytes, "
                "downloaded_bytes, sha256, failure_category, owner_pid, contract_version, "
                "evidence_version, remote_identity_provenance FROM downloads WHERE media_item_id=?",
                (media_item_id,),
            )).fetchone()
            return DownloadRecord(**dict(row)) if row else None
        finally:
            await db.close()

    async def assert_download_identity(self, candidate: DownloadCandidate) -> None:
        """Fail closed unless a persisted V1 download matches current media identity."""
        if (
            not isinstance(candidate.telegram_media_id, str)
            or not candidate.telegram_media_id.strip()
            or type(candidate.expected_bytes) is not int
            or candidate.expected_bytes < 0
        ):
            raise ValueError("download identity is insufficient")
        db = await self._connect()
        try:
            await db.execute("BEGIN")
            await _assert_media_identity(db, candidate, require_download=True)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def assert_candidate_identity(self, candidate: DownloadCandidate) -> None:
        """Validate current observation and any existing persisted identity."""
        db = await self._connect()
        try:
            await db.execute("BEGIN")
            await _assert_media_identity(db, candidate)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def start(self, candidate: DownloadCandidate, final_path: Path, partial_path: Path) -> None:
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            await _assert_media_identity(db, candidate)
            existing = await (await db.execute(
                "SELECT state, owner_pid, remote_identity_media_id, remote_identity_kind, "
                "remote_identity_size, remote_identity_provenance "
                "FROM downloads WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone()
            if existing is not None and existing["remote_identity_provenance"] != "CAPTURED_AT_START":
                raise ValueError("RESUME_IDENTITY_MISMATCH")
            if existing is not None and (
                existing["remote_identity_media_id"] != candidate.telegram_media_id
                or existing["remote_identity_kind"] != "DOCUMENT"
                or existing["remote_identity_size"] != candidate.expected_bytes
            ):
                raise ValueError("download remote media identity changed; blocked")
            if existing is not None and existing["state"] in {
                "DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"
            }:
                owner_state = _process_is_alive(existing["owner_pid"])
                if owner_state in {True, None}:
                    raise DownloadInProgress
            if (
                existing is not None
                and existing["state"] == "FAILED_RETRYABLE"
                and existing["owner_pid"] is not None
                and _process_is_alive(existing["owner_pid"]) is not False
            ):
                raise DownloadInProgress
            await db.execute(
                "DELETE FROM s6_v2_evidence WHERE media_item_id=?",
                (candidate.media_item_id,),
            )
            await db.execute(
                "INSERT INTO downloads(media_item_id,state,final_path,partial_path,expected_bytes,downloaded_bytes,attempts,owner_pid,created_at,updated_at,remote_identity_media_id,remote_identity_kind,remote_identity_size,remote_identity_provenance) "
                "VALUES(?, 'DOWNLOADING', ?, ?, ?, 0, 1, ?, ?, ?, ?, 'DOCUMENT', ?, 'CAPTURED_AT_START') "
                "ON CONFLICT(media_item_id) DO UPDATE SET state='DOWNLOADING', final_path=excluded.final_path, "
                "partial_path=excluded.partial_path, expected_bytes=excluded.expected_bytes, downloaded_bytes=0, "
                "sha256=NULL, validated_at=NULL, failure_category=NULL, owner_pid=excluded.owner_pid, "
                "remote_identity_provenance=excluded.remote_identity_provenance, "
                "contract_version=NULL, evidence_version=NULL, "
                "attempts=downloads.attempts+1, updated_at=excluded.updated_at",
                (candidate.media_item_id, str(final_path), str(partial_path), candidate.expected_bytes,
                 os.getpid(), now, now, candidate.telegram_media_id, candidate.expected_bytes),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def start_resume(
        self, candidate: DownloadCandidate, final_path: Path, partial_path: Path
    ) -> None:
        """Claim an existing partial without resetting its physical checkpoint."""
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            await _assert_media_identity(db, candidate, require_download=True)
            row = await (await db.execute(
                "SELECT state, owner_pid, final_path, partial_path, expected_bytes, "
                "remote_identity_media_id, remote_identity_kind, remote_identity_size "
                "FROM downloads WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone()
            if row is None or row["state"] not in {
                "FAILED_RETRYABLE", "DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"
            }:
                raise DownloadInProgress
            if row["state"] != "FAILED_RETRYABLE" and row["owner_pid"] is None:
                raise DownloadInProgress
            if row["owner_pid"] is not None and _process_is_alive(row["owner_pid"]) is not False:
                raise DownloadInProgress
            if (
                row["final_path"] != str(final_path)
                or row["partial_path"] != str(partial_path)
                or row["expected_bytes"] != candidate.expected_bytes
                or row["remote_identity_media_id"] != candidate.telegram_media_id
                or row["remote_identity_kind"] != "DOCUMENT"
                or row["remote_identity_size"] != candidate.expected_bytes
            ):
                raise ValueError("resume identity changed")
            await db.execute(
                "DELETE FROM s6_v2_evidence WHERE media_item_id=?",
                (candidate.media_item_id,),
            )
            cursor = await db.execute(
                "UPDATE downloads SET state='DOWNLOADING', owner_pid=?, failure_category=NULL, "
                "error_details=NULL, attempts=attempts+1, updated_at=? "
                "WHERE media_item_id=? AND owner_pid IS ?",
                (os.getpid(), now, candidate.media_item_id, row["owner_pid"]),
            )
            if cursor.rowcount != 1:
                raise DownloadInProgress
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def record_v2_selection(
        self,
        candidate: DownloadCandidate,
        *,
        selected_mode: str,
        invocation_id: str,
        plan_id: str | None = None,
        reference_manifest_path: str | None = None,
    ) -> str:
        """Persist an explicit V2 decision before any gateway call or payload read."""
        if selected_mode not in {
            "REMOTE_HASH_REQUIRED", "OPERATIONAL_ONLY", "TRUSTED_REFERENCE"
        } or not invocation_id:
            raise ValueError("invalid S6 V2 selection")
        attempt_id = f"s6v2:{invocation_id}:{candidate.media_item_id}:{uuid.uuid4().hex}"
        now = _now()
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            await _assert_media_identity(db, candidate, require_download=False)
            await db.execute(
                "INSERT INTO s6_v2_attempts(id, media_item_id, channel_id, "
                "telegram_message_id, media_ordinal, telegram_media_id, expected_bytes, "
                "selected_mode, schema_version, contract_version, evidence_version, plan_id, invocation_id, "
                "reference_manifest_path, status, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, 1, 2, 1, ?, ?, ?, 'SELECTED', ?, ?)",
                (
                    attempt_id, candidate.media_item_id, candidate.channel_id,
                    candidate.telegram_message_id, candidate.media_ordinal,
                    candidate.telegram_media_id, candidate.expected_bytes,
                    selected_mode, plan_id, invocation_id, reference_manifest_path,
                    now, now,
                ),
            )
            await db.commit()
            return attempt_id
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def update_v2_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        details: dict[str, object],
        remote_hash_class: str | None = None,
        evidence_class: str | None = None,
        requests: int = 0,
        bytes_reserved: int = 0,
        bytes_received: int = 0,
    ) -> None:
        if any(type(value) is not int for value in (requests, bytes_reserved, bytes_received)):
            raise ValueError("invalid S6 V2 counters")
        if min(requests, bytes_reserved, bytes_received) < 0:
            raise ValueError("invalid S6 V2 counters")
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            attempt_version = await (await db.execute(
                "SELECT schema_version, contract_version, evidence_version "
                "FROM s6_v2_attempts WHERE id=?",
                (attempt_id,),
            )).fetchone()
            if attempt_version is None:
                raise ValueError("S6 V2 attempt missing")
            _require_s6_v2_schema(attempt_version)
            cursor = await db.execute(
                "UPDATE s6_v2_attempts SET status=?, remote_hash_class=?, evidence_class=?, "
                "details_json=?, requests=?, bytes_reserved=?, bytes_received=?, updated_at=? "
                "WHERE id=?",
                (
                    status, remote_hash_class, evidence_class,
                    json.dumps(details, sort_keys=True, separators=(",", ":")),
                    requests, bytes_reserved, bytes_received, _now(), attempt_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("S6 V2 attempt missing")
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def get_v2_evidence(self, media_item_id: int) -> dict[str, object] | None:
        db = await self._connect()
        try:
            row = await (await db.execute(
                "SELECT * FROM s6_v2_evidence WHERE media_item_id=?",
                (media_item_id,),
            )).fetchone()
            _require_s6_v2_schema(row)
            return dict(row) if row else None
        finally:
            await db.close()

    async def get_latest_v2_attempt(
        self, media_item_id: int, *, exclude_attempt_id: str | None = None
    ) -> dict[str, object] | None:
        db = await self._connect()
        try:
            if exclude_attempt_id is None:
                row = await (await db.execute(
                    "SELECT * FROM s6_v2_attempts WHERE media_item_id=? "
                    "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                    (media_item_id,),
                )).fetchone()
            else:
                row = await (await db.execute(
                    "SELECT * FROM s6_v2_attempts WHERE media_item_id=? AND id<>? "
                    "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                    (media_item_id, exclude_attempt_id),
                )).fetchone()
            _require_s6_v2_schema(row)
            return dict(row) if row else None
        finally:
            await db.close()

    async def complete_v2(
        self,
        candidate: DownloadCandidate,
        *,
        attempt_id: str,
        final_path: Path,
        sha256: str,
        evidence_class: str,
        remote_hash_class: str,
        details: dict[str, object],
    ) -> None:
        """Atomically publish COMPLETED_V2 and its matching versioned evidence."""
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            await _assert_media_identity(db, candidate, require_download=True)
            attempt = await (await db.execute(
                "SELECT * FROM s6_v2_attempts WHERE id=? AND media_item_id=?",
                (attempt_id, candidate.media_item_id),
            )).fetchone()
            if attempt is None or (
                attempt["channel_id"] != candidate.channel_id
                or attempt["telegram_message_id"] != candidate.telegram_message_id
                or attempt["media_ordinal"] != candidate.media_ordinal
                or attempt["telegram_media_id"] != candidate.telegram_media_id
                or attempt["expected_bytes"] != candidate.expected_bytes
                or attempt["schema_version"] != 1
                or attempt["contract_version"] != 2
                or attempt["evidence_version"] != 1
            ):
                raise ValueError("S6 V2 evidence identity mismatch")
            if attempt["status"] != "EVIDENCE_READY":
                raise ValueError("S6 V2 evidence gates are incomplete")
            if (
                type(sha256) is not str
                or len(sha256) != 64
                or any(char not in "0123456789abcdef" for char in sha256)
                or attempt["selected_mode"] not in {"OPERATIONAL_ONLY", "TRUSTED_REFERENCE"}
                or evidence_class != (
                    "OPERATIONAL_ONLY"
                    if attempt["selected_mode"] == "OPERATIONAL_ONLY"
                    else "REFERENCE_MATCH"
                )
                or remote_hash_class not in {
                    "REMOTE_HASH_FULL", "REMOTE_HASH_PARTIAL", "REMOTE_HASH_ABSENT",
                    "REMOTE_HASH_UNVERIFIABLE_EOF",
                }
            ):
                raise ValueError("S6 V2 evidence version or class is invalid")
            selected_mode = str(attempt["selected_mode"])
            expected_identity = {
                "channel_id": candidate.channel_id,
                "telegram_message_id": candidate.telegram_message_id,
                "media_ordinal": candidate.media_ordinal,
                "telegram_media_id": candidate.telegram_media_id,
            }
            expected_guarantee = (
                "UNVERIFIED_ORIGIN"
                if selected_mode == "OPERATIONAL_ONLY"
                else "REFERENCE_MATCH"
            )
            if (
                not isinstance(details, dict)
                or type(details.get("schema_version")) is not int
                or details.get("schema_version") != 1
                or type(details.get("contract_version")) is not int
                or details.get("contract_version") != 2
                or type(details.get("evidence_version")) is not int
                or details.get("evidence_version") != 1
                or details.get("selected_mode") != selected_mode
                or details.get("evidence_classes") != [evidence_class]
                or details.get("remote_hash_class") != remote_hash_class
                or details.get("identity") != expected_identity
                or type(details.get("expected_bytes")) is not int
                or details.get("expected_bytes") != candidate.expected_bytes
                or details.get("final_sha256") != sha256
                or details.get("plan_id") != attempt["plan_id"]
                or details.get("invocation_id") != attempt["invocation_id"]
                or details.get("guarantee") != expected_guarantee
                or type(details.get("requests")) is not int
                or details.get("requests") != attempt["requests"]
                or type(details.get("bytes_received")) is not int
                or details.get("bytes_received") != attempt["bytes_received"]
                or type(details.get("prefix_reread_reserved")) is not int
                or type(details.get("transfer_reserved")) is not int
                or details.get("prefix_reread_reserved")
                + details.get("transfer_reserved") != attempt["bytes_reserved"]
                or not isinstance(details.get("remote_hash_events"), list)
            ):
                raise ValueError("S6 V2 evidence details are inconsistent")
            if selected_mode == "TRUSTED_REFERENCE" and (
                not attempt["reference_manifest_path"]
                or not isinstance(details.get("reference_manifest_sha256"), str)
                or len(str(details.get("reference_manifest_sha256"))) != 64
                or any(char not in "0123456789abcdef" for char in str(details.get("reference_manifest_sha256")))
                or details.get("reference_provenance_state") != "DOCUMENTED_UNATTESTED"
                or not isinstance(details.get("reference_provenance"), str)
                or not str(details.get("reference_provenance")).strip()
            ):
                raise ValueError("S6 V2 reference provenance is missing")
            download = await (await db.execute(
                "SELECT state, owner_pid, expected_bytes, final_path FROM downloads "
                "WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone()
            if download is None or (
                download["state"] not in {"FINALIZATION_PENDING", "FAILED_RETRYABLE"}
                or download["expected_bytes"] != candidate.expected_bytes
                or download["final_path"] != str(final_path)
            ):
                raise ValueError("S6 V2 finalization identity mismatch")
            owner_pid = download["owner_pid"]
            if download["state"] != "FAILED_RETRYABLE" and owner_pid is None:
                raise DownloadInProgress
            if owner_pid is not None and owner_pid != os.getpid():
                if _process_is_alive(owner_pid) is not False:
                    raise DownloadInProgress
                claimed = await db.execute(
                    "UPDATE downloads SET owner_pid=?, updated_at=? WHERE media_item_id=? "
                    "AND state=? AND owner_pid=? AND expected_bytes=? AND final_path=?",
                    (
                        os.getpid(), now, candidate.media_item_id, download["state"],
                        owner_pid, candidate.expected_bytes, str(final_path),
                    ),
                )
                if claimed.rowcount != 1:
                    raise ValueError("S6 V2 recovery ownership changed")
            cursor = await db.execute(
                "UPDATE downloads SET state='COMPLETED_V2', downloaded_bytes=?, sha256=?, "
                "contract_version=2, evidence_version=1, failure_category=NULL, "
                "error_details=NULL, owner_pid=NULL, updated_at=? "
                "WHERE media_item_id=? AND state IN ('FINALIZATION_PENDING','FAILED_RETRYABLE') "
                "AND (owner_pid IS NULL OR owner_pid=?) "
                "AND expected_bytes=? AND final_path=?",
                (
                    candidate.expected_bytes, sha256, now, candidate.media_item_id,
                    os.getpid(), candidate.expected_bytes, str(final_path),
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("S6 V2 finalization state mismatch")
            evidence_json = json.dumps(details, sort_keys=True, separators=(",", ":"))
            await db.execute(
                "INSERT INTO s6_v2_evidence(media_item_id, attempt_id, channel_id, "
                "telegram_message_id, media_ordinal, telegram_media_id, expected_bytes, "
                "final_path, final_sha256, selected_mode, evidence_class, remote_hash_class, "
                "schema_version, contract_version, evidence_version, plan_id, invocation_id, details_json, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 2, 1, ?, ?, ?, ?) "
                "ON CONFLICT(media_item_id) DO UPDATE SET attempt_id=excluded.attempt_id, "
                "channel_id=excluded.channel_id, telegram_message_id=excluded.telegram_message_id, "
                "media_ordinal=excluded.media_ordinal, telegram_media_id=excluded.telegram_media_id, "
                "expected_bytes=excluded.expected_bytes, final_path=excluded.final_path, "
                "final_sha256=excluded.final_sha256, selected_mode=excluded.selected_mode, "
                "evidence_class=excluded.evidence_class, remote_hash_class=excluded.remote_hash_class, "
                "schema_version=1, contract_version=2, evidence_version=1, plan_id=excluded.plan_id, "
                "invocation_id=excluded.invocation_id, details_json=excluded.details_json, "
                "created_at=excluded.created_at",
                (
                    candidate.media_item_id, attempt_id, candidate.channel_id,
                    candidate.telegram_message_id, candidate.media_ordinal,
                    candidate.telegram_media_id, candidate.expected_bytes, str(final_path),
                    sha256, attempt["selected_mode"], evidence_class, remote_hash_class,
                    attempt["plan_id"], attempt["invocation_id"], evidence_json, now,
                ),
            )
            await db.execute(
                "UPDATE s6_v2_attempts SET status='COMPLETED', evidence_class=?, "
                "remote_hash_class=?, details_json=?, updated_at=? WHERE id=?",
                (evidence_class, remote_hash_class, evidence_json, now, attempt_id),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def checkpoint(self, media_item_id: int, downloaded_bytes: int) -> None:
        """Persist an fsynced physical length while this process owns the row."""
        if type(downloaded_bytes) is not int or downloaded_bytes < 0:
            raise ValueError("invalid checkpoint")
        db = await self._connect()
        try:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "UPDATE downloads SET downloaded_bytes=?, updated_at=? "
                "WHERE media_item_id=? AND state='DOWNLOADING' AND owner_pid=?",
                (downloaded_bytes, _now(), media_item_id, os.getpid()),
            )
            if cursor.rowcount != 1:
                raise DownloadInProgress
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    async def transition(
        self, media_item_id: int, state: str, *, downloaded_bytes: int,
        sha256: str | None = None, failure_category: str | None = None,
    ) -> None:
        if state not in {"DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING", "DOWNLOADED", "FAILED_RETRYABLE", "FAILED"}:
            raise ValueError("invalid download state")
        predecessors = {
            "VALIDATED": ("DOWNLOADING",),
            "FINALIZATION_PENDING": ("VALIDATED",),
            "DOWNLOADED": ("VALIDATED", "FINALIZATION_PENDING"),
            "FAILED_RETRYABLE": ("DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING", "DOWNLOADED"),
            "FAILED": ("DOWNLOADING", "VALIDATED", "FINALIZATION_PENDING"),
        }.get(state, ())
        if not predecessors:
            raise ValueError("invalid transition")
        db = await self._connect()
        now = _now()
        try:
            await db.execute("BEGIN IMMEDIATE")
            owner = await (await db.execute(
                "SELECT owner_pid FROM downloads WHERE media_item_id=?",
                (media_item_id,),
            )).fetchone()
            if owner is None or owner["owner_pid"] != os.getpid():
                raise DownloadInProgress
            if state in {"VALIDATED", "FINALIZATION_PENDING", "DOWNLOADED"}:
                identity = await (await db.execute(
                    "SELECT d.remote_identity_media_id, d.remote_identity_kind, "
                    "d.remote_identity_size, d.remote_identity_provenance, "
                    "m.telegram_media_id, m.kind, m.file_size_bytes, m.remote_observation_state "
                    "FROM downloads d JOIN media_items m ON m.id=d.media_item_id "
                    "WHERE d.media_item_id=?",
                    (media_item_id,),
                )).fetchone()
                if identity is not None and identity["remote_observation_state"] != "OBSERVED":
                    raise DownloadMediaNotObserved
                if identity is None or (
                    identity["remote_identity_provenance"] != "CAPTURED_AT_START"
                    or
                    identity["remote_identity_media_id"] != identity["telegram_media_id"]
                    or identity["remote_identity_kind"] != identity["kind"]
                    or identity["remote_identity_size"] != identity["file_size_bytes"]
                ):
                    raise ValueError("download remote media identity changed; blocked")
            allowed = ",".join("?" for _ in predecessors)
            cursor = await db.execute(
                "UPDATE downloads SET state=?, downloaded_bytes=?, sha256=COALESCE(?,sha256), "
                "validated_at=CASE WHEN ?='VALIDATED' THEN ? ELSE validated_at END, "
                "failure_category=?, error_details=?, "
                "owner_pid=CASE WHEN ? IN ('DOWNLOADING','VALIDATED','FINALIZATION_PENDING') THEN owner_pid ELSE NULL END, "
                f"updated_at=? WHERE media_item_id=? AND owner_pid=? AND state IN ({allowed})",
                (state, downloaded_bytes, sha256, state, now, failure_category,
                 failure_category, state, now, media_item_id, os.getpid(), *predecessors),
            )
            if cursor.rowcount != 1:
                raise ValueError("download row missing")
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
