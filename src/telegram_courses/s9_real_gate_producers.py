"""Bounded S9 G1-G3 evidence collection and reconciliation.

The live entry point uses the existing Telegram gateway and CLI stages. Test
adapters are always marked synthetic and cannot produce a real contractual
PASS. Dataset reconciliation is read-only; only the isolated S9 ledger and
private run receipts are written by the supervisor.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from telegram_courses.channel_discovery import (
    ChannelDiscoveryApplication,
    ChannelDiscoveryError,
    DiscoveryOutcomeState,
    select_channel,
)
from telegram_courses.config import TelegramCredentials, load_telegram_credentials
from telegram_courses.telegram_gateway import TelegramGateway

MANIFEST_FILENAME = "approved-manifest.json"
G1_WORKER_RECEIPT = "g1-worker-evidence.json"
_G1_DISCOVERY_DIAGNOSTIC_REASONS = {
    "AUTHENTICATION_REQUIRED", "SESSION_INVALID", "CHANNEL_DISCOVERY_INCOMPLETE",
    "TARGET_CHANNEL_NOT_UNIQUELY_DISCOVERED", "CHANNEL_IDENTITY_MISMATCH",
    "TARGET_CHANNEL_ALIAS_MISMATCH", "DISCOVERY_ADAPTER_FAILURE",
    "DISCOVERY_AUTH_REQUIRED", "DISCOVERY_SESSION_INVALID", "DISCOVERY_ACCESS_DENIED",
    "DISCOVERY_NETWORK", "DISCOVERY_RATE_LIMITED", "DISCOVERY_INVALID_SELECTION",
    "DISCOVERY_CLEANUP_FAILED",
}
_G1_LEDGER_DIAGNOSTIC_REASONS = {
    "LEDGER_CHILD_IDENTITY_INVALID", "LEDGER_CHILD_IDENTITY_UNAVAILABLE",
    "LEDGER_WRITER_OWNERSHIP_UNAVAILABLE", "LEDGER_PRIVATE_DIRECTORY_UNVERIFIED",
    "LEDGER_PRIVATE_FILE_UNVERIFIED", "LEDGER_CORRUPT_OR_UNKNOWN",
}


def _g1_diagnostic(phase: str, state: str, failure: str = "NONE") -> None:
    """Best-effort fixed-label diagnostics; never include exception text or data."""
    phases = {"worker_entry", "context_manifest", "t24_initialization", "t24_logging", "gateway_open", "discovery", "evidence_persistence"}
    states = {"START", "BLOCKED", "FAILURE"}
    failures = {"NONE", "INVALID_ARGUMENTS", "INVALID_ENVIRONMENT", "INVALID_CONTEXT", "INVALID_AUDIT", "MANIFEST_MISMATCH", "G0_INVALID", "BLOCKED_OUTCOME", "OS_ERROR", "VALUE_ERROR", "RUNTIME_ERROR", "OTHER_ERROR"}
    failures |= _G1_DISCOVERY_DIAGNOSTIC_REASONS
    failures |= _G1_LEDGER_DIAGNOSTIC_REASONS
    if phase not in phases or state not in states or failure not in failures:
        return
    try:
        sys.stderr.write(json.dumps({"event": "s9.g1.diagnostic", "phase": phase, "state": state, "failure_class": failure}, separators=(",", ":")) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _g1_failure_class(error: BaseException) -> str:
    if (
        type(error).__module__ == "telegram_courses.s9_operational_ledger"
        and type(error).__name__ == "LedgerError" and len(error.args) == 1
        and type(error.args[0]) is str and error.args[0] in _G1_LEDGER_DIAGNOSTIC_REASONS
    ):
        return error.args[0]
    if isinstance(error, OSError):
        return "OS_ERROR"
    if isinstance(error, ValueError):
        return "VALUE_ERROR"
    if isinstance(error, RuntimeError):
        return "RUNTIME_ERROR"
    return "OTHER_ERROR"
GATE_RECEIPTS = {
    "G0": "g0-gate-receipt.json",
    "G1": "g1-gate-receipt.json",
    "G2": "g2-gate-receipt.json",
    "G3": "g3-gate-receipt.json",
    "G6": "g6-gate-receipt.json",
    "G7": "g7-gate-receipt.json",
}
MAX_MESSAGES_PER_SCAN = 200
MAX_SCAN_INVOCATIONS = 3
MAX_SCAN_OBSERVATIONS = 600
INCREMENTAL_WINDOW = 50
MAX_G7_SYNCS = 2
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_ALIAS = re.compile(r"[A-Za-z0-9_.:-]{1,96}\Z")
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
    "max_single_media_bytes": 128 * 1024 * 1024,
    "max_transfer_bytes": 512 * 1024 * 1024,
    "workers": 1,
    "attempts_per_media": 1,
    "integrity_mode": "REMOTE_HASH_REQUIRED",
}
_S9_LEDGER_ENV = "TELEGRAM_COURSES_S9_LEDGER_PATH"
_S9_SUPERVISED_CHILD_ENV = "TELEGRAM_COURSES_S9_SUPERVISED_CHILD"
_S9_STAGE_ENV = "TELEGRAM_COURSES_S9_STAGE"


def _g7_receipt_filename(sync_index: int) -> str:
    if type(sync_index) is not int or sync_index not in {1, 2}:
        raise GateEvidenceError("G7_SYNC_INDEX_INVALID")
    return f"g7-gate-receipt-{sync_index:02d}.json"


def _g7_supervisor_receipt_filename(sync_index: int) -> str:
    if type(sync_index) is not int or sync_index not in {1, 2}:
        raise GateEvidenceError("G7_SYNC_INDEX_INVALID")
    return f"g7-scan-supervisor-receipt-{sync_index:02d}.json"


def g5_supervisor_receipt_filename(profile: str, pass_index: int) -> str:
    if profile not in {"F", "M"} or type(pass_index) is not int or pass_index not in {1, 2}:
        raise GateEvidenceError("G5_QUEUE_IDENTITY_INVALID")
    return f"g5-queue-{profile.lower()}-{pass_index:02d}-supervisor-receipt.json"


def g5_queue_receipt_filename(profile: str, pass_index: int) -> str:
    if profile not in {"F", "M"} or type(pass_index) is not int or pass_index not in {1, 2}:
        raise GateEvidenceError("G5_QUEUE_IDENTITY_INVALID")
    return f"g5-queue-{profile.lower()}-{pass_index:02d}-receipt.json"


def _gate_receipt_path(
    root: Path,
    gate: str,
    *,
    receipt_index: int | None = None,
) -> Path:
    if gate != "G7":
        if receipt_index is not None:
            raise GateEvidenceError("GATE_RECEIPT_INDEX_INVALID")
        return root / GATE_RECEIPTS[gate]
    if receipt_index is not None:
        return root / _g7_receipt_filename(receipt_index)
    existing = [
        index for index in range(1, MAX_G7_SYNCS + 1)
        if (root / _g7_receipt_filename(index)).exists()
    ]
    if existing:
        return root / _g7_receipt_filename(max(existing))
    # Read the pre-versioned name only as a fail-closed compatibility path.
    return root / GATE_RECEIPTS[gate]


class GateEvidenceError(ValueError):
    """Invalid or incomplete evidence; callers must keep the gate blocked."""


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise GateEvidenceError("EVIDENCE_NOT_CANONICAL") from None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GateEvidenceError("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _run_root(run_directory: str | Path) -> Path:
    selected = Path(run_directory)
    if not selected.is_absolute():
        raise GateEvidenceError("RUN_DIRECTORY_MUST_BE_ABSOLUTE")
    try:
        info = selected.lstat()
        resolved = selected.resolve(strict=True)
    except OSError:
        raise GateEvidenceError("RUN_DIRECTORY_UNAVAILABLE") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or selected.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
        or os.path.normcase(str(selected.absolute())) != os.path.normcase(str(resolved))
    ):
        raise GateEvidenceError("RUN_DIRECTORY_UNSAFE")
    from telegram_courses.s9_operational_ledger import (
        LedgerError,
        _open_private_directory_guard,
    )

    try:
        guard = _open_private_directory_guard(selected)
        guard.verify(resolved)
        guard.close()
    except (LedgerError, OSError):
        raise GateEvidenceError("RUN_DIRECTORY_NOT_PRIVATE") from None
    return resolved


def _private_run_file(root: Path, name: str) -> Path:
    path = root / name
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        raise GateEvidenceError("RUN_FILE_UNAVAILABLE") from None
    if (
        not stat.S_ISREG(info.st_mode)
        or path.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
        or os.path.normcase(str(resolved.parent)) != os.path.normcase(str(root))
    ):
        raise GateEvidenceError("RUN_FILE_UNSAFE")
    from telegram_courses.s9_operational_ledger import LedgerError, _verify_private_file

    try:
        _verify_private_file(path)
    except (LedgerError, OSError):
        raise GateEvidenceError("RUN_FILE_NOT_PRIVATE") from None
    return path


def validate_manifest(manifest: object) -> tuple[dict[str, object], str, str]:
    if (
        type(manifest) is not dict
        or type(manifest.get("schema_version")) is not int
        or manifest.get("schema_version") != 1
    ):
        raise GateEvidenceError("MANIFEST_SCHEMA_INVALID")
    channel_id = manifest.get("channel_id")
    alias = manifest.get("channel_alias")
    scope = manifest.get("scope")
    hierarchy = manifest.get("hierarchy")
    unresolved = manifest.get("unresolved_count")
    catalog_expectation = manifest.get("catalog_expectation")
    approval = manifest.get("scope_approval")
    planned_catalog = catalog_expectation is not None
    hierarchy_valid = (
        type(hierarchy) is dict
        and set(hierarchy) == {"TRACK", "COURSE", "MODULE"}
        and all(
            type(hierarchy.get(key)) is int
            and 0 <= hierarchy[key] <= MAX_SCAN_OBSERVATIONS
            for key in ("TRACK", "COURSE", "MODULE")
        )
    )
    if planned_catalog:
        hierarchy_valid = hierarchy_valid and hierarchy == {
            "TRACK": 1, "COURSE": 2, "MODULE": 2,
        }
        unresolved_valid = unresolved is None
        expectation_valid = (
            type(catalog_expectation) is dict
            and catalog_expectation == _PLANNED_CATALOG_EXPECTATION
        )
        scope_valid = scope == _PLANNED_RASMOO_SCOPE
    else:
        unresolved_valid = type(unresolved) is int and unresolved >= 0
        expectation_valid = True
        scope_valid = True
    if (
        type(channel_id) is not int or channel_id > -1_000_000_000_000
        or type(alias) is not str or not _SAFE_ALIAS.fullmatch(alias)
        or type(scope) is not dict or not scope
        or type(scope.get("target_alias")) is not str
        or not _SAFE_ALIAS.fullmatch(str(scope.get("target_alias")))
        or not hierarchy_valid
        or not unresolved_valid
        or not expectation_valid
        or not scope_valid
        or type(approval) is not dict
        or approval.get("decision") != "APPROVED"
        or approval.get("confirmation_source") != "G0_HUMAN_CONFIRMATION"
    ):
        raise GateEvidenceError("MANIFEST_BINDING_INVALID")
    scope_sha256 = sha256_bytes(canonical_bytes(scope))
    if approval.get("scope_sha256") != scope_sha256:
        raise GateEvidenceError("MANIFEST_APPROVAL_SCOPE_MISMATCH")
    manifest_sha256 = sha256_bytes(canonical_bytes(manifest))
    return dict(manifest), manifest_sha256, scope_sha256


def load_approved_manifest(run_directory: str | Path) -> tuple[dict[str, object], str, str]:
    root = _run_root(run_directory)
    path = _private_run_file(root, MANIFEST_FILENAME)
    try:
        manifest = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
        )
    except GateEvidenceError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise GateEvidenceError("MANIFEST_JSON_INVALID") from None
    return validate_manifest(manifest)


def _live_discovery_gateway() -> Callable[[TelegramCredentials], TelegramGateway]:
    from telegram_courses.cli import _discovery_gateway

    return _discovery_gateway


def _channel_matches_alias(title: str, username: str | None, alias: str) -> bool:
    normalized_alias = alias.casefold()
    if username is not None and username.lstrip("@").casefold() == normalized_alias:
        return True
    pattern = re.compile(
        rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])",
        re.IGNORECASE,
    )
    return pattern.search(title) is not None


async def collect_g1_evidence(
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    run_directory: str | Path | None = None,
    ledger_snapshot: Mapping[str, object] | None = None,
    gateway_factory: Callable[[TelegramCredentials], TelegramGateway] | None = None,
    credentials_loader: Callable[[], TelegramCredentials] = load_telegram_credentials,
    diagnostic: Callable[[str, str, str], None] | None = None,
) -> dict[str, object]:
    """Use existing auth/discovery workflow; injected factories stay synthetic."""
    uses_default_gateway = gateway_factory is None
    uses_default_credentials = credentials_loader is load_telegram_credentials
    requires_human_g0 = uses_default_gateway or uses_default_credentials
    selected_factory = (
        _live_discovery_gateway() if uses_default_gateway else gateway_factory
    )
    if requires_human_g0:
        if run_directory is None or ledger_snapshot is None:
            raise GateEvidenceError("G0_CONFIRMATION_REQUIRED_BEFORE_G1")
        try:
            g0 = read_validated_gate_receipt(
                run_directory, ledger_snapshot, "G0", run_id=run_id,
                manifest_sha256=manifest_sha256,
            )
        except GateEvidenceError as error:
            raise GateEvidenceError("G0_CONFIRMATION_REQUIRED_BEFORE_G1") from error
        if (
            g0.get("status") != "PASS"
            or g0.get("evidence_origin") != "HUMAN_INTERACTIVE"
            or g0.get("channel_id") != manifest.get("channel_id")
            or g0.get("authorized_scope") != manifest.get("scope")
        ):
            raise GateEvidenceError("G0_CONFIRMATION_NOT_ELIGIBLE_FOR_G1")
    real_source = uses_default_gateway and uses_default_credentials
    origin = "REAL_CONTRACTUAL" if real_source else "SYNTHETIC"
    channel_id = manifest.get("channel_id")
    channel_alias = manifest.get("channel_alias")
    base: dict[str, object] = {
        "schema_version": 1,
        "gate": "G1",
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "evidence_origin": origin,
        "authentication": "UNKNOWN",
        "discovery_complete": False,
        "channel_id": channel_id,
        "channel_alias": channel_alias,
        "target_alias_match": False,
        "discovered_count": 0,
        "target_match_count": 0,
        "cleanup_complete": False,
        "status": "BLOCKED",
        "reason": "G1_NOT_ASSESSED",
    }
    diagnostic_phase = "gateway_open"
    try:
        if diagnostic is not None:
            diagnostic("gateway_open", "START", "NONE")
            original_factory = selected_factory

            def traced_factory(credentials: TelegramCredentials) -> TelegramGateway:
                nonlocal diagnostic_phase
                gateway = original_factory(credentials)
                diagnostic_phase = "discovery"
                diagnostic("discovery", "START", "NONE")
                return gateway

            selected_factory = traced_factory
        outcome = await ChannelDiscoveryApplication(
            selected_factory, credentials_loader,
        ).discover()
        if outcome.state is DiscoveryOutcomeState.AUTH_REQUIRED:
            base["reason"] = "AUTHENTICATION_REQUIRED"
            return base
        if outcome.state is DiscoveryOutcomeState.SESSION_INVALID:
            base["reason"] = "SESSION_INVALID"
            return base
        if outcome.state is not DiscoveryOutcomeState.COMPLETE or outcome.result is None:
            base["reason"] = "CHANNEL_DISCOVERY_INCOMPLETE"
            return base
        result = outcome.result
        matches = sum(item.telegram_chat_id == channel_id for item in result.channels)
        if not result.complete or matches != 1:
            base.update({
                "authentication": "AUTHENTICATED",
                "discovery_complete": result.complete,
                "discovered_count": len(result.channels),
                "target_match_count": matches,
                "cleanup_complete": True,
                "reason": "TARGET_CHANNEL_NOT_UNIQUELY_DISCOVERED",
            })
            return base
        selected = select_channel(result, channel_id)
        if selected.telegram_chat_id != channel_id:
            base["reason"] = "CHANNEL_IDENTITY_MISMATCH"
            return base
        matched_channel = next(
            item for item in result.channels
            if item.telegram_chat_id == channel_id
        )
        alias_match = _channel_matches_alias(
            matched_channel.title, matched_channel.username, str(channel_alias),
        )
        if not alias_match:
            base.update({
                "authentication": "AUTHENTICATED",
                "discovery_complete": True,
                "discovered_count": len(result.channels),
                "target_match_count": matches,
                "cleanup_complete": True,
                "reason": "TARGET_CHANNEL_ALIAS_MISMATCH",
            })
            return base
        base.update({
            "authentication": "AUTHENTICATED",
            "discovery_complete": True,
            "discovered_count": len(result.channels),
            "target_match_count": matches,
            "target_alias_match": alias_match,
            "cleanup_complete": True,
            "status": "PASS" if real_source else "OFFLINE_SYNTHETIC_PASS",
            "reason": "G1_EVIDENCE_COLLECTED" if real_source else "SYNTHETIC_GATEWAY_ONLY",
        })
        return base
    except ChannelDiscoveryError as error:
        if diagnostic is not None:
            diagnostic(diagnostic_phase, "FAILURE", _g1_failure_class(error))
        base["reason"] = f"DISCOVERY_{error.category.value}"
    except Exception as error:
        if diagnostic is not None:
            diagnostic(diagnostic_phase, "FAILURE", _g1_failure_class(error))
        base["reason"] = "DISCOVERY_ADAPTER_FAILURE"
    return base


def validate_g1_evidence(
    evidence: object,
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    require_supervisor: bool = False,
) -> tuple[str, str]:
    if type(require_supervisor) is not bool:
        return "BLOCKED", "G1_VALIDATION_MODE_INVALID"
    if type(evidence) is not dict:
        return "BLOCKED", "G1_EVIDENCE_MISSING"
    expected_origin = evidence.get("evidence_origin")
    if (
        evidence.get("schema_version") != 1
        or evidence.get("gate") != "G1"
        or expected_origin not in {"REAL_CONTRACTUAL", "SYNTHETIC"}
    ):
        return "BLOCKED", "G1_PROVENANCE_MISSING"
    if evidence.get("run_id") != run_id or evidence.get("manifest_sha256") != manifest_sha256:
        return "BLOCKED", "G1_RUN_OR_MANIFEST_MISMATCH"
    if (
        evidence.get("authentication") != "AUTHENTICATED"
        or evidence.get("discovery_complete") is not True
        or evidence.get("target_match_count") != 1
        or evidence.get("channel_id") != manifest.get("channel_id")
        or evidence.get("channel_alias") != manifest.get("channel_alias")
        or evidence.get("cleanup_complete") is not True
        or evidence.get("target_alias_match") is not True
    ):
        return "BLOCKED", "G1_AUTH_DISCOVERY_INCOMPLETE"
    if expected_origin == "SYNTHETIC":
        return "OFFLINE_SYNTHETIC_PASS", "SYNTHETIC_GATEWAY_ONLY"
    if evidence.get("status") != "PASS":
        return "BLOCKED", "G1_STATUS_NOT_PASS"
    if require_supervisor and (
        evidence.get("supervisor_stage") != "discovery"
        or type(evidence.get("supervisor_receipt_sha256")) is not str
        or not _HASH.fullmatch(str(evidence.get("supervisor_receipt_sha256")))
        or type(evidence.get("worker_evidence_sha256")) is not str
        or not _HASH.fullmatch(str(evidence.get("worker_evidence_sha256")))
    ):
        return "BLOCKED", "G1_SUPERVISOR_PROVENANCE_MISSING"
    return "PASS", "G1_REAL_EVIDENCE_VALIDATED"


def _regular_non_reparse_file(info: os.stat_result) -> bool:
    return (
        stat.S_ISREG(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and not (getattr(info, "st_file_attributes", 0) & 0x400)
    )


def _dataset_path(root: Path, database_path: str | Path) -> Path:
    selected = Path(database_path)
    if not selected.is_absolute():
        raise GateEvidenceError("DATABASE_PATH_MUST_BE_ABSOLUTE")
    try:
        resolved = selected.resolve(strict=True)
        info = selected.lstat()
    except OSError:
        raise GateEvidenceError("DATABASE_UNAVAILABLE") from None
    if (
        not _regular_non_reparse_file(info)
        or os.path.normcase(str(resolved.parent)) != os.path.normcase(str(root))
        or selected.name == "operational-ledger.sqlite3"
    ):
        raise GateEvidenceError("DATABASE_PATH_UNSAFE")
    from telegram_courses.s9_operational_ledger import LedgerError, _verify_private_file

    try:
        _verify_private_file(selected)
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(str(selected) + suffix)
            try:
                sidecar_info = sidecar.lstat()
            except FileNotFoundError:
                continue
            if (
                not _regular_non_reparse_file(sidecar_info)
            ):
                raise LedgerError("DATABASE_SIDECAR_UNSAFE")
            _verify_private_file(sidecar)
    except (LedgerError, OSError):
        raise GateEvidenceError("DATABASE_NOT_PRIVATE") from None
    return resolved


def read_sqlite_ids(
    run_directory: str | Path,
    database_path: str | Path,
    table: str,
) -> set[str]:
    if table not in {"scan_runs", "catalog_runs"}:
        raise GateEvidenceError("DATABASE_TABLE_INVALID")
    root = _run_root(run_directory)
    selected = Path(database_path)
    try:
        selected.lstat()
    except FileNotFoundError:
        return set()
    except OSError:
        raise GateEvidenceError("DATABASE_ID_SNAPSHOT_FAILED") from None
    path = _dataset_path(root, selected)
    try:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        db.execute("PRAGMA query_only=ON")
        tables = {
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if table not in tables:
            return set()
        return {str(row[0]) for row in db.execute(f"SELECT id FROM {table}").fetchall()}
    except (sqlite3.Error, OSError, ValueError):
        raise GateEvidenceError("DATABASE_ID_SNAPSHOT_FAILED") from None
    finally:
        if "db" in locals():
            db.close()


def _readonly_database(path: Path) -> sqlite3.Connection:
    try:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA query_only").fetchone()[0] != 1:
            db.close()
            raise GateEvidenceError("DATABASE_NOT_READONLY")
        integrity = db.execute("PRAGMA integrity_check").fetchall()
        if len(integrity) != 1 or integrity[0][0] != "ok":
            db.close()
            raise GateEvidenceError("DATABASE_INTEGRITY_FAILED")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            db.close()
            raise GateEvidenceError("DATABASE_FOREIGN_KEY_FAILED")
        return db
    except GateEvidenceError:
        raise
    except (sqlite3.Error, OSError, ValueError):
        raise GateEvidenceError("DATABASE_RECONCILIATION_FAILED") from None


def _database_sha256(path: Path) -> str:
    """Hash the quiescent SQLite snapshot, including committed WAL frames.

    The SHM file is a transient coordination/cache artifact. Opening a reader
    may change it without changing database content, so it is not part of the
    snapshot digest. Callers use this at stage boundaries after the writer
    process tree has been contained.
    """
    digest = hashlib.sha256()
    family: dict[Path, os.stat_result] = {}
    for candidate in (
        path,
        Path(str(path) + "-wal"),
        Path(str(path) + "-shm"),
        Path(str(path) + "-journal"),
    ):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            if candidate == path:
                raise GateEvidenceError("DATABASE_HASH_FAILED") from None
            continue
        except OSError:
            raise GateEvidenceError("DATABASE_HASH_FAILED") from None
        if not _regular_non_reparse_file(info):
            raise GateEvidenceError("DATABASE_HASH_FAILED")
        family[candidate] = info

    for candidate in (path, Path(str(path) + "-wal")):
        info = family.get(candidate)
        if info is None:
            continue
        if candidate != path and info.st_size == 0:
            continue
        try:
            current_info = candidate.lstat()
            if not _regular_non_reparse_file(current_info):
                raise GateEvidenceError("DATABASE_HASH_FAILED")
            if candidate != path and current_info.st_size == 0:
                continue
            digest.update(candidate.name.encode("utf-8"))
            with candidate.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        except GateEvidenceError:
            raise
        except OSError:
            raise GateEvidenceError("DATABASE_HASH_FAILED") from None
    return digest.hexdigest()


def _channel_messages_sha256(db: sqlite3.Connection, channel_id: int) -> tuple[int, str]:
    columns = [str(row[1]) for row in db.execute("PRAGMA table_info(messages)").fetchall()]
    if not columns or "channel_id" not in columns or "telegram_message_id" not in columns:
        raise GateEvidenceError("MESSAGE_SCHEMA_INVALID")
    digest = hashlib.sha256(canonical_bytes(columns))
    count = 0
    try:
        rows = db.execute(
            "SELECT * FROM messages WHERE channel_id=? ORDER BY telegram_message_id",
            (channel_id,),
        )
        for row in rows:
            encoded_row = []
            for value in row:
                if value is None:
                    encoded_row.append(["null", None])
                elif type(value) is int:
                    encoded_row.append(["integer", value])
                elif type(value) is float:
                    encoded_row.append(["real", value.hex()])
                elif type(value) is str:
                    encoded_row.append(["text", value])
                elif type(value) is bytes:
                    encoded_row.append(["blob", value.hex()])
                else:
                    raise GateEvidenceError("MESSAGE_VALUE_TYPE_INVALID")
            digest.update(b"\n")
            digest.update(canonical_bytes(encoded_row))
            count += 1
    except sqlite3.Error:
        raise GateEvidenceError("MESSAGE_SNAPSHOT_FAILED") from None
    return count, digest.hexdigest()


def persist_gate_receipt(
    run_directory: str | Path,
    ledger: Any,
    payload: Mapping[str, object],
    *,
    before_rename_checkpoint: Callable[[], object] | None = None,
) -> tuple[Path, str]:
    gate = payload.get("gate")
    run_id = payload.get("run_id")
    if gate not in GATE_RECEIPTS or type(run_id) is not str:
        raise GateEvidenceError("GATE_RECEIPT_IDENTITY_INVALID")
    root = _run_root(run_directory)
    canonical = dict(payload)
    if gate == "G7":
        sync_index = canonical.get("sync_index", 1)
        filename = _g7_receipt_filename(sync_index) if type(sync_index) is int else ""
        if not filename:
            raise GateEvidenceError("G7_SYNC_INDEX_INVALID")
        canonical["sync_index"] = sync_index
        canonical["receipt_file"] = filename
        path = root / filename
    else:
        path = root / GATE_RECEIPTS[str(gate)]
    encoded = (canonical_bytes(canonical) + b"\n")
    receipt_sha256 = sha256_bytes(encoded)
    event_ids = {
        name: hashlib.sha256(
            f"{run_id}:{gate}:{receipt_sha256}:{name}".encode("ascii")
        ).hexdigest()[:32]
        for name in ("prepared", "persisted", "finished")
    }
    origin = canonical.get("evidence_origin")
    if origin not in {"REAL_CONTRACTUAL", "SYNTHETIC", "OFFLINE_SYNTHETIC", "HUMAN_INTERACTIVE"}:
        origin = "UNKNOWN"

    def event(name: str, event_type: str, details: dict[str, object]) -> None:
        if origin not in {"REAL_CONTRACTUAL", "SYNTHETIC", "OFFLINE_SYNTHETIC", "HUMAN_INTERACTIVE"}:
            details.pop("evidence_origin", None)
        ledger.record_critical_event(
            event_type, details=details, event_id=event_ids[name],
        )

    def prepare_receipt(_raw: bytes) -> None:
        event(
            "prepared", "RECEIPT_PREPARED",
            {"gate": gate, "evidence_origin": origin, "receipt_sha256": receipt_sha256},
        )
        if (
            before_rename_checkpoint is not None
            and canonical.get("status") in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        ):
            before_rename_checkpoint()

    from telegram_courses.s9_supervisor import _write_no_overwrite_json

    _write_no_overwrite_json(
        path,
        canonical,
        before_rename=prepare_receipt,
        after_rename=lambda _raw: event(
            "persisted", "RECEIPT_PERSISTED",
            {"gate": gate, "evidence_origin": origin, "receipt_sha256": receipt_sha256},
        ),
    )
    status = "COMPLETED" if canonical.get("status") in {
        "PASS", "OFFLINE_SYNTHETIC_PASS", "PARTIAL",
    } else "BLOCKED"
    result = str(canonical.get("status"))
    real_status = (
        "REAL_CONTRACTUAL_PASS"
        if result == "PASS" and origin == "REAL_CONTRACTUAL"
        else "NOT_ASSESSED" if gate == "G0" else "REAL_EVIDENCE_PENDING"
    )
    offline_result = "OFFLINE_SYNTHETIC_PASS" if result == "OFFLINE_SYNTHETIC_PASS" else "UNKNOWN"
    event("finished", "GATE_FINISHED", {
        "gate": gate,
        "status": status,
        "result": result,
        **({"evidence_origin": origin} if origin != "UNKNOWN" else {}),
        "offline_result": offline_result,
        "real_evidence_status": real_status,
        "receipt_sha256": receipt_sha256,
    })
    return path, receipt_sha256


def persist_g5_queue_receipt(
    run_directory: str | Path,
    ledger: Any,
    payload: Mapping[str, object],
    *,
    before_rename_checkpoint: Callable[[], object] | None = None,
) -> tuple[Path, str]:
    """Persist one wrapper-produced, no-overwrite S9 queue-pass receipt."""
    canonical = dict(payload)
    profile = canonical.get("profile")
    pass_index = canonical.get("pass_index")
    if (
        canonical.get("schema") != "telegram-courses-s9-g5-queue-receipt-v1"
        or canonical.get("version") != 1
        or canonical.get("gate") != "G5"
        or type(canonical.get("run_id")) is not str
        or profile not in {"F", "M"}
        or type(pass_index) is not int or pass_index not in {1, 2}
        or canonical.get("stage") != ("queue_f" if profile == "F" else "queue_m")
        or canonical.get("status", "") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        or canonical.get("evidence_origin") not in {"REAL_CONTRACTUAL", "SYNTHETIC"}
        or (canonical.get("status") == "PASS")
        != (canonical.get("evidence_origin") == "REAL_CONTRACTUAL")
        or (canonical.get("measurement_source") == "GATEWAY_RESPONSE")
        != (canonical.get("evidence_origin") == "REAL_CONTRACTUAL")
    ):
        raise GateEvidenceError("G5_QUEUE_RECEIPT_CONTENT_INVALID")
    root = _run_root(run_directory)
    path = root / g5_queue_receipt_filename(str(profile), pass_index)
    encoded = canonical_bytes(canonical) + b"\n"
    receipt_sha256 = sha256_bytes(encoded)
    event_ids = {
        name: hashlib.sha256(
            f"{canonical['run_id']}:G5:{profile}:{pass_index}:{receipt_sha256}:{name}".encode("ascii")
        ).hexdigest()[:32]
        for name in ("prepared", "persisted", "finished")
    }

    def event(name: str, event_type: str, details: dict[str, object]) -> None:
        ledger.record_critical_event(
            event_type, details=details, event_id=event_ids[name],
        )

    def prepare_receipt(_raw: bytes) -> None:
        event(
            "prepared", "RECEIPT_PREPARED",
            {
                "gate": "G5", "profile": profile, "stage": canonical["stage"],
                "evidence_origin": canonical["evidence_origin"],
                "receipt_sha256": receipt_sha256,
            },
        )
        if before_rename_checkpoint is not None:
            before_rename_checkpoint()

    from telegram_courses.s9_supervisor import _write_no_overwrite_json

    _write_no_overwrite_json(
        path,
        canonical,
        before_rename=prepare_receipt,
        after_rename=lambda _raw: event(
            "persisted", "RECEIPT_PERSISTED",
            {
                "gate": "G5", "profile": profile, "stage": canonical["stage"],
                "evidence_origin": canonical["evidence_origin"],
                "receipt_sha256": receipt_sha256,
            },
        ),
    )
    event("finished", "GATE_FINISHED", {
        "gate": "G5", "status": "COMPLETED",
        "result": canonical["status"],
        "evidence_origin": canonical["evidence_origin"],
        "offline_result": (
            "OFFLINE_SYNTHETIC_PASS"
            if canonical["status"] == "OFFLINE_SYNTHETIC_PASS" else "UNKNOWN"
        ),
        "real_evidence_status": (
            "REAL_CONTRACTUAL_PASS"
            if canonical["status"] == "PASS" else "REAL_EVIDENCE_PENDING"
        ),
        "profile": profile, "stage": canonical["stage"],
        "receipt_sha256": receipt_sha256,
        "observed_bytes": canonical["observed_bytes"],
    })
    return path, receipt_sha256


def read_validated_g5_queue_receipt(
    run_directory: str | Path,
    ledger_snapshot: Mapping[str, object],
    *,
    run_id: str,
    manifest_sha256: str,
    profile: str,
    pass_index: int,
) -> dict[str, object]:
    """Reopen a queue pass and its supervisor/ledger attestations."""
    if profile not in {"F", "M"} or type(pass_index) is not int or pass_index not in {1, 2}:
        raise GateEvidenceError("G5_QUEUE_IDENTITY_INVALID")
    root = _run_root(run_directory)
    path = _private_run_file(root, g5_queue_receipt_filename(profile, pass_index))
    raw = path.read_bytes()
    receipt_sha256 = sha256_bytes(raw)
    try:
        receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except GateEvidenceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise GateEvidenceError("G5_QUEUE_RECEIPT_JSON_INVALID") from None
    origin = receipt.get("evidence_origin") if type(receipt) is dict else None
    expected_status = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
    stage = "queue_f" if profile == "F" else "queue_m"
    if (
        type(receipt) is not dict
        or receipt.get("schema") != "telegram-courses-s9-g5-queue-receipt-v1"
        or receipt.get("version") != 1
        or receipt.get("gate") != "G5"
        or receipt.get("run_id") != run_id
        or receipt.get("manifest_sha256") != manifest_sha256
        or receipt.get("profile") != profile
        or receipt.get("pass_index") != pass_index
        or receipt.get("stage") != stage
        or receipt.get("status") != expected_status
        or origin not in {"REAL_CONTRACTUAL", "SYNTHETIC"}
        or receipt.get("measurement_source") != (
            "GATEWAY_RESPONSE" if origin == "REAL_CONTRACTUAL" else "SYNTHETIC_TEST"
        )
        or type(receipt.get("channel_id")) is not int
        or receipt.get("database_file") != Path(str(receipt.get("database_file"))).name
        or type(receipt.get("download_root")) is not str
        or Path(str(receipt.get("download_root"))).name != receipt.get("download_root")
        or receipt.get("supervisor_receipt_file")
        != g5_supervisor_receipt_filename(profile, pass_index)
        or type(receipt.get("supervisor_receipt_sha256")) is not str
        or not _HASH.fullmatch(str(receipt.get("supervisor_receipt_sha256")))
        or type(receipt.get("observed_bytes")) is not int
        or receipt["observed_bytes"] < 0
        or type(receipt.get("max_media_items")) is not int
        or receipt["max_media_items"] < 1
        or type(receipt.get("max_transfer_bytes")) is not int
        or receipt["max_transfer_bytes"] < 1
        or receipt.get("workers") != 1
        or receipt.get("attempts_per_media") != 1
        or pass_index == 2
        and (
            receipt.get("max_media_items") < 1
            or receipt.get("max_transfer_bytes") != 1
            or receipt.get("observed_bytes") != 0
            or receipt.get("all_items_already_valid") is not True
        )
    ):
        raise GateEvidenceError("G5_QUEUE_RECEIPT_CONTENT_INVALID")
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list or audit.get("quarantined") is not False:
        raise GateEvidenceError("G5_QUEUE_AUDIT_UNAVAILABLE")
    expected_ids = {
        name: hashlib.sha256(
            f"{run_id}:G5:{profile}:{pass_index}:{receipt_sha256}:{name}".encode("ascii")
        ).hexdigest()[:32]
        for name in ("prepared", "persisted", "finished")
    }
    matched: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {
        name: [] for name in expected_ids
    }
    state_updates = []
    for event in events:
        if type(event) is not dict:
            continue
        try:
            details = json.loads(str(event.get("details_json")))
        except (TypeError, ValueError):
            continue
        if type(details) is not dict or details.get("gate") != "G5":
            continue
        if event.get("event_type") in {"GATE_STATE_UPDATED", "RUN_TERMINAL"}:
            state_updates.append((event, details))
        if details.get("receipt_sha256") != receipt_sha256:
            continue
        if event.get("event_type") == "RECEIPT_PREPARED":
            matched["prepared"].append((event, details))
        elif event.get("event_type") == "RECEIPT_PERSISTED":
            matched["persisted"].append((event, details))
        elif event.get("event_type") == "GATE_FINISHED":
            matched["finished"].append((event, details))
    if any(len(matched[name]) != 1 for name in matched):
        raise GateEvidenceError("G5_QUEUE_RECEIPT_AUDIT_INVALID")
    finished_event, finished_details = matched["finished"][0]
    if any(
        details.get("profile") != profile
        or details.get("stage") != stage
        or details.get("evidence_origin") != origin
        or item.get("event_id") != expected_ids[name]
        for name in ("prepared", "persisted", "finished")
        for item, details in matched[name]
    ) or (
        finished_event.get("event_id") != expected_ids["finished"]
        or finished_details.get("result") != expected_status
        or finished_details.get("status") != "COMPLETED"
        or not any(
            event.get("event_type") == "GATE_STATE_UPDATED"
            and event.get("sequence", 0) > finished_event.get("sequence", 0)
            and details.get("result") == expected_status
            and details.get("status") == "RUNNING"
            and details.get("observed_bytes") == receipt.get("observed_bytes")
            for event, details in state_updates
        )
    ):
        raise GateEvidenceError("G5_QUEUE_RECEIPT_ATTESTATION_INVALID")
    try:
        from telegram_courses.s9_supervisor_cli import (
            OfflineRunnerError,
            _read_supervisor_receipt_evidence,
        )

        supervisor_hash = _read_supervisor_receipt_evidence(
            _private_run_file(root, str(receipt["supervisor_receipt_file"])),
            dict(ledger_snapshot), run_id=run_id, stage=stage,
            expected_exit_code=0,
        )
    except (OfflineRunnerError, OSError, ValueError, TypeError):
        raise GateEvidenceError("G5_SUPERVISOR_RECEIPT_INVALID") from None
    if supervisor_hash != receipt.get("supervisor_receipt_sha256"):
        raise GateEvidenceError("G5_SUPERVISOR_RECEIPT_HASH_MISMATCH")
    return receipt


def read_validated_gate_receipt(
    run_directory: str | Path,
    ledger_snapshot: Mapping[str, object],
    gate: str,
    *,
    run_id: str,
    manifest_sha256: str,
    receipt_index: int | None = None,
    reopen_g6_snapshot: bool = True,
) -> dict[str, object]:
    if gate not in GATE_RECEIPTS:
        raise GateEvidenceError("GATE_RECEIPT_GATE_INVALID")
    root = _run_root(run_directory)
    path = _private_run_file(
        root, _gate_receipt_path(root, gate, receipt_index=receipt_index).name,
    )
    raw = path.read_bytes()
    receipt_sha256 = sha256_bytes(raw)
    try:
        receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except GateEvidenceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise GateEvidenceError("GATE_RECEIPT_JSON_INVALID") from None
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list or audit.get("quarantined") is not False:
        raise GateEvidenceError("GATE_RECEIPT_AUDIT_UNAVAILABLE")
    finished = []
    persisted = []
    prepared = []
    state_updates = []
    for item in events:
        if type(item) is not dict:
            continue
        try:
            details = json.loads(str(item.get("details_json")))
        except (TypeError, ValueError):
            continue
        if type(details) is not dict or details.get("gate") != gate:
            continue
        if item.get("event_type") in {"GATE_STATE_UPDATED", "RUN_TERMINAL"}:
            state_updates.append((item, details))
        if details.get("receipt_sha256") != receipt_sha256:
            continue
        if item.get("event_type") == "RECEIPT_PREPARED":
            prepared.append((item, details))
        elif item.get("event_type") == "GATE_FINISHED":
            finished.append((item, details))
        elif item.get("event_type") == "RECEIPT_PERSISTED":
            persisted.append((item, details))
    valid_status = (
        type(receipt) is dict
        and (
            receipt.get("status") == "PASS"
            and receipt.get("evidence_origin") == "REAL_CONTRACTUAL"
            or receipt.get("status") == "OFFLINE_SYNTHETIC_PASS"
            and receipt.get("evidence_origin") == "SYNTHETIC"
            or gate == "G0"
            and receipt.get("status") == "PASS"
            and receipt.get("evidence_origin") == "HUMAN_INTERACTIVE"
            or gate == "G7"
            and receipt.get("status") == "PARTIAL"
            and receipt.get("evidence_origin") in {"REAL_CONTRACTUAL", "SYNTHETIC"}
            or gate == "G6"
            and receipt.get("status") == "PARTIAL"
            and receipt.get("evidence_origin") in {"REAL_CONTRACTUAL", "SYNTHETIC"}
        )
    )
    expected_ids = {
        name: hashlib.sha256(
            f"{run_id}:{gate}:{receipt_sha256}:{name}".encode("ascii")
        ).hexdigest()[:32]
        for name in ("prepared", "persisted", "finished")
    }
    finished_event, finished_details = finished[0] if len(finished) == 1 else ({}, {})
    persisted_event, persisted_details = persisted[0] if len(persisted) == 1 else ({}, {})
    prepared_event, prepared_details = prepared[0] if len(prepared) == 1 else ({}, {})
    expected_state_event = (
        "RUN_TERMINAL" if type(receipt) is dict and receipt.get("status") == "PARTIAL"
        else "GATE_STATE_UPDATED"
    )
    expected_run_status = (
        "PARTIAL" if expected_state_event == "RUN_TERMINAL" else "RUNNING"
    )
    if (
        type(receipt) is not dict
        or receipt.get("gate") != gate
        or receipt.get("run_id") != run_id
        or receipt.get("manifest_sha256") != manifest_sha256
        or not valid_status
        or len(prepared) != 1 or len(persisted) != 1 or len(finished) != 1
        or prepared_event.get("event_id") != expected_ids["prepared"]
        or persisted_event.get("event_id") != expected_ids["persisted"]
        or finished_event.get("event_id") != expected_ids["finished"]
        or prepared_details.get("evidence_origin") != receipt.get("evidence_origin")
        or persisted_details.get("evidence_origin") != receipt.get("evidence_origin")
        or finished_details.get("status") != "COMPLETED"
        or finished_details.get("result") != receipt.get("status")
        or finished_details.get("evidence_origin") != receipt.get("evidence_origin")
        or not any(
            details.get("result") == receipt.get("status")
            and details.get("status") == expected_run_status
            and item.get("event_type") == expected_state_event
            and type(item.get("sequence")) is int
            and type(finished_event.get("sequence")) is int
            and item["sequence"] > finished_event["sequence"]
            for item, details in state_updates
        )
    ):
        raise GateEvidenceError("GATE_RECEIPT_NOT_ATTESTED")
    if gate != "G0":
        expected_supervisor_files = {
            "G1": "g1-discovery-supervisor-receipt.json",
            "G2": "g2-scan-supervisor-receipt.json",
            "G3": "g3-catalog-supervisor-receipt.json",
            "G7": "g7-scan-supervisor-receipt.json",
        }
        if gate not in expected_supervisor_files and gate != "G6":
            raise GateEvidenceError("GATE_SUPERVISOR_PROVENANCE_INVALID")
        if gate in expected_supervisor_files:
            supervisor_file = (
                _g7_supervisor_receipt_filename(receipt.get("sync_index"))
                if gate == "G7" else expected_supervisor_files[gate]
            )
            if (
                type(receipt.get("supervisor_receipt_sha256")) is not str
                or not _HASH.fullmatch(str(receipt.get("supervisor_receipt_sha256")))
                or receipt.get("supervisor_stage") != {
                    "G1": "discovery", "G2": "scan", "G3": "catalog", "G7": "scan",
                }[gate]
                or receipt.get("supervisor_receipt_file") != supervisor_file
            ):
                raise GateEvidenceError("GATE_SUPERVISOR_PROVENANCE_INVALID")
            supervisor_path = _private_run_file(root, supervisor_file)
            try:
                from telegram_courses.s9_supervisor_cli import (
                    OfflineRunnerError,
                    _read_supervisor_receipt_evidence,
                )

                supervisor_hash = _read_supervisor_receipt_evidence(
                    supervisor_path, dict(ledger_snapshot), run_id=run_id,
                    stage=str(receipt["supervisor_stage"]),
                )
            except (OfflineRunnerError, OSError, ValueError, TypeError):
                raise GateEvidenceError("GATE_SUPERVISOR_RECEIPT_INVALID") from None
            if supervisor_hash != receipt.get("supervisor_receipt_sha256"):
                raise GateEvidenceError("GATE_SUPERVISOR_RECEIPT_HASH_MISMATCH")
    if gate == "G0":
        manifest, actual_manifest_sha256, actual_scope_sha256 = load_approved_manifest(root)
        audit_events = events
        request_id = receipt.get("request_event_id")
        consumed_id = receipt.get("consumed_event_id")
        request_events = [
            item for item in audit_events if item.get("event_id") == request_id
            and item.get("event_type") == "G0_CONFIRMATION_REQUESTED"
        ]
        consumed_events = [
            item for item in audit_events if item.get("event_id") == consumed_id
            and item.get("event_type") == "G0_CONFIRMATION_CONSUMED"
        ]
        consumed_all = [
            item for item in audit_events
            if item.get("event_type") == "G0_CONFIRMATION_CONSUMED"
        ]
        blocked_all = [
            item for item in audit_events
            if item.get("event_type") == "G0_CONFIRMATION_BLOCKED"
        ]
        try:
            request_details = json.loads(request_events[0]["details_json"]) if len(request_events) == 1 else None
            consumed_details = json.loads(consumed_events[0]["details_json"]) if len(consumed_events) == 1 else None
        except (KeyError, TypeError, ValueError):
            request_details = consumed_details = None
        issued_ns = receipt.get("issued_ns")
        expires_ns = receipt.get("expires_ns")
        consumed_ns = receipt.get("consumed_ns")
        timeout_valid = (
            type(issued_ns) is int and type(expires_ns) is int
            and type(consumed_ns) is int
            and 0 < expires_ns - issued_ns <= 60_000_000_000
            and issued_ns <= consumed_ns <= expires_ns
        )
        source_origin_valid = (
            receipt.get("status") == "PASS"
            and receipt.get("evidence_origin") == "HUMAN_INTERACTIVE"
            and receipt.get("confirmation_source") == "INTERACTIVE_TTY"
            or receipt.get("status") == "OFFLINE_SYNTHETIC_PASS"
            and receipt.get("evidence_origin") == "SYNTHETIC"
            and receipt.get("confirmation_source") == "SYNTHETIC_TEST"
        )
        shared_confirmation = {
            "gate": "G0",
            "channel_ref": sha256_bytes(str(receipt.get("channel_id")).encode("utf-8")),
            "manifest_sha256": manifest_sha256,
            "scope_sha256": actual_scope_sha256,
            "nonce_sha256": receipt.get("nonce_sha256"),
            "confirmation_source": receipt.get("confirmation_source"),
            "issued_ns": issued_ns,
            "expires_ns": expires_ns,
        }
        if (
            actual_manifest_sha256 != manifest_sha256
            or receipt.get("scope_sha256") != actual_scope_sha256
            or receipt.get("channel_id") != manifest.get("channel_id")
            or receipt.get("channel_alias") != manifest.get("channel_alias")
            or receipt.get("authorized_scope") != manifest.get("scope")
            or receipt.get("authorized_limits") != {
                "max_per_scan": MAX_MESSAGES_PER_SCAN,
                "max_total_scans": MAX_SCAN_INVOCATIONS,
                "max_total_observations": MAX_SCAN_OBSERVATIONS,
                "incremental_window": INCREMENTAL_WINDOW,
            }
            or not isinstance(receipt.get("nonce_sha256"), str)
            or not _HASH.fullmatch(str(receipt.get("nonce_sha256")))
            or not source_origin_valid or not timeout_valid
            or len(request_events) != 1 or len(consumed_events) != 1
            or len(consumed_all) != 1
            or bool(blocked_all)
            or request_details != shared_confirmation
            or consumed_details != shared_confirmation | {"consumed_ns": consumed_ns}
            or type(request_events[0].get("sequence")) is not int
            or type(consumed_events[0].get("sequence")) is not int
            or consumed_events[0]["sequence"] <= request_events[0]["sequence"]
        ):
            raise GateEvidenceError("G0_CONFIRMATION_RECEIPT_INVALID")
        return receipt
    if gate == "G1":
        worker_path = _private_run_file(root, G1_WORKER_RECEIPT)
        try:
            worker_raw = worker_path.read_bytes()
            worker_evidence = json.loads(
                worker_raw.decode("utf-8"), object_pairs_hook=_unique_object,
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            raise GateEvidenceError("G1_WORKER_EVIDENCE_INVALID") from None
        worker_payload = {
            key: value for key, value in receipt.items()
            if key not in {
                "supervisor_stage", "supervisor_receipt_file",
                "supervisor_receipt_sha256", "worker_evidence_sha256",
            }
        }
        if (
            sha256_bytes(worker_raw) != receipt.get("worker_evidence_sha256")
            or worker_evidence != worker_payload
        ):
            raise GateEvidenceError("G1_WORKER_EVIDENCE_MISMATCH")
        manifest, actual_manifest_sha256, _scope_sha256 = load_approved_manifest(root)
        if actual_manifest_sha256 != manifest_sha256:
            raise GateEvidenceError("G1_MANIFEST_CHANGED")
        status, _reason = validate_g1_evidence(
            receipt, run_id=run_id, manifest=manifest,
            manifest_sha256=manifest_sha256, require_supervisor=True,
        )
        if status != receipt.get("status"):
            raise GateEvidenceError("G1_RECEIPT_CONTENT_INVALID")
    elif gate == "G2":
        if (
            type(receipt.get("channel_id")) is not int
            or receipt.get("channel_id", 0) > -1_000_000_000_000
            or type(receipt.get("database_file")) is not str
            or Path(str(receipt.get("database_file"))).name != receipt.get("database_file")
            or type(receipt.get("database_sha256")) is not str
            or not _HASH.fullmatch(str(receipt.get("database_sha256")))
            or type(receipt.get("persisted_messages_sha256")) is not str
            or not _HASH.fullmatch(str(receipt.get("persisted_messages_sha256")))
            or type(receipt.get("scan_run_id")) is not str
            or type(receipt.get("ledger_scan_id")) is not str
            or type(receipt.get("max_messages")) is not int
            or not 1 <= receipt["max_messages"] <= MAX_MESSAGES_PER_SCAN
            or type(receipt.get("observed_messages")) is not int
            or not 0 <= receipt["observed_messages"] <= receipt["max_messages"]
            or type(receipt.get("total_scan_invocations")) is not int
            or not 1 <= receipt["total_scan_invocations"] <= MAX_SCAN_INVOCATIONS
            or type(receipt.get("total_scan_observations")) is not int
            or not 0 <= receipt["total_scan_observations"] <= MAX_SCAN_OBSERVATIONS
            or receipt["total_scan_observations"] < receipt["observed_messages"]
            or type(receipt.get("persisted_message_count")) is not int
            or receipt["persisted_message_count"] < 0
            or type(receipt.get("application_exit_code")) is not int
            or receipt.get("application_exit_code") not in {0, 4}
            or type(receipt.get("external_exit_code")) is not int
            or type(receipt.get("external_exit_code")) is not int
            or receipt.get("external_exit_code") != receipt.get("application_exit_code")
            or receipt.get("scan_status") not in {"COMPLETE", "PARTIAL"}
            or receipt.get("stop_reason") not in {None, "MESSAGE_LIMIT"}
        ):
            raise GateEvidenceError("G2_RECEIPT_CONTENT_INVALID")
        manifest, actual_manifest_sha256, _scope_sha256 = load_approved_manifest(root)
        if (
            actual_manifest_sha256 != manifest_sha256
            or receipt.get("channel_id") != manifest.get("channel_id")
        ):
            raise GateEvidenceError("G2_MANIFEST_OR_CHANNEL_MISMATCH")
        supervisor_payload = json.loads(
            _private_run_file(root, "g2-scan-supervisor-receipt.json").read_text("utf-8"),
            object_pairs_hook=_unique_object,
        )
        external_exit_code = supervisor_payload.get("external_exit_code")
        expected_message_limit = external_exit_code == 4
        if (
            type(external_exit_code) is not int
            or external_exit_code != receipt.get("application_exit_code")
            or external_exit_code != receipt.get("external_exit_code")
            or supervisor_payload.get("run_id") != run_id
            or supervisor_payload.get("ledger_run_id") != run_id
            or supervisor_payload.get("message_limit_exit_allowed") is not True
            or supervisor_payload.get("result") != "COMPLETED"
            or supervisor_payload.get("reason") != (
                "EXPECTED_MESSAGE_LIMIT_EXIT" if expected_message_limit else "PROCESS_EXITED"
            )
        ):
            raise GateEvidenceError("G2_APPLICATION_EXTERNAL_EXIT_MISMATCH")
        scan_status = "PARTIAL" if expected_message_limit else "COMPLETE"
        stop_reason = "MESSAGE_LIMIT" if expected_message_limit else None
        if (
            receipt.get("scan_status") != scan_status
            or receipt.get("stop_reason") != stop_reason
            or expected_message_limit
            and receipt.get("observed_messages") != receipt.get("max_messages")
        ):
            raise GateEvidenceError("G2_SCAN_TERMINAL_STATE_INVALID")
        ledger_scans = _ledger_scan_rows(ledger_snapshot)
        matched_scans = [
            row for row in ledger_scans
            if row.get("scan_id") == receipt.get("ledger_scan_id")
        ]
        if (
            len(matched_scans) != 1
            or matched_scans[0].get("state") != "OBSERVED"
            or matched_scans[0].get("incremental") != 0
            or matched_scans[0].get("max_messages") != receipt.get("max_messages")
            or matched_scans[0].get("observed") != receipt.get("observed_messages")
            or len(ledger_scans) < receipt.get("total_scan_invocations")
            or sum(
                int(row.get("observed", 0)) for row in ledger_scans
                if type(row.get("observed")) is int
            ) < receipt.get("total_scan_observations")
            or len(ledger_scans) > MAX_SCAN_INVOCATIONS
            or sum(
                int(row.get("observed", 0)) for row in ledger_scans
                if type(row.get("observed")) is int
            ) > MAX_SCAN_OBSERVATIONS
        ):
            raise GateEvidenceError("G2_LEDGER_SCAN_DIVERGENCE")
        database_path = _dataset_path(root, root / str(receipt.get("database_file")))
        db = _readonly_database(database_path)
        try:
            tables = {
                str(row[0]) for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not {"scan_runs", "channels", "messages"}.issubset(tables):
                raise GateEvidenceError("G2_DATABASE_SCHEMA_INVALID")
            scan = db.execute(
                "SELECT id,channel_id,status,messages_seen,stop_reason,sync_mode,"
                "sync_max_messages,sync_reconcile_window FROM scan_runs WHERE id=?",
                (receipt.get("scan_run_id"),),
            ).fetchone()
            if (
                scan is None
                or scan[1] != manifest.get("channel_id")
                or scan[2] != scan_status
                or scan[3] != receipt.get("observed_messages")
                or scan[4] != stop_reason
                or scan[5] != "FULL"
                or scan[6] is not None
                or type(scan[7]) is not int or scan[7] != 0
                or db.execute(
                    "SELECT 1 FROM channels WHERE telegram_chat_id=?",
                    (manifest.get("channel_id"),),
                ).fetchone() is None
            ):
                raise GateEvidenceError("G2_DATABASE_SCAN_DIVERGENCE")
        finally:
            db.close()
    elif gate == "G3":
        hierarchy = receipt.get("hierarchy")
        if (
            type(receipt.get("channel_id")) is not int
            or receipt.get("channel_id", 0) > -1_000_000_000_000
            or type(receipt.get("database_sha256")) is not str
            or not _HASH.fullmatch(str(receipt.get("database_sha256")))
            or type(receipt.get("catalog_run_id")) is not str
            or type(receipt.get("scan_run_id")) is not str
            or type(hierarchy) is not dict
            or set(hierarchy) != {"TRACK", "COURSE", "MODULE"}
            or any(type(value) is not int or value < 0 for value in hierarchy.values())
            or hierarchy.get("TRACK", 0) < 1
            or hierarchy.get("COURSE", 0) < 2
            or hierarchy.get("MODULE", 0) < 2
            or type(receipt.get("unresolved_count")) is not int
            or receipt["unresolved_count"] < 0
        ):
            raise GateEvidenceError("G3_RECEIPT_CONTENT_INVALID")
    elif gate == "G6":
        strict_g6 = (
            receipt.get("status") in {"PASS", "PARTIAL"}
            or "g5_queue_receipts" in receipt
        )
        partial_without_m = receipt.get("status") == "PARTIAL"
        if (
            receipt.get("status") not in {"PASS", "OFFLINE_SYNTHETIC_PASS", "PARTIAL"}
            or receipt.get("evidence_origin") not in {"REAL_CONTRACTUAL", "SYNTHETIC"}
            or type(receipt.get("channel_id")) is not int
            or receipt.get("channel_id", 0) > -1_000_000_000_000
            or type(receipt.get("database_file")) is not str
            or Path(str(receipt.get("database_file"))).name != receipt.get("database_file")
            or type(receipt.get("database_sha256")) is not str
            or not _HASH.fullmatch(str(receipt.get("database_sha256")))
            or receipt.get("database_integrity") != "ok"
            or (receipt.get("status") == "PASS")
            != (receipt.get("evidence_origin") == "REAL_CONTRACTUAL")
            or receipt.get("status") == "OFFLINE_SYNTHETIC_PASS"
            and receipt.get("evidence_origin") != "SYNTHETIC"
            or partial_without_m and (
                receipt.get("reason") != "M_DATASET_UNAVAILABLE"
                or receipt.get("g5_m_status") != "BLOCKED_DATASET"
                or receipt.get("g6_aggregate_status") != "PARTIAL"
                or receipt.get("g7_real_eligible") is not False
                or receipt.get("nfr02_real") != "NOT_TESTED"
                or type(receipt.get("g5_m_eligible_count")) is not int
                or receipt.get("g5_m_eligible_count") != 0
                or type(receipt.get("g5_m_unresolved_count")) is not int
                or receipt.get("g5_m_unresolved_count") != 0
                or type(receipt.get("g5_m_inventory_sha256")) is not str
                or not _HASH.fullmatch(str(receipt.get("g5_m_inventory_sha256")))
                or receipt.get("real_evidence_status") != "REAL_EVIDENCE_PENDING"
            )
            or strict_g6 and (
                type(receipt.get("download_root")) is not str
                or Path(str(receipt.get("download_root"))).name != receipt.get("download_root")
                or type(receipt.get("download_snapshot_sha256")) is not str
                or not _HASH.fullmatch(str(receipt.get("download_snapshot_sha256")))
                or type(receipt.get("media_count")) is not int
                or receipt.get("media_count", 0) < 1
                or type(receipt.get("physical_bytes")) is not int
                or receipt.get("physical_bytes", -1) < 1
                or type(receipt.get("g5_queue_receipts")) is not list
                or len(receipt.get("g5_queue_receipts", []))
                != (2 if partial_without_m else 4)
            )
        ):
            raise GateEvidenceError("G6_RECEIPT_CONTENT_INVALID")
        manifest, actual_manifest_sha256, _scope_sha256 = load_approved_manifest(root)
        if (
            actual_manifest_sha256 != manifest_sha256
            or receipt.get("channel_id") != manifest.get("channel_id")
        ):
            raise GateEvidenceError("G6_MANIFEST_OR_CHANNEL_MISMATCH")
        if strict_g6 and reopen_g6_snapshot:
            _validate_g6_receipt_evidence(
                root, receipt, ledger_snapshot, run_id=run_id,
                manifest=manifest, manifest_sha256=manifest_sha256,
            )
    elif gate == "G7":
        sync_index = receipt.get("sync_index")
        if (
            type(receipt.get("channel_id")) is not int
            or receipt.get("channel_id", 0) > -1_000_000_000_000
            or type(receipt.get("database_file")) is not str
            or Path(str(receipt.get("database_file"))).name != receipt.get("database_file")
            or type(receipt.get("database_sha256_before")) is not str
            or not _HASH.fullmatch(str(receipt.get("database_sha256_before")))
            or type(receipt.get("database_sha256_after")) is not str
            or not _HASH.fullmatch(str(receipt.get("database_sha256_after")))
            or type(sync_index) is not int
            or sync_index not in {1, 2}
            or receipt.get("receipt_file") != _g7_receipt_filename(sync_index)
            or sync_index == 1
            and receipt.get("previous_g7_receipt_sha256") is not None
            or sync_index == 2
            and (
                type(receipt.get("previous_g7_receipt_sha256")) is not str
                or not _HASH.fullmatch(str(receipt.get("previous_g7_receipt_sha256")))
            )
            or type(receipt.get("g6_receipt_sha256")) is not str
            or not _HASH.fullmatch(str(receipt.get("g6_receipt_sha256")))
            or type(receipt.get("baseline_scan_run_id")) is not str
            or type(receipt.get("incremental_scan_run_id")) is not str
            or receipt.get("baseline_scan_run_id") == receipt.get("incremental_scan_run_id")
            or receipt.get("baseline_status") != "COMPLETE"
            or receipt.get("window_size") != INCREMENTAL_WINDOW
            or type(receipt.get("high_water_before")) is not int
            or type(receipt.get("high_water_after")) is not int
            or type(receipt.get("confirmed_high_water_after")) is not int
            or type(receipt.get("max_messages")) is not int
            or not 1 <= receipt.get("max_messages", 0) <= MAX_MESSAGES_PER_SCAN
            or type(receipt.get("observed_messages")) is not int
            or not 0 <= receipt.get("observed_messages", -1) <= receipt.get("max_messages", 0)
            or type(receipt.get("application_exit_code")) is not int
            or receipt.get("application_exit_code") not in {0, 4}
            or type(receipt.get("external_exit_code")) is not int
            or receipt.get("external_exit_code") != receipt.get("application_exit_code")
            or receipt.get("scan_status") not in {"COMPLETE", "PARTIAL"}
            or receipt.get("stop_reason") not in {None, "MESSAGE_LIMIT"}
            or receipt.get("deletions_inferred") is not False
            or receipt.get("database_integrity") != "ok"
            or receipt.get("status") == "PASS"
            and receipt.get("evidence_origin") != "REAL_CONTRACTUAL"
            or receipt.get("status") == "OFFLINE_SYNTHETIC_PASS"
            and receipt.get("evidence_origin") != "SYNTHETIC"
            or receipt.get("status") == "PARTIAL"
            and receipt.get("scan_status") != "PARTIAL"
            or receipt.get("status") in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
            and receipt.get("scan_status") != "COMPLETE"
        ):
            raise GateEvidenceError("G7_RECEIPT_CONTENT_INVALID")
        manifest, actual_manifest_sha256, _scope_sha256 = load_approved_manifest(root)
        if (
            actual_manifest_sha256 != manifest_sha256
            or receipt.get("channel_id") != manifest.get("channel_id")
        ):
            raise GateEvidenceError("G7_MANIFEST_OR_CHANNEL_MISMATCH")
        supervisor_file = _g7_supervisor_receipt_filename(sync_index)
        if receipt.get("supervisor_receipt_file") != supervisor_file:
            raise GateEvidenceError("G7_SUPERVISOR_RECEIPT_IDENTITY_INVALID")
        supervisor_payload = json.loads(
            _private_run_file(root, supervisor_file).read_text("utf-8"),
            object_pairs_hook=_unique_object,
        )
        external_exit_code = supervisor_payload.get("external_exit_code")
        message_limit = external_exit_code == 4
        if (
            type(external_exit_code) is not int
            or external_exit_code != receipt.get("application_exit_code")
            or external_exit_code != receipt.get("external_exit_code")
            or supervisor_payload.get("run_id") != run_id
            or supervisor_payload.get("ledger_run_id") != run_id
            or supervisor_payload.get("message_limit_exit_allowed") is not True
            or supervisor_payload.get("result") != "COMPLETED"
            or supervisor_payload.get("reason") != (
                "EXPECTED_MESSAGE_LIMIT_EXIT" if message_limit else "PROCESS_EXITED"
            )
        ):
            raise GateEvidenceError("G7_APPLICATION_EXTERNAL_EXIT_MISMATCH")
        expected_status = "PARTIAL" if message_limit else "COMPLETE"
        expected_stop = "MESSAGE_LIMIT" if message_limit else None
        if (
            receipt.get("scan_status") != expected_status
            or receipt.get("stop_reason") != expected_stop
            or message_limit
            and receipt.get("observed_messages") != receipt.get("max_messages")
        ):
            raise GateEvidenceError("G7_SCAN_TERMINAL_STATE_INVALID")
        g6 = read_validated_gate_receipt(
            root, ledger_snapshot, "G6", run_id=run_id,
            manifest_sha256=manifest_sha256,
            reopen_g6_snapshot=reopen_g6_snapshot,
        )
        if (
            g6.get("evidence_origin") != receipt.get("evidence_origin")
            or g6.get("database_file") != receipt.get("database_file")
            or sha256_bytes(_private_run_file(root, GATE_RECEIPTS["G6"]).read_bytes())
            != receipt.get("g6_receipt_sha256")
        ):
            raise GateEvidenceError("G7_G6_RECEIPT_BINDING_INVALID")
        if sync_index == 1:
            if (
                g6.get("database_sha256") != receipt.get("database_sha256_before")
                or receipt.get("previous_g7_receipt_sha256") is not None
            ):
                raise GateEvidenceError("G7_G6_RECEIPT_BINDING_INVALID")
        else:
            previous = read_validated_gate_receipt(
                root, ledger_snapshot, "G7", run_id=run_id,
                manifest_sha256=manifest_sha256, receipt_index=1,
                reopen_g6_snapshot=reopen_g6_snapshot,
            )
            previous_hash = sha256_bytes(
                _private_run_file(root, _g7_receipt_filename(1)).read_bytes(),
            )
            if (
                previous.get("sync_index") != 1
                or previous.get("status") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
                or previous.get("scan_status") != "COMPLETE"
                or previous.get("evidence_origin") != receipt.get("evidence_origin")
                or previous.get("database_file") != receipt.get("database_file")
                or previous.get("database_sha256_after")
                != receipt.get("database_sha256_before")
                or previous.get("incremental_scan_run_id")
                != receipt.get("baseline_scan_run_id")
                or previous.get("g6_receipt_sha256")
                != receipt.get("g6_receipt_sha256")
                or previous_hash != receipt.get("previous_g7_receipt_sha256")
            ):
                raise GateEvidenceError("G7_PREVIOUS_SYNC_BINDING_INVALID")
        g1 = read_validated_gate_receipt(
            root, ledger_snapshot, "G1", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        g2 = read_validated_gate_receipt(
            root, ledger_snapshot, "G2", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        if (
            g1.get("evidence_origin") != receipt.get("evidence_origin")
            or g2.get("evidence_origin") != receipt.get("evidence_origin")
            or g2.get("database_file") != receipt.get("database_file")
        ):
            raise GateEvidenceError("G7_PREDECESSOR_BINDING_INVALID")
        database_path = _dataset_path(root, root / str(receipt.get("database_file")))
        db = _readonly_database(database_path)
        try:
            baseline = db.execute(
                "SELECT r.channel_id,r.status,r.watermark_message_id,c.channel_id,"
                "c.status,c.watermark_message_id FROM scan_runs r "
                "JOIN sync_checkpoints c ON c.scan_run_id=r.id WHERE r.id=?",
                (receipt.get("baseline_scan_run_id"),),
            ).fetchone()
            incremental = db.execute(
                "SELECT r.channel_id,r.status,r.sync_mode,r.sync_baseline_confirmed,"
                "r.sync_high_water_before,r.sync_reconcile_floor_message_id,"
                "r.sync_reconcile_window,r.sync_snapshot_head_message_id,"
                "r.watermark_message_id,r.messages_unverified,c.channel_id,c.status,"
                "c.watermark_message_id,r.messages_seen,r.sync_max_messages,r.stop_reason "
                "FROM scan_runs r JOIN sync_checkpoints c ON c.scan_run_id=r.id WHERE r.id=?",
                (receipt.get("incremental_scan_run_id"),),
            ).fetchone()
            if (
                baseline is None or incremental is None
                or baseline[0] != manifest.get("channel_id")
                or baseline[3] != manifest.get("channel_id")
                or baseline[1] != "COMPLETE" or baseline[4] != "COMPLETE"
                or baseline[2] != receipt.get("high_water_before")
                or baseline[5] != receipt.get("high_water_before")
                or incremental[0] != manifest.get("channel_id")
                or incremental[10] != manifest.get("channel_id")
                or incremental[1] != expected_status
                or incremental[2] != "INCREMENTAL"
                or incremental[3] != 1
                or incremental[4] != receipt.get("high_water_before")
                or incremental[5] != max(1, receipt.get("high_water_before") - INCREMENTAL_WINDOW + 1)
                or incremental[6] != INCREMENTAL_WINDOW
                or incremental[8] != receipt.get("high_water_after")
                or incremental[9] not in {0, None}
                or incremental[11] != expected_status
                or incremental[12] != receipt.get("high_water_after")
                or incremental[13] != receipt.get("observed_messages")
                or incremental[14] != receipt.get("max_messages")
                or incremental[15] != expected_stop
                or receipt.get("confirmed_high_water_after")
                != receipt.get("high_water_before")
                and expected_status == "PARTIAL"
                or receipt.get("confirmed_high_water_after")
                != receipt.get("high_water_after")
                and expected_status == "COMPLETE"
            ):
                raise GateEvidenceError("G7_DATABASE_RECEIPT_DIVERGENCE")
        finally:
            db.close()
        if receipt_index is None:
            current_database_sha256 = _database_sha256(database_path)
            if current_database_sha256 != receipt.get("database_sha256_after"):
                try:
                    from telegram_courses.s9_operational_reconciliation import (
                        validate_g8_database_transition,
                    )

                    transition = validate_g8_database_transition(
                        root, ledger_snapshot, run_id=run_id,
                        manifest=manifest, manifest_sha256=manifest_sha256,
                        database_path=database_path,
                    )
                    latest_g7_path = _private_run_file(
                        root, _gate_receipt_path(root, "G7").name,
                    )
                    latest_g7_sha256 = sha256_bytes(latest_g7_path.read_bytes())
                except (GateEvidenceError, OSError, ValueError, TypeError, KeyError):
                    raise GateEvidenceError("G7_LATEST_DATABASE_SNAPSHOT_MISMATCH") from None
                if (
                    transition.get("run_id") != run_id
                    or transition.get("manifest_sha256") != manifest_sha256
                    or transition.get("database_file") != receipt.get("database_file")
                    or transition.get("database_sha256_before")
                    != receipt.get("database_sha256_after")
                    or transition.get("database_sha256_after") != current_database_sha256
                    or transition.get("g7_receipt_sha256") != latest_g7_sha256
                    or transition.get("evidence_origin") != receipt.get("evidence_origin")
                    or transition.get("status") not in {
                        "PASS", "OFFLINE_SYNTHETIC_PASS",
                    }
                ):
                    raise GateEvidenceError("G7_LATEST_DATABASE_SNAPSHOT_MISMATCH")
        ledger_scans = _ledger_scan_rows(ledger_snapshot)
        matched = [
            row for row in ledger_scans
            if row.get("scan_id") == receipt.get("ledger_scan_id")
        ]
        if (
            len(matched) != 1 or matched[0].get("incremental") != 1
            or matched[0].get("window_size") != INCREMENTAL_WINDOW
            or matched[0].get("max_messages") != receipt.get("max_messages")
            or matched[0].get("observed") != receipt.get("observed_messages")
            or matched[0].get("state") != "OBSERVED"
            or len(ledger_scans) < receipt.get("total_scan_invocations", 0)
            or len(ledger_scans) > MAX_SCAN_INVOCATIONS
            or sum(
                int(row.get("observed", 0)) for row in ledger_scans
                if type(row.get("observed")) is int
            ) < receipt.get("total_scan_observations", 0)
            or sum(
                int(row.get("observed", 0)) for row in ledger_scans
                if type(row.get("observed")) is int
            ) > MAX_SCAN_OBSERVATIONS
        ):
            raise GateEvidenceError("G7_LEDGER_RECEIPT_DIVERGENCE")
    return receipt


def _ledger_scan_rows(snapshot: Mapping[str, object]) -> list[dict[str, object]]:
    rows = snapshot.get("scans")
    if type(rows) is not list or any(type(row) is not dict for row in rows):
        raise GateEvidenceError("LEDGER_SCAN_SNAPSHOT_INVALID")
    return rows


def _blocked_gate(
    gate: str,
    *,
    run_id: str,
    manifest_sha256: str,
    reason: str,
    channel_id: object = None,
    evidence_origin: object = None,
    status: str = "BLOCKED",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "gate": gate,
        "status": status,
        "reason": reason,
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
    }
    if type(channel_id) is int:
        payload["channel_id"] = channel_id
    if type(evidence_origin) is str and evidence_origin in {
        "REAL_CONTRACTUAL", "SYNTHETIC", "OFFLINE_SYNTHETIC",
    }:
        payload["evidence_origin"] = evidence_origin
    return payload


def reconcile_g2_scan(
    run_directory: str | Path,
    database_path: str | Path,
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    g1_evidence: Mapping[str, object],
    database_scan_ids_before: set[str],
    ledger_before: Mapping[str, object],
    ledger_after: Mapping[str, object],
    requested_max_messages: int,
    application_exit_code: int = 0,
    external_exit_code: int | None = None,
    stage_started_ns: int,
    stage_finished_ns: int,
) -> dict[str, object]:
    source_origin = None

    def blocked(reason: str, *, status: str = "BLOCKED") -> dict[str, object]:
        return _blocked_gate(
            "G2", run_id=run_id, manifest_sha256=manifest_sha256,
            reason=reason, channel_id=manifest.get("channel_id"),
            evidence_origin=source_origin, status=status,
        )

    try:
        attested_g1 = read_validated_gate_receipt(
            run_directory, ledger_after, "G1", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
    except GateEvidenceError:
        return blocked("G1_RECEIPT_INVALID")
    source_origin = attested_g1.get("evidence_origin")
    if dict(attested_g1) != dict(g1_evidence):
        return blocked("G1_RECEIPT_MISMATCH")
    g1_status, g1_reason = validate_g1_evidence(
        dict(g1_evidence), run_id=run_id, manifest=manifest,
        manifest_sha256=manifest_sha256, require_supervisor=True,
    )
    if g1_status not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}:
        return blocked("G1_NOT_ELIGIBLE")
    if type(requested_max_messages) is not int or not 1 <= requested_max_messages <= MAX_MESSAGES_PER_SCAN:
        return blocked("SCAN_LIMIT_INVALID")
    if type(application_exit_code) is not int or application_exit_code not in {0, 4}:
        return blocked("SCAN_EXIT_CODE_INVALID")
    if type(external_exit_code) is not int or external_exit_code != application_exit_code:
        return blocked("APPLICATION_EXTERNAL_EXIT_MISMATCH")
    if any(type(value) is not int for value in (stage_started_ns, stage_finished_ns)) or stage_finished_ns < stage_started_ns:
        return blocked("STAGE_TIME_INVALID")
    before = _ledger_scan_rows(ledger_before)
    after = _ledger_scan_rows(ledger_after)
    before_ids = {str(row.get("scan_id")) for row in before}
    new_ledger = [row for row in after if str(row.get("scan_id")) not in before_ids]
    if len(new_ledger) != 1 or len(after) > MAX_SCAN_INVOCATIONS:
        return blocked("SCAN_LEDGER_DELTA_INVALID")
    ledger_scan = new_ledger[0]
    if (
        ledger_scan.get("state") != "OBSERVED"
        or ledger_scan.get("incremental") != 0
        or ledger_scan.get("max_messages") != requested_max_messages
        or type(ledger_scan.get("observed")) is not int
    ):
        return blocked("SCAN_LEDGER_STATE_INVALID")
    if any(
        row.get("state") != "OBSERVED"
        or type(row.get("max_messages")) is not int
        or not 1 <= row["max_messages"] <= MAX_MESSAGES_PER_SCAN
        or type(row.get("observed")) is not int
        or not 0 <= row["observed"] <= row["max_messages"]
        or row.get("incremental") not in {0, 1}
        for row in after
    ):
        return blocked("SCAN_LEDGER_INCOMPLETE")
    total_observations = sum(int(row["observed"]) for row in after if type(row.get("observed")) is int)
    if total_observations > MAX_SCAN_OBSERVATIONS:
        return blocked("SCAN_OBSERVATION_BUDGET_EXCEEDED", status="FAIL")
    try:
        root = _run_root(run_directory)
        path = _dataset_path(root, database_path)
        db = _readonly_database(path)
        try:
            tables = {
                str(row[0]) for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not {"scan_runs", "messages", "channels"}.issubset(tables):
                raise GateEvidenceError("SCAN_SCHEMA_MISSING")
            all_ids = {
                str(row[0]) for row in db.execute("SELECT id FROM scan_runs").fetchall()
            }
            added = all_ids - database_scan_ids_before
            if len(added) != 1:
                raise GateEvidenceError("SCAN_DATABASE_DELTA_INVALID")
            scan_id = next(iter(added))
            scan = db.execute(
                "SELECT id,channel_id,status,messages_seen,stop_reason,sync_mode,"
                "sync_max_messages,sync_reconcile_window,started_at FROM scan_runs WHERE id=?",
                (scan_id,),
            ).fetchone()
            if scan is None:
                raise GateEvidenceError("SCAN_RUN_NOT_PERSISTED")
            channel_id = manifest.get("channel_id")
            if scan[1] != channel_id:
                raise GateEvidenceError("SCAN_CHANNEL_MISMATCH")
            complete_scan = scan[2] == "COMPLETE" and scan[4] is None
            expected_message_limit = (
                scan[2] == "PARTIAL"
                and scan[4] == "MESSAGE_LIMIT"
                and type(scan[3]) is int
                and scan[3] == requested_max_messages
            )
            if (
                not (
                    complete_scan and application_exit_code == 0
                    or expected_message_limit and application_exit_code == 4
                )
                or scan[5] != "FULL" or scan[6] is not None
                or type(scan[7]) is not int or scan[7] != 0
            ):
                raise GateEvidenceError("SCAN_TERMINAL_STATE_INVALID")
            if (
                type(scan[3]) is not int or not 0 <= scan[3] <= requested_max_messages
                or scan[3] != ledger_scan["observed"]
            ):
                raise GateEvidenceError("SCAN_COUNTER_DIVERGENCE")
            try:
                timestamp = datetime.fromisoformat(str(scan[8]).replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    raise ValueError
                scan_started_ns = int(timestamp.timestamp() * 1_000_000_000)
            except (TypeError, ValueError, OverflowError, OSError):
                raise GateEvidenceError("SCAN_TIMESTAMP_INVALID") from None
            if not stage_started_ns - 5_000_000_000 <= scan_started_ns <= stage_finished_ns + 5_000_000_000:
                raise GateEvidenceError("SCAN_RUN_OUTSIDE_SUPERVISED_STAGE")
            if db.execute(
                "SELECT 1 FROM channels WHERE telegram_chat_id=?", (channel_id,),
            ).fetchone() is None:
                raise GateEvidenceError("SCAN_CHANNEL_NOT_PERSISTED")
            persisted_messages, persisted_messages_sha256 = _channel_messages_sha256(
                db, channel_id,
            )
        finally:
            db.close()
        origin = str(g1_evidence.get("evidence_origin"))
        is_real = origin == "REAL_CONTRACTUAL"
        return {
            "gate": "G2",
            "status": "PASS" if is_real else "OFFLINE_SYNTHETIC_PASS",
            "reason": "SCAN_RECONCILED" if is_real else "SYNTHETIC_GATEWAY_ONLY",
            "evidence_origin": origin,
            "run_id": run_id,
            "manifest_sha256": manifest_sha256,
            "channel_id": manifest["channel_id"],
            "database_file": path.name,
            "scan_run_id": scan_id,
            "ledger_scan_id": ledger_scan["scan_id"],
            "max_messages": requested_max_messages,
            "application_exit_code": application_exit_code,
            "external_exit_code": external_exit_code,
            "scan_status": str(scan[2]),
            "stop_reason": scan[4],
            "observed_messages": ledger_scan["observed"],
            "total_scan_invocations": len(after),
            "total_scan_observations": total_observations,
            "persisted_message_count": persisted_messages,
            "persisted_messages_sha256": persisted_messages_sha256,
            "database_sha256": _database_sha256(path),
            "database_integrity": "ok",
            "predecessor_reason": g1_reason,
        }
    except GateEvidenceError as error:
        return blocked(str(error))


def read_g7_baseline(
    run_directory: str | Path,
    database_path: str | Path,
    *,
    channel_id: int,
) -> tuple[str, int]:
    """Return the highest complete, checkpointed high-water for G7 preflight."""
    root = _run_root(run_directory)
    path = _dataset_path(root, database_path)
    db = _readonly_database(path)
    try:
        tables = {
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not {"scan_runs", "sync_checkpoints"}.issubset(tables):
            raise GateEvidenceError("G7_BASELINE_TABLES_MISSING")
        row = db.execute(
            "SELECT r.id,r.watermark_message_id,c.watermark_message_id "
            "FROM scan_runs r JOIN sync_checkpoints c ON c.scan_run_id=r.id "
            "WHERE r.channel_id=? AND r.status='COMPLETE' AND c.channel_id=? "
            "AND c.status='COMPLETE' AND r.watermark_message_id IS NOT NULL "
            "AND r.watermark_message_id=c.watermark_message_id "
            "ORDER BY r.watermark_message_id DESC,r.finished_at DESC,r.started_at DESC LIMIT 1",
            (channel_id, channel_id),
        ).fetchone()
        if (
            row is None or type(row[0]) is not str or not row[0]
            or type(row[1]) is not int or row[1] < 0 or row[1] != row[2]
        ):
            raise GateEvidenceError("G7_COMPLETE_BASELINE_UNAVAILABLE")
        return row[0], row[1]
    except sqlite3.Error:
        raise GateEvidenceError("G7_BASELINE_READ_FAILED") from None
    finally:
        db.close()


def _g6_download_snapshot(
    run_directory: Path,
    database_path: Path,
    *,
    channel_id: int,
    ledger: Any,
    ledger_snapshot: Mapping[str, object],
    expected_download_root_name: str | None = None,
) -> dict[str, object]:
    """Reconcile every S9-registered media item against its V1 DB/file state."""
    from telegram_courses.download_repository import DownloadCandidate
    from telegram_courses.downloads import (
        DownloadError,
        _matches,
        _reject_reparse_path,
        destination_paths,
    )
    from telegram_courses.s9_operational_ledger import (
        LedgerError,
        _open_private_directory_guard,
        _verify_private_file,
    )

    root = _run_root(run_directory)
    path = _dataset_path(root, database_path)
    db = _readonly_database(path)
    try:
        tables = {
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not {"media_items", "downloads", "catalog_nodes"}.issubset(tables):
            raise GateEvidenceError("G6_DOWNLOAD_SCHEMA_INVALID")
        media_columns = {
            str(row[1]) for row in db.execute("PRAGMA table_info(media_items)")
        }
        download_columns = {
            str(row[1]) for row in db.execute("PRAGMA table_info(downloads)")
        }
        if not {
            "remote_observation_state",
        }.issubset(media_columns) or not {
            "sha256", "remote_identity_media_id", "remote_identity_kind",
            "remote_identity_size", "remote_identity_provenance", "owner_pid",
        }.issubset(download_columns):
            raise GateEvidenceError("G6_DOWNLOAD_IDENTITY_SCHEMA_INVALID")
        media = ledger_snapshot.get("media")
        if type(media) is not list or not media:
            raise GateEvidenceError("G6_LEDGER_MEDIA_UNAVAILABLE")
        rows = db.execute(
            "SELECT m.id,m.channel_id,m.telegram_message_id,m.media_ordinal,"
            "m.telegram_media_id,m.kind,m.file_size_bytes,m.original_filename,"
            "m.catalog_node_id,m.remote_observation_state,d.state,d.final_path,"
            "d.partial_path,d.expected_bytes,d.downloaded_bytes,d.sha256,"
            "d.attempts,d.owner_pid,d.remote_identity_media_id,"
            "d.remote_identity_kind,d.remote_identity_size,"
            "d.remote_identity_provenance "
            "FROM media_items m LEFT JOIN downloads d ON d.media_item_id=m.id "
            "WHERE m.channel_id=? ORDER BY m.telegram_message_id,m.media_ordinal",
            (channel_id,),
        ).fetchall()
        rows_by_alias: dict[str, sqlite3.Row] = {}
        for row in rows:
            if (
                type(row[1]) is not int or type(row[2]) is not int
                or type(row[3]) is not int
            ):
                raise GateEvidenceError("G6_MEDIA_IDENTITY_INVALID")
            alias = ledger.pseudonym(f"{row[1]}:{row[2]}:{row[3]}")
            if alias in rows_by_alias:
                raise GateEvidenceError("G6_MEDIA_IDENTITY_DUPLICATED")
            rows_by_alias[alias] = row
    except (sqlite3.Error, LedgerError):
        raise GateEvidenceError("G6_DATABASE_RECONCILIATION_FAILED") from None
    finally:
        db.close()

    expected_media = {
        str(row.get("alias")): row for row in media
        if type(row) is dict
    }
    if len(expected_media) != len(media) or set(expected_media) - set(rows_by_alias):
        raise GateEvidenceError("G6_LEDGER_DATABASE_MEDIA_MISMATCH")

    physical_rows: list[dict[str, object]] = []
    discovered_root: Path | None = None
    physical_bytes = 0
    for alias, ledger_row in sorted(expected_media.items()):
        row = rows_by_alias[alias]
        expected_bytes = ledger_row.get("expected")
        if (
            type(expected_bytes) is not int
            or row[1] != channel_id
            or row[5] != "DOCUMENT"
            or row[6] != expected_bytes
            or type(row[4]) is not str or not row[4]
            or row[9] != "OBSERVED"
            or row[10] != "DOWNLOADED"
            or row[11] is None or row[12] is None
            or row[13] != expected_bytes
            or row[14] != expected_bytes
            or row[16] is None or row[16] < 1
            or row[17] is not None
            or row[18] != row[4]
            or row[19] != "DOCUMENT"
            or row[20] != expected_bytes
            or row[21] != "CAPTURED_AT_START"
            or type(row[15]) is not str or not _HASH.fullmatch(row[15])
            or row[8] is None
        ):
            raise GateEvidenceError("G6_SQLITE_DOWNLOAD_DIVERGENCE")
        lineage_rows = None
        # The lineage is read separately from the readonly DB to match S5's
        # deterministic destination_paths policy exactly.
        lineage_db = _readonly_database(path)
        try:
            lineage_rows = lineage_db.execute(
                "WITH RECURSIVE lineage(id,parent_id,kind,title,depth) AS ("
                " SELECT id,parent_id,kind,title,0 FROM catalog_nodes WHERE id=?"
                " UNION ALL SELECT p.id,p.parent_id,p.kind,p.title,l.depth+1"
                " FROM catalog_nodes p JOIN lineage l ON p.id=l.parent_id"
                " WHERE l.depth<4)"
                " SELECT kind,title FROM lineage ORDER BY depth DESC",
                (row[8],),
            ).fetchall()
        except sqlite3.Error:
            raise GateEvidenceError("G6_CATALOG_LINEAGE_INVALID") from None
        finally:
            lineage_db.close()
        lineage = tuple((str(item[0]), item[1]) for item in lineage_rows or ())
        if not lineage or tuple(kind for kind, _ in lineage) not in {
            ("lesson",), ("course", "lesson"), ("module", "lesson"),
            ("course", "module", "lesson"), ("track", "course", "lesson"),
            ("track", "course", "module", "lesson"),
        }:
            raise GateEvidenceError("G6_CATALOG_LINEAGE_INVALID")
        candidate = DownloadCandidate(
            media_item_id=int(row[0]), channel_id=int(row[1]),
            telegram_message_id=int(row[2]), media_ordinal=int(row[3]),
            telegram_media_id=str(row[4]), expected_bytes=expected_bytes,
            # S5 validates full catalog ancestry for selection, then passes
            # only the selected lesson to destination_paths.
            original_filename=row[7], lineage=(lineage[-1],),
        )
        final = Path(str(row[11]))
        partial = Path(str(row[12]))
        probe = root / ".g6-path-probe"
        try:
            expected_final, expected_partial = destination_paths(probe, candidate)
            suffix = expected_final.relative_to(probe)
        except (DownloadError, ValueError, OSError):
            raise GateEvidenceError("G6_S5_PATH_POLICY_INVALID") from None
        if (
            not final.is_absolute()
            or not partial.is_absolute()
            or len(final.parts) <= len(suffix.parts)
            or tuple(os.path.normcase(item) for item in final.parts[-len(suffix.parts):])
            != tuple(os.path.normcase(item) for item in suffix.parts)
            or partial != final.with_name(final.name + ".part")
        ):
            raise GateEvidenceError("G6_S5_PATH_POLICY_INVALID")
        download_root = final
        for _ in range(len(suffix.parts)):
            download_root = download_root.parent
        try:
            resolved_root = download_root.resolve(strict=True)
            if (
                resolved_root.parent != root.resolve(strict=True)
                or download_root.is_symlink()
                or getattr(download_root.lstat(), "st_file_attributes", 0) & 0x400
                or expected_download_root_name is not None
                and download_root.name != expected_download_root_name
                or discovered_root is not None
                and os.path.normcase(str(discovered_root))
                != os.path.normcase(str(download_root))
                or os.path.lexists(partial)
            ):
                raise GateEvidenceError("G6_DOWNLOAD_ROOT_OR_PARTIAL_INVALID")
            discovered_root = resolved_root
            guard = _open_private_directory_guard(download_root)
            guard.verify(download_root)
            try:
                _reject_reparse_path(download_root, final)
                _reject_reparse_path(download_root, partial)
                _verify_private_file(final)
                if not _matches(final, expected_bytes, str(row[15])):
                    raise GateEvidenceError("G6_PHYSICAL_DOWNLOAD_MISMATCH")
            finally:
                guard.close()
        except GateEvidenceError:
            raise
        except (LedgerError, DownloadError, OSError, RuntimeError, ValueError):
            raise GateEvidenceError("G6_PHYSICAL_DOWNLOAD_UNAVAILABLE") from None
        physical_bytes += expected_bytes
        physical_rows.append({
            "alias": alias,
            "profile": ledger_row.get("profile"),
            "expected_bytes": expected_bytes,
            "downloaded_bytes": row[14],
            "sha256": row[15],
            "state": row[10],
        })
    if discovered_root is None:
        raise GateEvidenceError("G6_DOWNLOAD_ROOT_UNAVAILABLE")
    snapshot_sha256 = sha256_bytes(canonical_bytes(physical_rows))
    return {
        "download_root": discovered_root.name,
        "download_snapshot_sha256": snapshot_sha256,
        "media_count": len(physical_rows),
        "physical_bytes": physical_bytes,
    }


def _g6_m_eligibility_snapshot(
    database_path: Path,
    *,
    channel_id: int,
) -> dict[str, object]:
    """Reopen the catalog and count eligible M-sized documents independently."""
    from telegram_courses.s9_operational_ledger import GIB

    path = database_path
    db = _readonly_database(path)
    try:
        tables = {
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not {"media_items", "messages", "channels", "catalog_nodes"}.issubset(tables):
            raise GateEvidenceError("G6_M_DATASET_SCHEMA_INVALID")
        rows = db.execute(
            "WITH RECURSIVE lineage(media_item_id,id,parent_id,kind,title,depth) AS ("
            " SELECT m.id,n.id,n.parent_id,n.kind,n.title,0 FROM media_items m "
            " JOIN catalog_nodes n ON n.id=m.catalog_node_id AND n.channel_id=m.channel_id "
            " WHERE m.channel_id=? AND n.kind='lesson' AND n.is_active=1 "
            " UNION ALL SELECT l.media_item_id,p.id,p.parent_id,p.kind,p.title,l.depth+1 "
            " FROM catalog_nodes p JOIN lineage l ON p.id=l.parent_id "
            " WHERE p.is_active=1 AND l.depth<4) "
            "SELECT m.id,m.channel_id,m.telegram_message_id,m.media_ordinal,"
            "m.telegram_media_id,m.file_size_bytes,m.kind,m.remote_observation_state,"
            "l.kind,l.title,l.depth FROM media_items m "
            "JOIN messages msg ON msg.channel_id=m.channel_id "
            "AND msg.telegram_message_id=m.telegram_message_id "
            "JOIN channels c ON c.telegram_chat_id=m.channel_id "
            "JOIN lineage l ON l.media_item_id=m.id "
            "WHERE m.channel_id=? AND m.kind='DOCUMENT' "
            "AND m.file_size_bytes BETWEEN ? AND ? AND m.telegram_media_id IS NOT NULL "
            "ORDER BY m.id,l.depth DESC",
            (channel_id, channel_id, GIB, 2 * GIB),
        ).fetchall()
    except (sqlite3.Error, TypeError, ValueError):
        raise GateEvidenceError("G6_M_DATASET_READ_FAILED") from None
    finally:
        db.close()

    allowed_lineages = {
        ("lesson",), ("course", "lesson"), ("module", "lesson"),
        ("course", "module", "lesson"), ("track", "course", "lesson"),
        ("track", "course", "module", "lesson"),
    }
    grouped: dict[int, list[object]] = {}
    for row in rows:
        if type(row[0]) is not int:
            raise GateEvidenceError("G6_M_DATASET_IDENTITY_INVALID")
        grouped.setdefault(row[0], []).append(row)

    eligible: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    for media_item_id, item_rows in sorted(grouped.items()):
        first = item_rows[0]
        lineage = tuple(str(row[8]) for row in item_rows)
        if (
            type(first[1]) is not int or first[1] != channel_id
            or type(first[2]) is not int or first[2] < 0
            or type(first[3]) is not int or first[3] < 0
            or type(first[4]) is not str or not first[4]
            or type(first[5]) is not int or not GIB <= first[5] <= 2 * GIB
            or first[6] != "DOCUMENT"
            or lineage not in allowed_lineages
            or any(row[8] not in {"lesson", "module", "course", "track"} for row in item_rows)
        ):
            continue
        snapshot_row: dict[str, object] = {
            "media_item_id": media_item_id,
            "message_id": first[2],
            "media_ordinal": first[3],
            "expected_bytes": first[5],
            "telegram_media_id_sha256": sha256_bytes(
                str(first[4]).encode("utf-8"),
            ),
            "lineage": lineage,
            "remote_observation_state": first[7],
        }
        if first[7] == "OBSERVED":
            eligible.append(snapshot_row)
        else:
            unresolved.append(snapshot_row)

    return {
        "eligible_count": len(eligible),
        "unresolved_count": len(unresolved),
        "snapshot_sha256": sha256_bytes(canonical_bytes({
            "eligible": eligible,
            "unresolved": unresolved,
        })),
    }


def _g6_chain_origin(
    g0: Mapping[str, object],
    predecessors: Mapping[str, Mapping[str, object]],
    pass_receipts: Sequence[Mapping[str, object]],
) -> str:
    human_g0 = (
        g0.get("status") == "PASS"
        and g0.get("evidence_origin") == "HUMAN_INTERACTIVE"
        and g0.get("confirmation_source") == "INTERACTIVE_TTY"
    )
    synthetic_g0 = (
        g0.get("status") == "OFFLINE_SYNTHETIC_PASS"
        and g0.get("evidence_origin") == "SYNTHETIC"
        and g0.get("confirmation_source") == "SYNTHETIC_TEST"
    )
    if not (human_g0 or synthetic_g0):
        raise GateEvidenceError("G6_PREDECESSOR_INVALID")
    origins = {
        str(receipt.get("evidence_origin")) for receipt in pass_receipts
    } | {
        str(evidence.get("evidence_origin")) for evidence in predecessors.values()
    }
    if origins not in ({"REAL_CONTRACTUAL"}, {"SYNTHETIC"}):
        raise GateEvidenceError("G6_EVIDENCE_ORIGIN_MISMATCH")
    origin = next(iter(origins))
    if (human_g0 and origin != "REAL_CONTRACTUAL") or (
        synthetic_g0 and origin != "SYNTHETIC"
    ):
        raise GateEvidenceError("G6_EVIDENCE_ORIGIN_MISMATCH")
    return origin


def _g6_reconcile_inputs(
    run_directory: str | Path,
    database_path: str | Path,
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    ledger: Any,
    ledger_snapshot: Mapping[str, object],
    expected_download_root_name: str | None = None,
) -> dict[str, object]:
    from telegram_courses.s9_operational_ledger import F_CAP, media_m_cap

    root = _run_root(run_directory)
    if (
        type(manifest.get("channel_id")) is not int
        or manifest.get("channel_id", 0) > -1_000_000_000_000
    ):
        raise GateEvidenceError("G6_CHANNEL_INVALID")
    manifest_on_disk, current_manifest_sha, scope_sha256 = load_approved_manifest(root)
    if current_manifest_sha != manifest_sha256 or dict(manifest_on_disk) != dict(manifest):
        raise GateEvidenceError("G6_MANIFEST_MISMATCH")
    g0 = read_validated_gate_receipt(
        root, ledger_snapshot, "G0", run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    predecessors = {
        gate: read_validated_gate_receipt(
            root, ledger_snapshot, gate, run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        for gate in ("G1", "G2", "G3")
    }
    if (
        predecessors["G2"].get("scan_status") != "COMPLETE"
        or predecessors["G2"].get("stop_reason") is not None
        or predecessors["G3"].get("unresolved_count") != 0
        or any(
            evidence.get("status") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
            for evidence in predecessors.values()
        )
    ):
        raise GateEvidenceError("G6_PREDECESSOR_INVALID")
    run = ledger_snapshot.get("run")
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    media = ledger_snapshot.get("media")
    reservations = ledger_snapshot.get("reservations")
    if (
        type(run) is not dict or run.get("run_id") != run_id
        or run.get("gate") not in {"G5", "G6", "G7", "G8", "G9"}
        or run.get("gate") == "G5"
        and run.get("result") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        or run.get("status") not in {
            "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED",
        }
        or type(events) is not list or audit.get("quarantined") is not False
        or type(media) is not list or type(reservations) is not list
        or any(row.get("state") != "OBSERVED" for row in reservations)
    ):
        raise GateEvidenceError("G6_LEDGER_STATE_INVALID")
    profile_media = {
        profile: [row for row in media if type(row) is dict and row.get("profile") == profile]
        for profile in ("F", "M")
    }
    m_eligibility = _g6_m_eligibility_snapshot(
        _dataset_path(root, Path(database_path)),
        channel_id=int(manifest["channel_id"]),
    )
    no_eligible_m = (
        m_eligibility["eligible_count"] == 0
        and m_eligibility["unresolved_count"] == 0
    )
    if no_eligible_m:
        m_receipt_files = (
            g5_queue_receipt_filename("M", pass_index)
            for pass_index in (1, 2)
        )
        m_supervisor_files = (
            g5_supervisor_receipt_filename("M", pass_index)
            for pass_index in (1, 2)
        )
        if (
            profile_media["M"]
            or any(os.path.lexists(root / name) for name in (*m_receipt_files, *m_supervisor_files))
        ):
            raise GateEvidenceError("G6_M_DATASET_STATUS_CONFLICT")
        required_profiles = ("F",)
    else:
        if m_eligibility["eligible_count"] < 1 or len(profile_media["M"]) != 1:
            raise GateEvidenceError("G6_PROFILE_MEDIA_PLAN_INVALID")
        required_profiles = ("F", "M")

    pass_receipts: list[dict[str, object]] = []
    for profile in required_profiles:
        for pass_index in (1, 2):
            pass_receipts.append(read_validated_g5_queue_receipt(
                root, ledger_snapshot, run_id=run_id,
                manifest_sha256=manifest_sha256,
                profile=profile, pass_index=pass_index,
            ))
    origin = _g6_chain_origin(g0, predecessors, pass_receipts)
    g5_expected_status = (
        "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
    )
    expected_status = "PARTIAL" if no_eligible_m else g5_expected_status
    if (
        any(receipt.get("status") != g5_expected_status for receipt in pass_receipts)
        or any(receipt.get("channel_id") != manifest.get("channel_id") for receipt in pass_receipts)
        or any(receipt.get("database_file") != Path(database_path).name for receipt in pass_receipts)
        or len({receipt.get("download_root") for receipt in pass_receipts}) != 1
    ):
        raise GateEvidenceError("G6_G5_QUEUE_BINDING_INVALID")
    if (
        not 1 <= len(profile_media["F"]) <= 8
        or not no_eligible_m and profile_media["M"][0].get("attempts") != 1
        or any(row.get("attempts") not in {0, 1} for row in media)
    ):
        raise GateEvidenceError("G6_PROFILE_MEDIA_PLAN_INVALID")
    reservations_by_profile = {"F": 0, "M": 0}
    reservations_by_alias: dict[str, int] = {}
    for reservation in reservations:
        if (
            type(reservation) is not dict
            or reservation.get("state") != "OBSERVED"
            or reservation.get("origin") != "MEASURED"
            or reservation.get("measurement_source") != (
                "GATEWAY_RESPONSE" if origin == "REAL_CONTRACTUAL" else "SYNTHETIC_TEST"
            )
            or reservation.get("profile") not in reservations_by_profile
            or type(reservation.get("observed")) is not int
        ):
            raise GateEvidenceError("G6_RESERVATION_PROVENANCE_INVALID")
        profile = str(reservation["profile"])
        alias = str(reservation["alias"])
        reservations_by_profile[profile] += int(reservation["observed"])
        reservations_by_alias[alias] = reservations_by_alias.get(alias, 0) + int(reservation["observed"])
    for row in media:
        alias = str(row["alias"])
        if row.get("attempts") == 1 and reservations_by_alias.get(alias) != row.get("expected"):
            raise GateEvidenceError("G6_MEDIA_RESERVATION_TOTAL_MISMATCH")
        if row.get("attempts") == 0 and alias in reservations_by_alias:
            raise GateEvidenceError("G6_MEDIA_RESERVATION_PLAN_MISMATCH")
    for profile in required_profiles:
        first = next(
            receipt for receipt in pass_receipts
            if receipt.get("profile") == profile and receipt.get("pass_index") == 1
        )
        second = next(
            receipt for receipt in pass_receipts
            if receipt.get("profile") == profile and receipt.get("pass_index") == 2
        )
        expected_count = len(profile_media[profile])
        expected_cap = (
            F_CAP if profile == "F"
            else media_m_cap(int(profile_media["M"][0]["expected"]))
        )
        if (
            first.get("max_media_items") != expected_count
            or first.get("max_transfer_bytes", expected_cap + 1) > expected_cap
            or second.get("max_media_items") != expected_count
            or second.get("max_transfer_bytes") != 1
            or second.get("observed_bytes") != 0
            or second.get("all_items_already_valid") is not True
            or first.get("observed_bytes") != reservations_by_profile[profile]
        ):
            raise GateEvidenceError("G6_SECOND_QUEUE_NOT_PROVEN")
    for receipt in pass_receipts:
        if receipt.get("download_root") != expected_download_root_name and expected_download_root_name is not None:
            raise GateEvidenceError("G6_DOWNLOAD_ROOT_BINDING_INVALID")
    physical = _g6_download_snapshot(
        root, Path(database_path), channel_id=int(manifest["channel_id"]),
        ledger=ledger, ledger_snapshot=ledger_snapshot,
        expected_download_root_name=expected_download_root_name
        or str(pass_receipts[0].get("download_root")),
    )
    if physical["media_count"] != len(media):
        raise GateEvidenceError("G6_PHYSICAL_MEDIA_COUNT_MISMATCH")
    return {
        "evidence_origin": origin,
        "status": expected_status,
        "g5_queue_receipts": [
            {
                "profile": receipt["profile"],
                "pass_index": receipt["pass_index"],
                "receipt_file": g5_queue_receipt_filename(
                    str(receipt["profile"]), int(receipt["pass_index"]),
                ),
                "receipt_sha256": sha256_bytes(canonical_bytes(receipt) + b"\n"),
                "supervisor_receipt_file": receipt["supervisor_receipt_file"],
                "supervisor_receipt_sha256": receipt["supervisor_receipt_sha256"],
            }
            for receipt in pass_receipts
        ],
        "download_root": physical["download_root"],
        "download_snapshot_sha256": physical["download_snapshot_sha256"],
        "media_count": physical["media_count"],
        "physical_bytes": physical["physical_bytes"],
        "database_sha256": _database_sha256(Path(database_path)),
        "database_file": Path(database_path).name,
        "database_integrity": "ok",
        "channel_id": manifest["channel_id"],
        "manifest_sha256": manifest_sha256,
        "scope_sha256": scope_sha256,
        "real_evidence_status": (
            "REAL_CONTRACTUAL_PASS"
            if origin == "REAL_CONTRACTUAL" and not no_eligible_m
            else "REAL_EVIDENCE_PENDING"
        ),
        "reason": (
            "M_DATASET_UNAVAILABLE"
            if no_eligible_m else "DOWNLOADS_AND_SECOND_QUEUE_RECONCILED"
        ),
        "gate": "G6",
        "run_id": run_id,
        **({
            "g5_m_status": "BLOCKED_DATASET",
            "g6_aggregate_status": "PARTIAL",
            "g7_real_eligible": False,
            "nfr02_real": "NOT_TESTED",
            "g5_m_eligible_count": m_eligibility["eligible_count"],
            "g5_m_unresolved_count": m_eligibility["unresolved_count"],
            "g5_m_inventory_sha256": m_eligibility["snapshot_sha256"],
        } if no_eligible_m else {}),
    }


def reconcile_g6_downloads(
    run_directory: str | Path,
    database_path: str | Path,
    download_root: str | Path,
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    ledger: Any,
    ledger_snapshot: Mapping[str, object],
) -> dict[str, object]:
    """Produce G6 only after re-opening G5 receipts, ledger, SQLite, and files."""
    from telegram_courses.s9_operational_ledger import LedgerError

    try:
        if (
            not Path(download_root).is_absolute()
            or Path(download_root).parent.resolve(strict=True)
            != _run_root(run_directory).resolve(strict=True)
        ):
            raise GateEvidenceError("G6_DOWNLOAD_ROOT_BINDING_INVALID")
        evidence = _g6_reconcile_inputs(
            run_directory, database_path, run_id=run_id, manifest=manifest,
            manifest_sha256=manifest_sha256, ledger=ledger,
            ledger_snapshot=ledger_snapshot,
            expected_download_root_name=Path(download_root).name,
        )
        evidence["database_sha256"] = _database_sha256(Path(database_path))
        return evidence
    except (GateEvidenceError, OSError, LedgerError, ValueError, TypeError, KeyError):
        return _blocked_gate(
            "G6", run_id=run_id, manifest_sha256=manifest_sha256,
            reason="G6_RECONCILIATION_FAILED",
            channel_id=manifest.get("channel_id"),
            evidence_origin=None,
        )


def _validate_g6_receipt_evidence(
    root: Path,
    receipt: Mapping[str, object],
    ledger_snapshot: Mapping[str, object],
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
) -> None:
    """Reopen all G5 passes and the physical snapshot behind a durable G6."""
    from telegram_courses.s9_operational_ledger import S9OperationalLedger

    try:
        ledger = S9OperationalLedger(root / "operational-ledger.sqlite3")
        current = _g6_reconcile_inputs(
            root, root / str(receipt.get("database_file")),
            run_id=run_id, manifest=manifest,
            manifest_sha256=manifest_sha256, ledger=ledger,
            ledger_snapshot=ledger_snapshot,
            expected_download_root_name=str(receipt.get("download_root")),
        )
    except (GateEvidenceError, OSError, RuntimeError, ValueError, TypeError, KeyError):
        raise GateEvidenceError("G6_REOPEN_RECONCILIATION_FAILED") from None
    if any(
        receipt.get(key) != current.get(key)
        for key in (
            "status", "evidence_origin", "g5_queue_receipts", "download_root",
            "download_snapshot_sha256", "media_count", "physical_bytes",
            "database_file", "database_integrity", "channel_id", "manifest_sha256",
            "scope_sha256", "real_evidence_status", "reason",
            "g5_m_status", "g6_aggregate_status", "g7_real_eligible",
            "nfr02_real", "g5_m_eligible_count", "g5_m_unresolved_count",
            "g5_m_inventory_sha256",
        )
    ):
        raise GateEvidenceError("G6_REOPEN_SNAPSHOT_MISMATCH")


def reconcile_g7_scan(
    run_directory: str | Path,
    database_path: str | Path,
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    g1_evidence: Mapping[str, object],
    g2_evidence: Mapping[str, object],
    g6_evidence: Mapping[str, object],
    baseline_scan_run_id: str,
    database_scan_ids_before: set[str],
    database_sha256_before: str,
    ledger_before: Mapping[str, object],
    ledger_after: Mapping[str, object],
    requested_max_messages: int,
    application_exit_code: int,
    external_exit_code: int | None,
    stage_started_ns: int,
    stage_finished_ns: int,
    sync_index: int = 1,
    previous_g7_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Reconcile one bounded incremental scan against S7 DB and S9 ledger."""
    source_origin = None

    def blocked(reason: str, *, status: str = "BLOCKED") -> dict[str, object]:
        return _blocked_gate(
            "G7", run_id=run_id, manifest_sha256=manifest_sha256,
            reason=reason, channel_id=manifest.get("channel_id"),
            evidence_origin=source_origin, status=status,
        )

    try:
        attested_g1 = read_validated_gate_receipt(
            run_directory, ledger_after, "G1", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        attested_g2 = read_validated_gate_receipt(
            run_directory, ledger_after, "G2", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        attested_g6 = read_validated_gate_receipt(
            run_directory, ledger_after, "G6", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
    except GateEvidenceError:
        return blocked("PREDECESSOR_RECEIPT_INVALID")
    source_origin = attested_g6.get("evidence_origin")
    origins = {
        str(attested_g1.get("evidence_origin")),
        str(attested_g2.get("evidence_origin")),
        str(attested_g6.get("evidence_origin")),
    }
    if (
        dict(attested_g1) != dict(g1_evidence)
        or dict(attested_g2) != dict(g2_evidence)
        or dict(attested_g6) != dict(g6_evidence)
        or origins not in ({"REAL_CONTRACTUAL"}, {"SYNTHETIC"})
        or attested_g1.get("channel_id") != manifest.get("channel_id")
        or attested_g2.get("channel_id") != manifest.get("channel_id")
        or attested_g6.get("channel_id") != manifest.get("channel_id")
        or attested_g1.get("status")
        != ("PASS" if source_origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS")
        or attested_g2.get("status") != attested_g1.get("status")
        or attested_g6.get("status") != attested_g1.get("status")
        or attested_g2.get("scan_status") != "COMPLETE"
        or attested_g2.get("stop_reason") is not None
        or attested_g6.get("database_file") != attested_g2.get("database_file")
    ):
        return blocked("PREDECESSOR_PROVENANCE_OR_BASELINE_INVALID")
    if type(sync_index) is not int or sync_index not in {1, MAX_G7_SYNCS}:
        return blocked("G7_SYNC_INDEX_INVALID")
    attested_previous: dict[str, object] | None = None
    if sync_index == 1:
        if previous_g7_evidence is not None:
            return blocked("G7_UNEXPECTED_PREVIOUS_SYNC")
    else:
        try:
            attested_previous = read_validated_gate_receipt(
                run_directory, ledger_after, "G7", run_id=run_id,
                manifest_sha256=manifest_sha256, receipt_index=1,
            )
        except GateEvidenceError:
            return blocked("G7_PREVIOUS_SYNC_INVALID")
        if (
            previous_g7_evidence is None
            or dict(attested_previous) != dict(previous_g7_evidence)
            or attested_previous.get("sync_index") != 1
            or attested_previous.get("status") not in {
                "PASS", "OFFLINE_SYNTHETIC_PASS",
            }
            or attested_previous.get("scan_status") != "COMPLETE"
            or attested_previous.get("evidence_origin") != source_origin
            or attested_previous.get("incremental_scan_run_id") != baseline_scan_run_id
            or attested_previous.get("g6_receipt_sha256")
            != sha256_bytes(
                _private_run_file(
                    _run_root(run_directory), GATE_RECEIPTS["G6"],
                ).read_bytes(),
            )
        ):
            return blocked("G7_PREVIOUS_SYNC_BINDING_INVALID")
    if (
        type(requested_max_messages) is not int
        or not 1 <= requested_max_messages <= MAX_MESSAGES_PER_SCAN
    ):
        return blocked("INCREMENTAL_SCAN_LIMIT_INVALID")
    if (
        type(application_exit_code) is not int
        or application_exit_code not in {0, 4}
        or type(external_exit_code) is not int
        or external_exit_code != application_exit_code
    ):
        return blocked("APPLICATION_EXTERNAL_EXIT_MISMATCH")
    expected_database_before = (
        attested_g6.get("database_sha256") if sync_index == 1
        else attested_previous.get("database_sha256_after")
        if attested_previous is not None else None
    )
    if (
        any(type(value) is not int for value in (stage_started_ns, stage_finished_ns))
        or stage_finished_ns < stage_started_ns
        or type(database_sha256_before) is not str
        or not _HASH.fullmatch(database_sha256_before)
        or expected_database_before != database_sha256_before
    ):
        return blocked("STAGE_BASELINE_BINDING_INVALID")
    before = _ledger_scan_rows(ledger_before)
    after = _ledger_scan_rows(ledger_after)
    before_ids = {str(row.get("scan_id")) for row in before}
    added_ledger = [row for row in after if str(row.get("scan_id")) not in before_ids]
    if len(added_ledger) != 1 or len(after) > MAX_SCAN_INVOCATIONS:
        return blocked("INCREMENTAL_LEDGER_DELTA_INVALID")
    ledger_scan = added_ledger[0]
    if (
        ledger_scan.get("state") != "OBSERVED"
        or ledger_scan.get("incremental") != 1
        or ledger_scan.get("window_size") != INCREMENTAL_WINDOW
        or ledger_scan.get("max_messages") != requested_max_messages
        or type(ledger_scan.get("observed")) is not int
        or not 0 <= ledger_scan["observed"] <= requested_max_messages
        or any(
            row.get("state") != "OBSERVED"
            or type(row.get("observed")) is not int
            or type(row.get("max_messages")) is not int
            or row.get("incremental") not in {0, 1}
            or row.get("incremental") == 1
            and row.get("window_size") != INCREMENTAL_WINDOW
            for row in after
        )
    ):
        return blocked("INCREMENTAL_LEDGER_STATE_INVALID")
    total_observations = sum(
        int(row["observed"]) for row in after if type(row.get("observed")) is int
    )
    if total_observations > MAX_SCAN_OBSERVATIONS:
        return blocked("SCAN_OBSERVATION_BUDGET_EXCEEDED", status="FAIL")

    try:
        root = _run_root(run_directory)
        path = _dataset_path(root, database_path)
        if (
            path.name != attested_g2.get("database_file")
            or path.name != attested_g6.get("database_file")
        ):
            raise GateEvidenceError("G7_DATABASE_BINDING_MISMATCH")
        db = _readonly_database(path)
        try:
            tables = {
                str(row[0]) for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not {"scan_runs", "sync_checkpoints", "messages"}.issubset(tables):
                raise GateEvidenceError("G7_CHECKPOINT_SCHEMA_MISSING")
            all_ids = {
                str(row[0]) for row in db.execute("SELECT id FROM scan_runs").fetchall()
            }
            added_db = all_ids - database_scan_ids_before
            if len(added_db) != 1:
                raise GateEvidenceError("G7_DATABASE_SCAN_DELTA_INVALID")
            incremental_id = next(iter(added_db))
            if incremental_id == baseline_scan_run_id:
                raise GateEvidenceError("G7_SCAN_BINDING_INVALID")
            channel_id = manifest.get("channel_id")
            baseline = db.execute(
                "SELECT r.channel_id,r.status,r.watermark_message_id,c.channel_id,"
                "c.status,c.watermark_message_id FROM scan_runs r "
                "JOIN sync_checkpoints c ON c.scan_run_id=r.id WHERE r.id=?",
                (baseline_scan_run_id,),
            ).fetchone()
            incremental = db.execute(
                "SELECT r.channel_id,r.status,r.sync_mode,r.sync_baseline_confirmed,"
                "r.sync_high_water_before,r.sync_reconcile_floor_message_id,"
                "r.sync_reconcile_window,r.sync_snapshot_head_message_id,"
                "r.watermark_message_id,r.messages_unverified,c.channel_id,c.status,"
                "c.watermark_message_id,r.messages_seen,r.sync_max_messages,r.stop_reason,"
                "r.started_at FROM scan_runs r JOIN sync_checkpoints c "
                "ON c.scan_run_id=r.id WHERE r.id=?",
                (incremental_id,),
            ).fetchone()
            if baseline is None or incremental is None:
                raise GateEvidenceError("G7_SCAN_BINDING_MISSING")
            baseline_high_water = baseline[2]
            if (
                baseline[0] != channel_id or baseline[3] != channel_id
                or baseline[1] != "COMPLETE" or baseline[4] != "COMPLETE"
                or type(baseline_high_water) is not int or baseline_high_water < 0
                or baseline[5] != baseline_high_water
            ):
                raise GateEvidenceError("G7_BASELINE_INCOMPLETE")
            before_high_water = incremental[4]
            snapshot_head = incremental[7]
            watermark_after = incremental[8]
            checkpoint_after = incremental[12]
            complete = (
                incremental[1] == "COMPLETE" and incremental[11] == "COMPLETE"
                and incremental[15] is None and application_exit_code == 0
            )
            message_limit_partial = (
                incremental[1] == "PARTIAL" and incremental[11] == "PARTIAL"
                and incremental[15] == "MESSAGE_LIMIT"
                and application_exit_code == 4
                and incremental[13] == requested_max_messages
            )
            if not (complete or message_limit_partial):
                raise GateEvidenceError("G7_TERMINAL_STATE_INVALID")
            if (
                incremental[0] != channel_id or incremental[10] != channel_id
                or incremental[2] != "INCREMENTAL"
                or incremental[3] != 1
                or type(before_high_water) is not int
                or before_high_water != baseline_high_water
                or incremental[6] != INCREMENTAL_WINDOW
                or incremental[5] != max(1, before_high_water - INCREMENTAL_WINDOW + 1)
                or (snapshot_head is not None and type(snapshot_head) is not int)
                or type(watermark_after) is not int
                or type(incremental[13]) is not int
                or not 0 <= incremental[13] <= requested_max_messages
                or incremental[13] != ledger_scan.get("observed")
                or incremental[14] != requested_max_messages
                or checkpoint_after != watermark_after
                or incremental[9] not in {0, None}
                or not complete and watermark_after < before_high_water
            ):
                raise GateEvidenceError("G7_INCREMENTAL_PERSISTENCE_DIVERGENCE")
            if (
                complete
                and watermark_after != max(before_high_water, snapshot_head or before_high_water)
            ):
                raise GateEvidenceError("G7_HIGH_WATER_DIVERGENCE")
            if message_limit_partial:
                confirmed_after = db.execute(
                    "SELECT MAX(watermark_message_id) FROM scan_runs "
                    "WHERE channel_id=? AND status='COMPLETE'",
                    (channel_id,),
                ).fetchone()[0]
                if confirmed_after != before_high_water:
                    raise GateEvidenceError("G7_PARTIAL_PROMOTED_HIGH_WATER")
            else:
                confirmed_after = db.execute(
                    "SELECT MAX(watermark_message_id) FROM scan_runs "
                    "WHERE channel_id=? AND status='COMPLETE'",
                    (channel_id,),
                ).fetchone()[0]
                if confirmed_after != watermark_after:
                    raise GateEvidenceError("G7_CONFIRMED_HIGH_WATER_DIVERGENCE")
            timestamp = datetime.fromisoformat(str(incremental[16]).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError
            scan_started_ns = int(timestamp.timestamp() * 1_000_000_000)
            if not stage_started_ns - 5_000_000_000 <= scan_started_ns <= stage_finished_ns + 5_000_000_000:
                raise GateEvidenceError("G7_SCAN_OUTSIDE_SUPERVISED_STAGE")
            duplicates = db.execute(
                "SELECT 1 FROM messages GROUP BY channel_id,telegram_message_id "
                "HAVING COUNT(*)>1 LIMIT 1",
            ).fetchone()
            if duplicates is not None:
                raise GateEvidenceError("G7_MESSAGE_DEDUPLICATION_FAILED")
        finally:
            db.close()
        origin = str(source_origin)
        is_real = origin == "REAL_CONTRACTUAL"
        status = (
            "PARTIAL" if message_limit_partial
            else "PASS" if is_real else "OFFLINE_SYNTHETIC_PASS"
        )
        previous_g7_receipt_sha256 = (
            None if sync_index == 1 else sha256_bytes(
                _private_run_file(
                    root, _g7_receipt_filename(1),
                ).read_bytes(),
            )
        )
        return {
            "gate": "G7",
            "status": status,
            "reason": (
                "MESSAGE_LIMIT_PARTIAL_NO_PROMOTION" if message_limit_partial
                else "INCREMENTAL_RECONCILED" if is_real
                else "SYNTHETIC_INCREMENTAL_RECONCILED"
            ),
            "evidence_origin": origin,
            "run_id": run_id,
            "manifest_sha256": manifest_sha256,
            "channel_id": channel_id,
            "database_file": path.name,
            "database_sha256_before": database_sha256_before,
            "database_sha256_after": _database_sha256(path),
            "database_integrity": "ok",
            "sync_index": sync_index,
            "receipt_file": _g7_receipt_filename(sync_index),
            "previous_g7_receipt_sha256": previous_g7_receipt_sha256,
            "g6_receipt_sha256": sha256_bytes(
                _private_run_file(root, GATE_RECEIPTS["G6"]).read_bytes(),
            ),
            "baseline_scan_run_id": baseline_scan_run_id,
            "baseline_status": "COMPLETE",
            "incremental_scan_run_id": incremental_id,
            "ledger_scan_id": ledger_scan["scan_id"],
            "window_size": INCREMENTAL_WINDOW,
            "high_water_before": before_high_water,
            "high_water_after": watermark_after,
            "confirmed_high_water_after": confirmed_after,
            "max_messages": requested_max_messages,
            "observed_messages": ledger_scan["observed"],
            "scan_status": str(incremental[1]),
            "stop_reason": incremental[15],
            "application_exit_code": application_exit_code,
            "external_exit_code": external_exit_code,
            "total_scan_invocations": len(after),
            "total_scan_observations": total_observations,
            "deletions_inferred": False,
        }
    except (GateEvidenceError, sqlite3.Error, TypeError, ValueError, OverflowError) as error:
        return blocked(str(error) or "G7_DATABASE_RECONCILIATION_FAILED")


def _hierarchy_valid(db: sqlite3.Connection, channel_id: int) -> bool:
    rows = db.execute(
        "SELECT id,parent_id,kind FROM catalog_nodes WHERE channel_id=? AND is_active=1",
        (channel_id,),
    ).fetchall()
    by_id = {row[0]: (row[1], str(row[2]).upper()) for row in rows}
    for _node_id, (parent_id, kind) in by_id.items():
        expected_parent = {"TRACK": None, "COURSE": "TRACK", "MODULE": "COURSE"}.get(kind)
        if kind not in {"TRACK", "COURSE", "MODULE"}:
            continue
        if expected_parent is None:
            if parent_id is not None:
                return False
        elif parent_id not in by_id or by_id[parent_id][1] != expected_parent:
            return False
    return True


def reconcile_g3_catalog(
    run_directory: str | Path,
    database_path: str | Path,
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    g2_receipt: Mapping[str, object],
    ledger_snapshot: Mapping[str, object],
    database_catalog_ids_before: set[str],
) -> dict[str, object]:
    source_origin = None

    def blocked(reason: str) -> dict[str, object]:
        return _blocked_gate(
            "G3", run_id=run_id, manifest_sha256=manifest_sha256,
            reason=reason, channel_id=manifest.get("channel_id"),
            evidence_origin=source_origin,
        )

    try:
        attested_g1 = read_validated_gate_receipt(
            run_directory, ledger_snapshot, "G1", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        attested_g2 = read_validated_gate_receipt(
            run_directory, ledger_snapshot, "G2", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
    except GateEvidenceError:
        return blocked("PREDECESSOR_RECEIPT_INVALID")
    source_origin = attested_g2.get("evidence_origin")
    if dict(attested_g2) != dict(g2_receipt):
        return blocked("G2_RECEIPT_MISMATCH")
    g2_origin = g2_receipt.get("evidence_origin")
    if (
        g2_receipt.get("gate") != "G2"
        or g2_receipt.get("run_id") != run_id
        or g2_receipt.get("manifest_sha256") != manifest_sha256
        or g2_receipt.get("channel_id") != manifest.get("channel_id")
        or g2_origin not in {"REAL_CONTRACTUAL", "SYNTHETIC"}
        or g2_receipt.get("status") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        or attested_g1.get("evidence_origin") != g2_origin
        or attested_g1.get("status") != g2_receipt.get("status")
    ):
        return blocked("PREDECESSOR_PROVENANCE_MISMATCH")
    try:
        root = _run_root(run_directory)
        path = _dataset_path(root, database_path)
        if path.name != g2_receipt.get("database_file"):
            raise GateEvidenceError("G2_G3_DATABASE_MISMATCH")
        db = _readonly_database(path)
        try:
            tables = {
                str(row[0]) for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            required = {
                "catalog_runs", "catalog_nodes", "catalog_unresolved_sources",
                "scan_runs", "messages",
            }
            if not required.issubset(tables):
                raise GateEvidenceError("CATALOG_SCHEMA_MISSING")
            all_ids = {
                str(row[0]) for row in db.execute("SELECT id FROM catalog_runs").fetchall()
            }
            added = all_ids - database_catalog_ids_before
            if len(added) != 1:
                raise GateEvidenceError("CATALOG_RUN_DELTA_INVALID")
            catalog_id = next(iter(added))
            channel_id = manifest.get("channel_id")
            run = db.execute(
                "SELECT id,channel_id,status,source_message_count,catalog_node_count,unresolved_count "
                "FROM catalog_runs WHERE id=?", (catalog_id,),
            ).fetchone()
            if run is None or run[1] != channel_id or run[2] != "COMPLETE":
                raise GateEvidenceError("CATALOG_TERMINAL_STATE_INVALID")
            persisted_messages, persisted_messages_sha256 = _channel_messages_sha256(
                db, channel_id,
            )
            scan = db.execute(
                "SELECT id,channel_id,status,messages_seen,stop_reason,sync_mode "
                "FROM scan_runs WHERE id=?", (g2_receipt.get("scan_run_id"),),
            ).fetchone()
            complete_scan = (
                scan is not None
                and scan[2] == "COMPLETE" and scan[4] is None
                and g2_receipt.get("application_exit_code") == 0
            )
            g2_max_messages = g2_receipt.get("max_messages")
            message_limit_scan = (
                scan is not None
                and scan[2] == "PARTIAL" and scan[4] == "MESSAGE_LIMIT"
                and g2_receipt.get("application_exit_code") == 4
                and type(g2_max_messages) is int
                and 1 <= g2_max_messages <= MAX_MESSAGES_PER_SCAN
                and type(scan[3]) is int
                and scan[3] == g2_max_messages
                and scan[3] == g2_receipt.get("observed_messages")
            )
            if (
                scan is None or scan[1] != channel_id
                or not (complete_scan or message_limit_scan)
                or scan[5] != "FULL"
                or type(scan[3]) is not int
                or scan[3] != g2_receipt.get("observed_messages")
            ):
                raise GateEvidenceError("G2_SCAN_PERSISTENCE_DIVERGENCE")
            if (
                run[3] != persisted_messages
                or persisted_messages != g2_receipt.get("persisted_message_count")
                or persisted_messages_sha256 != g2_receipt.get("persisted_messages_sha256")
            ):
                raise GateEvidenceError("CATALOG_SCAN_SOURCE_COUNT_MISMATCH")
            counts = {
                str(row[0]).upper(): int(row[1]) for row in db.execute(
                    "SELECT kind,COUNT(*) FROM catalog_nodes "
                    "WHERE channel_id=? AND is_active=1 GROUP BY kind", (channel_id,),
                ).fetchall()
            }
            hierarchy = manifest.get("hierarchy")
            planned_catalog = manifest.get("catalog_expectation") is not None
            if type(hierarchy) is not dict:
                raise GateEvidenceError("CATALOG_MANIFEST_DIVERGENCE")
            if planned_catalog:
                if any(
                    counts.get(kind, 0) < hierarchy.get(kind, 0)
                    for kind in ("TRACK", "COURSE", "MODULE")
                ):
                    raise GateEvidenceError("BLOCKED_DATASET")
            elif any(
                counts.get(kind, 0) != hierarchy.get(kind)
                for kind in ("TRACK", "COURSE", "MODULE")
            ):
                raise GateEvidenceError("CATALOG_MANIFEST_DIVERGENCE")
            if (
                counts.get("TRACK", 0) < 1
                or counts.get("COURSE", 0) < 2
                or counts.get("MODULE", 0) < 2
            ):
                raise GateEvidenceError("BLOCKED_DATASET")
            active_nodes = sum(counts.values())
            if run[4] != active_nodes or not _hierarchy_valid(db, channel_id):
                raise GateEvidenceError("CATALOG_HIERARCHY_INVALID")
            unresolved_count = int(db.execute(
                "SELECT COUNT(*) FROM catalog_unresolved_sources WHERE run_id=?",
                (catalog_id,),
            ).fetchone()[0])
            if run[5] != unresolved_count or (
                not planned_catalog
                and unresolved_count != manifest.get("unresolved_count")
            ):
                raise GateEvidenceError("CATALOG_UNRESOLVED_DIVERGENCE")
        finally:
            db.close()
        is_real = g2_origin == "REAL_CONTRACTUAL"
        return {
            "gate": "G3",
            "status": "PASS" if is_real else "OFFLINE_SYNTHETIC_PASS",
            "reason": "CATALOG_RECONCILED" if is_real else "SYNTHETIC_GATEWAY_ONLY",
            "evidence_origin": str(g2_origin),
            "run_id": run_id,
            "manifest_sha256": manifest_sha256,
            "channel_id": manifest["channel_id"],
            "database_file": path.name,
            "scan_run_id": g2_receipt["scan_run_id"],
            "catalog_run_id": catalog_id,
            "source_message_count": persisted_messages,
            "hierarchy": {kind: counts.get(kind, 0) for kind in ("TRACK", "COURSE", "MODULE")},
            "active_node_count": active_nodes,
            "unresolved_count": unresolved_count,
            "database_sha256": _database_sha256(path),
            "database_integrity": "ok",
        }
    except GateEvidenceError as error:
        return blocked(str(error))


def g1_worker_main(argv: Sequence[str] | None = None) -> int:
    """Supervised child entry point; creates no gateway unless explicitly run."""
    phase = "worker_entry"
    _g1_diagnostic(phase, "START")
    values = list(argv if argv is not None else sys.argv[1:])
    if len(values) != 3:
        _g1_diagnostic(phase, "BLOCKED", "INVALID_ARGUMENTS")
        return 2
    run_directory, run_id, expected_manifest_sha256 = values
    try:
        phase = "t24_initialization"
        _g1_diagnostic(phase, "START")
        try:
            from telegram_courses.operational_logging import (
                configure_operational_logging,
                emit_operational_event,
            )
        except ImportError as error:
            _g1_diagnostic(phase, "FAILURE", _g1_failure_class(error))
            raise
        phase = "context_manifest"
        _g1_diagnostic(phase, "START")
        from telegram_courses.s9_operational_ledger import S9OperationalLedger

        ledger_path = os.environ.get(_S9_LEDGER_ENV)
        if (
            os.environ.get(_S9_SUPERVISED_CHILD_ENV) != "1"
            or os.environ.get(_S9_STAGE_ENV) != "discovery"
            or not ledger_path or not Path(ledger_path).is_absolute()
        ):
            _g1_diagnostic(phase, "BLOCKED", "INVALID_ENVIRONMENT")
            return 4
        ledger = S9OperationalLedger(ledger_path)
        ledger_snapshot = ledger.snapshot()
        run = ledger_snapshot.get("run")
        audit = ledger_snapshot.get("critical_audit")
        events = audit.get("events") if type(audit) is dict else None
        if (
            type(run) is not dict or run.get("run_id") != run_id
            or run.get("gate") != "G1" or run.get("status") != "RUNNING"
            or run.get("result") != "UNKNOWN"
            or type(events) is not list
            or audit.get("quarantined") is not False
        ):
            _g1_diagnostic(phase, "BLOCKED", "INVALID_CONTEXT")
            return 4
        stage_events: dict[str, list[dict[str, object]]] = {}
        for item in events:
            if type(item) is not dict:
                continue
            try:
                details = json.loads(str(item.get("details_json")))
            except (TypeError, ValueError):
                continue
            if type(details) is dict and details.get("stage") == "discovery":
                stage_events.setdefault(str(item.get("event_type")), []).append(details)
        if any(len(stage_events.get(name, [])) != 1 for name in (
            "RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "GATE_STARTED",
            "CHILD_PROCESS_CONFIRMED",
        )):
            _g1_diagnostic(phase, "BLOCKED", "INVALID_AUDIT")
            return 4
        phase = "t24_initialization"
        _g1_diagnostic(phase, "START")
        configure_operational_logging("INFO")
        phase = "context_manifest"
        _g1_diagnostic(phase, "START")
        manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(run_directory)
        if manifest_sha256 != expected_manifest_sha256:
            _g1_diagnostic(phase, "BLOCKED", "MANIFEST_MISMATCH")
            return 4
        g0 = read_validated_gate_receipt(
            run_directory, ledger_snapshot, "G0", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        if (
            g0.get("status") != "PASS"
            or g0.get("evidence_origin") != "HUMAN_INTERACTIVE"
            or g0.get("channel_id") != manifest.get("channel_id")
            or g0.get("authorized_scope") != manifest.get("scope")
        ):
            _g1_diagnostic(phase, "BLOCKED", "G0_INVALID")
            return 4
        phase = "gateway_open"
        evidence = asyncio.run(collect_g1_evidence(
            run_id=run_id, manifest=manifest, manifest_sha256=manifest_sha256,
            run_directory=run_directory, ledger_snapshot=ledger_snapshot,
            diagnostic=_g1_diagnostic,
        ))
        if evidence.get("status") != "PASS":
            reason = evidence.get("reason")
            _g1_diagnostic(
                "discovery", "BLOCKED",
                reason if isinstance(reason, str) and reason in _G1_DISCOVERY_DIAGNOSTIC_REASONS
                else "BLOCKED_OUTCOME",
            )
        phase = "t24_logging"
        emit_operational_event(
            "s9.g1.evidence_collected", component="s9.g1",
            status=str(evidence.get("status", "BLOCKED")),
            category=str(evidence.get("reason", "G1_NOT_ASSESSED")),
        )
        phase = "evidence_persistence"
        _g1_diagnostic(phase, "START")
        root = _run_root(run_directory)
        payload = canonical_bytes(evidence) + b"\n"
        destination = root / G1_WORKER_RECEIPT
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return 0 if evidence.get("status") == "PASS" and evidence.get("evidence_origin") == "REAL_CONTRACTUAL" else 4
    except (GateEvidenceError, OSError, RuntimeError, ValueError) as error:
        _g1_diagnostic(phase, "FAILURE", _g1_failure_class(error))
        return 4
    except Exception as error:
        _g1_diagnostic(phase, "FAILURE", _g1_failure_class(error))
        raise

