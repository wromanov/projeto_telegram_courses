"""Offline, two-process proof of the frozen S6 resume path and durable budgets."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
from tools.manual_proofs import s6_real_resume_proof as config

from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import (
    CHUNK_BYTES,
    ChunkReservation,
    DownloadError,
    DownloadGatewayError,
    RemoteFileHash,
    SingleMediaDownloadApplication,
)

MAX_GETFILE = config.MAX_GETFILE_REQUESTS
MAX_HASHES = config.MAX_GETFILEHASHES_REQUESTS
MAX_PAYLOAD = config.MAX_TRANSFER_BYTES
TARGET_ID = {
    "channel_id": config.CHANNEL_ID,
    "message_id": config.MESSAGE_ID,
    "media_ordinal": config.MEDIA_ORDINAL,
    "media_kind": config.MEDIA_KIND,
    "telegram_media_id": config.TELEGRAM_MEDIA_ID,
    "expected_bytes": config.EXPECTED_BYTES,
}


class BudgetStop(Exception):
    pass


def _capture_hash_range_geometry(ranges: object) -> tuple[list[dict[str, object]], int | None]:
    """Best-effort sanitized snapshot, independent of fail-fast validation."""
    if not isinstance(ranges, (tuple, list)):
        return [], None
    captured: list[dict[str, object]] = []
    for index, item in enumerate(ranges):
        try:
            offset = getattr(item, "offset", None)
        except BaseException:
            offset = None
        try:
            limit = getattr(item, "limit", None)
        except BaseException:
            limit = None
        try:
            raw_digest = getattr(item, "sha256", None)
            if isinstance(raw_digest, bytes):
                digest_length = len(raw_digest)
            elif isinstance(raw_digest, str):
                try:
                    digest_length = len(bytes.fromhex(raw_digest))
                except ValueError:
                    digest_length = None
            else:
                digest_length = None
        except BaseException:
            digest_length = None
        valid_offset = offset if type(offset) is int else None
        valid_limit = limit if type(limit) is int else None
        end = (valid_offset + valid_limit
               if valid_offset is not None and valid_limit is not None else None)
        captured.append({
            "index": index,
            "offset": valid_offset,
            "limit": valid_limit,
            "length": valid_limit,
            "end": end,
            "digest_length": digest_length,
        })
    return captured, len(ranges)


def validate_hash_response(
    offset: int,
    ranges: object,
    expected_bytes: int,
    *,
    diagnostics: dict[str, object] | None = None,
) -> int:
    """Validate one response and return its contiguous exclusive end offset."""
    current_index: int | None = None

    def reject(category: str, reason: str) -> None:
        if diagnostics is not None:
            diagnostic_classifications = {
                "range_exceeds_expected_bytes": "RANGE_EXTENDS_BEYOND_EOF",
                "invalid_digest_length": "INVALID_RANGE",
                "invalid_range_length": "INVALID_RANGE",
                "digest_not_hex": "INVALID_RANGE",
                "invalid_digest_type": "INVALID_RANGE",
                "invalid_request_bounds": "INVALID_RANGE",
                "invalid_range_bounds": "INVALID_RANGE",
                "range_before_cursor": "RANGE_BEFORE_CURSOR",
                "range_overlap": "ACTUAL_RANGE_OVERLAP",
                "range_gap": "OTHER_CONFIRMED_REASON",
                "response_made_no_progress": "OTHER_CONFIRMED_REASON",
                "empty_or_non_sequence_response": "OTHER_CONFIRMED_REASON",
                "unexpected_range_type": "OTHER_CONFIRMED_REASON",
            }
            legacy_classifications = {
                "range_exceeds_expected_bytes": "HASH_RANGE_EXTENDS_BEYOND_EOF",
                "invalid_digest_length": "INVALID_HASH_LENGTH",
                "invalid_range_length": "INVALID_HASH_LENGTH",
                "digest_not_hex": "INVALID_HASH_LENGTH",
                "invalid_digest_type": "INVALID_HASH_LENGTH",
                "invalid_request_bounds": "INVALID_HASH_OFFSET",
                "invalid_range_bounds": "INVALID_HASH_OFFSET",
                "range_before_cursor": "HASH_INTERVAL_OVERLAP",
                "range_overlap": "HASH_INTERVAL_OVERLAP",
                "range_gap": "HASH_INTERVAL_GAP",
                "response_made_no_progress": "HASH_CURSOR_NO_PROGRESS",
                "empty_or_non_sequence_response": "HASH_CURSOR_NO_PROGRESS",
                "unexpected_range_type": "OTHER_CONFIRMED_REASON",
            }
            diagnostics["rejection_reason"] = reason
            diagnostics["failure_category"] = category
            diagnostics["diagnostic_classification"] = diagnostic_classifications.get(
                reason, "OTHER_CONFIRMED_REASON"
            )
            diagnostics["rejection_classification"] = legacy_classifications.get(
                reason, "OTHER_CONFIRMED_REASON"
            )
            diagnostics["first_rejected_index"] = current_index
            diagnostics["cursor_after"] = (
                diagnostics.get("cursor_after")
                if diagnostics.get("cursor_after") is not None
                else diagnostics.get("cursor_before")
            )
        raise BudgetStop(category)

    if diagnostics is not None:
        try:
            captured_ranges, count_received = _capture_hash_range_geometry(ranges)
            capture_error = None
        except BaseException as error:
            # Telemetry is best effort and must never replace a validation result.
            captured_ranges, count_received = [], (
                len(ranges) if isinstance(ranges, (tuple, list)) else None
            )
            capture_error = type(error).__name__
        diagnostics.update({
            "requested_offset": offset,
            "expected_bytes": expected_bytes,
            "cursor_before": offset,
            "cursor_after": None,
            "returned_ranges": captured_ranges,
            "range_count_received": count_received,
            "range_count_inspected": 0,
            "first_rejected_index": None,
            "telemetry_capture_status": "FAILED" if capture_error else "COMPLETE",
            "telemetry_capture_error": capture_error,
            "rejection_reason": None,
            "failure_category": None,
        })
    if type(offset) is not int or type(expected_bytes) is not int or not 0 <= offset <= expected_bytes:
        reject("HASH_COVERAGE_INVALID", "invalid_request_bounds")
    if not isinstance(ranges, (tuple, list)) or not ranges:
        reject("HASH_COVERAGE_STALLED", "empty_or_non_sequence_response")
    cursor = offset
    accepted_intervals: list[tuple[int, int]] = []
    for index, item in enumerate(ranges):
        current_index = index
        if diagnostics is not None:
            diagnostics["range_count_inspected"] = index + 1
            captured = diagnostics.get("returned_ranges", [])
            range_evidence = captured[index] if index < len(captured) else {
                "index": index, "offset": None, "limit": None, "length": None,
                "end": None, "digest_length": None,
            }
        else:
            range_evidence = {}
        if not isinstance(item, RemoteFileHash):
            reject("HASH_COVERAGE_INVALID", "unexpected_range_type")
        if type(item.offset) is not int or item.offset < 0:
            reject("HASH_COVERAGE_INVALID", "invalid_range_bounds")
        if type(item.limit) is not int:
            reject("HASH_COVERAGE_INVALID", "invalid_range_length")
        end = item.offset + item.limit
        range_evidence["end"] = end
        if item.limit <= 0:
            reject("HASH_COVERAGE_INVALID", "invalid_range_length")
        if end > expected_bytes:
            reject("HASH_COVERAGE_INVALID", "range_exceeds_expected_bytes")
        if item.offset < cursor:
            overlaps_prior = any(
                item.offset < prior_end and end > prior_offset
                for prior_offset, prior_end in accepted_intervals
            )
            if not overlaps_prior and end <= offset:
                reject("HASH_COVERAGE_OVERLAP", "range_before_cursor")
            reject("HASH_COVERAGE_OVERLAP", "range_overlap")
        if item.offset > cursor:
            reject("HASH_COVERAGE_GAP", "range_gap")
        raw_digest = item.sha256
        if isinstance(raw_digest, str):
            try:
                digest = bytes.fromhex(raw_digest)
            except ValueError:
                reject("HASH_COVERAGE_INVALID", "digest_not_hex")
        elif isinstance(raw_digest, bytes):
            digest = raw_digest
        else:
            reject("HASH_COVERAGE_INVALID", "invalid_digest_type")
        range_evidence["digest_length"] = len(digest)
        if len(digest) != hashlib.sha256().digest_size:
            reject(
                "HASH_COVERAGE_INVALID",
                "invalid_digest_length",
            )
        accepted_intervals.append((item.offset, end))
        cursor = end
        if diagnostics is not None:
            diagnostics["cursor_after"] = cursor
    if cursor <= offset:
        reject("HASH_COVERAGE_STALLED", "response_made_no_progress")
    return cursor


def _persist_hash_coverage_event(path: Path, event: dict[str, object]) -> None:
    """Durably append sanitized hash-coverage metadata without retaining digests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _safe_remote_reason(error: BaseException) -> str:
    reason = getattr(error, "category", type(error).__name__)
    if (isinstance(reason, str) and reason.isascii() and 0 < len(reason) <= 80
            and all(character.isupper() or character.isdigit() or character == "_"
                    for character in reason)):
        return reason
    return "REMOTE_REQUEST_FAILED"


class DurableBudgetLedger:
    """SQLite reservation ledger shared by independent interpreter processes."""

    def __init__(
        self,
        path: Path,
        *,
        getfile_cap: int = MAX_GETFILE,
        payload_cap: int = MAX_PAYLOAD,
        hash_cap: int = MAX_HASHES,
    ) -> None:
        self.path = path
        self.getfile_cap = getfile_cap
        self.payload_cap = payload_cap
        self.hash_cap = hash_cap
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS budget_totals (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    getfile_calls INTEGER NOT NULL,
                    payload_reserved INTEGER NOT NULL,
                    payload_received INTEGER NOT NULL,
                    hash_calls INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO budget_totals VALUES (1, 0, 0, 0, 0);
                CREATE TABLE IF NOT EXISTS reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('GETFILE','GETFILEHASHES')),
                    reserved_bytes INTEGER NOT NULL,
                    received_bytes INTEGER,
                    status TEXT NOT NULL CHECK(status IN ('RESERVED','SETTLED','UNCERTAIN')),
                    process_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def reserve_getfile(self, amount: int) -> "LedgerReservation":
        if type(amount) is not int or not 0 < amount <= CHUNK_BYTES:
            raise BudgetStop("TRANSFER_BUDGET_RESERVATION_INVALID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            calls, reserved, _received, _hashes = db.execute(
                "SELECT getfile_calls,payload_reserved,payload_received,hash_calls "
                "FROM budget_totals WHERE singleton=1"
            ).fetchone()
            if calls >= self.getfile_cap or reserved + amount > self.payload_cap:
                db.rollback()
                raise BudgetStop("TRANSFER_BUDGET_EXHAUSTED")
            cur = db.execute(
                "INSERT INTO reservations(kind,reserved_bytes,status,process_id,created_at) "
                "VALUES('GETFILE',?,'RESERVED',?,?)",
                (amount, os.getpid(), datetime.now(UTC).isoformat()),
            )
            db.execute(
                "UPDATE budget_totals SET getfile_calls=getfile_calls+1, "
                "payload_reserved=payload_reserved+? WHERE singleton=1",
                (amount,),
            )
            db.commit()
            return LedgerReservation(self.path, cur.lastrowid, amount)

    def reserve_hash_call(self) -> "HashCallReservation":
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            (calls,) = db.execute(
                "SELECT hash_calls FROM budget_totals WHERE singleton=1"
            ).fetchone()
            if calls >= self.hash_cap:
                db.rollback()
                raise BudgetStop("HASH_COVERAGE_BUDGET_EXHAUSTED")
            cur = db.execute(
                "INSERT INTO reservations(kind,reserved_bytes,status,process_id,created_at) "
                "VALUES('GETFILEHASHES',0,'RESERVED',?,?)",
                (os.getpid(), datetime.now(UTC).isoformat()),
            )
            db.execute(
                "UPDATE budget_totals SET hash_calls=hash_calls+1 WHERE singleton=1"
            )
            db.commit()
            return HashCallReservation(self.path, cur.lastrowid)

    def snapshot(self) -> dict[str, int]:
        with self._connect() as db:
            row = db.execute(
                "SELECT getfile_calls,payload_reserved,payload_received,hash_calls "
                "FROM budget_totals WHERE singleton=1"
            ).fetchone()
            (open_reservations,) = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE status='RESERVED'"
            ).fetchone()
            (uncertain,) = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE status='UNCERTAIN'"
            ).fetchone()
        return {
            "getfile_calls_reserved": row[0],
            "payload_bytes_reserved": row[1],
            "payload_bytes_received": row[2],
            "getfilehashes_calls_reserved": row[3],
            "open_reservations": open_reservations,
            "uncertain_reservations": uncertain,
        }


class LedgerReservation(ChunkReservation):
    def __init__(self, path: Path, reservation_id: int, amount: int) -> None:
        self.path = path
        self.reservation_id = reservation_id
        self.amount = amount
        self._settled = False

    def received(self, byte_count: int) -> None:
        if self._settled or type(byte_count) is not int or not 0 <= byte_count <= self.amount:
            raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute(
                "UPDATE reservations SET status='SETTLED',received_bytes=? "
                "WHERE reservation_id=? AND status='RESERVED'",
                (byte_count, self.reservation_id),
            )
            if cur.rowcount != 1:
                db.rollback()
                raise DownloadError("TRANSFER_BUDGET_STATE_INVALID")
            db.execute(
                "UPDATE budget_totals SET payload_received=payload_received+? "
                "WHERE singleton=1", (byte_count,)
            )
            db.commit()
        self._settled = True

    def release(self) -> None:
        # Reservations are intentionally never refunded by this proof ledger.
        self.charge_uncertain()

    def charge_uncertain(self) -> None:
        if self._settled:
            return
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "UPDATE reservations SET status='UNCERTAIN' WHERE reservation_id=? "
                "AND status='RESERVED'", (self.reservation_id,)
            )
        self._settled = True


class HashCallReservation:
    def __init__(self, path: Path, reservation_id: int) -> None:
        self.path = path
        self.reservation_id = reservation_id
        self._settled = False

    def received(self) -> None:
        self._settle("SETTLED")

    def charge_uncertain(self) -> None:
        self._settle("UNCERTAIN")

    def _settle(self, status: str) -> None:
        if self._settled:
            return
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("PRAGMA synchronous=FULL")
            cursor = db.execute(
                "UPDATE reservations SET status=? WHERE reservation_id=? AND status='RESERVED'",
                (status, self.reservation_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("HASH_BUDGET_STATE_INVALID")
        self._settled = True


class BudgetedRealGateway:
    """Apply the proof's durable aggregate ledger to the production Telethon adapter."""

    def __init__(self, gateway, ledger: DurableBudgetLedger, *, phase: int) -> None:
        self.gateway = gateway
        self.ledger = ledger
        self.phase = phase
        self.hash_ranges: list[tuple[int, int]] = []
        self.prefix_bytes_yielded = 0
        self.hash_evidence_path = ledger.path.with_name("hash-coverage.jsonl")
        self.call_index = 0
        self.next_justification: str | None = None

    async def restore(self):
        return await self.gateway.restore()

    async def get_file_hashes(self, *args, **kwargs):
        try:
            reservation = self.ledger.reserve_hash_call()
        except BudgetStop as error:
            raise DownloadGatewayError(str(error)) from None
        self.call_index += 1
        requested_offset = kwargs.get("offset", 0)
        expected_bytes = kwargs.get("expected_bytes")
        event: dict[str, object] = {
            "event": "GETFILEHASHES_RESPONSE",
            "phase": self.phase,
            "process_id": os.getpid(),
            "reservation_id": reservation.reservation_id,
            "call_index": self.call_index,
            "correlation_id": f"GETFILEHASHES-{reservation.reservation_id:04d}",
            "requested_offset": requested_offset,
            "expected_bytes": expected_bytes,
            "response_received": False,
            "range_count": None,
            "range_count_received": None,
            "range_count_inspected": 0,
            "first_rejected_index": None,
            "returned_ranges": [],
            "cursor_before": requested_offset,
            "cursor_after": None,
            "failure_category": None,
            "rejection_classification": None,
            "rejection_reason": None,
            "validation_result": "NOT_VALIDATED",
            "justification": self.next_justification,
        }
        self.next_justification = None
        try:
            ranges = await self.gateway.get_file_hashes(*args, **kwargs)
        except BaseException as error:
            reservation.charge_uncertain()
            event.update({
                "failure_category": "REMOTE_REQUEST_FAILED",
                "rejection_classification": "OTHER_CONFIRMED_REASON",
                "rejection_reason": _safe_remote_reason(error),
                "validation_result": "NOT_VALIDATED",
            })
            _persist_hash_coverage_event(self.hash_evidence_path, event)
            raise
        event["response_received"] = True
        event["range_count"] = len(ranges) if isinstance(ranges, (tuple, list)) else None
        reservation.received()
        diagnostics: dict[str, object] = {}
        try:
            end = validate_hash_response(requested_offset, ranges, expected_bytes, diagnostics=diagnostics)
        except BudgetStop as error:
            event.update(diagnostics)
            event["validation_result"] = "REJECTED"
            try:
                _persist_hash_coverage_event(self.hash_evidence_path, event)
            except BaseException:
                # Preserve the validator's fail-closed category if evidence I/O fails.
                pass
            raise DownloadGatewayError(str(error)) from None
        event.update(diagnostics)
        event["validation_result"] = "PASS"
        _persist_hash_coverage_event(self.hash_evidence_path, event)
        self.hash_ranges.extend((item.offset, item.offset + item.limit) for item in ranges)
        if end <= requested_offset:
            raise DownloadGatewayError("HASH_COVERAGE_STALLED")
        return ranges

    async def stream_media(self, *args, **kwargs):
        source = self.gateway.stream_media(*args, **kwargs)
        if self.phase != 1:
            async for chunk in source:
                yield chunk
            return
        remaining = config.PREFIX_BYTES
        async for chunk in source:
            portion = chunk[:remaining]
            if portion:
                self.prefix_bytes_yielded += len(portion)
                remaining -= len(portion)
                yield portion
            if remaining == 0:
                await source.aclose()
                raise DownloadGatewayError("CONTROLLED_INTERRUPTION_AFTER_DURABLE_PREFIX")
        raise DownloadGatewayError("PREFIX_TARGET_NOT_REACHED")

    async def close(self) -> None:
        await self.gateway.close()


async def _real_gateway(ledger: DurableBudgetLedger, *, phase: int) -> BudgetedRealGateway:
    from telegram_courses.auth import AuthState
    from telegram_courses.config import load_telegram_credentials
    from telegram_courses.telethon_gateway import TelethonGateway

    gateway = None
    try:
        credentials = load_telegram_credentials()
        gateway = TelethonGateway(
            credentials, request_retries=0, connection_retries=0,
        )
        wrapped = BudgetedRealGateway(gateway, ledger, phase=phase)
        state = await wrapped.restore()
        if state is not AuthState.AUTHENTICATED:
            await wrapped.close()
            raise RuntimeError("SESSION_UNAVAILABLE")
        return wrapped
    except RuntimeError:
        raise
    except Exception:
        if gateway is not None:
            try:
                await gateway.close()
            except Exception:
                pass
        raise RuntimeError("SESSION_UNAVAILABLE") from None


async def _real_phase1(root: Path) -> dict[str, object]:
    database = root / "isolated-app.sqlite3"
    ledger = DurableBudgetLedger(root / "budget-ledger.sqlite3")
    await seed_isolated_catalog(database)
    gateway = await _real_gateway(ledger, phase=1)
    repository = DownloadRepository(database)
    app = SingleMediaDownloadApplication(repository, gateway, root / "downloads")

    async def reserve(amount: int):
        try:
            return ledger.reserve_getfile(amount)
        except BudgetStop as error:
            raise DownloadError(str(error)) from None

    app.chunk_reserver = reserve
    try:
        try:
            await app.download(config.CHANNEL_ID, config.MESSAGE_ID, config.MEDIA_ORDINAL)
            raise RuntimeError("CONTROLLED_INTERRUPTION_NOT_OBSERVED")
        except DownloadError as error:
            if error.category != "CONTROLLED_INTERRUPTION_AFTER_DURABLE_PREFIX":
                raise
        candidate = await repository.select_candidate(
            config.CHANNEL_ID, config.MESSAGE_ID, config.MEDIA_ORDINAL
        )
        record = await repository.get_record(candidate.media_item_id) if candidate else None
        partial = next((root / "downloads").rglob("*.part"), None)
        if (candidate is None or record is None or partial is None
                or record.state != "FAILED_RETRYABLE"
                or record.downloaded_bytes != config.PREFIX_BYTES
                or partial.stat().st_size != config.PREFIX_BYTES):
            raise RuntimeError("PHASE1_PREFIX_CHECKPOINT_MISMATCH")
        return {
            "process_id": os.getpid(), "partial_bytes": partial.stat().st_size,
            "sqlite_state": record.state, "sqlite_checkpoint_bytes": record.downloaded_bytes,
            "getfile_calls": ledger.snapshot()["getfile_calls_reserved"],
            "getfilehashes_calls": ledger.snapshot()["getfilehashes_calls_reserved"],
            "network_payload_bytes": ledger.snapshot()["payload_bytes_received"],
            "budget": ledger.snapshot(), "remote_identity_rechecked": True,
        }
    finally:
        await gateway.close()


async def _real_phase2(root: Path, phase1_pid: int) -> dict[str, object]:
    from telegram_courses.download_repository import _process_is_alive

    if _process_is_alive(phase1_pid):
        raise RuntimeError("PROCESS_1_STILL_RUNNING")
    database = root / "isolated-app.sqlite3"
    ledger = DurableBudgetLedger(root / "budget-ledger.sqlite3")
    before = ledger.snapshot()
    repository = DownloadRepository(database)
    candidate = await repository.select_candidate(
        config.CHANNEL_ID, config.MESSAGE_ID, config.MEDIA_ORDINAL
    )
    record = await repository.get_record(candidate.media_item_id) if candidate else None
    partial = next((root / "downloads").rglob("*.part"), None)
    if (candidate is None or record is None or partial is None
            or record.downloaded_bytes != config.PREFIX_BYTES or partial.stat().st_size != config.PREFIX_BYTES):
        raise RuntimeError("PHASE1_EVIDENCE_REOPEN_FAILED")
    gateway = await _real_gateway(ledger, phase=2)
    app = SingleMediaDownloadApplication(repository, gateway, root / "downloads")

    async def reserve(amount: int):
        try:
            return ledger.reserve_getfile(amount)
        except BudgetStop as error:
            raise DownloadError(str(error)) from None

    app.chunk_reserver = reserve
    try:
        outcome = await app.download(config.CHANNEL_ID, config.MESSAGE_ID, config.MEDIA_ORDINAL)
        final = outcome.final_path
        final_hash = hashlib.sha256()
        with final.open("rb") as content:
            for block in iter(lambda: content.read(1024 * 1024), b""):
                final_hash.update(block)
        record = await repository.get_record(candidate.media_item_id)
        if (outcome.result != "DOWNLOADED" or final.stat().st_size != config.EXPECTED_BYTES
                or record is None or record.state != "DOWNLOADED"
                or record.downloaded_bytes != config.EXPECTED_BYTES or record.sha256 != final_hash.hexdigest()):
            raise RuntimeError("FINAL_INTEGRITY_OR_SQLITE_CHECK_FAILED")
        intervals = sorted(gateway.hash_ranges)
        cursor = 0
        for start, end in intervals:
            if start > cursor:
                break
            cursor = max(cursor, end)
        remote_full_coverage = cursor >= config.EXPECTED_BYTES
        if not remote_full_coverage:
            raise RuntimeError("REMOTE_HASH_COVERAGE_INCOMPLETE")
        snapshot = ledger.snapshot()
        return {
            "process_id": os.getpid(), "ledger_before": before, "ledger_after": snapshot,
            "hash_intervals": intervals, "remote_full_coverage": remote_full_coverage,
            "prefix_validated": True, "hash_complement_validated": True,
            "overlap_bytes": config.OVERLAP_BYTES, "wire_offset": config.WIRE_OFFSET,
            "final_bytes": final.stat().st_size, "final_sha256": final_hash.hexdigest(),
            "historical_sha256_candidate": config.HISTORICAL_SHA256_CANDIDATE,
            "historical_sha256_match": final_hash.hexdigest() == config.HISTORICAL_SHA256_CANDIDATE,
            "sqlite_state": record.state, "sqlite_checkpoint_bytes": record.downloaded_bytes,
            "partial_exists_after_finalize": next((root / "downloads").rglob("*.part"), None) is not None,
            "outcome": outcome.result,
        }
    finally:
        await gateway.close()


def _real_failure_snapshot(root: Path) -> dict[str, object]:
    ledger_path = root / "budget-ledger.sqlite3"
    database_path = root / "isolated-app.sqlite3"
    ledger = DurableBudgetLedger(ledger_path).snapshot() if ledger_path.is_file() else {}
    download_rows: list[dict[str, object]] = []
    if database_path.is_file():
        with sqlite3.connect(database_path) as db:
            try:
                rows = db.execute(
                    "SELECT state, downloaded_bytes FROM downloads ORDER BY media_item_id"
                ).fetchall()
            except sqlite3.Error:
                rows = []
        download_rows = [
            {"sqlite_state": str(state), "checkpoint_bytes": int(checkpoint)}
            for state, checkpoint in rows
        ]
    partials = [
        {"bytes": item.stat().st_size}
        for item in root.rglob("*.part") if item.is_file() and not item.is_symlink()
    ]
    return {"budget": ledger, "download_rows": download_rows, "partials": partials}


def real_phase_main(phase: int, root: Path, output_path: Path, phase1_pid: int = 0) -> int:
    try:
        result = asyncio.run(
            _real_phase1(root) if phase == 1 else _real_phase2(root, phase1_pid)
        )
    except DownloadError as error:
        reason = "FLOODWAIT" if error.category == "RATE_LIMITED" else error.category
        result = {
            "process_id": os.getpid(), "stop_condition": reason,
            **_real_failure_snapshot(root),
        }
        output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 5
    except Exception as error:
        reason = str(error) if str(error) in {
            "SESSION_UNAVAILABLE", "PROCESS_1_STILL_RUNNING",
            "PHASE1_EVIDENCE_REOPEN_FAILED", "PHASE1_PREFIX_CHECKPOINT_MISMATCH",
            "CONTROLLED_INTERRUPTION_NOT_OBSERVED", "REMOTE_HASH_COVERAGE_INCOMPLETE",
            "FINAL_INTEGRITY_OR_SQLITE_CHECK_FAILED", "PREFIX_TARGET_NOT_REACHED",
        } else "REAL_PHASE_FAILED"
        result = {
            "process_id": os.getpid(), "stop_condition": reason,
            **_real_failure_snapshot(root),
        }
        output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 5
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0

def synthetic_payload() -> bytes:
    return bytes((index * 31 + 7) % 256 for index in range(config.EXPECTED_BYTES))


async def seed_isolated_catalog(database: Path) -> None:
    repository = DownloadRepository(database)
    await repository.migrate()
    async with aiosqlite.connect(database) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (config.CHANNEL_ID, "Synthetic S6 proof", "synthetic", "synthetic"),
        )
        await db.execute(
            "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
            "VALUES(?,?,?,?,?)",
            (config.CHANNEL_ID, config.MESSAGE_ID, "2026-01-01T00:00:00+00:00", "synthetic", "synthetic"),
        )
        await db.execute(
            "INSERT INTO catalog_nodes(channel_id,kind,title,source_message_id,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (config.CHANNEL_ID, "lesson", "Synthetic lesson", config.MESSAGE_ID, "synthetic", "synthetic"),
        )
        node_id = (await (await db.execute("SELECT id FROM catalog_nodes")).fetchone())[0]
        await db.execute(
            "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
            "telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (config.CHANNEL_ID, config.MESSAGE_ID, 0, node_id, "DOCUMENT", config.TELEGRAM_MEDIA_ID,
             "synthetic.bin", config.EXPECTED_BYTES, "synthetic", "synthetic"),
        )
        await db.commit()


class SyntheticGateway:
    """Remote fixture with explicit, variable hash-range responses and durable caps."""

    def __init__(self, payload: bytes, ledger: DurableBudgetLedger, *, phase: int) -> None:
        self.payload = payload
        self.ledger = ledger
        self.phase = phase
        self.hash_response_log: list[tuple[int, int]] = []
        self.hash_response_overrides: list[tuple[RemoteFileHash, ...]] = []

    async def stream_media(
        self, channel_id: int, message_id: int, ordinal: int, *,
        telegram_media_id: str, expected_bytes: int, offset: int = 0, reserve_chunk=None,
    ):
        if (channel_id, message_id, ordinal, telegram_media_id, expected_bytes) != (
            config.CHANNEL_ID, config.MESSAGE_ID, 0, config.TELEGRAM_MEDIA_ID, len(self.payload)
        ):
            raise DownloadGatewayError("SYNTHETIC_IDENTITY_MISMATCH")
        if reserve_chunk is None or offset not in (0, config.WIRE_OFFSET):
            raise DownloadGatewayError("BUDGET_ENFORCEMENT_UNAVAILABLE")
        if self.phase == 1:
            if offset != 0:
                raise DownloadGatewayError("UNEXPECTED_PHASE1_OFFSET")
            sent = 0
            while sent < config.PREFIX_BYTES:
                amount = min(CHUNK_BYTES, config.PREFIX_BYTES - sent)
                reservation = await reserve_chunk(CHUNK_BYTES)
                if reservation is None:
                    raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
                data = self.payload[sent:sent + amount]
                reservation.received(len(data))
                sent += len(data)
                yield data
            raise DownloadGatewayError("CONTROLLED_INTERRUPTION_AFTER_DURABLE_PREFIX")

        if self.phase != 2 or offset != config.WIRE_OFFSET:
            raise DownloadGatewayError("UNEXPECTED_RESUME_OFFSET")
        position = offset
        while position < len(self.payload):
            reservation = await reserve_chunk(CHUNK_BYTES)
            if reservation is None:
                raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
            data = self.payload[position:min(position + CHUNK_BYTES, len(self.payload))]
            reservation.received(len(data))
            position += len(data)
            yield data

    async def get_file_hashes(
        self, channel_id: int, message_id: int, ordinal: int, *,
        telegram_media_id: str, expected_bytes: int, offset: int = 0,
    ):
        if (channel_id, message_id, ordinal, telegram_media_id, expected_bytes) != (
            config.CHANNEL_ID, config.MESSAGE_ID, 0, config.TELEGRAM_MEDIA_ID, len(self.payload)
        ):
            raise DownloadGatewayError("SYNTHETIC_IDENTITY_MISMATCH")
        try:
            reservation = self.ledger.reserve_hash_call()
        except BudgetStop as error:
            raise DownloadGatewayError(str(error)) from None

        if self.hash_response_overrides:
            response = self.hash_response_overrides.pop(0)
        elif self.phase == 2 and offset < config.PREFIX_BYTES:
            # Deliberately variable coverage: the next call continues at this end.
            size = min(900_001, config.PREFIX_BYTES - offset)
            response = None
        else:
            size = len(self.payload) - offset
            response = None
        if response is None:
            if size <= 0:
                reservation.charge_uncertain()
                raise DownloadGatewayError("HASH_COVERAGE_STALLED")
            end = offset + size
            response = (RemoteFileHash(offset, size, hashlib.sha256(self.payload[offset:end]).digest()),)
        reservation.received()
        try:
            end = validate_hash_response(offset, response, expected_bytes)
        except BudgetStop as error:
            raise DownloadGatewayError(str(error)) from None
        self.hash_response_log.extend((item.offset, item.limit) for item in response)
        return response

    async def close(self) -> None:
        return None


async def _phase1(root: Path) -> dict[str, object]:
    database = root / "isolated-app.sqlite3"
    ledger_path = root / "budget-ledger.sqlite3"
    download_root = root / "downloads"
    await seed_isolated_catalog(database)
    ledger = DurableBudgetLedger(ledger_path)
    gateway = SyntheticGateway(synthetic_payload(), ledger, phase=1)
    app = SingleMediaDownloadApplication(DownloadRepository(database), gateway, download_root)
    async def reserve(amount: int):
        try:
            return ledger.reserve_getfile(amount)
        except BudgetStop as error:
            raise DownloadError(str(error)) from None
    app.chunk_reserver = reserve
    try:
        await app.download(config.CHANNEL_ID, config.MESSAGE_ID, config.MEDIA_ORDINAL)
        raise AssertionError("controlled interruption was not raised")
    except DownloadError as error:
        if error.category != "CONTROLLED_INTERRUPTION_AFTER_DURABLE_PREFIX":
            raise
    candidate = await DownloadRepository(database).select_candidate(
        config.CHANNEL_ID, config.MESSAGE_ID, config.MEDIA_ORDINAL
    )
    assert candidate is not None
    record = await DownloadRepository(database).get_record(candidate.media_item_id)
    partial = next(download_root.rglob("*.part"))
    assert record is not None and record.state == "FAILED_RETRYABLE"
    assert record.downloaded_bytes == config.PREFIX_BYTES
    assert partial.stat().st_size == config.PREFIX_BYTES
    return {
        "process_id": os.getpid(),
        "isolated_media_item_id": candidate.media_item_id,
        "app_database": str(database),
        "partial_bytes": partial.stat().st_size,
        "sqlite_state": record.state,
        "sqlite_checkpoint_bytes": record.downloaded_bytes,
        "ledger": ledger.snapshot(),
    }


async def _phase2(root: Path) -> dict[str, object]:
    database = root / "isolated-app.sqlite3"
    ledger = DurableBudgetLedger(root / "budget-ledger.sqlite3")
    before = ledger.snapshot()
    if before["getfile_calls_reserved"] == 0 or before["payload_bytes_received"] < config.PREFIX_BYTES:
        raise AssertionError("phase 2 did not recover the durable phase-1 ledger")
    payload = synthetic_payload()
    gateway = SyntheticGateway(payload, ledger, phase=2)
    app = SingleMediaDownloadApplication(
        DownloadRepository(database), gateway, root / "downloads"
    )
    async def reserve(amount: int):
        try:
            return ledger.reserve_getfile(amount)
        except BudgetStop as error:
            raise DownloadError(str(error)) from None
    app.chunk_reserver = reserve
    outcome = await app.download(config.CHANNEL_ID, config.MESSAGE_ID, config.MEDIA_ORDINAL)
    candidate = outcome.candidate
    record = await DownloadRepository(database).get_record(candidate.media_item_id)
    final = outcome.final_path
    actual_hash = hashlib.sha256(final.read_bytes()).hexdigest()
    expected_hash = hashlib.sha256(payload).hexdigest()
    if (
        outcome.result != "DOWNLOADED" or actual_hash != expected_hash
        or actual_hash != outcome.sha256 or final.stat().st_size != config.EXPECTED_BYTES
        or record is None or record.state != "DOWNLOADED"
        or record.downloaded_bytes != config.EXPECTED_BYTES
        or record.sha256 != expected_hash
    ):
        raise AssertionError("final synthetic integrity or SQLite state failed")
    return {
        "process_id": os.getpid(),
        "ledger_before": before,
        "ledger_after": ledger.snapshot(),
        "hash_response_intervals": gateway.hash_response_log,
        "wire_offset": config.WIRE_OFFSET,
        "overlap_bytes": config.OVERLAP_BYTES,
        "final_bytes": final.stat().st_size,
        "final_sha256": actual_hash,
        "sqlite_state": record.state,
        "sqlite_checkpoint_bytes": record.downloaded_bytes,
        "partial_exists_after_finalize": next((root / "downloads").rglob("*.part"), None) is not None,
        "outcome": outcome.result,
    }


def phase_main(phase: int, root: Path, output_path: Path) -> int:
    result = asyncio.run(_phase1(root) if phase == 1 else _phase2(root))
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


def run_two_process_proof(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).with_name("s6_real_resume_proof.py")
    phases: list[dict[str, object]] = []
    for phase in (1, 2):
        output_path = root / f"phase-{phase}-report.json"
        project_root = Path(__file__).resolve().parents[2]
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        pythonpath = str(project_root) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        completed = subprocess.run(
            [sys.executable, str(script), f"--phase-{phase}", "--evidence-root", str(root),
             "--phase-output", str(output_path)],
            cwd=project_root,
            capture_output=True, text=True, timeout=180, check=False,
            env={**os.environ, "PYTHONPATH": pythonpath, "S6_OFFLINE_ONLY": "1"},
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"OFFLINE_PHASE_{phase}_FAILED / exit={completed.returncode} / "
                f"{completed.stderr[-1200:]}"
            )
        phases.append(json.loads(output_path.read_text(encoding="utf-8")))
    if phases[0]["process_id"] == phases[1]["process_id"]:
        raise AssertionError("the proof phases must use distinct OS processes")
    return {"phase1": phases[0], "phase2": phases[1]}


def exercise_budget_edge_cases(root: Path) -> dict[str, object]:
    """Offline control probes for caps, variable coverage, stalls and crash recovery."""
    probes = root / "budget-probes"
    probes.mkdir(parents=True)
    ledger = DurableBudgetLedger(probes / "limits.sqlite3")
    for _ in range(MAX_GETFILE):
        reservation = ledger.reserve_getfile(CHUNK_BYTES)
        reservation.received(CHUNK_BYTES)
    try:
        ledger.reserve_getfile(CHUNK_BYTES)
    except BudgetStop as error:
        getfile_stopped = str(error)
    else:
        raise AssertionError("GetFile cap did not stop request 52")

    hash_ledger = DurableBudgetLedger(probes / "hashes.sqlite3")
    for _ in range(MAX_HASHES):
        hash_reservation = hash_ledger.reserve_hash_call()
        hash_reservation.received()
    try:
        hash_ledger.reserve_hash_call()
    except BudgetStop as error:
        hashes_stopped = str(error)
    else:
        raise AssertionError("GetFileHashes cap did not stop request 17")

    crash_db_path = probes / "crash.sqlite3"
    script = Path(__file__).with_name("s6_real_resume_proof.py")
    project_root = Path(__file__).resolve().parents[2]
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = str(project_root) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    crashed = subprocess.run(
        [sys.executable, str(script), "--crash-after-reserve", "--ledger-path", str(crash_db_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "PYTHONPATH": pythonpath, "S6_OFFLINE_ONLY": "1"},
    )
    if crashed.returncode != 77:
        raise AssertionError(f"crash-after-reserve probe returned {crashed.returncode}")
    reopened = DurableBudgetLedger(probes / "crash.sqlite3").snapshot()
    if reopened["getfile_calls_reserved"] != 1 or reopened["open_reservations"] != 1:
        raise AssertionError("reserved operation did not survive ledger reopen")
    with sqlite3.connect(crash_db_path) as db:
        reservation_id = db.execute(
            "SELECT reservation_id FROM reservations WHERE status='RESERVED'"
        ).fetchone()[0]
    LedgerReservation(crash_db_path, reservation_id, CHUNK_BYTES).charge_uncertain()
    reconciled = DurableBudgetLedger(crash_db_path).snapshot()
    if reconciled["uncertain_reservations"] != 1:
        raise AssertionError("ambiguous reservation was not charged conservatively")

    variable_coverage = [(0, 900_001), (900_001, config.PREFIX_BYTES - 900_001)]
    first_end = validate_hash_response(
        0, (RemoteFileHash(0, variable_coverage[0][1], b"x" * 32),), config.PREFIX_BYTES
    )
    complete_end = validate_hash_response(
        first_end,
        (RemoteFileHash(first_end, variable_coverage[1][1], b"y" * 32),),
        config.PREFIX_BYTES,
    )
    full_coverage_end = validate_hash_response(
        0, (RemoteFileHash(0, config.EXPECTED_BYTES, b"z" * 32),), config.EXPECTED_BYTES
    )
    if complete_end != config.PREFIX_BYTES or full_coverage_end != config.EXPECTED_BYTES:
        raise AssertionError("variable partial hash ranges did not cover the prefix")
    try:
        validate_hash_response(0, (), config.PREFIX_BYTES)
    except BudgetStop as error:
        no_progress = str(error)
    else:
        raise AssertionError("empty hash response did not stop as stalled")
    for bad_response, expected_error in (
        ((RemoteFileHash(1, 1, b"x" * 32),), "HASH_COVERAGE_GAP"),
        ((RemoteFileHash(0, 2, b"x" * 32), RemoteFileHash(1, 1, b"x" * 32)), "HASH_COVERAGE_OVERLAP"),
    ):
        try:
            validate_hash_response(0, bad_response, config.PREFIX_BYTES)
        except BudgetStop as error:
            if str(error) != expected_error:
                raise AssertionError("hash gap/overlap validation returned wrong stop") from error
        else:
            raise AssertionError("invalid hash coverage was accepted")

    incomplete_ledger = DurableBudgetLedger(probes / "incomplete.sqlite3")
    cursor = 0
    for _ in range(MAX_HASHES):
        hash_reservation = incomplete_ledger.reserve_hash_call()
        hash_reservation.received()
        cursor = validate_hash_response(
            cursor, (RemoteFileHash(cursor, 1, b"x" * 32),), config.PREFIX_BYTES
        )
    if cursor >= config.PREFIX_BYTES:
        raise AssertionError("incomplete-coverage fixture unexpectedly completed")
    try:
        incomplete_ledger.reserve_hash_call()
    except BudgetStop as error:
        incomplete = str(error)
    else:
        raise AssertionError("hash coverage limit did not stop at 16 calls")
    return {
        "getfile_cap_stop": getfile_stopped,
        "hash_cap_stop": hashes_stopped,
        "crash_reopen": reopened,
        "crash_conservative_reconciliation": reconciled,
        "variable_coverage_intervals": variable_coverage,
        "variable_coverage_contiguous_end": complete_end,
        "full_coverage_end": full_coverage_end,
        "no_progress_stop": no_progress,
        "incomplete_coverage_stop": incomplete,
        "incomplete_coverage_contiguous_end": cursor,
        "invalid_gap_stop": "HASH_COVERAGE_GAP",
        "invalid_overlap_stop": "HASH_COVERAGE_OVERLAP",
    }

