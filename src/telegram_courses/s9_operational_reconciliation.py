"""Durable operational S9 G8/G9 evidence reconciliation.

The bundle-based offline reconciler remains in ``s9_gate_reconciliation``.
This module reads receipts produced by the supervised operational stages and
keeps synthetic, contractual-real, and pending evidence distinct.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from telegram_courses.s9_operational_ledger import (
    LedgerError,
    S9OperationalLedger,
    _open_private_directory_guard,
)
from telegram_courses.s9_real_gate_producers import (
    GATE_RECEIPTS,
    GateEvidenceError,
    _database_sha256,
    _dataset_path,
    _g7_receipt_filename,
    _private_run_file,
    _run_root,
    canonical_bytes,
    g5_queue_receipt_filename,
    load_approved_manifest,
    read_validated_g5_queue_receipt,
    read_validated_gate_receipt,
    sha256_bytes,
)
from telegram_courses.s9_supervisor import _write_no_overwrite_json

G8_PREFIX_PROOF_FILE = "g8-s6-prefix-proof.json"
G8_INTERRUPTION_SUPERVISOR_FILE = "g8-interruption-supervisor-receipt.json"
G8_RECOVERY_SUPERVISOR_FILE = "g8-recovery-supervisor-receipt.json"
G8_OPERATIONAL_RECEIPT_FILE = "g8-operational-receipt.json"
G9_OPERATIONAL_RECEIPT_FILE = "g9-operational-receipt.json"
G9_OPERATIONAL_REPORT_FILE = "g9-operational-report.md"

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ALIAS = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECEIPT_BYTES = 4 * 1024 * 1024


class OperationalReconciliationError(ValueError):
    """A durable operational receipt or its linked evidence is invalid."""


@runtime_checkable
class PrefixHashRange(Protocol):
    offset: int
    limit: int
    sha256: bytes | str


@runtime_checkable
class S6PrefixProofObservation(Protocol):
    """Typed output emitted only after S6 V1 has verified a local prefix."""

    candidate_identity: tuple[int, int, int]
    expected_bytes: int
    physical_prefix_bytes: int
    local_prefix_sha256: str
    remote_ranges: Sequence[PrefixHashRange]
    verification_payload_bytes: int
    integrity_mode: str


@dataclass(frozen=True)
class OperationalGateResult:
    gate: str
    status: str
    reason: str
    evidence_origin: str
    real_evidence_status: str
    run_id: str
    manifest_sha256: str
    summary: Mapping[str, object]
    receipt_path: Path | None = None


@dataclass(frozen=True)
class OperationalReconciliation:
    run_id: str
    result: str
    evidence_origin: str
    real_evidence_status: str
    gates: tuple[OperationalGateResult, ...]
    receipt_path: Path | None
    report_path: Path | None
    manifest_sha256: str


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OperationalReconciliationError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _read_json(path: Path, *, maximum_bytes: int = _MAX_RECEIPT_BYTES) -> dict[str, object]:
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or info.st_size <= 0
            or info.st_size > maximum_bytes
        ):
            raise OperationalReconciliationError("EVIDENCE_FILE_UNSAFE")
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except OperationalReconciliationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise OperationalReconciliationError("EVIDENCE_FILE_UNAVAILABLE") from None
    if type(value) is not dict:
        raise OperationalReconciliationError("EVIDENCE_OBJECT_INVALID")
    return value


def _private_run_output_path(root: Path, name: str) -> Path:
    """Validate a new run-local destination without requiring it to exist."""
    if (
        type(name) is not str or not name
        or Path(name).name != name or name in {".", ".."}
    ):
        raise OperationalReconciliationError("RUN_FILE_OUTPUT_NAME_INVALID")
    try:
        private_root = _run_root(root)
        path = private_root / name
        if (
            path.parent.resolve(strict=True) != private_root
            or os.path.lexists(path)
        ):
            raise OperationalReconciliationError("RUN_FILE_OUTPUT_UNAVAILABLE")
    except GateEvidenceError:
        raise OperationalReconciliationError("RUN_FILE_OUTPUT_UNAVAILABLE") from None
    except OSError:
        raise OperationalReconciliationError("RUN_FILE_OUTPUT_UNAVAILABLE") from None
    return path


def _event_details(event: Mapping[str, object]) -> dict[str, object]:
    try:
        raw = json.loads(str(event.get("details_json")), object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
        raise OperationalReconciliationError("AUDIT_DETAILS_INVALID") from None
    if type(raw) is not dict:
        raise OperationalReconciliationError("AUDIT_DETAILS_INVALID")
    return raw


def _event_id(run_id: str, gate: str, digest: str, event_kind: str) -> str:
    return hashlib.sha256(
        f"{run_id}:{gate}:{digest}:{event_kind}".encode("ascii"),
    ).hexdigest()[:32]


def _persist_receipt(
    run_root: Path,
    ledger: S9OperationalLedger,
    payload: Mapping[str, object],
    *,
    filename: str,
    before_rename_checkpoint: Callable[[], object] | None = None,
) -> tuple[Path, str]:
    gate = payload.get("gate")
    run_id = payload.get("run_id")
    origin = payload.get("evidence_origin")
    if (
        gate not in {"G8", "G9"}
        or type(run_id) is not str
        or origin not in {"REAL_CONTRACTUAL", "SYNTHETIC", "UNKNOWN"}
    ):
        raise OperationalReconciliationError("OPERATIONAL_RECEIPT_IDENTITY_INVALID")
    path = _private_run_output_path(run_root, filename)
    canonical = dict(payload)
    status = str(canonical.get("status"))
    checkpoint_required = (
        gate in {"G8", "G9"}
        and status in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
    )
    raw = canonical_bytes(canonical) + b"\n"
    receipt_hash = sha256_bytes(raw)
    identifiers = {
        kind: _event_id(run_id, str(gate), receipt_hash, kind)
        for kind in ("prepared", "persisted", "finished")
    }

    def event(kind: str, event_type: str, details: dict[str, object]) -> None:
        details.update({
            "gate": gate,
            "evidence_origin": origin,
            "receipt_sha256": receipt_hash,
        })
        ledger.record_critical_event(
            event_type,
            details=details,
            event_id=identifiers[kind],
        )

    def prepare(_raw: bytes) -> None:
        event("prepared", "RECEIPT_PREPARED", {})
        if checkpoint_required and before_rename_checkpoint is not None:
            before_rename_checkpoint()

    _write_no_overwrite_json(
        path,
        canonical,
        before_rename=prepare,
        after_rename=lambda _raw: event("persisted", "RECEIPT_PERSISTED", {}),
    )
    completion_status = (
        "COMPLETED" if status in {"PASS", "OFFLINE_SYNTHETIC_PASS", "PARTIAL"}
        else "BLOCKED" if status == "BLOCKED"
        else "FAILED"
    )
    real_status = (
        "REAL_CONTRACTUAL_PASS"
        if status == "PASS" and origin == "REAL_CONTRACTUAL"
        else "REAL_EVIDENCE_PENDING"
    )
    offline_result = (
        "OFFLINE_SYNTHETIC_PASS"
        if status == "OFFLINE_SYNTHETIC_PASS"
        else status
    )
    event("finished", "GATE_FINISHED", {
        "status": completion_status,
        "result": status,
        "offline_result": offline_result,
        "real_evidence_status": real_status,
    })
    return path, receipt_hash


def _read_operational_receipt(
    run_root: Path,
    ledger_snapshot: Mapping[str, object],
    *,
    gate: Literal["G8", "G9"],
    run_id: str,
    manifest_sha256: str,
    filename: str,
) -> tuple[dict[str, object], str]:
    path = _private_run_file(run_root, filename)
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    receipt = _read_json(path)
    expected_schema = f"telegram-courses-s9-{gate.lower()}-operational-receipt-v1"
    if (
        receipt.get("schema") != expected_schema
        or receipt.get("version") != 1
        or receipt.get("gate") != gate
        or receipt.get("run_id") != run_id
        or receipt.get("manifest_sha256") != manifest_sha256
        or receipt.get("evidence_origin") not in {
            "REAL_CONTRACTUAL", "SYNTHETIC", "UNKNOWN",
        }
        or receipt.get("status") not in {
            "PASS", "OFFLINE_SYNTHETIC_PASS", "PARTIAL", "BLOCKED", "FAIL",
        }
        or receipt.get("status") == "PASS"
        and receipt.get("evidence_origin") != "REAL_CONTRACTUAL"
        or receipt.get("status") == "OFFLINE_SYNTHETIC_PASS"
        and receipt.get("evidence_origin") != "SYNTHETIC"
        or receipt.get("real_evidence_status") != (
            "REAL_CONTRACTUAL_PASS"
            if receipt.get("status") == "PASS"
            and receipt.get("evidence_origin") == "REAL_CONTRACTUAL"
            else "REAL_EVIDENCE_PENDING"
        )
    ):
        raise OperationalReconciliationError("OPERATIONAL_RECEIPT_CONTENT_INVALID")
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list or audit.get("quarantined") is not False:
        raise OperationalReconciliationError("OPERATIONAL_RECEIPT_AUDIT_UNAVAILABLE")
    matched: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {
        key: [] for key in ("prepared", "persisted", "finished")
    }
    updates: list[tuple[dict[str, object], dict[str, object]]] = []
    for event in events:
        if type(event) is not dict:
            continue
        details = _event_details(event)
        if details.get("gate") != gate:
            continue
        if event.get("event_type") in {"GATE_STATE_UPDATED", "RUN_TERMINAL"}:
            updates.append((event, details))
        if details.get("receipt_sha256") != digest:
            continue
        if event.get("event_type") == "RECEIPT_PREPARED":
            matched["prepared"].append((event, details))
        elif event.get("event_type") == "RECEIPT_PERSISTED":
            matched["persisted"].append((event, details))
        elif event.get("event_type") == "GATE_FINISHED":
            matched["finished"].append((event, details))
    if any(len(items) != 1 for items in matched.values()):
        raise OperationalReconciliationError("OPERATIONAL_RECEIPT_ATTESTATION_INVALID")
    for kind, matches in matched.items():
        event, details = matches[0]
        if (
            event.get("event_id") != _event_id(run_id, gate, digest, kind)
            or details.get("evidence_origin") != receipt.get("evidence_origin")
        ):
            raise OperationalReconciliationError("OPERATIONAL_RECEIPT_ATTESTATION_INVALID")
    finished_event, finished = matched["finished"][0]
    completion_status = (
        "COMPLETED" if receipt["status"] in {"PASS", "OFFLINE_SYNTHETIC_PASS", "PARTIAL"}
        else "BLOCKED" if receipt["status"] == "BLOCKED"
        else "FAILED"
    )
    if (
        finished.get("result") != receipt.get("status")
        or finished.get("status") != completion_status
        or not any(
            int(event.get("sequence", 0)) > int(finished_event.get("sequence", 0))
            and details.get("result") == receipt.get("ledger_result")
            and event.get("event_type") == (
                "RUN_TERMINAL" if gate == "G9" else "GATE_STATE_UPDATED"
            )
            for event, details in updates
        )
    ):
        raise OperationalReconciliationError("OPERATIONAL_RECEIPT_STATE_NOT_ATTESTED")
    return receipt, digest


def _write_sanitized_report(path: Path, content: str) -> str:
    if os.path.lexists(path):
        raise OperationalReconciliationError("REPORT_ALREADY_EXISTS")
    raw = content.encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.urandom(8).hex()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        temporary.unlink()
    except FileExistsError:
        raise OperationalReconciliationError("REPORT_ALREADY_EXISTS") from None
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise OperationalReconciliationError("REPORT_PERSIST_FAILED") from None
    return sha256_bytes(raw)


def _validate_sanitized_report(
    path: Path,
    *,
    expected_sha256: object,
    forbidden_values: Sequence[str],
) -> None:
    if type(expected_sha256) is not str or not _HASH.fullmatch(expected_sha256):
        raise OperationalReconciliationError("REPORT_HASH_INVALID")
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or info.st_size <= 0 or info.st_size > 1024 * 1024
        ):
            raise OperationalReconciliationError("REPORT_FILE_UNSAFE")
        raw = path.read_bytes()
        content = raw.decode("utf-8")
    except OperationalReconciliationError:
        raise
    except (OSError, UnicodeDecodeError):
        raise OperationalReconciliationError("REPORT_FILE_UNAVAILABLE") from None
    if (
        sha256_bytes(raw) != expected_sha256
        or any(value and value in content for value in forbidden_values)
        or re.search(r"(?i)(?:[a-f0-9]{64}|\\.session|api[_ -]?hash|access[_ -]?hash)", content)
    ):
        raise OperationalReconciliationError("REPORT_SANITIZATION_INVALID")


def persist_s6_prefix_proof(
    run_directory: str | Path,
    ledger: S9OperationalLedger,
    observation: S6PrefixProofObservation,
    *,
    measurement_source: Literal["GATEWAY_RESPONSE", "SYNTHETIC_TEST"],
) -> tuple[Path, str]:
    """Persist the typed observation emitted after S6 V1 prefix verification.

    The caller provides no success boolean. This boundary validates the actual
    values and labels the evidence from the queue's established byte source.
    """
    if measurement_source not in {"GATEWAY_RESPONSE", "SYNTHETIC_TEST"}:
        raise OperationalReconciliationError("PREFIX_PROOF_SOURCE_INVALID")
    if not all(
        hasattr(observation, name)
        for name in (
            "candidate_identity", "expected_bytes", "physical_prefix_bytes",
            "local_prefix_sha256", "remote_ranges",
            "verification_payload_bytes", "integrity_mode",
        )
    ):
        raise OperationalReconciliationError("PREFIX_PROOF_OBSERVATION_INVALID")
    identity = observation.candidate_identity
    if (
        type(identity) is not tuple or len(identity) != 3
        or any(type(value) is not int for value in identity)
        or type(observation.expected_bytes) is not int
        or type(observation.physical_prefix_bytes) is not int
        or not 0 < observation.physical_prefix_bytes < observation.expected_bytes
        or type(observation.verification_payload_bytes) is not int
        or observation.verification_payload_bytes < 0
        or observation.integrity_mode != "REMOTE_HASH_REQUIRED"
        or type(observation.local_prefix_sha256) is not str
        or not _HASH.fullmatch(observation.local_prefix_sha256)
        or not isinstance(observation.remote_ranges, Sequence)
        or isinstance(observation.remote_ranges, (str, bytes, bytearray))
    ):
        raise OperationalReconciliationError("PREFIX_PROOF_OBSERVATION_INVALID")
    run_root = _run_root(run_directory)
    manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(run_root)
    if identity[0] != manifest.get("channel_id"):
        raise OperationalReconciliationError("PREFIX_PROOF_OBSERVATION_INVALID")
    snapshot = ledger.snapshot()
    run = snapshot["run"]
    if snapshot["critical_audit"]["quarantined"]:
        raise OperationalReconciliationError("LEDGER_AUDIT_QUARANTINED")
    if ledger.path.parent.resolve(strict=True) != run_root.resolve(strict=True):
        raise OperationalReconciliationError("LEDGER_RUN_BINDING_INVALID")
    identity_alias = ledger.pseudonym(f"{identity[0]}:{identity[1]}:{identity[2]}")
    media = [row for row in snapshot["media"] if row.get("alias") == identity_alias]
    if (
        len(media) != 1
        or media[0].get("profile") != "F"
        or media[0].get("expected") != observation.expected_bytes
        or media[0].get("kind") != "DOCUMENT"
        or media[0].get("attempts") < 2
        or run.get("run_id") != snapshot["run"].get("run_id")
    ):
        raise OperationalReconciliationError("PREFIX_PROOF_LEDGER_BINDING_INVALID")
    ranges: list[dict[str, object]] = []
    cursor = 0
    for item in observation.remote_ranges:
        try:
            offset, limit, raw_digest = item.offset, item.limit, item.sha256
        except AttributeError:
            try:
                offset, limit, raw_digest = item
            except (TypeError, ValueError):
                raise OperationalReconciliationError("PREFIX_PROOF_RANGE_INVALID") from None
        if type(offset) is not int or type(limit) is not int or offset != cursor or limit <= 0:
            raise OperationalReconciliationError("PREFIX_PROOF_RANGE_INVALID")
        if isinstance(raw_digest, bytes) and len(raw_digest) == 32:
            digest = raw_digest.hex()
        elif type(raw_digest) is str and _HASH.fullmatch(raw_digest.lower()):
            digest = raw_digest.lower()
        else:
            raise OperationalReconciliationError("PREFIX_PROOF_RANGE_INVALID")
        cursor += limit
        if cursor > observation.expected_bytes:
            raise OperationalReconciliationError("PREFIX_PROOF_RANGE_INVALID")
        ranges.append({"offset": offset, "limit": limit, "sha256": digest})
    if cursor < observation.physical_prefix_bytes or not ranges:
        raise OperationalReconciliationError("PREFIX_PROOF_COVERAGE_INCOMPLETE")
    if run.get("gate") != "G8" or run.get("status") != "RUNNING":
        raise OperationalReconciliationError("PREFIX_PROOF_OUTSIDE_G8")
    origin = "REAL_CONTRACTUAL" if measurement_source == "GATEWAY_RESPONSE" else "SYNTHETIC"
    status = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
    payload = {
        "schema": "telegram-courses-s9-g8-prefix-proof-v1",
        "version": 1,
        "gate": "G8",
        "run_id": run["run_id"],
        "manifest_sha256": manifest_sha256,
        "channel_id": manifest["channel_id"],
        "identity_alias": identity_alias,
        "profile": "F",
        "expected_bytes": observation.expected_bytes,
        "physical_prefix_bytes": observation.physical_prefix_bytes,
        "local_prefix_sha256": observation.local_prefix_sha256,
        "remote_hash_ranges": ranges,
        "remote_hash_coverage_bytes": cursor,
        "verification_payload_bytes": observation.verification_payload_bytes,
        "integrity_mode": "REMOTE_HASH_REQUIRED",
        "remote_hash_origin": (
            "TELEGRAM_GET_FILE_HASHES"
            if origin == "REAL_CONTRACTUAL" else "SYNTHETIC_TEST"
        ),
        "evidence_origin": origin,
        "status": status,
        "timestamp_ns": time.time_ns(),
    }
    path = _private_run_output_path(run_root, G8_PREFIX_PROOF_FILE)
    if os.path.lexists(path):
        raise OperationalReconciliationError("PREFIX_PROOF_ALREADY_EXISTS")
    raw = canonical_bytes(payload) + b"\n"
    digest = sha256_bytes(raw)
    ids = {
        kind: _event_id(str(run["run_id"]), "G8_PREFIX", digest, kind)
        for kind in ("prepared", "persisted", "finished")
    }

    def event(kind: str, event_type: str) -> None:
        ledger.record_critical_event(
            event_type,
            details={
                "gate": "G8",
                "evidence_kind": "S6_V1_PREFIX_PROOF",
                "evidence_origin": origin,
                "identity_alias": identity_alias,
                "receipt_sha256": digest,
            },
            event_id=ids[kind],
        )

    _write_no_overwrite_json(
        path,
        payload,
        before_rename=lambda _raw: event("prepared", "RECEIPT_PREPARED"),
        after_rename=lambda _raw: event("persisted", "RECEIPT_PERSISTED"),
    )
    event("finished", "GATE_FINISHED")
    return path, digest


def _read_prefix_proof(
    run_root: Path,
    ledger_snapshot: Mapping[str, object],
    *,
    run_id: str,
    manifest_sha256: str,
) -> tuple[dict[str, object], str]:
    path = _private_run_file(run_root, G8_PREFIX_PROOF_FILE)
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    proof = _read_json(path)
    if (
        proof.get("schema") != "telegram-courses-s9-g8-prefix-proof-v1"
        or proof.get("version") != 1
        or proof.get("gate") != "G8"
        or proof.get("run_id") != run_id
        or proof.get("manifest_sha256") != manifest_sha256
        or proof.get("profile") != "F"
        or type(proof.get("channel_id")) is not int
        or proof.get("status") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        or proof.get("evidence_origin") not in {"REAL_CONTRACTUAL", "SYNTHETIC"}
        or (proof.get("status") == "PASS")
        != (proof.get("evidence_origin") == "REAL_CONTRACTUAL")
        or proof.get("integrity_mode") != "REMOTE_HASH_REQUIRED"
        or proof.get("remote_hash_origin") != (
            "TELEGRAM_GET_FILE_HASHES"
            if proof.get("evidence_origin") == "REAL_CONTRACTUAL"
            else "SYNTHETIC_TEST"
        )
        or type(proof.get("identity_alias")) is not str
        or not _ALIAS.fullmatch(str(proof.get("identity_alias")))
        or type(proof.get("expected_bytes")) is not int
        or type(proof.get("physical_prefix_bytes")) is not int
        or not 0 < proof.get("physical_prefix_bytes", 0) < proof.get("expected_bytes", 0)
        or type(proof.get("local_prefix_sha256")) is not str
        or not _HASH.fullmatch(str(proof.get("local_prefix_sha256")))
        or type(proof.get("remote_hash_ranges")) is not list
        or not proof.get("remote_hash_ranges")
        or type(proof.get("remote_hash_coverage_bytes")) is not int
        or proof.get("remote_hash_coverage_bytes", 0) < proof.get("physical_prefix_bytes", 0)
        or proof.get("remote_hash_coverage_bytes", 0) > proof.get("expected_bytes", 0)
        or type(proof.get("verification_payload_bytes")) is not int
        or proof.get("verification_payload_bytes", -1) < 0
    ):
        raise OperationalReconciliationError("PREFIX_PROOF_CONTENT_INVALID")
    cursor = 0
    for remote_range in proof["remote_hash_ranges"]:
        if type(remote_range) is not dict:
            raise OperationalReconciliationError("PREFIX_PROOF_RANGE_INVALID")
        offset = remote_range.get("offset")
        limit = remote_range.get("limit")
        digest_value = remote_range.get("sha256")
        if (
            type(offset) is not int or type(limit) is not int
            or offset != cursor or limit <= 0
            or type(digest_value) is not str or not _HASH.fullmatch(digest_value)
        ):
            raise OperationalReconciliationError("PREFIX_PROOF_RANGE_INVALID")
        cursor += limit
    if cursor != proof.get("remote_hash_coverage_bytes"):
        raise OperationalReconciliationError("PREFIX_PROOF_COVERAGE_INCOMPLETE")
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list or audit.get("quarantined") is not False:
        raise OperationalReconciliationError("PREFIX_PROOF_AUDIT_UNAVAILABLE")
    expected_ids = {
        kind: _event_id(run_id, "G8_PREFIX", digest, kind)
        for kind in ("prepared", "persisted", "finished")
    }
    found = {kind: [] for kind in expected_ids}
    for event in events:
        if type(event) is not dict:
            continue
        details = _event_details(event)
        if (
            details.get("gate") != "G8"
            or details.get("evidence_kind") != "S6_V1_PREFIX_PROOF"
            or details.get("receipt_sha256") != digest
        ):
            continue
        if event.get("event_type") == "RECEIPT_PREPARED":
            found["prepared"].append(event)
        elif event.get("event_type") == "RECEIPT_PERSISTED":
            found["persisted"].append(event)
        elif event.get("event_type") == "GATE_FINISHED":
            found["finished"].append(event)
    if any(len(rows) != 1 for rows in found.values()) or any(
        found[kind][0].get("event_id") != expected_ids[kind]
        for kind in expected_ids
    ):
        raise OperationalReconciliationError("PREFIX_PROOF_NOT_ATTESTED")
    return proof, digest


def _read_database_download(
    database_path: Path,
    download_root: Path,
    ledger: S9OperationalLedger,
    identity_alias: str,
    expected_bytes: int,
    expected_channel_id: int,
    physical_prefix_bytes: int,
    expected_range_coverage_bytes: int,
    *,
    remote_ranges: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    try:
        database_run_root = _run_root(download_root.parent)
        selected_database = _dataset_path(database_run_root, database_path)
    except GateEvidenceError:
        raise OperationalReconciliationError("RECOVERY_DATABASE_UNAVAILABLE") from None
    try:
        uri = selected_database.as_uri() + "?mode=ro"
        db = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok" or foreign_keys:
                raise OperationalReconciliationError("RECOVERY_DATABASE_INTEGRITY_FAILED")
            media_rows = db.execute(
                "SELECT id,channel_id,telegram_message_id,media_ordinal,kind,"
                "telegram_media_id,file_size_bytes FROM media_items"
            ).fetchall()
            matched = []
            for item in media_rows:
                item_alias = ledger.pseudonym(
                    f"{item['channel_id']}:{item['telegram_message_id']}:{item['media_ordinal']}"
                )
                if item_alias == identity_alias:
                    matched.append(item)
            if len(matched) != 1:
                raise OperationalReconciliationError("RECOVERY_MEDIA_IDENTITY_INVALID")
            media = matched[0]
            if (
                media["channel_id"] != expected_channel_id
                or
                media["kind"] != "DOCUMENT"
                or media["file_size_bytes"] != expected_bytes
                or not isinstance(media["telegram_media_id"], str)
                or not media["telegram_media_id"]
            ):
                raise OperationalReconciliationError("RECOVERY_MEDIA_IDENTITY_INVALID")
            rows = db.execute(
                "SELECT state,final_path,partial_path,expected_bytes,downloaded_bytes,sha256 "
                "FROM downloads WHERE media_item_id=?",
                (media["id"],),
            ).fetchall()
            if len(rows) != 1:
                raise OperationalReconciliationError("RECOVERY_DOWNLOAD_ROW_INVALID")
            download = rows[0]
            if (
                download["state"] != "DOWNLOADED"
                or download["expected_bytes"] != expected_bytes
                or download["downloaded_bytes"] != expected_bytes
                or type(download["sha256"]) is not str
                or not _HASH.fullmatch(download["sha256"])
                or type(download["partial_path"]) is not str
                or not download["partial_path"]
            ):
                raise OperationalReconciliationError("RECOVERY_DOWNLOAD_NOT_COMPLETE")
            final_path = Path(str(download["final_path"]))
            if not final_path.is_absolute() or final_path.is_symlink():
                raise OperationalReconciliationError("RECOVERY_FINAL_PATH_UNSAFE")
            final_resolved = final_path.resolve(strict=True)
            root_resolved = download_root.resolve(strict=True)
            if root_resolved not in final_resolved.parents:
                raise OperationalReconciliationError("RECOVERY_FINAL_PATH_OUTSIDE_ROOT")
            partial_path = Path(str(download["partial_path"]))
            if not partial_path.is_absolute() or partial_path.is_symlink():
                raise OperationalReconciliationError("RECOVERY_PARTIAL_PATH_UNSAFE")
            partial_resolved = partial_path.resolve(strict=False)
            if (
                root_resolved not in partial_resolved.parents
                or partial_resolved == final_resolved
            ):
                raise OperationalReconciliationError("RECOVERY_PARTIAL_PATH_OUTSIDE_ROOT")
            try:
                partial_path.lstat()
            except FileNotFoundError:
                pass
            else:
                raise OperationalReconciliationError("RECOVERY_PARTIAL_FILE_REMAINS")
            info = final_resolved.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size != expected_bytes:
                raise OperationalReconciliationError("RECOVERY_FINAL_FILE_INVALID")
            with final_resolved.open("rb") as stream:
                file_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            if file_hash != download["sha256"]:
                raise OperationalReconciliationError("RECOVERY_FINAL_HASH_MISMATCH")
            verified_ranges = 0
            cursor = 0
            for item in remote_ranges:
                offset, limit, expected_hash = (
                    item.get("offset"), item.get("limit"), item.get("sha256"),
                )
                if (
                    type(offset) is not int or type(limit) is not int
                    or type(expected_hash) is not str or not _HASH.fullmatch(expected_hash)
                    or offset != cursor or limit <= 0 or offset + limit > expected_bytes
                ):
                    raise OperationalReconciliationError("PREFIX_PROOF_RANGE_INVALID")
                with final_resolved.open("rb") as stream:
                    stream.seek(offset)
                    range_hash = hashlib.sha256()
                    remaining = limit
                    while remaining:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise OperationalReconciliationError(
                                "PREFIX_PROOF_RANGE_TRUNCATED",
                            )
                        range_hash.update(chunk)
                        remaining -= len(chunk)
                    actual = range_hash.hexdigest()
                if actual != expected_hash:
                    raise OperationalReconciliationError("PREFIX_PROOF_FINAL_RANGE_MISMATCH")
                verified_ranges += limit
                cursor += limit
            if cursor < physical_prefix_bytes or cursor != expected_range_coverage_bytes:
                raise OperationalReconciliationError("PREFIX_PROOF_COVERAGE_INCOMPLETE")
            return {
                "database_integrity": "ok",
                "final_file_bytes": expected_bytes,
                "final_file_sha256": file_hash,
                "remote_range_bytes_rechecked": verified_ranges,
                "final_path": final_resolved,
                "download_state": download["state"],
                "media_kind": media["kind"],
            }
        finally:
            db.close()
    except OperationalReconciliationError:
        raise
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        raise OperationalReconciliationError("RECOVERY_DATABASE_RECONCILIATION_FAILED") from None


def _database_file_sha256(path: Path) -> str:
    try:
        return _database_sha256(path)
    except GateEvidenceError:
        raise OperationalReconciliationError("DATABASE_FILE_UNAVAILABLE") from None


def _open_private_download_root(run_root: Path, name: str):
    if (
        type(name) is not str or not name
        or Path(name).name != name or name in {".", ".."}
    ):
        raise OperationalReconciliationError("G8_DOWNLOAD_ROOT_BINDING_INVALID")
    selected = run_root / name
    try:
        info = selected.lstat()
        resolved = selected.resolve(strict=True)
        if (
            not stat.S_ISDIR(info.st_mode)
            or selected.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or os.path.normcase(str(resolved.parent))
            != os.path.normcase(str(run_root.resolve(strict=True)))
            or os.path.normcase(str(resolved))
            != os.path.normcase(str(selected.absolute()))
        ):
            raise OperationalReconciliationError("G8_DOWNLOAD_ROOT_UNSAFE")
        guard = _open_private_directory_guard(selected)
        guard.verify(selected)
    except OperationalReconciliationError:
        raise
    except (LedgerError, OSError):
        raise OperationalReconciliationError("G8_DOWNLOAD_ROOT_UNSAFE") from None
    return selected, guard


def _validated_gate(
    run_root: Path,
    snapshot: Mapping[str, object],
    *,
    gate: str,
    run_id: str,
    manifest_sha256: str,
    reopen_g6_snapshot: bool = True,
) -> dict[str, object]:
    if gate not in GATE_RECEIPTS:
        raise OperationalReconciliationError("GATE_RECEIPT_UNSUPPORTED")
    try:
        return read_validated_gate_receipt(
            run_root,
            snapshot,
            gate,
            run_id=run_id,
            manifest_sha256=manifest_sha256,
            reopen_g6_snapshot=reopen_g6_snapshot,
        )
    except (GateEvidenceError, OSError, ValueError, TypeError):
        raise OperationalReconciliationError(f"{gate}_RECEIPT_INVALID") from None


def _validated_supervisor_receipt(
    run_root: Path,
    snapshot: Mapping[str, object],
    *,
    filename: str,
    run_id: str,
    expected_stage: str,
    expected_exit_code: int | None,
    expected_result: str,
    requires_confirmation: bool = True,
) -> tuple[dict[str, object], str]:
    path = _private_run_file(run_root, filename)
    receipt = _read_json(path)
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    interrupted = expected_result in {"INTERRUPTED", "INTERRUPTED_SYNTHETIC"}
    actual_result = receipt.get("result")
    valid_result = (
        (
            actual_result in {"TIMED_OUT", "CANCELLED"}
            and receipt.get("reason") in {
                "STAGE_TIMEOUT", "GLOBAL_DEADLINE_EXCEEDED",
                "USER_CANCELLATION_REQUESTED",
            }
            and type(receipt.get("external_exit_code")) is int
        )
        or (
            expected_result == "INTERRUPTED_SYNTHETIC"
            and actual_result == "FAILED"
            and receipt.get("reason") == "PROCESS_EXITED"
            and receipt.get("external_exit_code") == 4
        )
    ) if interrupted else actual_result == expected_result
    valid_supervisor_gate = (
        receipt.get("supervisor_offline_gate") == "BLOCKED"
        if interrupted else receipt.get("supervisor_offline_gate") == "PASS"
    )
    if (
        receipt.get("schema") != "telegram-courses-s9-supervisor-receipt-v1"
        or receipt.get("run_id") != run_id
        or receipt.get("ledger_run_id") != run_id
        or receipt.get("stage") != expected_stage
        or not valid_result
        or expected_exit_code is not None
        and receipt.get("external_exit_code") != expected_exit_code
        or receipt.get("receipt_attestation_event_id") is None
        or receipt.get("critical_audit_gate") != "PASS"
        or not valid_supervisor_gate
        or receipt.get("process_control_offline_gate") != "PASS"
        or receipt.get("memory_monitoring_offline_gate") != "PASS"
        or receipt.get("process_tree_termination_confirmed") is not True
        or requires_confirmation
        and (
            receipt.get("tty_required") is not True
            or receipt.get("tty_available") is not True
            or receipt.get("preconfirmation_prompt_signal_available") is not True
            or receipt.get("preconfirmation_release_callback_available") is not True
            or receipt.get("preconfirmation_confirmation_released") is not True
        )
    ):
        raise OperationalReconciliationError("G8_SUPERVISOR_RECEIPT_INVALID")
    events = snapshot.get("critical_audit", {}).get("events", [])
    if not isinstance(events, list):
        raise OperationalReconciliationError("G8_SUPERVISOR_AUDIT_MISSING")
    event_by_id = {
        event.get("event_id"): event for event in events if type(event) is dict
    }
    acknowledgements = receipt.get("critical_audit_acknowledgements")
    if type(acknowledgements) is not list or not acknowledgements:
        raise OperationalReconciliationError("G8_SUPERVISOR_AUDIT_ACK_MISSING")
    acknowledged_ids: set[str] = set()
    prior_sequence = 0
    stage_event_types: set[str] = set()
    for ack in acknowledgements:
        if type(ack) is not dict:
            raise OperationalReconciliationError("G8_SUPERVISOR_AUDIT_ACK_INVALID")
        event = event_by_id.get(ack.get("event_id"))
        if (
            ack.get("run_id") != run_id
            or event is None
            or event.get("event_hash") != ack.get("event_hash")
            or event.get("sequence") != ack.get("sequence")
            or type(ack.get("sequence")) is not int
            or ack["sequence"] <= prior_sequence
            or ack.get("event_id") in acknowledged_ids
        ):
            raise OperationalReconciliationError("G8_SUPERVISOR_AUDIT_ACK_INVALID")
        acknowledged_ids.add(str(ack["event_id"]))
        prior_sequence = ack["sequence"]
        try:
            details = _event_details(event)
        except OperationalReconciliationError:
            raise OperationalReconciliationError("G8_SUPERVISOR_AUDIT_ACK_INVALID") from None
        if details.get("stage") == expected_stage:
            stage_event_types.add(str(event.get("event_type")))
    if not {
        "RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "GATE_STARTED",
        "CHILD_PROCESS_CONFIRMED", "SUPERVISOR_RUN_FINISHED",
    }.issubset(stage_event_types):
        raise OperationalReconciliationError("G8_SUPERVISOR_STAGE_AUDIT_INCOMPLETE")
    for event_type, event_id_field in (
        ("RECEIPT_PREPARED", "receipt_prepared_event_id"),
        ("RECEIPT_PERSISTED", "receipt_attestation_event_id"),
    ):
        event = event_by_id.get(receipt.get(event_id_field))
        if (
            event is None or event.get("event_type") != event_type
            or _event_details(event).get("receipt_sha256") != digest
        ):
            raise OperationalReconciliationError("G8_SUPERVISOR_RECEIPT_UNATTESTED")
    finished = [
        event for event in events
        if type(event) is dict
        and event.get("event_type") == "SUPERVISOR_RUN_FINISHED"
        and event.get("event_id") in acknowledged_ids
        and _event_details(event).get("stage") == expected_stage
    ]
    if len(finished) != 1:
        raise OperationalReconciliationError("G8_SUPERVISOR_RECEIPT_UNATTESTED")
    finished_details = _event_details(finished[0])
    if (
        finished_details.get("result") != actual_result
        or finished_details.get("exit_code") != receipt.get("external_exit_code")
        or finished_details.get("tree_confirmed") is not True
    ):
        raise OperationalReconciliationError("G8_SUPERVISOR_RECEIPT_UNATTESTED")
    return receipt, digest


def _origin_chain(
    g0: Mapping[str, object],
    gates: Sequence[Mapping[str, object]],
    proof: Mapping[str, object] | None = None,
) -> str:
    origins = [
        "REAL_CONTRACTUAL"
        if g0.get("evidence_origin") == "HUMAN_INTERACTIVE"
        else str(g0.get("evidence_origin")),
        *(str(gate.get("evidence_origin")) for gate in gates),
    ]
    if proof is not None:
        origins.append(str(proof.get("evidence_origin")))
    if all(origin == "REAL_CONTRACTUAL" for origin in origins):
        return "REAL_CONTRACTUAL"
    if all(origin == "SYNTHETIC" for origin in origins):
        return "SYNTHETIC"
    raise OperationalReconciliationError("G8_PROVENANCE_MIXED")


def _g8_predecessor_paths(
    run_root: Path,
    predecessors: Mapping[str, Mapping[str, object]],
) -> dict[str, Path]:
    paths = {
        gate: _private_run_file(run_root, GATE_RECEIPTS[gate])
        for gate in ("G0", "G1", "G2", "G3", "G6")
    }
    for index in (1, 2):
        paths[f"G5_F_{index}"] = _private_run_file(
            run_root, g5_queue_receipt_filename("F", index),
        )
    g7 = predecessors.get("G7")
    if type(g7) is not dict or type(g7.get("sync_index")) is not int:
        raise OperationalReconciliationError("G8_G7_RECEIPT_INVALID")
    paths["G7"] = _private_run_file(
        run_root, _g7_receipt_filename(int(g7["sync_index"])),
    )
    return paths


def _g8_predecessor_hashes(
    run_root: Path,
    predecessors: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, str], str]:
    paths = _g8_predecessor_paths(run_root, predecessors)
    hashes: dict[str, str] = {}
    for gate, path in paths.items():
        raw = path.read_bytes()
        receipt = _read_json(path)
        if (
            receipt.get("gate") != ("G5" if gate.startswith("G5_") else gate)
            or receipt.get("run_id") != predecessors["G0"].get("run_id")
            or receipt.get("manifest_sha256") != predecessors["G0"].get("manifest_sha256")
        ):
            raise OperationalReconciliationError("G8_PREDECESSOR_RECEIPT_BINDING_INVALID")
        hashes[gate] = sha256_bytes(raw)
    aggregate = sha256_bytes(canonical_bytes(hashes))
    return hashes, aggregate


def _g8_baseline_event_id(run_id: str, manifest_sha256: str) -> str:
    return hashlib.sha256(
        f"{run_id}:G8_DATABASE_BASELINE:{manifest_sha256}".encode("ascii"),
    ).hexdigest()[:32]


def record_g8_database_baseline(
    run_directory: str | Path,
    ledger: S9OperationalLedger,
    *,
    database_sha256_before: str,
    database_file: str,
    download_root: str,
    manifest_sha256: str,
    evidence_origin: Literal["REAL_CONTRACTUAL", "SYNTHETIC"],
    predecessors: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Attest the validated G0-G7/DB baseline before any G8 write occurs."""
    if (
        not _HASH.fullmatch(database_sha256_before)
        or not _HASH.fullmatch(manifest_sha256)
        or evidence_origin not in {"REAL_CONTRACTUAL", "SYNTHETIC"}
        or type(database_file) is not str
        or not database_file
        or Path(database_file).name != database_file
        or database_file in {".", ".."}
        or type(download_root) is not str
        or not download_root
        or Path(download_root).name != download_root
        or download_root in {".", ".."}
    ):
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_INVALID")
    root = _run_root(run_directory)
    snapshot = ledger.snapshot()
    run_id = str(snapshot["run"]["run_id"])
    hashes, predecessor_hash = _g8_predecessor_hashes(root, predecessors)
    g6 = predecessors.get("G6")
    g7 = predecessors.get("G7")
    if (
        type(g6) is not dict or type(g7) is not dict
        or g6.get("database_file") != g7.get("database_file")
        or g7.get("database_sha256_before") != g6.get("database_sha256")
        or g7.get("database_sha256_after") != database_sha256_before
        or g6.get("database_file") != database_file
        or g7.get("database_file") != database_file
        or g7.get("evidence_origin") != evidence_origin
        or g6.get("evidence_origin") != evidence_origin
    ):
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_BINDING_INVALID")
    for receipt_key in ("G5_F_01", "G5_F_02"):
        queue_receipt = predecessors.get(receipt_key)
        if (
            type(queue_receipt) is not dict
            or queue_receipt.get("database_file") != database_file
            or queue_receipt.get("download_root") != download_root
        ):
            raise OperationalReconciliationError("G8_DATABASE_BASELINE_BINDING_INVALID")
    details: dict[str, object] = {
        "gate": "G8",
        "stage": "g8-interruption",
        "status": "PASS",
        "evidence_origin": evidence_origin,
        "manifest_sha256": manifest_sha256,
        "database_file": database_file,
        "download_root": download_root,
        "database_sha256_before": database_sha256_before,
        "g6_receipt_sha256": hashes["G6"],
        "g7_receipt_sha256": hashes["G7"],
        "predecessor_receipts_sha256": predecessor_hash,
    }
    event_id = _g8_baseline_event_id(run_id, manifest_sha256)
    ledger.record_critical_event(
        "G8_DATABASE_BASELINE", details=details, event_id=event_id,
    )
    return details


def read_g8_database_baseline(
    run_directory: str | Path,
    ledger_snapshot: Mapping[str, object],
    *,
    run_id: str,
    manifest_sha256: str,
) -> dict[str, object]:
    """Reopen the pre-G8 receipt hashes without requiring the DB to be unchanged."""
    root = _run_root(run_directory)
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list or audit.get("quarantined") is not False:
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_AUDIT_UNAVAILABLE")
    matches: list[tuple[dict[str, object], dict[str, object]]] = []
    for event in events:
        if type(event) is not dict or event.get("event_type") != "G8_DATABASE_BASELINE":
            continue
        details = _event_details(event)
        if details.get("gate") == "G8":
            matches.append((event, details))
    if len(matches) != 1:
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_MISSING")
    event, details = matches[0]
    run = ledger_snapshot.get("run")
    if type(run) is not dict or run.get("run_id") != run_id:
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_RUN_INVALID")
    expected_origin = details.get("evidence_origin")
    if expected_origin not in {"REAL_CONTRACTUAL", "SYNTHETIC"}:
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_ORIGIN_INVALID")
    if (
        event.get("event_id") != _g8_baseline_event_id(run_id, manifest_sha256)
        or details.get("stage") != "g8-interruption"
        or details.get("status") != "PASS"
        or details.get("manifest_sha256") != manifest_sha256
        or type(details.get("database_sha256_before")) is not str
        or not _HASH.fullmatch(str(details.get("database_sha256_before")))
    ):
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_CONTENT_INVALID")
    manifest, current_manifest_sha256, _scope_sha256 = load_approved_manifest(root)
    if current_manifest_sha256 != manifest_sha256:
        raise OperationalReconciliationError("G8_DATABASE_BASELINE_MANIFEST_CHANGED")
    # Rehash all pre-G8 receipt files and verify the baseline's aggregate.
    predecessor_files: dict[str, Path] = {
        gate: _private_run_file(root, GATE_RECEIPTS[gate])
        for gate in ("G0", "G1", "G2", "G3", "G6")
    }
    for index in (1, 2):
        predecessor_files[f"G5_F_{index}"] = _private_run_file(
            root, g5_queue_receipt_filename("F", index),
        )
    g7_versioned = [
        _private_run_file(root, _g7_receipt_filename(index))
        for index in (1, 2)
        if os.path.lexists(root / _g7_receipt_filename(index))
    ]
    g7_path = (
        g7_versioned[-1]
        if g7_versioned
        else _private_run_file(root, GATE_RECEIPTS["G7"])
    )
    predecessor_files["G7"] = g7_path
    receipt_hashes: dict[str, str] = {}
    receipts: dict[str, dict[str, object]] = {}
    for name, path in predecessor_files.items():
        receipt = _read_json(path)
        expected_gate = "G5" if name.startswith("G5_") else name
        if (
            receipt.get("gate") != expected_gate
            or receipt.get("run_id") != run_id
            or receipt.get("manifest_sha256") != manifest_sha256
        ):
            raise OperationalReconciliationError("G8_PREDECESSOR_RECEIPT_BINDING_INVALID")
        receipts[name] = receipt
        receipt_hashes[name] = sha256_bytes(path.read_bytes())
    origin = str(expected_origin)
    expected_gate_status = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
    try:
        for index in (1, 2):
            validated_queue = read_validated_g5_queue_receipt(
                root,
                ledger_snapshot,
                run_id=run_id,
                manifest_sha256=manifest_sha256,
                profile="F",
                pass_index=index,
            )
            key = f"G5_F_{index}"
            if validated_queue != receipts[key]:
                raise OperationalReconciliationError("G8_F_QUEUE_RECEIPT_CHANGED")
    except (GateEvidenceError, OSError, TypeError, ValueError):
        raise OperationalReconciliationError("G8_F_QUEUE_RECEIPT_INVALID") from None
    if (
        receipts["G0"].get("status") != (
            "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
        )
        or receipts["G0"].get("evidence_origin") != (
            "HUMAN_INTERACTIVE" if origin == "REAL_CONTRACTUAL" else "SYNTHETIC"
        )
        or origin == "REAL_CONTRACTUAL"
        and receipts["G0"].get("confirmation_source") != "INTERACTIVE_TTY"
        or origin == "SYNTHETIC"
        and receipts["G0"].get("confirmation_source") != "SYNTHETIC_TEST"
        or any(
            receipts[name].get("evidence_origin") != origin
            or receipts[name].get("status") != expected_gate_status
            for name in ("G1", "G2", "G3", "G6", "G7", "G5_F_1", "G5_F_2")
        )
        or receipts["G6"].get("database_file") != receipts["G7"].get("database_file")
        or receipts["G6"].get("database_file") != details.get("database_file")
        or any(
            receipts[name].get("download_root") != details.get("download_root")
            for name in ("G5_F_1", "G5_F_2")
        )
        or receipts["G7"].get("database_sha256_after") != details.get("database_sha256_before")
        or receipt_hashes["G6"] != details.get("g6_receipt_sha256")
        or receipt_hashes["G7"] != details.get("g7_receipt_sha256")
        or sha256_bytes(canonical_bytes(receipt_hashes))
        != details.get("predecessor_receipts_sha256")
        or receipts["G7"].get("channel_id") != manifest.get("channel_id")
        or any(
            receipts[name].get("channel_id") != manifest.get("channel_id")
            for name in ("G0", "G1", "G2", "G3", "G6", "G7", "G5_F_1", "G5_F_2")
        )
    ):
        raise OperationalReconciliationError("G8_PREDECESSOR_BASELINE_MISMATCH")
    return {
        **details,
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "database_file": details["database_file"],
        "download_root": details["download_root"],
        "g7_receipt_sha256": receipt_hashes["G7"],
        "g6_receipt_sha256": receipt_hashes["G6"],
        "evidence_origin": origin,
        "predecessor_receipts_sha256": sha256_bytes(canonical_bytes(receipt_hashes)),
    }


def _audit_gate_status(
    snapshot: Mapping[str, object], gate: str,
) -> tuple[str, str | None]:
    audit = snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list:
        return "UNKNOWN", None
    matches: list[dict[str, object]] = []
    for event in events:
        if type(event) is not dict or event.get("event_type") not in {
            "GATE_STATE_UPDATED", "RUN_TERMINAL",
        }:
            continue
        details = _event_details(event)
        if details.get("gate") == gate:
            matches.append(details)
    if not matches:
        return "UNKNOWN", None
    return str(matches[-1].get("result", "UNKNOWN")), str(matches[-1].get("cause"))


def _g8_source_evidence(
    run_root: Path,
    database_path: Path,
    download_root: Path,
    ledger: S9OperationalLedger,
) -> tuple[dict[str, object], str, dict[str, object], str]:
    manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(run_root)
    snapshot = ledger.snapshot()
    run_id = str(snapshot["run"]["run_id"])
    g0 = _validated_gate(
        run_root, snapshot, gate="G0", run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    g1 = _validated_gate(
        run_root, snapshot, gate="G1", run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    g2 = _validated_gate(
        run_root, snapshot, gate="G2", run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    g3 = _validated_gate(
        run_root, snapshot, gate="G3", run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    g6 = _validated_gate(
        run_root, snapshot, gate="G6", run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    if (
        g0.get("channel_id") != manifest.get("channel_id")
        or g1.get("channel_id") != manifest.get("channel_id")
        or g2.get("channel_id") != manifest.get("channel_id")
        or g3.get("channel_id") != manifest.get("channel_id")
        or g6.get("channel_id") != manifest.get("channel_id")
        or g6.get("database_file") != database_path.name
        or not download_root.is_absolute()
        or download_root.parent.resolve(strict=True) != run_root.resolve(strict=True)
    ):
        raise OperationalReconciliationError("G8_RUN_CHANNEL_STORAGE_BINDING_INVALID")
    try:
        f_receipts = [
            read_validated_g5_queue_receipt(
                run_root,
                snapshot,
                run_id=run_id,
                manifest_sha256=manifest_sha256,
                profile="F",
                pass_index=index,
            )
            for index in (1, 2)
        ]
    except (GateEvidenceError, OSError, ValueError, TypeError):
        raise OperationalReconciliationError("G8_F_QUEUE_RECEIPTS_INVALID") from None
    if any(
        receipt.get("channel_id") != manifest.get("channel_id")
        or receipt.get("database_file") != database_path.name
        or receipt.get("download_root") != download_root.name
        for receipt in f_receipts
    ):
        raise OperationalReconciliationError("G8_F_QUEUE_BINDING_INVALID")
    origin = _origin_chain(g0, [g1, g2, g3, g6, *f_receipts])
    expected_status = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
    if any(
        receipt.get("status") != expected_status
        or receipt.get("evidence_origin") != origin
        for receipt in f_receipts
    ):
        raise OperationalReconciliationError("G8_F_QUEUE_NOT_ELIGIBLE")
    g7_status, _g7_cause = _audit_gate_status(snapshot, "G7")
    try:
        g7 = _validated_gate(
            run_root, snapshot, gate="G7", run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
    except OperationalReconciliationError:
        raise OperationalReconciliationError("G8_G7_NOT_RECONCILED") from None
    if g7_status == "UNKNOWN":
        g7_status = str(g7.get("status"))
    elif g7.get("status") != g7_status:
        raise OperationalReconciliationError("G8_G7_LEDGER_RECEIPT_MISMATCH")
    if g6.get("status") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}:
        raise OperationalReconciliationError("G8_G6_NOT_ELIGIBLE")
    expected_g7 = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
    if g7_status != expected_g7:
        raise OperationalReconciliationError("G8_G7_NOT_ELIGIBLE")
    return manifest, manifest_sha256, {
        "G0": g0, "G1": g1, "G2": g2, "G3": g3,
        "G5_F_01": f_receipts[0], "G5_F_02": f_receipts[1],
        "G6": g6,
        "G7": g7,
        "G7_STATUS": {"status": g7_status},
    }, origin


def reconcile_g8_operational(
    run_directory: str | Path,
    database_path: str | Path,
    download_root: str | Path,
) -> OperationalGateResult:
    """Reopen G8 interruption/recovery evidence and persist an operational result.

    G8 requires the preceding G7 profile to be eligible. A G6 no-M partial
    remains visible to G9 without manufacturing a G8 result.
    """
    run_root = _run_root(run_directory)
    db_path = Path(database_path)
    root = Path(download_root)
    ledger = S9OperationalLedger(run_root / "operational-ledger.sqlite3")
    manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(run_root)
    snapshot = ledger.snapshot()
    run_id = str(snapshot["run"]["run_id"])
    if os.path.lexists(run_root / G8_OPERATIONAL_RECEIPT_FILE):
        receipt, _digest = _read_operational_receipt(
            run_root, snapshot, gate="G8", run_id=run_id,
            manifest_sha256=manifest_sha256,
            filename=G8_OPERATIONAL_RECEIPT_FILE,
        )
        transition = validate_g8_database_transition(
            run_root,
            snapshot,
            run_id=run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            database_path=db_path,
        )
        receipt_evidence = receipt.get("evidence")
        if (
            transition.get("status") != receipt.get("status")
            or type(receipt_evidence) is not dict
            or receipt_evidence.get("download_root") != root.name
        ):
            raise OperationalReconciliationError("G8_OPERATIONAL_REOPEN_MISMATCH")
        return _gate_result_from_receipt(receipt, run_root / G8_OPERATIONAL_RECEIPT_FILE)
    if snapshot["critical_audit"]["quarantined"]:
        raise OperationalReconciliationError("LEDGER_AUDIT_QUARANTINED")

    evidence: dict[str, object] = {}
    reason = "G8_RECOVERY_RECONCILED"
    origin = "UNKNOWN"
    status = "BLOCKED"
    try:
        baseline = read_g8_database_baseline(
            run_root,
            snapshot,
            run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        origin = str(baseline["evidence_origin"])
        if baseline.get("database_file") != db_path.name:
            raise OperationalReconciliationError("G8_DATABASE_FILE_BINDING_INVALID")
        interruption, interruption_hash = _validated_supervisor_receipt(
            run_root,
            snapshot,
            filename=G8_INTERRUPTION_SUPERVISOR_FILE,
            run_id=run_id,
            expected_stage="queue_f",
            expected_exit_code=None,
            expected_result=(
                "INTERRUPTED"
                if origin == "REAL_CONTRACTUAL"
                else "INTERRUPTED_SYNTHETIC"
            ),
            requires_confirmation=True,
        )
        recovery, recovery_hash = _validated_supervisor_receipt(
            run_root,
            snapshot,
            filename=G8_RECOVERY_SUPERVISOR_FILE,
            run_id=run_id,
            expected_stage="queue_f",
            expected_exit_code=0,
            expected_result="COMPLETED",
            requires_confirmation=True,
        )
        proof, proof_hash = _read_prefix_proof(
            run_root,
            snapshot,
            run_id=run_id,
            manifest_sha256=manifest_sha256,
        )
        if proof.get("evidence_origin") != origin:
            raise OperationalReconciliationError("G8_PREFIX_PROOF_PROVENANCE_MISMATCH")
        if proof.get("channel_id") != manifest.get("channel_id"):
            raise OperationalReconciliationError("G8_PREFIX_PROOF_CHANNEL_MISMATCH")
        alias = proof.get("identity_alias")
        if type(alias) is not str or not _ALIAS.fullmatch(alias):
            raise OperationalReconciliationError("G8_MEDIA_ALIAS_INVALID")
        meta = snapshot["run"]
        media = [row for row in snapshot["media"] if row.get("alias") == alias]
        attempt_events: list[dict[str, object]] = []
        interruption_events: list[dict[str, object]] = []
        for event in snapshot["critical_audit"]["events"]:
            if event.get("event_type") not in {"ATTEMPT_STARTED", "INTERRUPTION_RECORDED"}:
                continue
            details = _event_details(event)
            if details.get("alias") == alias:
                if event.get("event_type") == "ATTEMPT_STARTED":
                    attempt_events.append(details)
                else:
                    interruption_events.append(details)
        if (
            len(media) != 1
            or media[0].get("profile") != "F"
            or media[0].get("kind") != "DOCUMENT"
            or media[0].get("expected") != proof.get("expected_bytes")
            or media[0].get("attempts") != 2
            or meta.get("interruptions") != 1
            or meta.get("recoveries") != 1
            or len(interruption_events) != 1
            or len(attempt_events) != 2
            or sum(event.get("recovery") is True for event in attempt_events) != 1
            or sum(event.get("recovery") is False for event in attempt_events) != 1
            or type(interruption_events[0].get("part_bytes")) is not int
            or interruption_events[0].get("part_bytes") != proof.get("physical_prefix_bytes")
            or interruption_events[0].get("expected_bytes") != proof.get("expected_bytes")
            or proof.get("physical_prefix_bytes", 0) <= 0
            or proof.get("physical_prefix_bytes", 0) >= proof.get("expected_bytes", 0)
        ):
            raise OperationalReconciliationError("G8_LEDGER_INTERRUPTION_RECOVERY_MISMATCH")
        database_evidence = _read_database_download(
            db_path,
            root,
            ledger,
            alias,
            int(proof["expected_bytes"]),
            int(manifest["channel_id"]),
            int(proof["physical_prefix_bytes"]),
            int(proof["remote_hash_coverage_bytes"]),
            remote_ranges=proof["remote_hash_ranges"],
        )
        database_sha256_after = _database_file_sha256(db_path)
        budgets = snapshot["budgets"]["F"]
        if (
            budgets["reserved"] != 0
            or budgets["consumed"] > budgets["cap"]
            or budgets["observed"] < proof["verification_payload_bytes"]
            or snapshot["aggregate_remaining"] < 0
        ):
            raise OperationalReconciliationError("G8_BUDGET_NOT_RECONCILED")
        result_status = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
        status = result_status
        reason = "G8_F_RECOVERY_RECONCILED"
        evidence = {
            "profile": "F",
            "download_root": root.name,
            "identity_alias": alias,
            "interruption_count": 1,
            "recovery_count": 1,
            "attempt_count": 2,
            "interrupted_prefix_bytes": interruption_events[0]["part_bytes"],
            "budget_uncertain_bytes_preserved": budgets["uncertain"],
            "interruption_supervisor_receipt_file": G8_INTERRUPTION_SUPERVISOR_FILE,
            "interruption_supervisor_receipt_sha256": interruption_hash,
            "recovery_supervisor_receipt_file": G8_RECOVERY_SUPERVISOR_FILE,
            "recovery_supervisor_receipt_sha256": recovery_hash,
            "prefix_proof_file": G8_PREFIX_PROOF_FILE,
            "prefix_proof_sha256": proof_hash,
            "remote_hash_policy": "REMOTE_HASH_REQUIRED",
            "remote_prefix_bytes": proof["physical_prefix_bytes"],
            "remote_hash_coverage_bytes": proof["remote_hash_coverage_bytes"],
            "remote_hash_origin": proof["remote_hash_origin"],
            "database_integrity": database_evidence["database_integrity"],
            "final_file_bytes": database_evidence["final_file_bytes"],
            "final_file_sha256": database_evidence["final_file_sha256"],
            "remote_range_bytes_rechecked": database_evidence["remote_range_bytes_rechecked"],
            "database_file": db_path.name,
            "database_sha256_before": baseline["database_sha256_before"],
            "database_sha256_after": database_sha256_after,
            "g7_receipt_sha256": baseline["g7_receipt_sha256"],
            "g6_receipt_sha256": baseline["g6_receipt_sha256"],
            "predecessor_receipts_sha256": baseline["predecessor_receipts_sha256"],
            "ledger_f_budget": {
                "cap": budgets["cap"], "consumed": budgets["consumed"],
                "reserved": budgets["reserved"], "uncertain": budgets["uncertain"],
            },
            "real_evidence_status": (
                "REAL_CONTRACTUAL_PASS"
                if origin == "REAL_CONTRACTUAL" else "REAL_EVIDENCE_PENDING"
            ),
            "g7_real_eligibility": (
                baseline.get("evidence_origin") == "REAL_CONTRACTUAL"
                if origin == "REAL_CONTRACTUAL" else False
            ),
        }
    except (OperationalReconciliationError, GateEvidenceError, LedgerError, OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        status = "BLOCKED"
        reason = str(error) if isinstance(error, OperationalReconciliationError) else "G8_EVIDENCE_RECONCILIATION_FAILED"
        evidence = {"failure_category": reason}
        try:
            proof, _proof_digest = _read_prefix_proof(
                run_root, snapshot, run_id=run_id, manifest_sha256=manifest_sha256,
            )
            origin = str(proof.get("evidence_origin", "SYNTHETIC"))
        except (OperationalReconciliationError, OSError, ValueError, TypeError, KeyError):
            try:
                baseline = read_g8_database_baseline(
                    run_root, snapshot, run_id=run_id,
                    manifest_sha256=manifest_sha256,
                )
                origin = str(baseline.get("evidence_origin", "UNKNOWN"))
            except (OperationalReconciliationError, OSError, ValueError, TypeError, KeyError):
                origin = "UNKNOWN"

    payload = {
        "schema": "telegram-courses-s9-g8-operational-receipt-v1",
        "version": 1,
        "gate": "G8",
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "channel_id": manifest.get("channel_id"),
        "status": status,
        "reason": reason,
        "evidence_origin": origin,
        "real_evidence_status": (
            "REAL_CONTRACTUAL_PASS"
            if status == "PASS" and origin == "REAL_CONTRACTUAL"
            else "REAL_EVIDENCE_PENDING"
        ),
        "ledger_result": status,
        "evidence": evidence,
    }
    path, _digest = _persist_receipt(
        run_root, ledger, payload, filename=G8_OPERATIONAL_RECEIPT_FILE,
        before_rename_checkpoint=ledger.checkpoint,
    )
    ledger.update_execution(
        gate="G8",
        status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=int(ledger.snapshot()["run"]["deadline_ns"]),
        process_state="EXITED",
        result=status,
        cause="NONE" if status in {"PASS", "OFFLINE_SYNTHETIC_PASS"} else "OTHER",
    )
    return OperationalGateResult(
        "G8", status, reason, origin,
        str(payload["real_evidence_status"]), run_id, manifest_sha256,
        evidence, path,
    )


def _gate_result_from_receipt(receipt: Mapping[str, object], path: Path) -> OperationalGateResult:
    return OperationalGateResult(
        str(receipt["gate"]),
        str(receipt["status"]),
        str(receipt.get("reason", "REOPENED")),
        str(receipt["evidence_origin"]),
        str(receipt.get("real_evidence_status", "REAL_EVIDENCE_PENDING")),
        str(receipt["run_id"]),
        str(receipt["manifest_sha256"]),
        receipt.get("evidence", {}) if type(receipt.get("evidence")) is dict else {},
        path,
    )


def validate_g8_database_transition(
    run_directory: str | Path,
    ledger_snapshot: Mapping[str, object],
    *,
    run_id: str,
    manifest: Mapping[str, object],
    manifest_sha256: str,
    database_path: str | Path,
) -> dict[str, object]:
    """Validate G8's bounded DB delta without recursively reopening G7."""
    run_root = _run_root(run_directory)
    selected_database = Path(database_path)
    manifest_on_disk, current_manifest_sha, _scope_sha256 = load_approved_manifest(run_root)
    if (
        current_manifest_sha != manifest_sha256
        or dict(manifest_on_disk) != dict(manifest)
        or not selected_database.is_absolute()
        or selected_database.parent.resolve(strict=True) != run_root.resolve(strict=True)
    ):
        raise OperationalReconciliationError("G8_DATABASE_TRANSITION_BINDING_INVALID")
    run = ledger_snapshot.get("run")
    if type(run) is not dict or run.get("run_id") != run_id:
        raise OperationalReconciliationError("G8_DATABASE_TRANSITION_RUN_INVALID")
    baseline = read_g8_database_baseline(
        run_root,
        ledger_snapshot,
        run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    try:
        selected_database = _dataset_path(run_root, selected_database)
    except GateEvidenceError:
        raise OperationalReconciliationError("DATABASE_FILE_UNAVAILABLE") from None
    if baseline.get("database_file") != selected_database.name:
        raise OperationalReconciliationError("G8_DATABASE_FILE_BINDING_INVALID")
    receipt, receipt_hash = _read_operational_receipt(
        run_root,
        ledger_snapshot,
        gate="G8",
        run_id=run_id,
        manifest_sha256=manifest_sha256,
        filename=G8_OPERATIONAL_RECEIPT_FILE,
    )
    origin = str(baseline["evidence_origin"])
    expected_status = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
    evidence = receipt.get("evidence")
    if (
        receipt.get("status") != expected_status
        or receipt.get("ledger_result") != expected_status
        or receipt.get("evidence_origin") != origin
        or receipt.get("channel_id") != manifest.get("channel_id")
        or type(evidence) is not dict
        or evidence.get("profile") != "F"
        or evidence.get("database_file") != selected_database.name
        or evidence.get("download_root") != baseline.get("download_root")
        or evidence.get("database_sha256_before") != baseline.get("database_sha256_before")
        or evidence.get("g7_receipt_sha256") != baseline.get("g7_receipt_sha256")
        or evidence.get("g6_receipt_sha256") != baseline.get("g6_receipt_sha256")
        or evidence.get("predecessor_receipts_sha256")
        != baseline.get("predecessor_receipts_sha256")
        or evidence.get("interruption_count") != 1
        or evidence.get("recovery_count") != 1
        or evidence.get("attempt_count") != 2
        or evidence.get("remote_hash_policy") != "REMOTE_HASH_REQUIRED"
        or evidence.get("g7_real_eligibility") != (origin == "REAL_CONTRACTUAL")
        or type(evidence.get("database_sha256_after")) is not str
        or not _HASH.fullmatch(str(evidence.get("database_sha256_after")))
    ):
        raise OperationalReconciliationError("G8_DATABASE_TRANSITION_RECEIPT_INVALID")
    expected_interruption = (
        "INTERRUPTED" if origin == "REAL_CONTRACTUAL" else "INTERRUPTED_SYNTHETIC"
    )
    _interruption, interruption_hash = _validated_supervisor_receipt(
        run_root,
        ledger_snapshot,
        filename=G8_INTERRUPTION_SUPERVISOR_FILE,
        run_id=run_id,
        expected_stage="queue_f",
        expected_exit_code=None,
        expected_result=expected_interruption,
    )
    _recovery, recovery_hash = _validated_supervisor_receipt(
        run_root,
        ledger_snapshot,
        filename=G8_RECOVERY_SUPERVISOR_FILE,
        run_id=run_id,
        expected_stage="queue_f",
        expected_exit_code=0,
        expected_result="COMPLETED",
    )
    proof, proof_hash = _read_prefix_proof(
        run_root,
        ledger_snapshot,
        run_id=run_id,
        manifest_sha256=manifest_sha256,
    )
    if (
        proof.get("evidence_origin") != origin
        or proof.get("channel_id") != manifest.get("channel_id")
        or proof_hash != evidence.get("prefix_proof_sha256")
        or evidence.get("interruption_supervisor_receipt_sha256") != interruption_hash
        or evidence.get("recovery_supervisor_receipt_sha256") != recovery_hash
    ):
        raise OperationalReconciliationError("G8_DATABASE_TRANSITION_PROOF_INVALID")
    alias = proof.get("identity_alias")
    if type(alias) is not str or not _ALIAS.fullmatch(alias):
        raise OperationalReconciliationError("G8_MEDIA_ALIAS_INVALID")
    ledger = S9OperationalLedger(run_root / "operational-ledger.sqlite3")
    media = [row for row in ledger_snapshot.get("media", []) if row.get("alias") == alias]
    attempts: list[dict[str, object]] = []
    interruptions: list[dict[str, object]] = []
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list or audit.get("quarantined") is not False:
        raise OperationalReconciliationError("G8_LEDGER_AUDIT_INVALID")
    for event in events:
        if type(event) is not dict or event.get("event_type") not in {
            "ATTEMPT_STARTED", "INTERRUPTION_RECORDED",
        }:
            continue
        details = _event_details(event)
        if details.get("alias") == alias:
            (attempts if event.get("event_type") == "ATTEMPT_STARTED" else interruptions).append(details)
    run_meta = ledger_snapshot["run"]
    budget = ledger_snapshot["budgets"]["F"]
    if (
        len(media) != 1 or media[0].get("profile") != "F"
        or media[0].get("expected") != proof.get("expected_bytes")
        or media[0].get("attempts") != 2
        or run_meta.get("interruptions") != 1 or run_meta.get("recoveries") != 1
        or len(attempts) != 2
        or sum(item.get("recovery") is True for item in attempts) != 1
        or sum(item.get("recovery") is False for item in attempts) != 1
        or len(interruptions) != 1
        or interruptions[0].get("part_bytes") != proof.get("physical_prefix_bytes")
        or interruptions[0].get("expected_bytes") != proof.get("expected_bytes")
        or budget.get("reserved") != 0
        or budget.get("consumed", 0) > budget.get("cap", -1)
        or budget.get("observed", 0) < proof.get("verification_payload_bytes", 0)
        or ledger_snapshot.get("aggregate_remaining", -1) < 0
    ):
        raise OperationalReconciliationError("G8_LEDGER_RECOVERY_STATE_INVALID")
    download_root_name = evidence.get("download_root")
    if (
        type(download_root_name) is not str
        or not download_root_name
        or Path(download_root_name).name != download_root_name
        or download_root_name in {".", ".."}
    ):
        raise OperationalReconciliationError("G8_DOWNLOAD_ROOT_BINDING_INVALID")
    selected_download_root, download_root_guard = _open_private_download_root(
        run_root, download_root_name,
    )
    try:
        physical = _read_database_download(
            selected_database,
            selected_download_root,
            ledger,
            alias,
            int(proof["expected_bytes"]),
            int(manifest["channel_id"]),
            int(proof["physical_prefix_bytes"]),
            int(proof["remote_hash_coverage_bytes"]),
            remote_ranges=proof["remote_hash_ranges"],
        )
    finally:
        download_root_guard.close()
    database_sha256_after = _database_file_sha256(selected_database)
    if (
        database_sha256_after != evidence.get("database_sha256_after")
        or physical.get("database_integrity") != "ok"
        or physical.get("final_file_bytes") != evidence.get("final_file_bytes")
        or physical.get("final_file_sha256") != evidence.get("final_file_sha256")
        or physical.get("remote_range_bytes_rechecked")
        != evidence.get("remote_range_bytes_rechecked")
        or evidence.get("remote_prefix_bytes") != proof.get("physical_prefix_bytes")
        or evidence.get("remote_hash_coverage_bytes")
        != proof.get("remote_hash_coverage_bytes")
        or evidence.get("remote_hash_origin") != proof.get("remote_hash_origin")
    ):
        raise OperationalReconciliationError("G8_DATABASE_TRANSITION_AFTER_HASH_MISMATCH")
    return {
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "database_file": selected_database.name,
        "database_sha256_before": baseline["database_sha256_before"],
        "database_sha256_after": database_sha256_after,
        "g7_receipt_sha256": baseline["g7_receipt_sha256"],
        "g6_receipt_sha256": baseline["g6_receipt_sha256"],
        "predecessor_receipts_sha256": baseline["predecessor_receipts_sha256"],
        "g8_operational_receipt_sha256": receipt_hash,
        "evidence_origin": origin,
        "status": expected_status,
    }


def _gate_result(
    gate: str,
    receipt: Mapping[str, object],
    path: Path | None = None,
) -> OperationalGateResult:
    return OperationalGateResult(
        gate,
        str(receipt.get("status", "UNKNOWN")),
        str(receipt.get("reason", "UNKNOWN")),
        str(receipt.get("evidence_origin", "UNKNOWN")),
        str(receipt.get("real_evidence_status", "REAL_EVIDENCE_PENDING")),
        str(receipt.get("run_id", "")),
        str(receipt.get("manifest_sha256", "")),
        receipt,
        path,
    )


def _g9_gate_inventory(
    run_root: Path,
    snapshot: Mapping[str, object],
    manifest: Mapping[str, object],
    manifest_sha256: str,
    database_path: Path,
    download_root: Path,
) -> tuple[list[OperationalGateResult], dict[str, object]]:
    run_id = str(snapshot["run"]["run_id"])
    inventory: list[OperationalGateResult] = []
    receipts: dict[str, object] = {}
    g8_receipt_present = os.path.lexists(run_root / G8_OPERATIONAL_RECEIPT_FILE)
    for gate in ("G0", "G1", "G2", "G3", "G6"):
        try:
            receipt = _validated_gate(
                run_root,
                snapshot,
                gate=gate,
                run_id=run_id,
                manifest_sha256=manifest_sha256,
                # G8's verified G6→G7→G8 database hash chain preserves the
                # historical G6 snapshot after G8 adds its recovered media.
                reopen_g6_snapshot=not (gate == "G6" and g8_receipt_present),
            )
            receipts[gate] = receipt
            inventory.append(_gate_result(gate, receipt, run_root / GATE_RECEIPTS[gate]))
        except OperationalReconciliationError as error:
            inventory.append(OperationalGateResult(
                gate, "BLOCKED", str(error), "UNKNOWN", "REAL_EVIDENCE_PENDING",
                run_id, manifest_sha256, {}, None,
            ))
    g6 = receipts.get("G6")
    no_m_partial = _is_no_m_partial(g6)
    if no_m_partial:
        inventory.append(OperationalGateResult(
            "G7", "NOT_TESTED", "NO_ELIGIBLE_M_DATASET",
            str(g6.get("evidence_origin")),
            str(g6.get("real_evidence_status", "REAL_EVIDENCE_PENDING")),
            run_id, manifest_sha256, {}, None,
        ))
    else:
        try:
            g7_receipt = _validated_gate(
                run_root, snapshot, gate="G7", run_id=run_id,
                manifest_sha256=manifest_sha256,
                reopen_g6_snapshot=not g8_receipt_present,
            )
            receipts["G7"] = g7_receipt
            inventory.append(_gate_result("G7", g7_receipt))
        except OperationalReconciliationError as error:
            inventory.append(OperationalGateResult(
                "G7", "BLOCKED", str(error), "UNKNOWN", "REAL_EVIDENCE_PENDING",
                run_id, manifest_sha256, {}, None,
            ))
    for profile in ("F", "M"):
        for index in (1, 2):
            try:
                receipt = read_validated_g5_queue_receipt(
                    run_root,
                    snapshot,
                    run_id=run_id,
                    manifest_sha256=manifest_sha256,
                    profile=profile,
                    pass_index=index,
                )
                if (
                    receipt.get("channel_id") != manifest.get("channel_id")
                    or receipt.get("database_file") != database_path.name
                    or receipt.get("download_root") != download_root.name
                ):
                    raise OperationalReconciliationError("G5_STORAGE_BINDING_INVALID")
                receipts[f"G5_{profile}_{index}"] = receipt
                inventory.append(_gate_result(f"G5_{profile}_{index}", receipt))
            except (GateEvidenceError, OperationalReconciliationError, OSError, ValueError, TypeError):
                inventory.append(OperationalGateResult(
                    f"G5_{profile}_{index}", "BLOCKED", "RECEIPT_MISSING_OR_INVALID",
                    "UNKNOWN", "REAL_EVIDENCE_PENDING", run_id, manifest_sha256,
                    {}, None,
                ))
    if no_m_partial:
        inventory.append(OperationalGateResult(
            "G8", "NOT_TESTED", "NO_ELIGIBLE_M_DATASET",
            str(g6.get("evidence_origin")),
            str(g6.get("real_evidence_status", "REAL_EVIDENCE_PENDING")),
            run_id, manifest_sha256, {}, None,
        ))
    else:
        try:
            g8_receipt, _g8_digest = _read_operational_receipt(
                run_root,
                snapshot,
                gate="G8",
                run_id=run_id,
                manifest_sha256=manifest_sha256,
                filename=G8_OPERATIONAL_RECEIPT_FILE,
            )
            transition = validate_g8_database_transition(
                run_root,
                snapshot,
                run_id=run_id,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                database_path=database_path,
            )
            g8_evidence = g8_receipt.get("evidence")
            if (
                transition.get("status") != g8_receipt.get("status")
                or transition.get("evidence_origin") != g8_receipt.get("evidence_origin")
                or type(g8_evidence) is not dict
                or g8_evidence.get("download_root") != download_root.name
            ):
                raise OperationalReconciliationError("G8_OPERATIONAL_REOPEN_MISMATCH")
            receipts["G8"] = g8_receipt
            inventory.append(_gate_result("G8", g8_receipt, run_root / G8_OPERATIONAL_RECEIPT_FILE))
        except (GateEvidenceError, OperationalReconciliationError, OSError):
            inventory.append(OperationalGateResult(
                "G8", "BLOCKED", "OPERATIONAL_RECEIPT_MISSING_OR_INVALID",
                "UNKNOWN", "REAL_EVIDENCE_PENDING", run_id, manifest_sha256,
                {}, None,
            ))
    if no_m_partial:
        inventory = [
            OperationalGateResult(
                item.gate,
                "BLOCKED_DATASET" if item.gate.startswith("G5_M_") else
                "NOT_TESTED" if item.gate in {"G7", "G8"} else item.status,
                "NO_ELIGIBLE_M_DATASET" if item.gate.startswith("G5_M_")
                or item.gate in {"G7", "G8"} else item.reason,
                item.evidence_origin,
                item.real_evidence_status,
                item.run_id,
                item.manifest_sha256,
                item.summary,
                item.receipt_path,
            )
            for item in inventory
        ]
    return inventory, receipts


def _is_no_m_partial(g6: object) -> bool:
    return bool(
        type(g6) is dict
        and g6.get("status") == "PARTIAL"
        and g6.get("evidence_origin") in {"REAL_CONTRACTUAL", "SYNTHETIC"}
        and g6.get("g5_m_status") == "BLOCKED_DATASET"
        and g6.get("g6_aggregate_status") == "PARTIAL"
        and g6.get("g7_real_eligible") is False
        and g6.get("nfr02_real") == "NOT_TESTED"
    )


def reconcile_g9_operational(
    run_directory: str | Path,
    database_path: str | Path,
    download_root: str | Path,
) -> OperationalReconciliation:
    """Produce the durable operational G9 result and a sanitized report.

    Real PASS is possible only when each required receipt is contractual-real
    and the full scope (including M and eligible G7) is proven. Synthetic
    receipts can produce only OFFLINE_SYNTHETIC_PASS. A proven F profile with
    no eligible M is reported PARTIAL with real evidence still pending.
    """
    run_root = _run_root(run_directory)
    db_path = Path(database_path)
    output_root = Path(download_root)
    ledger = S9OperationalLedger(run_root / "operational-ledger.sqlite3")
    manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(run_root)
    snapshot = ledger.snapshot()
    run_id = str(snapshot["run"]["run_id"])
    if (
        not db_path.is_absolute()
        or db_path.parent.resolve(strict=True) != run_root.resolve(strict=True)
        or not output_root.is_absolute()
        or output_root.parent.resolve(strict=True) != run_root.resolve(strict=True)
    ):
        raise OperationalReconciliationError("G9_STORAGE_BINDING_INVALID")
    if snapshot["critical_audit"]["quarantined"]:
        raise OperationalReconciliationError("LEDGER_AUDIT_QUARANTINED")
    existing_receipt: dict[str, object] | None = None
    if os.path.lexists(run_root / G9_OPERATIONAL_RECEIPT_FILE):
        existing_receipt, _existing_digest = _read_operational_receipt(
            run_root,
            snapshot,
            gate="G9",
            run_id=run_id,
            manifest_sha256=manifest_sha256,
            filename=G9_OPERATIONAL_RECEIPT_FILE,
        )
    inventory, receipts = _g9_gate_inventory(
        run_root, snapshot, manifest, manifest_sha256, db_path, output_root,
    )
    gates_by_name = {item.gate: item for item in inventory}
    g0 = receipts.get("G0")
    contractual = (
        type(g0) is dict and g0.get("status") == "PASS"
        and g0.get("evidence_origin") == "HUMAN_INTERACTIVE"
    )
    synthetic = (
        type(g0) is dict and g0.get("status") == "OFFLINE_SYNTHETIC_PASS"
        and g0.get("evidence_origin") == "SYNTHETIC"
    )
    origin = "REAL_CONTRACTUAL" if contractual else "SYNTHETIC" if synthetic else "UNKNOWN"
    no_m_partial = _is_no_m_partial(receipts.get("G6"))
    g7_valid = False
    if origin == "UNKNOWN":
        overall = "BLOCKED"
        reason = "G0_ORIGIN_NOT_ATTESTED"
    else:
        expected_status = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
        expected_gate_origin = origin
        required = ["G1", "G2", "G3"] + ([] if no_m_partial else ["G6", "G8"])
        missing_or_mismatched = [
            name for name in required
            if name not in receipts
            or receipts[name].get("status") != expected_status
            or receipts[name].get("evidence_origin") != expected_gate_origin
        ]
        f1 = receipts.get("G5_F_1")
        f2 = receipts.get("G5_F_2")
        f_valid = all(
            type(item) is dict
            and item.get("status") == expected_status
            and item.get("evidence_origin") == expected_gate_origin
            for item in (f1, f2)
        )
        m1 = receipts.get("G5_M_1")
        m2 = receipts.get("G5_M_2")
        m_valid = all(
            type(item) is dict
            and item.get("status") == expected_status
            and item.get("evidence_origin") == expected_gate_origin
            for item in (m1, m2)
        )
        g7 = gates_by_name.get("G7")
        g7_valid = (
            g7 is not None and g7.status == expected_status
            and g7.evidence_origin == expected_gate_origin
        )
        if any(gates_by_name[name].status == "FAIL" for name in gates_by_name):
            overall, reason = "FAIL", "CONTRACTUAL_GATE_FAILED"
        elif no_m_partial:
            if f_valid:
                overall, reason = "PARTIAL", "M_PROFILE_NOT_ELIGIBLE"
            else:
                overall, reason = "BLOCKED", "F_PROFILE_EVIDENCE_INCOMPLETE"
        elif origin == "REAL_CONTRACTUAL" and not m_valid:
            f_status = None
            g6 = receipts.get("G6")
            profiles = g6.get("profile_statuses") if type(g6) is dict else None
            if type(profiles) is dict:
                f_status = profiles.get("F")
            if f_valid and f_status in {"PASS", "REAL_CONTRACTUAL_PASS"}:
                overall, reason = "PARTIAL", "M_PROFILE_NOT_ELIGIBLE"
            else:
                overall, reason = "BLOCKED", "REAL_PROFILE_EVIDENCE_INCOMPLETE"
        elif origin == "SYNTHETIC" and not m_valid:
            overall, reason = "PARTIAL", "SYNTHETIC_M_PROFILE_NOT_PROVEN"
        elif missing_or_mismatched or not f_valid or not g7_valid:
            overall, reason = "BLOCKED", "GATE_CHAIN_INCOMPLETE_OR_PROVENANCE_MISMATCH"
        else:
            overall = expected_status
            reason = "ALL_REQUIRED_GATES_RECONCILED"
    real_status = (
        "REAL_CONTRACTUAL_PASS"
        if overall == "PASS" and origin == "REAL_CONTRACTUAL"
        else "REAL_EVIDENCE_PENDING"
    )
    normalized_gate_statuses = [
        {
            "gate": item.gate,
            "status": item.status,
            "reason": item.reason,
            "evidence_origin": item.evidence_origin,
            "real_evidence_status": item.real_evidence_status,
        }
        for item in inventory
    ]
    if existing_receipt is not None:
        expected_ledger_result = {
            "PASS": "REAL_CONTRACTUAL_PASS",
            "OFFLINE_SYNTHETIC_PASS": "OFFLINE_SYNTHETIC_PASS",
            "PARTIAL": "PARTIAL",
            "BLOCKED": "BLOCKED",
            "FAIL": "FAIL",
        }[overall]
        g6_receipt = receipts.get("G6")
        expected_g8_real_eligibility = bool(
            not no_m_partial
            and g7_valid
            and origin == "REAL_CONTRACTUAL"
            and "G8" in receipts
            and receipts["G8"].get("status") == "PASS"
        )
        existing_matches = (
            existing_receipt.get("status") == overall
            and existing_receipt.get("reason") == reason
            and existing_receipt.get("evidence_origin") == origin
            and existing_receipt.get("offline_result")
            == (overall if origin == "SYNTHETIC" else "UNKNOWN")
            and existing_receipt.get("real_evidence_status") == real_status
            and existing_receipt.get("ledger_result") == expected_ledger_result
            and existing_receipt.get("gates") == normalized_gate_statuses
            and existing_receipt.get("g5_m_status") == (
                g6_receipt.get("g5_m_status", "UNKNOWN")
                if type(g6_receipt) is dict else "UNKNOWN"
            )
            and existing_receipt.get("g6_aggregate_status") == (
                g6_receipt.get("g6_aggregate_status", "UNKNOWN")
                if type(g6_receipt) is dict else "UNKNOWN"
            )
            and existing_receipt.get("g7_real_eligibility") == (
                g6_receipt.get("g7_real_eligible", g7_valid)
                if type(g6_receipt) is dict else g7_valid
            )
            and existing_receipt.get("nfr02_real") == (
                g6_receipt.get("nfr02_real", "UNKNOWN")
                if type(g6_receipt) is dict else "UNKNOWN"
            )
            and existing_receipt.get("g8_real_eligibility")
            is expected_g8_real_eligibility
            and existing_receipt.get("report_file") == G9_OPERATIONAL_REPORT_FILE
            and existing_receipt.get("telegram_rpc")
            == (0 if origin == "SYNTHETIC" else "NOT_ASSERTED")
            and existing_receipt.get("operational_db_writes")
            == "ISOLATED_RUN_DATABASE"
        )
        if not existing_matches:
            raise OperationalReconciliationError("G9_OPERATIONAL_REOPEN_MISMATCH")
        report_path = _private_run_file(run_root, G9_OPERATIONAL_REPORT_FILE)
        _validate_sanitized_report(
            report_path,
            expected_sha256=existing_receipt.get("report_sha256"),
            forbidden_values=(
                str(manifest.get("channel_id")),
                str(run_root.resolve(strict=True)),
                str(db_path),
                str(output_root),
            ),
        )
        return OperationalReconciliation(
            run_id,
            overall,
            origin,
            real_status,
            tuple(inventory),
            run_root / G9_OPERATIONAL_RECEIPT_FILE,
            report_path,
            manifest_sha256,
        )
    report_lines = [
        "# S9 Operational Reconciliation",
        "",
        f"Run: `{run_id}`",
        f"Outcome: **{overall}**",
        f"Evidence origin: `{origin}`",
        f"Real evidence: `{real_status}`",
        f"Reason: `{reason}`",
        "",
        "## Gate results",
        "",
        "| Gate | Result | Evidence |",
        "|---|---|---|",
    ]
    for item in inventory:
        report_lines.append(
            f"| {item.gate} | {item.status} | {item.reason} |"
        )
    report_lines.extend([
        "",
        "The report contains no channel or media IDs, path details, or credential data.",
        "",
    ])
    report_path = _private_run_output_path(run_root, G9_OPERATIONAL_REPORT_FILE)
    report_sha256 = _write_sanitized_report(report_path, "\n".join(report_lines))
    _validate_sanitized_report(
        report_path,
        expected_sha256=report_sha256,
        forbidden_values=(
            str(manifest.get("channel_id")),
            str(run_root.resolve(strict=True)),
            str(db_path),
            str(output_root),
        ),
    )
    ledger_result = {
        "PASS": "REAL_CONTRACTUAL_PASS",
        "OFFLINE_SYNTHETIC_PASS": "OFFLINE_SYNTHETIC_PASS",
        "PARTIAL": "PARTIAL",
        "BLOCKED": "BLOCKED",
        "FAIL": "FAIL",
    }[overall]
    receipt_payload = {
        "schema": "telegram-courses-s9-g9-operational-receipt-v1",
        "version": 1,
        "gate": "G9",
        "run_id": run_id,
        "manifest_sha256": manifest_sha256,
        "channel_id": manifest.get("channel_id"),
        "status": overall,
        "reason": reason,
        "evidence_origin": origin,
        "offline_result": overall if origin == "SYNTHETIC" else "UNKNOWN",
        "real_evidence_status": real_status,
        "ledger_result": ledger_result,
        "gates": normalized_gate_statuses,
        "g5_m_status": (
            receipts.get("G6", {}).get("g5_m_status", "UNKNOWN")
            if type(receipts.get("G6")) is dict else "UNKNOWN"
        ),
        "g6_aggregate_status": (
            receipts.get("G6", {}).get("g6_aggregate_status", "UNKNOWN")
            if type(receipts.get("G6")) is dict else "UNKNOWN"
        ),
        "g7_real_eligibility": (
            receipts.get("G6", {}).get("g7_real_eligible", g7_valid)
            if type(receipts.get("G6")) is dict else g7_valid
        ),
        "nfr02_real": (
            receipts.get("G6", {}).get("nfr02_real", "UNKNOWN")
            if type(receipts.get("G6")) is dict else "UNKNOWN"
        ),
        "g8_real_eligibility": bool(
            not no_m_partial
            and g7_valid
            and origin == "REAL_CONTRACTUAL"
            and "G8" in receipts
            and receipts["G8"].get("status") == "PASS"
        ),
        "report_file": G9_OPERATIONAL_REPORT_FILE,
        "report_sha256": report_sha256,
        "contract": "S9_V1.0_APPROVED_FROZEN",
        "telegram_rpc": 0 if origin == "SYNTHETIC" else "NOT_ASSERTED",
        "operational_db_writes": "ISOLATED_RUN_DATABASE",
    }
    receipt_path, _receipt_digest = _persist_receipt(
        run_root, ledger, receipt_payload,
        filename=G9_OPERATIONAL_RECEIPT_FILE,
        before_rename_checkpoint=ledger.checkpoint,
    )
    terminal_status = {
        "PASS": "COMPLETED",
        "OFFLINE_SYNTHETIC_PASS": "COMPLETED",
        "PARTIAL": "PARTIAL",
        "BLOCKED": "BLOCKED",
        "FAIL": "FAILED",
    }[overall]
    current_run = ledger.snapshot()["run"]
    applied_terminal_status = (
        str(current_run["status"])
        if current_run.get("status") in {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"}
        else terminal_status
    )
    terminal_cause = (
        str(current_run["cause"])
        if current_run.get("status") in {"COMPLETED", "PARTIAL", "FAILED", "CANCELLED", "BLOCKED"}
        else "NONE" if overall in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        else "OTHER"
    )
    ledger.update_execution(
        gate="G9",
        status=applied_terminal_status,
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=int(ledger.snapshot()["run"]["deadline_ns"]),
        process_state="EXITED",
        result=ledger_result,
        cause=terminal_cause,
    )
    refreshed = ledger.snapshot()
    _read_operational_receipt(
        run_root,
        refreshed,
        gate="G9",
        run_id=run_id,
        manifest_sha256=manifest_sha256,
        filename=G9_OPERATIONAL_RECEIPT_FILE,
    )
    return OperationalReconciliation(
        run_id,
        overall,
        origin,
        real_status,
        tuple(inventory),
        receipt_path,
        report_path,
        manifest_sha256,
    )
