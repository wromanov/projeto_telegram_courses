"""Offline-only, append-only S9 gate evidence validation.

This module validates a synthetic evidence bundle against one already-started
S9 run. It never creates a Telegram gateway and never writes to the
application's operational database. Gate receipts are private run artifacts;
the existing operational-ledger audit chain attests their SHA-256 values.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Callable, Mapping

from telegram_courses.s9_operational_ledger import (
    LedgerError,
    S9OperationalLedger,
    _open_private_directory_guard,
    _verify_private_file,
)
from telegram_courses.s9_supervisor import (
    STAGE_TIMEOUTS_SECONDS,
    _write_no_overwrite_json,
)

SCHEMA_VERSION = 1
MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
MAX_RECEIPT_BYTES = 128 * 1024
MAX_MESSAGES_PER_SCAN = 200
MAX_SCAN_INVOCATIONS = 3
MAX_SCAN_OBSERVATIONS = 600
INCREMENTAL_WINDOW = 50
MIB = 1024 * 1024
F_MEDIA_COUNT = 8
F_MEDIA_MAX = 128 * MIB
F_CAP = 512 * MIB
M_MIN = 1 * 1024 * MIB
M_MAX = 2 * 1024 * MIB
M_CAP_MAX = 2_147_745_792
TOTAL_CAP = 2_684_616_704
DISK_RESERVE = 256 * MIB
WORKING_SET_MAX = 512 * MIB
WORKING_SET_GROWTH_MAX = 128 * MIB
_PLANNED_CATALOG_EXPECTATION = {
    "state": "PENDING_G3",
    "hierarchy_semantics": "MINIMUMS",
    "unresolved_semantics": "OBSERVE_AND_REVIEW",
}
_PLANNED_RASMOO_SCOPE = {
    "target_alias": "RASMOO",
    "max_messages_per_scan": 200,
    "max_scan_observations": 600,
    "max_media_items": 1,
    "max_single_media_bytes": 128 * MIB,
    "max_transfer_bytes": 512 * MIB,
    "workers": 1,
    "attempts_per_media": 1,
    "integrity_mode": "REMOTE_HASH_REQUIRED",
}
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
ALIAS_RE = re.compile(r"[0-9a-f]{64}\Z")
_FORBIDDEN_REAL_ORIGINS = {"REAL", "LIVE", "TELEGRAM", "OPERATIONAL"}


class ReconciliationError(ValueError):
    """The evidence or run context is invalid and must fail closed."""


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: str
    reason: str
    source_sha256: str | None
    receipt_sha256: str
    receipt_path: Path
    summary: dict[str, object]


@dataclass(frozen=True)
class OfflineReconciliation:
    run_id: str
    result: str
    gates: tuple[GateResult, ...]
    receipt_path: Path
    manifest_sha256: str
    real_evidence_status: str = "REAL_EVIDENCE_PENDING"


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise ReconciliationError("EVIDENCE_NOT_CANONICAL_JSON") from None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: object, name: str) -> str:
    if type(value) is not str or not HASH_RE.fullmatch(value):
        raise ReconciliationError(f"{name}_INVALID")
    return value


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ReconciliationError(f"{name}_INVALID")
    return value


def _bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ReconciliationError(f"{name}_INVALID")
    return value


def _regular_file(root: Path, filename: object, *, max_bytes: int) -> Path:
    if type(filename) is not str or not filename or len(filename) > 180:
        raise ReconciliationError("EVIDENCE_FILE_INVALID")
    candidate = Path(filename)
    if candidate.is_absolute() or candidate.name != filename or filename in {".", ".."}:
        raise ReconciliationError("EVIDENCE_FILE_OUTSIDE_RUN")
    path = root / filename
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        raise ReconciliationError("EVIDENCE_FILE_UNAVAILABLE") from None
    if (
        not stat.S_ISREG(info.st_mode)
        or path.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
        or os.path.normcase(str(resolved.parent)) != os.path.normcase(str(root))
        or info.st_size > max_bytes
    ):
        raise ReconciliationError("EVIDENCE_FILE_UNSAFE")
    try:
        _verify_private_file(path)
    except (LedgerError, OSError):
        raise ReconciliationError("EVIDENCE_FILE_NOT_PRIVATE") from None
    return path


def load_evidence_file(run_directory: str | Path, evidence_file: str | Path) -> dict[str, object]:
    """Load one bounded JSON bundle placed directly inside the private run."""
    root = Path(run_directory).resolve(strict=True)
    selected = Path(evidence_file)
    if not selected.is_absolute():
        selected = root / selected
    try:
        parent = selected.parent.resolve(strict=True)
    except OSError:
        raise ReconciliationError("EVIDENCE_FILE_UNAVAILABLE") from None
    if os.path.normcase(str(parent)) != os.path.normcase(str(root)):
        raise ReconciliationError("EVIDENCE_FILE_OUTSIDE_RUN")
    path = _regular_file(root, selected.name, max_bytes=MAX_EVIDENCE_BYTES)
    try:
        raw = path.read_bytes()
        bundle = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except ReconciliationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ReconciliationError("EVIDENCE_JSON_INVALID") from None
    if type(bundle) is not dict:
        raise ReconciliationError("EVIDENCE_SCHEMA_INVALID")
    return bundle


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReconciliationError("EVIDENCE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    try:
        uri = path.as_uri() + "?mode=ro"
        db = sqlite3.connect(uri, uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA query_only").fetchone()[0] != 1:
            db.close()
            raise ReconciliationError("SYNTHETIC_DATABASE_NOT_READONLY")
        integrity = db.execute("PRAGMA integrity_check").fetchall()
        if len(integrity) != 1 or integrity[0][0] != "ok":
            db.close()
            raise ReconciliationError("SYNTHETIC_DATABASE_INTEGRITY_FAILED")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            db.close()
            raise ReconciliationError("SYNTHETIC_DATABASE_FOREIGN_KEY_FAILED")
        return db
    except ReconciliationError:
        raise
    except (sqlite3.Error, OSError, ValueError):
        raise ReconciliationError("SYNTHETIC_DATABASE_UNAVAILABLE") from None


def _database_path(root: Path, bundle: Mapping[str, object]) -> Path:
    path = _regular_file(root, bundle.get("database_file"), max_bytes=512 * MIB)
    if path.name == "operational-ledger.sqlite3":
        raise ReconciliationError("OPERATIONAL_LEDGER_CANNOT_BE_DATASET")
    return path


def _query_tables(db: sqlite3.Connection) -> set[str]:
    try:
        return {
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    except sqlite3.Error:
        raise ReconciliationError("SYNTHETIC_DATABASE_SCHEMA_INVALID") from None


def _scan_database(
    root: Path, bundle: Mapping[str, object], manifest: Mapping[str, object],
    evidence: Mapping[str, object], *, run_started_ns: int,
) -> tuple[str, dict[str, object]]:
    calls = evidence.get("invocations")
    if type(calls) is not list or not 1 <= len(calls) <= MAX_SCAN_INVOCATIONS:
        return "BLOCKED", {"reason": "SCAN_INVOCATION_COUNT_INVALID"}
    channel_id = manifest.get("channel_id")
    if type(channel_id) is not int or channel_id == 0 or not -(2**63) <= channel_id <= 2**63 - 1:
        return "BLOCKED", {"reason": "SYNTHETIC_CHANNEL_BINDING_MISSING"}
    g7 = bundle.get("gates", {}).get("G7") if type(bundle.get("gates")) is dict else None
    if type(g7) is not dict:
        return "BLOCKED", {"reason": "SCAN_AGGREGATE_G7_BINDING_MISSING"}
    g7_scan_ids = [g7.get("baseline_scan_run_id"), g7.get("incremental_scan_run_id")]
    if any(type(scan_id) is not str or not scan_id or len(scan_id) > 128 for scan_id in g7_scan_ids):
        return "BLOCKED", {"reason": "SCAN_AGGREGATE_G7_BINDING_MISSING"}
    all_scan_ids = list(dict.fromkeys([
        *(call.get("scan_run_id") for call in calls if type(call) is dict),
        *g7_scan_ids,
    ]))
    if len(all_scan_ids) > MAX_SCAN_INVOCATIONS:
        return "FAIL", {"reason": "SCAN_INVOCATION_COUNT_INVALID"}
    path = _database_path(root, bundle)
    db = _open_sqlite_readonly(path)
    try:
        if "scan_runs" not in _query_tables(db):
            return "BLOCKED", {"reason": "SCAN_RUNS_TABLE_MISSING"}
        scan_ids: set[str] = set()
        for expected in calls:
            if type(expected) is not dict:
                return "FAIL", {"reason": "SCAN_INVOCATION_SCHEMA_INVALID"}
            scan_id = expected.get("scan_run_id")
            if type(scan_id) is not str or not scan_id or len(scan_id) > 128 or scan_id in scan_ids:
                return "FAIL", {"reason": "SCAN_RUN_ID_INVALID_OR_DUPLICATE"}
            scan_ids.add(scan_id)
        channel_scans = db.execute(
            "SELECT id,channel_id,status,messages_seen,stop_reason,sync_mode,"
            "sync_max_messages,sync_reconcile_window,started_at "
            "FROM scan_runs WHERE channel_id=?",
            (channel_id,),
        ).fetchall()
        persisted_messages = int(db.execute(
            "SELECT COUNT(*) FROM messages WHERE channel_id=?", (channel_id,)
        ).fetchone()[0])
    except sqlite3.Error:
        return "BLOCKED", {"reason": "SCAN_RUNS_READ_FAILED"}
    finally:
        db.close()
    run_started = datetime.fromtimestamp(run_started_ns / 1_000_000_000, timezone.utc).timestamp()
    now_timestamp = time.time() + 5.0
    persisted_by_id: dict[str, sqlite3.Row] = {}
    for row in channel_scans:
        try:
            started_at = row[8]
            if type(started_at) is not str:
                raise ValueError
            parsed_started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            if parsed_started.tzinfo is None:
                raise ValueError
            timestamp = parsed_started.timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            return "BLOCKED", {"reason": "SCAN_TIMESTAMP_UNRECONCILED"}
        if run_started <= timestamp <= now_timestamp or row[0] in g7_scan_ids:
            persisted_by_id[str(row[0])] = row
    if set(persisted_by_id) != set(all_scan_ids):
        return "FAIL", {"reason": "SCAN_AGGREGATE_COUNT_MISMATCH"}
    if any(scan_id not in persisted_by_id for scan_id in scan_ids):
        return "BLOCKED", {"reason": "SCAN_RUNS_COUNT_MISMATCH"}
    total = 0
    clean = True
    compact: list[dict[str, object]] = []
    for expected in calls:
        if type(expected) is not dict:
            return "FAIL", {"reason": "SCAN_INVOCATION_SCHEMA_INVALID"}
        stored = persisted_by_id.get(str(expected.get("scan_run_id")))
        maximum = expected.get("max_messages")
        observed = expected.get("observed")
        if (
            type(maximum) is not int or not 1 <= maximum <= MAX_MESSAGES_PER_SCAN
            or type(observed) is not int or not 0 <= observed <= maximum
            or stored is None or stored[1] != channel_id or stored[3] != observed
        ):
            return "FAIL", {"reason": "SCAN_LIMIT_OR_COUNT_MISMATCH"}
        status = expected.get("status")
        stop_reason = expected.get("stop_reason")
        if status not in {"COMPLETE", "PARTIAL"} or stored[2] != status or stored[4] != stop_reason:
            return "PARTIAL", {"reason": "SCAN_TERMINAL_STATUS_UNRECONCILED"}
        if status == "PARTIAL" and stop_reason != "MESSAGE_LIMIT":
            clean = False
        if expected.get("persisted") is not True:
            return "BLOCKED", {"reason": "SCAN_PERSISTENCE_UNPROVEN"}
        total += int(stored[3])
        clean = clean and expected.get("errors", 0) == 0
        compact.append({
            "scan_run_id": str(expected["scan_run_id"]),
            "max_messages": maximum, "observed": observed, "status": status,
        })
    for scan_id in g7_scan_ids:
        stored = persisted_by_id.get(str(scan_id))
        if stored is None:
            return "BLOCKED", {"reason": "SCAN_RUNS_COUNT_MISMATCH"}
        if scan_id == g7_scan_ids[0] and stored[2] != "COMPLETE":
            return "BLOCKED", {"reason": "SCAN_AGGREGATE_BASELINE_INCOMPLETE"}
        if scan_id == g7_scan_ids[1]:
            maximum = stored[6]
            observed = stored[3]
            if (
                stored[2] != "COMPLETE" or stored[5] != "INCREMENTAL"
                or type(maximum) is not int or not 1 <= maximum <= MAX_MESSAGES_PER_SCAN
                or type(observed) is not int or not 0 <= observed <= maximum
            ):
                return "FAIL", {"reason": "SCAN_INCREMENTAL_LIMIT_OR_COUNT_MISMATCH"}
        if scan_id not in scan_ids:
            total += int(stored[3])
    if total > MAX_SCAN_OBSERVATIONS:
        return "FAIL", {"reason": "SCAN_CUMULATIVE_LIMIT_EXCEEDED"}
    if evidence.get("deletions_inferred") is not False:
        return "FAIL", {"reason": "SCAN_DELETE_INFERENCE_FORBIDDEN"}
    if type(evidence.get("high_water_before")) is not int or type(evidence.get("high_water_after")) is not int:
        return "BLOCKED", {"reason": "S7_HIGH_WATER_UNPROVEN"}
    if evidence["high_water_after"] < evidence["high_water_before"]:
        return "FAIL", {"reason": "S7_HIGH_WATER_REGRESSION"}
    return ("PASS" if clean else "PARTIAL"), {
        "invocations": compact, "scan_run_ids": all_scan_ids,
        "observations": total,
        "high_water_before": evidence["high_water_before"],
        "high_water_after": evidence["high_water_after"],
        "persisted_message_count": persisted_messages,
        "database_sha256": _hash_file(path),
        "database_integrity": "ok",
    }


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError:
        raise ReconciliationError("EVIDENCE_FILE_READ_FAILED") from None
    return digest.hexdigest()


def _catalog_database(
    root: Path, bundle: Mapping[str, object], manifest: Mapping[str, object],
    evidence: Mapping[str, object], g2_summary: Mapping[str, object],
) -> tuple[str, dict[str, object]]:
    channel_id = manifest.get("channel_id")
    if type(channel_id) is not int or channel_id == 0 or not -(2**63) <= channel_id <= 2**63 - 1:
        return "BLOCKED", {"reason": "SYNTHETIC_CHANNEL_BINDING_MISSING"}
    path = _database_path(root, bundle)
    db = _open_sqlite_readonly(path)
    try:
        tables = _query_tables(db)
        required = {"catalog_nodes", "catalog_runs", "catalog_unresolved_sources"}
        if not required.issubset(tables):
            return "BLOCKED", {"reason": "CATALOG_TABLES_MISSING"}
        counts = {
            str(row[0]).upper(): int(row[1]) for row in db.execute(
                "SELECT kind,COUNT(*) FROM catalog_nodes WHERE channel_id=? AND is_active=1 GROUP BY kind",
                (channel_id,),
            )
        }
        run = db.execute(
            "SELECT id,channel_id,status,source_message_count,catalog_node_count,unresolved_count "
            "FROM catalog_runs WHERE channel_id=? ORDER BY rowid DESC LIMIT 1",
            (channel_id,),
        ).fetchone()
        if run is None or run[2] != "COMPLETE":
            return "BLOCKED", {"reason": "CATALOG_BASELINE_NOT_COMPLETE"}
        unresolved = int(db.execute(
            "SELECT COUNT(*) FROM catalog_unresolved_sources WHERE run_id=?", (run[0],)
        ).fetchone()[0])
        message_count = int(db.execute(
            "SELECT COUNT(*) FROM messages WHERE channel_id=?", (run[1],)
        ).fetchone()[0])
    except sqlite3.Error:
        return "BLOCKED", {"reason": "CATALOG_RECONCILIATION_FAILED"}
    finally:
        db.close()
    expected = manifest.get("hierarchy")
    if type(expected) is not dict:
        return "BLOCKED", {"reason": "MANIFEST_HIERARCHY_MISSING"}
    expected_counts: dict[str, int] = {}
    for kind in ("TRACK", "COURSE", "MODULE"):
        value = expected.get(kind)
        if type(value) is not int or value < 0:
            return "BLOCKED", {"reason": "MANIFEST_HIERARCHY_INVALID"}
        expected_counts[kind] = value
    catalog_expectation = manifest.get("catalog_expectation")
    planned_catalog = catalog_expectation is not None
    if planned_catalog and (
        catalog_expectation != _PLANNED_CATALOG_EXPECTATION
        or expected_counts != {"TRACK": 1, "COURSE": 2, "MODULE": 2}
        or manifest.get("unresolved_count") is not None
        or manifest.get("scope") != _PLANNED_RASMOO_SCOPE
    ):
        return "BLOCKED", {"reason": "MANIFEST_CATALOG_EXPECTATION_INVALID"}
    if evidence.get("database_sha256") != g2_summary.get("database_sha256"):
        return "FAIL", {"reason": "G2_G3_DATABASE_MISMATCH"}
    if run[3] != message_count or message_count != g2_summary.get("persisted_message_count"):
        return "FAIL", {"reason": "CATALOG_SCAN_SOURCE_COUNT_MISMATCH"}
    active_node_count = sum(counts.values())
    if run[4] != active_node_count:
        return "FAIL", {"reason": "CATALOG_NODE_COUNT_MISMATCH"}
    if planned_catalog:
        if any(counts.get(kind, 0) < expected_counts[kind] for kind in expected_counts):
            return "BLOCKED", {"reason": "BLOCKED_DATASET"}
    elif any(counts.get(kind, 0) != expected_counts[kind] for kind in expected_counts):
        return "FAIL", {"reason": "CATALOG_MANIFEST_DIVERGENCE"}
    if counts.get("TRACK", 0) < 1 or counts.get("COURSE", 0) < 2 or counts.get("MODULE", 0) < 2:
        return "BLOCKED", {"reason": "BLOCKED_DATASET"}
    expected_unresolved = manifest.get("unresolved_count")
    if (
        unresolved != run[5]
        or (
            not planned_catalog
            and (type(expected_unresolved) is not int or expected_unresolved != unresolved)
        )
    ):
        return "FAIL", {"reason": "UNRESOLVED_COUNT_DIVERGENCE"}
    if evidence.get("database_sha256") != _hash_file(path):
        return "FAIL", {"reason": "CATALOG_DATABASE_CHANGED"}
    if evidence.get("unresolved_reviewed") is not True:
        return "PARTIAL", {"reason": "UNRESOLVED_REVIEW_PENDING"}
    return "PASS", {
        "hierarchy": {kind: counts.get(kind, 0) for kind in ("TRACK", "COURSE", "MODULE")},
        "active_node_count": active_node_count,
        "unresolved": unresolved, "catalog_run_status": "COMPLETE",
        "database_sha256": _hash_file(path),
    }


def _validate_plan(
    manifest_sha256: str, evidence: Mapping[str, object],
) -> tuple[str, dict[str, object]]:
    plan = evidence.get("plan")
    if type(plan) is not dict:
        return "BLOCKED", {"reason": "PLAN_MISSING"}
    if plan.get("manifest_sha256") != manifest_sha256:
        return "FAIL", {"reason": "PLAN_MANIFEST_STALE"}
    if evidence.get("fresh") is not True or evidence.get("limit_check_result") != "PASS":
        return "BLOCKED", {"reason": "PLAN_NOT_FRESH_OR_LIMITS_NOT_PASS"}
    if evidence.get("synthetic_tty_confirmation") is not True:
        return "BLOCKED", {"reason": "TTY_CONFIRMATION_NOT_PROVEN"}
    if evidence.get("confirm_bypass") is not False:
        return "FAIL", {"reason": "CONFIRM_BYPASS_FORBIDDEN"}
    if evidence.get("reservations_before_payload") is not True:
        return "FAIL", {"reason": "RESERVATION_ORDER_INVALID"}
    media = plan.get("media")
    if type(media) is not list or not media:
        return "BLOCKED", {"reason": "PLAN_MEDIA_MISSING"}
    identities: set[str] = set()
    f_count = 0
    f_total = 0
    m_items = 0
    for item in media:
        if type(item) is not dict:
            return "FAIL", {"reason": "PLAN_MEDIA_INVALID"}
        identity = item.get("identity_alias")
        profile = item.get("profile")
        size = item.get("expected_bytes")
        if type(identity) is not str or not ALIAS_RE.fullmatch(identity):
            return "FAIL", {"reason": "PLAN_IDENTITY_NOT_PSEUDONYM"}
        if identity in identities:
            return "FAIL", {"reason": "PLAN_DUPLICATE_IDENTITY"}
        identities.add(identity)
        if type(size) is not int or size <= 0 or item.get("kind") != "DOCUMENT":
            return "FAIL", {"reason": "PLAN_MEDIA_PROFILE_INVALID"}
        if profile == "F":
            f_count += 1
            f_total += size
            if size > F_MEDIA_MAX:
                return "FAIL", {"reason": "F_ITEM_CAP_EXCEEDED"}
        elif profile == "M":
            m_items += 1
            if not M_MIN <= size <= M_MAX or item.get("fresh") is not True:
                return "FAIL", {"reason": "M_MEDIA_PROFILE_INVALID"}
        else:
            return "FAIL", {"reason": "UNKNOWN_MEDIA_PROFILE"}
    if f_count > F_MEDIA_COUNT or f_total > F_CAP or m_items > 1:
        return "FAIL", {"reason": "PROFILE_CAP_EXCEEDED"}
    if f_total + sum(item["expected_bytes"] for item in media if item["profile"] == "M") > TOTAL_CAP:
        return "FAIL", {"reason": "AGGREGATE_CAP_EXCEEDED"}
    if evidence.get("workers") != 1 or evidence.get("attempts_per_media") != 1:
        return "FAIL", {"reason": "QUEUE_CONCURRENCY_CAP_EXCEEDED"}
    disk_reserve = evidence.get("disk_reserve_bytes")
    if type(disk_reserve) is not int or disk_reserve < DISK_RESERVE:
        return "BLOCKED", {"reason": "DISK_RESERVE_UNPROVEN"}
    return "PASS", {
        "plan_sha256": _sha256(_canonical(plan)),
        "media_count": len(media), "f_count": f_count, "m_count": m_items,
        "f_expected_bytes": f_total,
        "m_expected_bytes": sum(item["expected_bytes"] for item in media if item["profile"] == "M"),
        "profiles": [item["profile"] for item in media],
        "media_contracts": [
            {
                "identity_alias": item["identity_alias"],
                "profile": item["profile"],
                "expected_bytes": item["expected_bytes"],
            }
            for item in media
        ],
    }


def _validate_queue_memory_receipt(receipt: Mapping[str, object]) -> str | None:
    if (
        receipt.get("memory_monitoring_offline_gate") != "PASS"
        or receipt.get("limit_check_result") != "PASS"
        or receipt.get("preconfirmation_prompt_signal_available") is not True
        or receipt.get("preconfirmation_release_callback_available") is not True
        or receipt.get("preconfirmation_confirmation_released") is not True
    ):
        return "MEMORY_PRECONFIRMATION_WINDOW_UNPROVEN"
    memory = receipt.get("memory")
    if type(memory) is not dict:
        return "MEMORY_RECEIPT_MISSING"
    samples = memory.get("baseline_samples")
    if (
        memory.get("baseline_status") != "PASS_PROMPT_SIGNAL_AND_TWO_SECOND_WINDOW"
        or memory.get("memory_source") != "WINDOWS_PROCESS_MEMORY_COUNTERS_EX"
        or memory.get("target_sampling_interval_ms") != 250
        or type(samples) is not list or len(samples) < 9
    ):
        return "MEMORY_BASELINE_UNPROVEN"
    elapsed_values: list[float] = []
    working_sets: list[int] = []
    private_sets: list[int] = []
    for sample in samples:
        if type(sample) is not dict:
            return "MEMORY_BASELINE_SAMPLE_INVALID"
        elapsed = sample.get("elapsed_seconds")
        process_count = sample.get("process_count")
        working_set = sample.get("working_set_bytes")
        private_bytes = sample.get("private_bytes")
        if (
            type(elapsed) not in {int, float} or isinstance(elapsed, bool)
            or not math.isfinite(elapsed)
            or type(process_count) is not int or process_count < 1
            or type(working_set) is not int or working_set < 0
            or type(private_bytes) is not int or private_bytes < 0
        ):
            return "MEMORY_BASELINE_SAMPLE_INVALID"
        elapsed_values.append(float(elapsed))
        working_sets.append(working_set)
        private_sets.append(private_bytes)
    intervals = [after - before for before, after in zip(elapsed_values, elapsed_values[1:])]
    if (
        elapsed_values != sorted(elapsed_values)
        or any(interval <= 0 or interval > 0.500 for interval in intervals)
        or elapsed_values[-1] - elapsed_values[0] < 2.0
    ):
        return "MEMORY_BASELINE_WINDOW_UNPROVEN"
    baseline = memory.get("baseline_working_set_bytes")
    baseline_private = memory.get("baseline_private_bytes")
    peak = memory.get("peak_working_set_bytes")
    monitoring_samples = memory.get("samples")
    if (
        type(baseline) is not int or baseline != int(median(working_sets))
        or type(baseline_private) is not int
        or baseline_private != int(median(private_sets))
        or type(peak) is not int or peak < baseline
        or type(monitoring_samples) is not list or not monitoring_samples
    ):
        return "MEMORY_MEASUREMENT_RECONCILIATION_FAILED"
    for sample in monitoring_samples:
        if (
            type(sample) is not dict
            or type(sample.get("process_count")) is not int
            or sample["process_count"] < 1
            or type(sample.get("working_set_bytes")) is not int
            or sample["working_set_bytes"] < 0
        ):
            return "MEMORY_MEASUREMENT_RECONCILIATION_FAILED"
    if peak > WORKING_SET_MAX or peak - baseline > WORKING_SET_GROWTH_MAX:
        return "MEMORY_LIMIT_EXCEEDED"
    return None


def _validate_queue_disk(
    evidence: object, snapshot: Mapping[str, object],
    expected_media: list[dict[str, object]],
) -> tuple[dict[str, int], str | None]:
    if (
        type(evidence) is not dict
        or evidence.get("extra_reserve_bytes") != DISK_RESERVE
        or type(evidence.get("checks")) is not list
    ):
        return {}, "DISK_RESERVE_UNPROVEN"
    ledger_checks = snapshot.get("disk_checks")
    if type(ledger_checks) is not list or not ledger_checks:
        return {}, "DISK_MEASUREMENT_MISSING"
    checks = evidence["checks"]
    if len(checks) != len(expected_media) or len(ledger_checks) != len(checks):
        return {}, "DISK_CHECK_SET_MISMATCH"
    ledger_by_id = {
        str(row["check_id"]): row for row in ledger_checks
        if type(row) is dict and type(row.get("check_id")) is str
    }
    if len(ledger_by_id) != len(ledger_checks):
        return {}, "DISK_LEDGER_CHECK_INVALID"
    aliases = {str(item["identity_alias"]): int(item["expected_bytes"]) for item in expected_media}
    seen_ids: set[str] = set()
    seen_currents: set[str] = set()
    for check in checks:
        if type(check) is not dict or set(check) != {
            "check_id", "current_item_alias", "current_item_bytes", "other_pending_items",
        }:
            return {}, "DISK_CHECK_SCHEMA_INVALID"
        check_id = check.get("check_id")
        current_alias = check.get("current_item_alias")
        if (
            type(check_id) is not str or check_id in seen_ids
            or type(current_alias) is not str or current_alias not in aliases
            or current_alias in seen_currents
            or check.get("current_item_bytes") != aliases[current_alias]
            or type(check.get("other_pending_items")) is not list
        ):
            return {}, "DISK_CHECK_SET_MISMATCH"
        row = ledger_by_id.get(check_id)
        if row is None:
            return {}, "DISK_CHECK_SET_MISMATCH"
        seen_ids.add(check_id)
        seen_currents.add(current_alias)
        pending = aliases[current_alias]
        other_aliases: set[str] = set()
        for other in check["other_pending_items"]:
            if (
                type(other) is not dict
                or set(other) != {"identity_alias", "bytes"}
                or type(other.get("identity_alias")) is not str
                or other["identity_alias"] not in aliases
                or other["identity_alias"] == current_alias
                or other["identity_alias"] in other_aliases
                or other.get("bytes") != aliases[other["identity_alias"]]
            ):
                return {}, "DISK_PENDING_ITEM_MISMATCH"
            other_aliases.add(other["identity_alias"])
            pending += aliases[other["identity_alias"]]
        if type(row.get("pending")) is not int or row["pending"] != pending:
            return {}, "DISK_PENDING_ITEM_MISMATCH"
        available = row.get("available")
        margin = row.get("margin")
        extra = row.get("extra")
        checked_ns = row.get("checked_ns")
        if (
            row.get("available_origin") != "MEASURED"
            or row.get("margin_origin") != "DERIVED"
            or type(available) is not int or available < 0
            or type(margin) is not int
            or margin != max(1024 * MIB, (pending + 9) // 10)
            or margin < max(1024 * MIB, pending // 10)
            or extra != DISK_RESERVE or type(checked_ns) is not int
        ):
            return {}, "DISK_MEASUREMENT_UNPROVEN"
        details = {
            "pending_bytes": pending, "available_bytes": available,
            "margin_bytes": margin, "extra_bytes": extra,
            "checked_ns": checked_ns, "check_id": check_id,
            "available_origin": "MEASURED", "margin_origin": "DERIVED",
            "status": "MEASURED",
        }
        if not _audit_detail_valid(snapshot, check_id, "DISK_CHECKED", details):
            return {}, "DISK_AUDIT_ATTESTATION_MISSING"
        if available < pending + margin + extra:
            return {}, "DISK_RESERVE_EXCEEDED"
    if seen_ids != set(ledger_by_id) or seen_currents != set(aliases):
        return {}, "DISK_CHECK_SET_MISMATCH"
    return {"verified_checks": len(checks)}, None


def _validate_queue(
    evidence: Mapping[str, object], expected_media: list[dict[str, object]],
    expected_m_bytes: int, *, ledger: S9OperationalLedger, root: Path,
    scan_run_ids: list[str],
) -> tuple[str, dict[str, object]]:
    if evidence.get("limit_check_result") != "PASS":
        return "BLOCKED", {"reason": "QUEUE_LIMIT_CHECK_NOT_PASS"}
    if evidence.get("flood_wait") is not False:
        return "BLOCKED", {"reason": "FLOODWAIT_OR_UNKNOWN"}
    expected_profiles = [str(item["profile"]) for item in expected_media]
    if "F" not in expected_profiles:
        return "BLOCKED", {"reason": "G5_F_BLOCKED_DATASET"}
    has_m = "M" in expected_profiles
    snapshot = ledger.snapshot()
    stage_receipts = evidence.get("stage_receipts")
    expected_receipts = [("scan", scan_id) for scan_id in scan_run_ids]
    expected_receipts.extend([
        ("catalog", None), ("inspection", None), ("queue_f", None),
    ])
    if has_m:
        expected_receipts.append(("queue_m", None))
    expected_receipts.append(("verification_local", None))
    if type(stage_receipts) is not list or len(stage_receipts) != len(expected_receipts):
        return "BLOCKED", {"reason": "STAGE_RECEIPT_SET_INCOMPLETE"}
    receipt_by_key: dict[tuple[str, str | None], dict[str, object]] = {}
    for entry in stage_receipts:
        if type(entry) is not dict:
            return "BLOCKED", {"reason": "STAGE_RECEIPT_SCHEMA_INVALID"}
        stage = entry.get("stage")
        scan_run_id = entry.get("scan_run_id")
        key = (stage, scan_run_id if type(scan_run_id) is str else None)
        if key not in expected_receipts or key in receipt_by_key:
            return "FAIL", {"reason": "STAGE_RECEIPT_SET_MISMATCH"}
        expected_keys = {"stage", "filename", "sha256"}
        if stage == "scan":
            expected_keys.add("scan_run_id")
        if set(entry) != expected_keys:
            return "FAIL", {"reason": "STAGE_RECEIPT_SCHEMA_INVALID"}
        receipt_by_key[key] = entry
    if set(receipt_by_key) != set(expected_receipts):
        return "BLOCKED", {"reason": "STAGE_RECEIPT_SET_INCOMPLETE"}

    total_elapsed = 0.0
    verified_receipts: dict[tuple[str, str | None], dict[str, object]] = {}
    for key in expected_receipts:
        entry = receipt_by_key[key]
        digest = _digest(entry.get("sha256"), "STAGE_RECEIPT_SHA256")
        path = _regular_file(root, entry.get("filename"), max_bytes=MAX_RECEIPT_BYTES)
        try:
            encoded = path.read_bytes()
            receipt = json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            return "BLOCKED", {"reason": "STAGE_RECEIPT_UNAVAILABLE"}
        if (
            _sha256(encoded) != digest or type(receipt) is not dict
            or encoded != _canonical(receipt) + b"\n"
        ):
            return "FAIL", {"reason": "STAGE_RECEIPT_INTEGRITY_MISMATCH"}
        stage, scan_id = key
        run_id = snapshot["run"]["run_id"]
        if (
            receipt.get("schema") != "telegram-courses-s9-supervisor-receipt-v1"
            or receipt.get("run_id") != run_id
            or receipt.get("ledger_run_id") != run_id
            or receipt.get("stage") != stage
            or receipt.get("receipt_attestation_event_id") is None
            or not _receipt_event_valid(
                snapshot, str(receipt.get("receipt_attestation_event_id")), digest,
            )
        ):
            return "BLOCKED", {"reason": "STAGE_RECEIPT_UNATTESTED"}
        if (
            receipt.get("result") != "COMPLETED"
            or receipt.get("external_exit_code") != 0
            or receipt.get("process_tree_termination_confirmed") is not True
            or receipt.get("critical_audit_gate") != "PASS"
            or receipt.get("supervisor_offline_gate") != "PASS"
            or receipt.get("process_control_offline_gate") != "PASS"
        ):
            return "BLOCKED", {"reason": "STAGE_PROCESS_STATE_UNPROVEN"}
        timeout = STAGE_TIMEOUTS_SECONDS.get(stage)
        elapsed = receipt.get("elapsed_seconds")
        if (
            timeout is None or receipt.get("stage_timeout_seconds") != timeout
            or type(elapsed) not in {int, float} or isinstance(elapsed, bool)
            or not math.isfinite(elapsed) or elapsed < 0
        ):
            return "FAIL", {"reason": "STAGE_TIMEOUT_CONTRACT_MISMATCH"}
        if elapsed > timeout:
            return "FAIL", {"reason": "STAGE_TIMEOUT_EXCEEDED"}
        total_elapsed += float(elapsed)
        if stage in {"queue_f", "queue_m"}:
            memory_reason = _validate_queue_memory_receipt(receipt)
            if memory_reason is not None:
                if memory_reason == "MEMORY_LIMIT_EXCEEDED":
                    return "FAIL", {"reason": memory_reason}
                return "BLOCKED", {"reason": memory_reason}
        verified_receipts[key] = receipt
    if total_elapsed > 3600:
        return "FAIL", {"reason": "GLOBAL_DEADLINE_EXCEEDED"}

    disk_summary, disk_reason = _validate_queue_disk(
        evidence.get("disk"), snapshot, expected_media,
    )
    if disk_reason is not None:
        failed_disk_reasons = {
            "DISK_CHECK_SET_MISMATCH", "DISK_PENDING_ITEM_MISMATCH",
            "DISK_RESERVE_EXCEEDED",
        }
        return "FAIL" if disk_reason in failed_disk_reasons else "BLOCKED", {"reason": disk_reason}
    if has_m and evidence.get("m_execution") != "LOGICAL_FIXTURE_ONLY":
        return "BLOCKED", {"reason": "M_REAL_TRANSFER_NOT_AUTHORIZED"}
    reservations = evidence.get("reservations")
    if type(reservations) is not list or len(reservations) != len(expected_media):
        return "BLOCKED", {"reason": "BYTE_ACCOUNTING_MISSING"}
    consumed: dict[str, int] = {"F": 0, "M": 0}
    uncertain: dict[str, int] = {"F": 0, "M": 0}
    for entry, expected in zip(reservations, expected_media, strict=True):
        expected_profile = str(expected["profile"])
        expected_bytes = int(expected["expected_bytes"])
        expected_alias = str(expected["identity_alias"])
        if type(entry) is not dict or entry.get("profile") not in {"F", "M"}:
            return "FAIL", {"reason": "RESERVATION_SCHEMA_INVALID"}
        profile = str(entry["profile"])
        if (
            profile != expected_profile
            or entry.get("identity_alias") != expected_alias
            or entry.get("expected_bytes") != expected_bytes
        ):
            return "FAIL", {"reason": "RESERVATION_PLAN_MISMATCH"}
        amount = _integer(entry.get("reserved_bytes"), "RESERVED_BYTES")
        if amount != expected_bytes:
            return "FAIL", {"reason": "RESERVATION_SIZE_MISMATCH"}
        observed = entry.get("observed_bytes")
        source = entry.get("measurement_source")
        state = entry.get("state")
        if state == "OBSERVED":
            if type(observed) is not int or not 0 <= observed <= amount or source != "SYNTHETIC_TEST":
                return "BLOCKED", {"reason": "OBSERVED_BYTE_SOURCE_UNTRUSTED"}
            consumed[profile] += observed
        elif state in {"RESERVED", "UNCERTAIN"}:
            uncertain[profile] += amount
        else:
            return "FAIL", {"reason": "RESERVATION_STATE_INVALID"}
    if consumed["F"] + uncertain["F"] > F_CAP:
        return "FAIL", {"reason": "F_BUDGET_EXCEEDED"}
    m_expected = evidence.get("m_expected_bytes", 0)
    if m_expected != expected_m_bytes:
        return "FAIL", {"reason": "M_PLAN_BUDGET_MISMATCH"}
    if m_expected:
        m_expected = _integer(m_expected, "M_EXPECTED_BYTES", minimum=M_MIN)
        if m_expected > M_MAX:
            return "FAIL", {"reason": "M_EXPECTED_BYTES_EXCEEDED"}
        m_cap = min(M_CAP_MAX, ((m_expected + 262143) // 262144) * 262144 + 262144)
    else:
        m_cap = 0
    if consumed["M"] + uncertain["M"] > m_cap:
        return "FAIL", {"reason": "M_BUDGET_EXCEEDED"}
    if consumed["F"] + uncertain["F"] + consumed["M"] + uncertain["M"] > TOTAL_CAP:
        return "FAIL", {"reason": "AGGREGATE_BUDGET_EXCEEDED"}
    attempts = evidence.get("attempts")
    if type(attempts) is not list or len(attempts) != len(expected_media):
        return "FAIL", {"reason": "S9_ATTEMPT_LIMIT_EXCEEDED"}
    for attempt, expected in zip(attempts, expected_media, strict=True):
        if (
            type(attempt) is not dict
            or attempt.get("identity_alias") != expected["identity_alias"]
            or attempt.get("profile") != expected["profile"]
            or attempt.get("expected_bytes") != expected["expected_bytes"]
            or attempt.get("attempt") != 1
        ):
            return "FAIL", {"reason": "ATTEMPT_PLAN_MISMATCH"}
    if any(uncertain.values()):
        profile_statuses = {
            profile: "PARTIAL" if uncertain[profile] else "PASS"
            for profile in ("F", "M") if profile in expected_profiles
        }
        if not has_m:
            profile_statuses["M"] = "BLOCKED_DATASET"
        return "PARTIAL", {
            "f_consumed_or_uncertain": consumed["F"] + uncertain["F"],
            "m_consumed_or_uncertain": consumed["M"] + uncertain["M"],
            "unknown_bytes": sum(uncertain.values()),
            "profile_statuses": profile_statuses,
            "reason": "UNCERTAIN_BYTES_CHARGED_CONSERVATIVELY",
        }
    observed_bytes = evidence.get("observed_bytes")
    ledger_observed = sum(consumed.values())
    if type(observed_bytes) is not int or observed_bytes != ledger_observed:
        return "FAIL", {"reason": "QUEUE_BYTE_TOTAL_MISMATCH"}
    profile_statuses = {"F": "PASS", "M": "PASS" if has_m else "BLOCKED_DATASET"}
    summary = {
        "f_observed_bytes": consumed["F"], "m_observed_bytes": consumed["M"],
        "aggregate_observed_bytes": ledger_observed,
        "deadline_seconds": total_elapsed,
        "verified_stage_receipts": len(verified_receipts),
        "verified_disk_checks": disk_summary["verified_checks"],
        "profile_statuses": profile_statuses,
        "no_pending_children": all(
            receipt["process_tree_termination_confirmed"] is True
            for receipt in verified_receipts.values()
        ),
        "active_children": 0,
    }
    if not has_m:
        return "PARTIAL", {**summary, "reason": "G5_M_BLOCKED_DATASET"}
    return "PASS", summary


def _private_final_path(root: Path, value: object) -> Path:
    if type(value) is not str or not value:
        raise ReconciliationError("DOWNLOAD_FINAL_PATH_INVALID")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise ReconciliationError("DOWNLOAD_FINAL_PATH_INVALID")
    try:
        resolved_root = root.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=True)
        relative = resolved_candidate.relative_to(resolved_root)
    except (OSError, ValueError):
        raise ReconciliationError("DOWNLOAD_FINAL_PATH_OUTSIDE_RUN") from None
    if os.path.normcase(str(candidate.absolute())) != os.path.normcase(str(resolved_candidate)):
        raise ReconciliationError("DOWNLOAD_FINAL_PATH_REPARSE")
    cursor = resolved_root
    try:
        for part in relative.parts:
            cursor = cursor / part
            info = cursor.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400
                or (cursor != resolved_candidate and not stat.S_ISDIR(info.st_mode))
            ):
                raise ReconciliationError("DOWNLOAD_FINAL_PATH_REPARSE")
        if not stat.S_ISREG(cursor.lstat().st_mode):
            raise ReconciliationError("DOWNLOAD_FINAL_PATH_INVALID")
    except OSError:
        raise ReconciliationError("DOWNLOAD_FINAL_PATH_UNAVAILABLE") from None
    return resolved_candidate


def _snapshot_identity_alias(ledger: S9OperationalLedger, row: sqlite3.Row) -> str:
    identity = f"{row['channel_id']}:{row['telegram_message_id']}:{row['media_ordinal']}"
    return ledger.pseudonym(identity)


def _validate_integrity(
    ledger: S9OperationalLedger, root: Path, bundle: Mapping[str, object],
    manifest: Mapping[str, object],
    manifest_sha256: str, evidence: Mapping[str, object],
    g2_summary: Mapping[str, object], expected_media: list[dict[str, object]],
    g5_profile_statuses: Mapping[str, object],
) -> tuple[str, dict[str, object]]:
    if evidence.get("database_sha256") != g2_summary.get("database_sha256"):
        return "FAIL", {"reason": "SQLITE_MANIFEST_DIVERGENCE"}
    if evidence.get("manifest_sha256") != manifest_sha256:
        return "FAIL", {"reason": "G6_MANIFEST_DIVERGENCE"}
    physical_media = [item for item in expected_media if item.get("profile") == "F"]
    logical_media = [item for item in expected_media if item.get("profile") == "M"]
    if not physical_media:
        return "BLOCKED", {"reason": "PHYSICAL_ARTIFACT_MISSING"}
    if logical_media and (
        g5_profile_statuses.get("M") != "PASS"
        or evidence.get("m_logical_fixture_only") is not True
        or evidence.get("m_logical_item_count") != len(logical_media)
    ):
        return "BLOCKED", {"reason": "M_LOGICAL_FIXTURE_NOT_RECONCILED"}
    if not logical_media and evidence.get("m_logical_item_count", 0) != 0:
        return "FAIL", {"reason": "M_LOGICAL_ITEM_COUNT_DIVERGENCE"}
    artifacts = evidence.get("artifacts")
    if type(artifacts) is not list or len(artifacts) != len(physical_media):
        return "BLOCKED", {"reason": "ARTIFACT_PLAN_COVERAGE_MISMATCH"}
    planned_by_alias = {
        str(item["identity_alias"]): item for item in physical_media
    }
    artifact_aliases: list[str] = []
    for artifact in artifacts:
        if type(artifact) is not dict:
            return "FAIL", {"reason": "PHYSICAL_ARTIFACT_SCHEMA_INVALID"}
        alias = artifact.get("identity_alias")
        if type(alias) is not str or alias not in planned_by_alias or alias in artifact_aliases:
            return "FAIL", {"reason": "DOWNLOAD_IDENTITY_NOT_IN_PLAN"}
        artifact_aliases.append(alias)
    if set(artifact_aliases) != set(planned_by_alias):
        return "BLOCKED", {"reason": "ARTIFACT_PLAN_COVERAGE_MISMATCH"}
    db_path = _database_path(root, bundle)
    db = _open_sqlite_readonly(db_path)
    total_bytes = 0
    verified_hashes: list[str] = []
    try:
        tables = _query_tables(db)
        if not {"downloads", "media_items"}.issubset(tables):
            return "BLOCKED", {"reason": "DOWNLOAD_TABLES_MISSING"}
        for artifact in artifacts:
            path = _regular_file(root, artifact.get("filename"), max_bytes=2 * M_MAX)
            actual_hash = _hash_file(path)
            actual_size = path.stat().st_size
            if actual_hash != artifact.get("sha256") or actual_size != artifact.get("size_bytes"):
                return "FAIL", {"reason": "PHYSICAL_ARTIFACT_DIVERGENCE"}
            if artifact.get("checkpoint_sha256") != actual_hash:
                return "FAIL", {"reason": "CHECKPOINT_HASH_DIVERGENCE"}
            media_item_id = artifact.get("media_item_id")
            if type(media_item_id) is not int or media_item_id <= 0:
                return "BLOCKED", {"reason": "DOWNLOAD_IDENTITY_BINDING_MISSING"}
            row = db.execute(
                "SELECT d.state,d.final_path,d.expected_bytes,d.downloaded_bytes,d.sha256,"
                "d.remote_identity_media_id,d.remote_identity_kind,d.remote_identity_size,"
                "d.remote_identity_provenance,m.channel_id,m.telegram_message_id,m.media_ordinal,"
                "m.kind,m.telegram_media_id,m.file_size_bytes,m.remote_observation_state "
                "FROM downloads d JOIN media_items m ON m.id=d.media_item_id "
                "WHERE d.media_item_id=?",
                (media_item_id,),
            ).fetchone()
            if row is None:
                return "BLOCKED", {"reason": "DOWNLOAD_LEDGER_ROW_MISSING"}
            try:
                persisted_path = _private_final_path(root, row["final_path"])
            except ReconciliationError as error:
                return "BLOCKED", {"reason": str(error)}
            if persisted_path != path.resolve(strict=True):
                return "FAIL", {"reason": "DOWNLOAD_FINAL_PATH_DIVERGENCE"}
            expected_bytes = planned_by_alias[artifact["identity_alias"]].get("expected_bytes")
            try:
                persisted_alias = _snapshot_identity_alias(ledger, row)
            except LedgerError:
                return "BLOCKED", {"reason": "S7_IDENTITY_PSEUDONYM_UNAVAILABLE"}
            snapshot_matches = (
                row["remote_observation_state"] == "OBSERVED"
                and row["remote_identity_provenance"] == "CAPTURED_AT_START"
                and row["remote_identity_media_id"] == row["telegram_media_id"]
                and row["remote_identity_kind"] == row["kind"] == "DOCUMENT"
                and row["remote_identity_size"] == row["file_size_bytes"] == expected_bytes
                and row["channel_id"] == manifest.get("channel_id")
                and persisted_alias == artifact["identity_alias"]
            )
            if not snapshot_matches:
                return "FAIL", {"reason": "S7_MEDIA_IDENTITY_SNAPSHOT_DIVERGENCE"}
            if (
                row["state"] != "DOWNLOADED"
                or row["expected_bytes"] != expected_bytes
                or row["downloaded_bytes"] != actual_size
                or row["expected_bytes"] != row["downloaded_bytes"]
                or row["sha256"] != actual_hash
            ):
                return "FAIL", {"reason": "DOWNLOAD_LEDGER_ARTIFACT_DIVERGENCE"}
            total_bytes += actual_size
            verified_hashes.append(actual_hash)
    except sqlite3.Error:
        return "BLOCKED", {"reason": "DOWNLOAD_LEDGER_READ_FAILED"}
    finally:
        db.close()
    for name in ("ownership_confirmed", "no_overwrite_confirmed", "hash_verified"):
        if evidence.get(name) is not True:
            return "BLOCKED", {"reason": f"{name.upper()}_UNPROVEN"}
    second = evidence.get("second_queue")
    if type(second) is not dict:
        return "BLOCKED", {"reason": "SECOND_QUEUE_EVIDENCE_MISSING"}
    if second.get("new_payload_bytes") != 0 or second.get("all_items_already_valid") is not True:
        return "FAIL", {"reason": "SECOND_QUEUE_NOT_IDEMPOTENT"}
    return "PASS", {
        "verified_f_item_count": len(physical_media),
        "physical_size_bytes": total_bytes,
        "physical_hashes": verified_hashes,
        "logical_m_item_count": len(logical_media),
        "second_queue_new_payload_bytes": 0, "ownership_confirmed": True,
        "sqlite_download_reconciled": True, "s7_identity_snapshot_reconciled": True,
    }


def _validate_incremental(
    root: Path, bundle: Mapping[str, object], manifest: Mapping[str, object],
    g6_status: str, evidence: Mapping[str, object],
    g2_summary: Mapping[str, object],
) -> tuple[str, dict[str, object]]:
    if g6_status != "PASS":
        return "BLOCKED", {"reason": "G6_NOT_ELIGIBLE"}
    if evidence.get("baseline_status") != "COMPLETE" or evidence.get("baseline_verified") is not True:
        return "BLOCKED", {"reason": "BLOCKED_BASELINE_INCOMPLETE"}
    if evidence.get("window_size") != INCREMENTAL_WINDOW:
        return "FAIL", {"reason": "INCREMENTAL_WINDOW_INVALID"}
    baseline_id = evidence.get("baseline_scan_run_id")
    incremental_id = evidence.get("incremental_scan_run_id")
    if (
        type(baseline_id) is not str or not baseline_id
        or type(incremental_id) is not str or not incremental_id
        or baseline_id == incremental_id
    ):
        return "BLOCKED", {"reason": "S7_SCAN_BINDING_MISSING"}
    try:
        path = _database_path(root, bundle)
        if (
            evidence.get("database_sha256") != g2_summary.get("database_sha256")
            or _hash_file(path) != g2_summary.get("database_sha256")
        ):
            return "FAIL", {"reason": "G7_DATABASE_BINDING_MISMATCH"}
        db = _open_sqlite_readonly(path)
    except ReconciliationError as error:
        return "BLOCKED", {"reason": str(error)}
    try:
        if not {"scan_runs", "sync_checkpoints"}.issubset(_query_tables(db)):
            return "BLOCKED", {"reason": "S7_CHECKPOINT_TABLES_MISSING"}
        baseline = db.execute(
            "SELECT r.channel_id,r.status,r.watermark_message_id,c.channel_id,"
            "c.status,c.watermark_message_id FROM scan_runs r "
            "JOIN sync_checkpoints c ON c.scan_run_id=r.id WHERE r.id=?",
            (baseline_id,),
        ).fetchone()
        incremental = db.execute(
            "SELECT r.channel_id,r.status,r.sync_mode,r.sync_baseline_confirmed,"
            "r.sync_high_water_before,r.sync_reconcile_floor_message_id,"
            "r.sync_reconcile_window,r.sync_snapshot_head_message_id,r.watermark_message_id,"
            "r.messages_unverified,c.channel_id,c.status,c.watermark_message_id,c.last_message_id,"
            "r.messages_seen,r.sync_max_messages "
            "FROM scan_runs r JOIN sync_checkpoints c ON c.scan_run_id=r.id WHERE r.id=?",
            (incremental_id,),
        ).fetchone()
    except sqlite3.Error:
        return "BLOCKED", {"reason": "S7_CHECKPOINT_READ_FAILED"}
    finally:
        db.close()
    if baseline is None or incremental is None:
        return "BLOCKED", {"reason": "S7_SCAN_BINDING_MISSING"}
    channel_id = manifest.get("channel_id")
    baseline_high_water = baseline[2]
    if (
        baseline[0] != channel_id or baseline[3] != channel_id
        or baseline[1] != "COMPLETE" or baseline[4] != "COMPLETE"
        or type(baseline_high_water) is not int or baseline_high_water < 0
        or baseline[5] != baseline_high_water
    ):
        return "BLOCKED", {"reason": "BLOCKED_BASELINE_INCOMPLETE"}
    before = incremental[4]
    snapshot_head = incremental[7]
    after = incremental[8]
    checkpoint_after = incremental[12]
    if (
        incremental[0] != channel_id or incremental[10] != channel_id
        or incremental[1] != "COMPLETE" or incremental[2] != "INCREMENTAL"
        or incremental[3] != 1 or type(before) is not int
        or before != baseline_high_water
        or incremental[6] != INCREMENTAL_WINDOW
        or incremental[5] != max(1, before - INCREMENTAL_WINDOW + 1)
        or (snapshot_head is not None and type(snapshot_head) is not int)
        or incremental[8] != max(before, snapshot_head or before)
        or incremental[9] not in {0, None}
        or incremental[11] != "COMPLETE"
        or checkpoint_after != after
        or incremental[13] is None
        or type(incremental[14]) is not int
        or not 0 <= incremental[14] <= MAX_MESSAGES_PER_SCAN
        or type(incremental[15]) is not int
        or not 1 <= incremental[15] <= MAX_MESSAGES_PER_SCAN
        or incremental[14] > incremental[15]
    ):
        return "FAIL", {"reason": "S7_INCREMENTAL_RUN_DIVERGENCE"}
    if after < before:
        return "FAIL", {"reason": "HIGH_WATER_DIVERGENCE"}
    if (
        evidence.get("high_water_before") != before
        or evidence.get("baseline_high_water") != baseline_high_water
        or evidence.get("high_water_after") != after
    ):
        return "FAIL", {"reason": "HIGH_WATER_DIVERGENCE"}
    if evidence.get("deletions_inferred") is not False:
        return "FAIL", {"reason": "DELETE_INFERENCE_FORBIDDEN"}
    return "PASS", {
        "window_size": INCREMENTAL_WINDOW,
        "high_water_before": before,
        "high_water_after": after,
        "baseline_status": "COMPLETE",
        "incremental_messages_seen": incremental[14],
        "incremental_max_messages": incremental[15],
        "s7_checkpoint_reconciled": True,
    }


def _validate_recovery(evidence: Mapping[str, object]) -> tuple[str, dict[str, object]]:
    interruption = evidence.get("interruption_count")
    recoveries = evidence.get("recovery_count")
    if type(interruption) is not int or type(recoveries) is not int:
        return "BLOCKED", {"reason": "RECOVERY_COUNTS_MISSING"}
    if interruption > 1 or recoveries > 1:
        return "FAIL", {"reason": "RECOVERY_CAP_EXCEEDED"}
    if interruption == 0 and recoveries == 0:
        return "BLOCKED", {"reason": "NO_INTERRUPTION_EVIDENCE"}
    if interruption != 1 or recoveries != 1:
        return "PARTIAL", {"reason": "RECOVERY_SEQUENCE_INCOMPLETE"}
    if evidence.get("profile") != "F" or evidence.get("part_preserved") is not True:
        return "BLOCKED", {"reason": "F_PART_NOT_PRESERVED"}
    if evidence.get("ownership_confirmed") is not True or evidence.get("containment_proven") is not True:
        return "BLOCKED", {"reason": "RECOVERY_CONTAINMENT_UNPROVEN"}
    if evidence.get("remote_hash_policy") != "REMOTE_HASH_REQUIRED":
        return "BLOCKED", {"reason": "V1_REMOTE_HASH_POLICY_MISSING"}
    if evidence.get("synthetic_remote_prefix_verified") is not True:
        return "BLOCKED", {"reason": "V1_PREFIX_CHECK_NOT_RECONCILED"}
    if evidence.get("remote_hash_origin") != "SYNTHETIC_TEST":
        return "FAIL", {"reason": "OFFLINE_PREFIX_ORIGIN_INVALID"}
    if evidence.get("real_prefix_hash_proven") is not False:
        return "FAIL", {"reason": "SYNTHETIC_PREFIX_CLAIMED_AS_REAL"}
    uncertainty = evidence.get("uncertainty_bytes")
    if type(uncertainty) is not int or uncertainty != 0:
        return "PARTIAL", {"reason": "RECOVERY_BYTES_UNCERTAIN"}
    return "PASS", {
        "interruptions": 1, "recoveries": 1,
        "remote_hash_origin": "SYNTHETIC_TEST", "real_prefix_hash_proven": False,
    }


def _event_id(run_id: str, gate: str, source_sha256: str, suffix: str) -> str:
    return _sha256(f"{run_id}|{gate}|{source_sha256}|{suffix}".encode("ascii"))[:32]


def _audit_event(ledger: S9OperationalLedger, event_type: str, details: dict[str, object], event_id: str) -> None:
    try:
        ledger.record_critical_event(event_type, details=details, event_id=event_id)
    except LedgerError as error:
        raise ReconciliationError("LEDGER_AUDIT_WRITE_FAILED") from error


def _persist_receipt(
    ledger: S9OperationalLedger, run_root: Path, gate: str,
    receipt: dict[str, object], source_sha256: str,
    *, before_rename_checkpoint: Callable[[], object] | None = None,
) -> tuple[str, Path]:
    path = run_root / f"{gate.lower()}-receipt.json"
    encoded = _canonical(receipt) + b"\n"
    if len(encoded) > MAX_RECEIPT_BYTES:
        raise ReconciliationError("RECEIPT_TOO_LARGE")
    digest = _sha256(encoded)
    prepared_id = _event_id(str(receipt["run_id"]), gate, source_sha256, "receipt-prepared")
    persisted_id = _event_id(str(receipt["run_id"]), gate, source_sha256, "receipt-persisted")

    def prepare(raw: bytes) -> None:
        if raw != encoded:
            raise ReconciliationError("RECEIPT_BYTES_CHANGED")
        _audit_event(ledger, "RECEIPT_PREPARED", {"receipt_sha256": digest}, prepared_id)
        if before_rename_checkpoint is not None:
            before_rename_checkpoint()

    def persist(raw: bytes) -> None:
        if raw != encoded:
            raise ReconciliationError("RECEIPT_BYTES_CHANGED")
        _audit_event(ledger, "RECEIPT_PERSISTED", {"receipt_sha256": digest}, persisted_id)

    if path.exists():
        try:
            info = path.lstat()
            existing = path.read_bytes()
        except OSError:
            raise ReconciliationError("RECEIPT_UNAVAILABLE") from None
        if (
            not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or existing != encoded
        ):
            raise ReconciliationError("RECEIPT_REPLAY_CONFLICT")
        try:
            _verify_private_file(path)
        except (LedgerError, OSError):
            raise ReconciliationError("RECEIPT_NOT_PRIVATE") from None
        if not _receipt_event_valid(ledger.snapshot(), prepared_id, digest):
            raise ReconciliationError("RECEIPT_PREPARATION_ATTESTATION_MISSING")
        prepare(encoded)
        persist(encoded)
    else:
        try:
            _write_no_overwrite_json(path, receipt, before_rename=prepare, after_rename=persist)
        except ReconciliationError:
            raise
        except Exception as error:
            raise ReconciliationError("RECEIPT_PERSIST_FAILED") from error
    return digest, path


def _persist_gate(
    ledger: S9OperationalLedger,
    run_root: Path,
    run_id: str,
    gate: str,
    status: str,
    reason: str,
    source_sha256: str | None,
    manifest_sha256: str,
    scope_sha256: str,
    summary: dict[str, object],
) -> GateResult:
    if status not in {"PASS", "PARTIAL", "BLOCKED", "FAIL", "NOT_ASSESSED"}:
        raise ReconciliationError("GATE_STATUS_INVALID")
    source = source_sha256 or _sha256(f"{run_id}|{gate}|MISSING".encode("ascii"))
    evidence_origin = "OFFLINE_SYNTHETIC" if gate == "G9" else "SYNTHETIC"
    real_evidence_status = (
        str(summary.get("real_evidence_status", "REAL_EVIDENCE_PENDING"))
        if gate == "G9" else "NOT_ASSESSED"
    )
    _audit_event(
        ledger, "GATE_STARTED", {"gate": gate},
        _event_id(run_id, gate, source, "gate-started"),
    )
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate": gate,
        "status": status,
        "evidence_origin": evidence_origin,
        "real_evidence_status": real_evidence_status,
        "manifest_sha256": manifest_sha256,
        "scope_sha256": scope_sha256,
        "source_sha256": source,
        "reason": reason,
        "summary": summary,
    }
    checkpoint_required = (
        gate in {"G5", "G6", "G7", "G8", "G9"}
        and status in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
    )
    digest, path = _persist_receipt(
        ledger, run_root, gate, receipt, source,
        before_rename_checkpoint=ledger.checkpoint if checkpoint_required else None,
    )
    finished_details: dict[str, object] = {
        "gate": gate,
        "result": status if status in {"PASS", "PARTIAL", "FAIL", "BLOCKED"} else "UNKNOWN",
    }
    if gate == "G9":
        finished_details.update({
            "evidence_origin": evidence_origin,
            "offline_result": str(summary.get("offline_result", status)),
            "real_evidence_status": real_evidence_status,
        })
    _audit_event(
        ledger, "GATE_FINISHED", finished_details,
        _event_id(run_id, gate, source, "gate-finished"),
    )
    return GateResult(gate, status, reason, source_sha256, digest, path, summary)


def _receipt_event_valid(ledger_snapshot: Mapping[str, object], event_id: str, digest: str) -> bool:
    audit = ledger_snapshot.get("critical_audit")
    if type(audit) is not dict or audit.get("quarantined") is not False:
        return False
    events = audit.get("events")
    if type(events) is not list:
        return False
    for event in events:
        if event.get("event_id") != event_id:
            continue
        try:
            details = json.loads(event["details_json"])
        except (KeyError, TypeError, ValueError):
            return False
        return details == {"receipt_sha256": digest}
    return False


def _audit_detail_valid(
    ledger_snapshot: Mapping[str, object], event_id: str,
    event_type: str, expected: dict[str, object],
) -> bool:
    audit = ledger_snapshot.get("critical_audit")
    if type(audit) is not dict or audit.get("quarantined") is not False:
        return False
    events = audit.get("events")
    if type(events) is not list:
        return False
    for event in events:
        if event.get("event_id") != event_id:
            continue
        try:
            details = json.loads(event["details_json"])
        except (KeyError, TypeError, ValueError):
            return False
        return event.get("event_type") == event_type and details == expected
    return False


def _load_existing_gate(
    ledger: S9OperationalLedger,
    run_root: Path,
    run_id: str,
    gate: str,
    source_sha256: str,
    manifest_sha256: str,
    scope_sha256: str,
) -> GateResult | None:
    path = run_root / f"{gate.lower()}-receipt.json"
    if not path.exists():
        return None
    try:
        info = path.lstat()
        encoded = path.read_bytes()
    except OSError:
        raise ReconciliationError("RECEIPT_UNAVAILABLE") from None
    expected_origin = "OFFLINE_SYNTHETIC" if gate == "G9" else "SYNTHETIC"
    expected_real_status = "REAL_EVIDENCE_PENDING" if gate == "G9" else "NOT_ASSESSED"
    if (
        not stat.S_ISREG(info.st_mode) or path.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
        or len(encoded) > MAX_RECEIPT_BYTES
    ):
        raise ReconciliationError("RECEIPT_UNSAFE")
    try:
        _verify_private_file(path)
        payload = json.loads(encoded.decode("utf-8"), object_pairs_hook=_unique_object)
    except ReconciliationError:
        raise
    except (LedgerError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ReconciliationError("RECEIPT_INVALID") from None
    if type(payload) is not dict or encoded != _canonical(payload) + b"\n":
        raise ReconciliationError("RECEIPT_NONCANONICAL")
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("run_id") != run_id
        or payload.get("gate") != gate
        or payload.get("evidence_origin") != expected_origin
        or payload.get("real_evidence_status") != expected_real_status
        or payload.get("manifest_sha256") != manifest_sha256
        or payload.get("scope_sha256") != scope_sha256
        or payload.get("source_sha256") != source_sha256
        or payload.get("status") not in {"PASS", "PARTIAL", "BLOCKED", "FAIL", "NOT_ASSESSED"}
        or type(payload.get("summary")) is not dict
    ):
        raise ReconciliationError("RECEIPT_REPLAY_CONFLICT")
    digest = _sha256(encoded)
    started_id = _event_id(run_id, gate, source_sha256, "gate-started")
    finished_id = _event_id(run_id, gate, source_sha256, "gate-finished")
    prepared_id = _event_id(run_id, gate, source_sha256, "receipt-prepared")
    persisted_id = _event_id(run_id, gate, source_sha256, "receipt-persisted")
    snapshot = ledger.snapshot()
    finished_result = payload["status"] if payload["status"] != "NOT_ASSESSED" else "UNKNOWN"
    finished_details: dict[str, object] = {"gate": gate, "result": finished_result}
    if gate == "G9":
        finished_details.update({
            "evidence_origin": "OFFLINE_SYNTHETIC",
            "offline_result": str(payload["summary"].get("offline_result", payload["status"])),
            "real_evidence_status": "REAL_EVIDENCE_PENDING",
        })
    if (
        not _audit_detail_valid(snapshot, started_id, "GATE_STARTED", {"gate": gate})
        or not _audit_detail_valid(
            snapshot, finished_id, "GATE_FINISHED",
            finished_details,
        )
        or not _receipt_event_valid(snapshot, prepared_id, digest)
        or not _receipt_event_valid(snapshot, persisted_id, digest)
    ):
        return None
    return GateResult(
        gate, str(payload["status"]), str(payload["reason"]),
        source_sha256, digest, path, dict(payload["summary"]),
    )


def _validated_deadline(snapshot: Mapping[str, object]) -> int:
    run = snapshot.get("run")
    audit = snapshot.get("critical_audit")
    if type(run) is not dict or type(audit) is not dict:
        raise ReconciliationError("GLOBAL_DEADLINE_INVALID")
    deadline = run.get("deadline_ns")
    events = audit.get("events")
    if type(deadline) is not int or type(events) is not list:
        raise ReconciliationError("GLOBAL_DEADLINE_INVALID")
    starts: list[dict[str, object]] = []
    for event in events:
        if event.get("event_type") == "RUN_DEADLINE_STARTED":
            try:
                details = json.loads(event["details_json"])
            except (KeyError, TypeError, ValueError):
                raise ReconciliationError("GLOBAL_DEADLINE_INVALID") from None
            if type(details) is dict:
                starts.append(details)
    if (
        len(starts) != 1 or starts[0].get("seconds") != 3600
        or starts[0].get("deadline_ns") != deadline
    ):
        raise ReconciliationError("GLOBAL_DEADLINE_INVALID")
    return deadline


def _validate_bundle(bundle: Mapping[str, object], run_id: str) -> tuple[dict[str, object], str, str, str, str]:
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise ReconciliationError("EVIDENCE_SCHEMA_VERSION_UNSUPPORTED")
    if bundle.get("evidence_origin") != "SYNTHETIC":
        origin = str(bundle.get("evidence_origin", "UNKNOWN")).upper()
        if origin in _FORBIDDEN_REAL_ORIGINS:
            raise ReconciliationError("REAL_EVIDENCE_NOT_AUTHORIZED")
        raise ReconciliationError("EVIDENCE_ORIGIN_UNTRUSTED")
    if bundle.get("run_id") != run_id:
        raise ReconciliationError("EVIDENCE_RUN_MISMATCH")
    manifest = bundle.get("manifest")
    if type(manifest) is not dict:
        raise ReconciliationError("MANIFEST_MISSING")
    manifest_sha256 = _sha256(_canonical(manifest))
    scope = manifest.get("scope")
    if type(scope) is not dict or not scope:
        raise ReconciliationError("MANIFEST_SCOPE_MISSING")
    scope_sha256 = _sha256(_canonical(scope))
    gates = bundle.get("gates")
    if type(gates) is not dict:
        gates = {}
    return dict(gates), manifest_sha256, scope_sha256, _sha256(_canonical(bundle)), str(bundle.get("database_file", ""))


def _evaluate_gate(
    gate: str,
    evidence: object,
    *,
    ledger: S9OperationalLedger,
    run_root: Path,
    bundle: Mapping[str, object],
    manifest: Mapping[str, object],
    manifest_sha256: str,
    prior: Mapping[str, GateResult],
) -> tuple[str, str, dict[str, object], str | None]:
    if type(evidence) is not dict:
        return "BLOCKED", "EVIDENCE_MISSING", {}, None
    source_sha256 = _sha256(_canonical(evidence))
    if evidence.get("origin") != "SYNTHETIC":
        return "FAIL", "EVIDENCE_ORIGIN_UNTRUSTED", {}, source_sha256
    if evidence.get("manifest_sha256") != manifest_sha256:
        return "FAIL", "MANIFEST_BINDING_MISMATCH", {}, source_sha256
    if gate == "G1":
        if (
            evidence.get("authentication") != "SYNTHETIC_AUTHENTICATED"
            or evidence.get("target_selected") is not True
            or evidence.get("cleanup_complete") is not True
            or evidence.get("scope_sha256") != _sha256(_canonical(manifest.get("scope")))
        ):
            return "BLOCKED", "SYNTHETIC_AUTH_DISCOVERY_INCOMPLETE", {}, source_sha256
        return "PASS", "SYNTHETIC_G1_PASS", {"target_alias": "SYNTHETIC_TARGET", "authentication": "SYNTHETIC_AUTHENTICATED"}, source_sha256
    required = f"G{int(gate[1:]) - 1}"
    predecessor_eligible = required in prior and prior[required].status == "PASS"
    if gate == "G6" and required in prior and prior[required].status == "PARTIAL":
        predecessor_eligible = (
            prior[required].summary.get("profile_statuses", {}).get("F") == "PASS"
        )
    if not predecessor_eligible:
        return "BLOCKED", "PREDECESSOR_NOT_PASS", {}, source_sha256
    if gate == "G2":
        status, summary = _scan_database(
            run_root, bundle, manifest, evidence,
            run_started_ns=int(ledger.snapshot()["run"]["created_ns"]),
        )
        reason = str(summary.pop("reason", "SCAN_RECONCILED"))
        return status, reason, summary, source_sha256
    if gate == "G3":
        status, summary = _catalog_database(
            run_root, bundle, manifest, evidence, prior["G2"].summary,
        )
        reason = str(summary.pop("reason", "CATALOG_RECONCILED"))
        return status, reason, summary, source_sha256
    if gate == "G4":
        status, summary = _validate_plan(manifest_sha256, evidence)
        reason = str(summary.pop("reason", "PLAN_RECONCILED"))
        return status, reason, summary, source_sha256
    if gate == "G5":
        status, summary = _validate_queue(
            evidence, list(prior["G4"].summary["media_contracts"]),
            int(prior["G4"].summary["m_expected_bytes"]),
            ledger=ledger, root=run_root,
            scan_run_ids=list(prior["G2"].summary["scan_run_ids"]),
        )
        reason = str(summary.pop("reason", "QUEUE_RECONCILED"))
        return status, reason, summary, source_sha256
    if gate == "G6":
        g5 = prior.get("G5")
        if g5 is None or not (
            g5.status == "PASS"
            or g5.status == "PARTIAL"
            and g5.summary.get("profile_statuses", {}).get("F") == "PASS"
        ):
            return "BLOCKED", "G5_NOT_ELIGIBLE", {}, source_sha256
        status, summary = _validate_integrity(
            ledger, run_root, bundle, manifest, manifest_sha256, evidence,
            prior["G2"].summary, list(prior["G4"].summary["media_contracts"]),
            g5.summary.get("profile_statuses", {}),
        )
        reason = str(summary.pop("reason", "INTEGRITY_RECONCILED"))
        return status, reason, summary, source_sha256
    if gate == "G7":
        status, summary = _validate_incremental(
            run_root, bundle, manifest, prior["G6"].status, evidence,
            prior["G2"].summary,
        )
        reason = str(summary.pop("reason", "INCREMENTAL_RECONCILED"))
        return status, reason, summary, source_sha256
    if gate == "G8":
        status, summary = _validate_recovery(evidence)
        reason = str(summary.pop("reason", "RECOVERY_RECONCILED"))
        return status, reason, summary, source_sha256
    return "NOT_ASSESSED", "GATE_NOT_SUPPORTED", {}, source_sha256


def reconcile_offline_evidence(
    run_directory: str | Path,
    evidence_file: str | Path,
    *,
    now_ns: int | None = None,
) -> OfflineReconciliation:
    """Validate G1-G8 synthetic evidence and persist a G9 reconciliation.

    Every receipt is bound to the ledger run, a canonical manifest/scope digest,
    source digest, and audit-chain receipt events. Existing receipts are never
    replaced. The final state is strictly offline and leaves real evidence
    pending.
    """
    selected = Path(run_directory)
    try:
        resolved = selected.resolve(strict=True)
        info = selected.lstat()
        if (
            not selected.is_absolute() or selected.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or not stat.S_ISDIR(info.st_mode)
            or os.path.normcase(str(selected.absolute())) != os.path.normcase(str(resolved))
        ):
            raise ReconciliationError("RUN_DIRECTORY_UNSAFE")
        guard = _open_private_directory_guard(selected)
    except ReconciliationError:
        raise
    except (OSError, LedgerError):
        raise ReconciliationError("RUN_DIRECTORY_PRIVATE_OR_UNAVAILABLE") from None
    try:
        guard.verify(resolved)
        ledger_path = resolved / "operational-ledger.sqlite3"
        _regular_file(resolved, ledger_path.name, max_bytes=512 * MIB)
        ledger = S9OperationalLedger(ledger_path)
        snapshot = ledger.snapshot()
        run = snapshot["run"]
        run_id = str(run["run_id"])
        if snapshot["critical_audit"]["quarantined"]:
            raise ReconciliationError("LEDGER_AUDIT_QUARANTINED")
        deadline_ns = _validated_deadline(snapshot)
        terminal_resume = (
            run["gate"] == "G9"
            and run["status"] in {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"}
        )
        if not terminal_resume and (
            run["gate"] != "G1" or run["result"] != "UNKNOWN" or run["status"] != "RUNNING"
        ):
            raise ReconciliationError("OFFLINE_RECONCILIATION_REQUIRES_FRESH_RUN")
        if type(now_ns) is not int and now_ns is not None:
            raise ReconciliationError("CLOCK_VALUE_INVALID")

        bundle = load_evidence_file(resolved, evidence_file)
        manifest = bundle.get("manifest")
        if type(manifest) is not dict:
            manifest = {}
        gates, manifest_sha256, scope_sha256, bundle_sha256, _database_file = _validate_bundle(bundle, run_id)
        results: dict[str, GateResult] = {}
        for gate in (f"G{i}" for i in range(1, 9)):
            raw_evidence = gates.get(gate)
            source_sha256 = (
                _sha256(_canonical(raw_evidence)) if type(raw_evidence) is dict
                else _sha256(f"{run_id}|{gate}|MISSING".encode("ascii"))
            )
            existing = _load_existing_gate(
                ledger, resolved, run_id, gate, source_sha256,
                manifest_sha256, scope_sha256,
            )
            if existing is not None:
                results[gate] = existing
                continue
            if terminal_resume:
                raise ReconciliationError("TERMINAL_RUN_GATE_RECEIPT_MISSING")
            current_ns = time.time_ns() if now_ns is None else now_ns
            if current_ns >= deadline_ns:
                status, reason, summary = "BLOCKED", "GLOBAL_DEADLINE_EXPIRED", {}
            else:
                try:
                    status, reason, summary, evaluated_source = _evaluate_gate(
                        gate, raw_evidence, ledger=ledger, run_root=resolved, bundle=bundle,
                        manifest=manifest, manifest_sha256=manifest_sha256, prior=results,
                    )
                    if type(raw_evidence) is dict and evaluated_source != source_sha256:
                        raise ReconciliationError("EVIDENCE_SOURCE_CHANGED")
                except ReconciliationError as error:
                    status, reason, summary = "BLOCKED", str(error), {}
                except (KeyError, TypeError, ValueError, OverflowError, sqlite3.Error):
                    status, reason, summary = "BLOCKED", "EVIDENCE_RECONCILIATION_INVALID", {}
            results[gate] = _persist_gate(
                ledger, resolved, run_id, gate, status, reason,
                source_sha256, manifest_sha256, scope_sha256, summary,
            )

        gate_summary = [
            {
                "gate": item.gate, "status": item.status,
                "reason": item.reason, "receipt_sha256": item.receipt_sha256,
            }
            for item in results.values()
        ]
        g9_source = _sha256(_canonical(gate_summary))
        statuses = [results[f"G{i}"].status for i in range(1, 9)]
        current_ns = time.time_ns() if now_ns is None else now_ns
        deadline_expired = current_ns >= deadline_ns
        if "FAIL" in statuses:
            proposed_status, offline_result, cause = "FAIL", "FAIL", "OTHER"
        elif deadline_expired and not terminal_resume:
            proposed_status, offline_result, cause = "PARTIAL", "PARTIAL", "DEADLINE"
        elif "BLOCKED" in statuses or "NOT_ASSESSED" in statuses:
            proposed_status, offline_result, cause = "BLOCKED", "BLOCKED", "OTHER"
        elif "PARTIAL" in statuses:
            proposed_status, offline_result, cause = "PARTIAL", "PARTIAL", "OTHER"
        else:
            proposed_status, offline_result, cause = "PASS", "OFFLINE_SYNTHETIC_PASS", "NONE"

        g5_summary = results["G5"].summary
        no_pending_children = (
            results["G5"].status == "PASS"
            and g5_summary.get("no_pending_children") is True
            and g5_summary.get("active_children") == 0
        )
        proposed_summary: dict[str, object] = {
            "activity_id": "TELEGRAM_S9_G1_G9_OFFLINE_COMPLETION_01",
            "offline_result": offline_result,
            "evidence_origin": "OFFLINE_SYNTHETIC",
            "real_g1_status": "REAL_G1_NOT_ASSESSED",
            "real_evidence_status": "REAL_EVIDENCE_PENDING",
            "bundle_sha256": bundle_sha256,
            "gates": gate_summary,
            "global_deadline_ns": deadline_ns,
            "global_deadline_status": "EXPIRED" if deadline_expired else "WITHIN_3600S",
            "no_pending_children": no_pending_children,
            "budgets": {
                "f_observed_bytes": g5_summary.get("f_observed_bytes"),
                "m_observed_bytes": g5_summary.get("m_observed_bytes"),
                "aggregate_observed_bytes": g5_summary.get("aggregate_observed_bytes"),
                "unknown_bytes": g5_summary.get("unknown_bytes", 0),
            },
            "manifest_plan_reconciled": (
                results["G3"].status == "PASS" and results["G4"].status == "PASS"
            ),
            "telegram_rpc": 0,
            "operational_db_writes": 0,
            "risk_03_residual_acceptance": "NOT_IMPLIED",
            "contract": "S9_V1.0_APPROVED_FROZEN",
            "s10": "NOT_AUTHORIZED",
        }
        g9_result = _load_existing_gate(
            ledger, resolved, run_id, "G9", g9_source,
            manifest_sha256, scope_sha256,
        )
        if g9_result is None:
            if terminal_resume:
                raise ReconciliationError("TERMINAL_RUN_G9_RECEIPT_MISSING")
            g9_result = _persist_gate(
                ledger, resolved, run_id, "G9", proposed_status,
                "FINAL_RECONCILIATION", g9_source, manifest_sha256,
                scope_sha256, proposed_summary,
            )
        elif g9_result.summary != proposed_summary:
            # If G9 was durably written before a crash, its exact result is the
            # recovery source. Recompute only the immutable inputs and allow
            # the deadline status to come from the receipt itself.
            expected_summary = dict(g9_result.summary)
            expected_summary.pop("global_deadline_status", None)
            expected_summary.pop("offline_result", None)
            candidate_summary = dict(proposed_summary)
            candidate_summary.pop("global_deadline_status", None)
            candidate_summary.pop("offline_result", None)
            if expected_summary != candidate_summary:
                raise ReconciliationError("G9_RECEIPT_REPLAY_CONFLICT")
            proposed_status = g9_result.status
            offline_result = str(g9_result.summary.get("offline_result"))
            deadline_expired = g9_result.summary.get("global_deadline_status") == "EXPIRED"

        cause = {
            "PASS": "NONE", "PARTIAL": "DEADLINE" if deadline_expired else "OTHER",
            "BLOCKED": "OTHER", "FAIL": "OTHER",
        }[proposed_status]

        run_status = {
            "PASS": "COMPLETED", "PARTIAL": "PARTIAL",
            "BLOCKED": "BLOCKED", "FAIL": "FAILED",
        }[proposed_status]
        ledger_result = {
            "PASS": "OFFLINE_SYNTHETIC_PASS",
            "PARTIAL": "PARTIAL", "BLOCKED": "BLOCKED", "FAIL": "FAIL",
        }[proposed_status]
        if terminal_resume:
            if run["result"] != ledger_result:
                raise ReconciliationError("TERMINAL_RUN_RESULT_DIVERGENCE")
        elif run["status"] != "RUNNING":
            raise ReconciliationError("GLOBAL_RUN_NOT_ACTIVE")
        else:
            ledger_snapshot = ledger.snapshot()
            elapsed_ms = S9OperationalLedger.execution_elapsed_ms(ledger_snapshot)
            ledger.update_execution(
                gate="G9", status=run_status, elapsed_ms=elapsed_ms,
                deadline_ns=deadline_ns, process_state="EXITED",
                result=ledger_result, cause=cause,
            )
            if ledger.snapshot()["run"]["status"] != run_status:
                raise ReconciliationError("G9_LEDGER_TERMINAL_MISMATCH")

        result = offline_result
        return OfflineReconciliation(
            run_id, result, tuple((*results.values(), g9_result)),
            g9_result.receipt_path, manifest_sha256,
        )
    finally:
        guard.close()

