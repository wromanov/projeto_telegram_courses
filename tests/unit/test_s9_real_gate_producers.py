from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import (
    ChannelKind,
    ChannelSummary,
    DiscoveryLimits,
    DiscoveryResult,
    DiscoveryStats,
)
from telegram_courses.config import TelegramCredentials
from telegram_courses.download_repository import DownloadCandidate
from telegram_courses.downloads import destination_paths
from telegram_courses.s9_g0_confirmation import request_g0_confirmation
from telegram_courses.s9_gate_reconciliation import _canonical
from telegram_courses.s9_operational_ledger import (
    F_CAP,
    GIB,
    LedgerError,
    S9OperationalLedger,
    _create_private_directory,
    media_m_cap,
)
from telegram_courses.s9_real_gate_producers import (
    G1_WORKER_RECEIPT,
    GateEvidenceError,
    _database_sha256,
    _g6_chain_origin,
    _g7_receipt_filename,
    collect_g1_evidence,
    g5_queue_receipt_filename,
    g5_supervisor_receipt_filename,
    load_approved_manifest,
    persist_g5_queue_receipt,
    persist_gate_receipt,
    read_g7_baseline,
    read_sqlite_ids,
    read_validated_g5_queue_receipt,
    read_validated_gate_receipt,
    reconcile_g2_scan,
    reconcile_g3_catalog,
    reconcile_g6_downloads,
    reconcile_g7_scan,
    sha256_bytes,
    validate_g1_evidence,
    validate_manifest,
)
from telegram_courses.s9_supervisor import (
    SupervisorError,
    _write_no_overwrite_json,
)
from telegram_courses.s9_supervisor_cli import (
    OfflineRunnerError,
    _read_supervisor_receipt_evidence,
    run_supervised_g1,
    start_supervised_run,
)


def test_database_snapshot_hash_ignores_shm_and_tracks_db_and_wal(tmp_path: Path) -> None:
    database = tmp_path / "catalog.sqlite3"
    wal = Path(str(database) + "-wal")
    shm = Path(str(database) + "-shm")
    database.write_bytes(b"main database bytes")
    wal.write_bytes(b"committed WAL frames")
    shm.write_bytes(b"transient shared-memory state A")

    initial = _database_sha256(database)
    shm.write_bytes(b"transient shared-memory state B")
    assert _database_sha256(database) == initial

    wal.write_bytes(b"different committed WAL frames")
    after_wal_change = _database_sha256(database)
    assert after_wal_change != initial

    database.write_bytes(b"different main database bytes")
    assert _database_sha256(database) != after_wal_change


def test_database_snapshot_hash_tracks_commits_still_in_wal(tmp_path: Path) -> None:
    database = tmp_path / "catalog.sqlite3"
    writer = sqlite3.connect(database)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        writer.execute("CREATE TABLE records (value TEXT NOT NULL)")
        writer.commit()
        before = _database_sha256(database)

        writer.execute("INSERT INTO records VALUES('committed')")
        writer.commit()
        wal = Path(str(database) + "-wal")
        assert wal.is_file() and wal.stat().st_size > 0
        assert _database_sha256(database) != before
    finally:
        writer.close()


@pytest.mark.parametrize("part", ["main", "wal", "shm", "journal"])
def test_database_snapshot_hash_rejects_windows_reparse_files_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    part: str,
) -> None:
    database = tmp_path / "catalog.sqlite3"
    database.write_bytes(b"main database")
    target = database if part == "main" else Path(str(database) + f"-{part}")
    original_lstat = Path.lstat
    original_open = Path.open
    opened: list[Path] = []

    def fake_lstat(path: Path):
        if path == target:
            return SimpleNamespace(
                st_mode=stat.S_IFREG,
                st_size=12,
                st_file_attributes=0x400,
            )
        return original_lstat(path)

    def tracking_open(path: Path, *args, **kwargs):
        opened.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    monkeypatch.setattr(Path, "open", tracking_open)

    with pytest.raises(GateEvidenceError, match="DATABASE_HASH_FAILED"):
        _database_sha256(database)
    assert opened == []

pytestmark = pytest.mark.skipif(os.name != "nt", reason="S9 private-run validation is Windows-specific")

CHANNEL_ID = -1000000000123


def _manifest(module_count: int = 2, *, planned_catalog: bool = False) -> dict[str, object]:
    scope = (
        {
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
        if planned_catalog else {"target_alias": "SYNTHETIC_RASMOO"}
    )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "channel_alias": "RASMOO" if planned_catalog else "SYNTHETIC_CHANNEL",
        "scope": scope,
        "hierarchy": (
            {"TRACK": 1, "COURSE": 2, "MODULE": 2}
            if planned_catalog
            else {"TRACK": 1, "COURSE": 2, "MODULE": module_count}
        ),
        "unresolved_count": None if planned_catalog else 0,
        "scope_approval": {
            "decision": "APPROVED",
            "confirmation_source": "G0_HUMAN_CONFIRMATION",
            "scope_sha256": sha256_bytes(_canonical(scope)),
        },
    }
    if planned_catalog:
        manifest["catalog_expectation"] = {
            "state": "PENDING_G3",
            "hierarchy_semantics": "MINIMUMS",
            "unresolved_semantics": "OBSERVE_AND_REVIEW",
        }
    return manifest


def _start_run(
    tmp_path: Path, *, module_count: int = 2, planned_catalog: bool = False,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    context = start_supervised_run(tmp_path / "run")
    manifest = _manifest(module_count, planned_catalog=planned_catalog)
    (context.run_directory / "approved-manifest.json").write_bytes(
        _canonical(manifest) + b"\n",
    )
    loaded, manifest_sha256, _scope_sha256 = load_approved_manifest(
        context.run_directory,
    )
    ledger = S9OperationalLedger(context.ledger_path)
    return context, loaded, manifest_sha256, ledger


def test_planned_catalog_manifest_marks_requirements_not_observations() -> None:
    manifest = _manifest(planned_catalog=True)
    validated, manifest_sha256, scope_sha256 = validate_manifest(manifest)
    assert validated["catalog_expectation"] == {
        "state": "PENDING_G3",
        "hierarchy_semantics": "MINIMUMS",
        "unresolved_semantics": "OBSERVE_AND_REVIEW",
    }
    assert validated["hierarchy"] == {"TRACK": 1, "COURSE": 2, "MODULE": 2}
    assert validated["unresolved_count"] is None
    assert scope_sha256 == sha256_bytes(_canonical(manifest["scope"]))
    assert manifest_sha256 == sha256_bytes(_canonical(validated))

    invalid = _manifest(planned_catalog=True)
    invalid["hierarchy"] = {"TRACK": 4, "COURSE": 2, "MODULE": 2}
    with pytest.raises(GateEvidenceError, match="MANIFEST_BINDING_INVALID"):
        validate_manifest(invalid)

    invalid = _manifest(planned_catalog=True)
    invalid["scope"]["max_transfer_bytes"] = 1024 * 1024 * 1024
    with pytest.raises(GateEvidenceError, match="MANIFEST_BINDING_INVALID"):
        validate_manifest(invalid)


class _SyntheticTerminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _synthetic_g0(
    context,
    manifest: dict[str, object],
    manifest_sha256: str,
    ledger: S9OperationalLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    def accept_confirmation(prompt: str, **_kwargs) -> str:
        match = re.search(r"APROVAR S9 G0 ([0-9a-f]{32})", prompt)
        assert match is not None
        return match.group(0)

    monkeypatch.setattr(
        "telegram_courses.s9_g0_confirmation._read_tty_line",
        accept_confirmation,
    )
    receipt = request_g0_confirmation(
        context.run_directory,
        ledger,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        scope_sha256=sha256_bytes(_canonical(manifest["scope"])),
        test_mode=True,
        stdin=_SyntheticTerminal(),
        stdout=_SyntheticTerminal(),
    )
    ledger.update_execution(
        gate="G0", status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns, process_state="UNKNOWN",
        result="OFFLINE_SYNTHETIC_PASS",
    )
    return receipt


def _write_synthetic_sparse_zero_file(path: Path, size: int) -> str:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    device_io_control = kernel32.DeviceIoControl
    device_io_control.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    device_io_control.restype = wintypes.BOOL
    bytes_returned = wintypes.DWORD()
    with path.open("wb") as stream:
        if not device_io_control(
            msvcrt.get_osfhandle(stream.fileno()), 0x000900C4,
            None, 0, None, 0, ctypes.byref(bytes_returned), None,
        ):
            raise OSError(ctypes.get_last_error(), "FSCTL_SET_SPARSE failed")
        stream.truncate(size)
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _record_supervisor_receipt(
    root: Path,
    ledger: S9OperationalLedger,
    *,
    run_id: str,
    stage: str,
    exit_code: int = 0,
    external_exit_code: int | None = None,
    receipt_name: str | None = None,
) -> tuple[str, str]:
    """Create an offline-only supervisor receipt with the production audit shape."""
    receipt_names = {
        "discovery": "g1-discovery-supervisor-receipt.json",
        "scan": "g2-scan-supervisor-receipt.json",
        "catalog": "g3-catalog-supervisor-receipt.json",
        "queue_f": "g5-queue-f-01-supervisor-receipt.json",
        "queue_m": "g5-queue-m-01-supervisor-receipt.json",
    }
    external_code = exit_code if external_exit_code is None else external_exit_code
    if external_code not in {0, 4} or (external_code == 4 and stage != "scan"):
        raise ValueError("unsupported synthetic supervisor exit code")
    path = root / (receipt_name or receipt_names[stage])
    acknowledgements = []

    def event_id(counter: int) -> str:
        return hashlib.sha256(
            f"{run_id}:{stage}:{path.name}:{counter}".encode("ascii"),
        ).hexdigest()[:32]

    base_events = (
        ("RUN_INITIALIZED", {"stage": stage}),
        ("PREFLIGHT_CONFIRMED", {"stage": stage}),
        ("GATE_STARTED", {"stage": stage}),
        ("CHILD_PROCESS_CONFIRMED", {
            "stage": stage, "pid": 12345, "process_creation_time": 67890,
        }),
        ("SUPERVISOR_RUN_FINISHED", {
            "stage": stage, "result": "COMPLETED", "exit_code": external_code,
            "tree_confirmed": True,
        }),
    )
    for index, (event_type, details) in enumerate(base_events, 1):
        acknowledgements.append(ledger.record_critical_event(
            event_type, details=details, event_id=event_id(index),
        ))
    receipt = {
        "schema": "telegram-courses-s9-supervisor-receipt-v1",
        "run_id": run_id,
        "ledger_run_id": run_id,
        "stage": stage,
        "result": "COMPLETED",
        "reason": "EXPECTED_MESSAGE_LIMIT_EXIT" if external_code == 4 else "PROCESS_EXITED",
        "external_exit_code": external_code,
        "message_limit_exit_allowed": True,
        "process_tree_termination_confirmed": True,
        "critical_audit_gate": "PASS",
        "supervisor_offline_gate": "PASS",
        "process_control_offline_gate": "PASS",
        "memory_monitoring_offline_gate": "PASS",
        "memory": {
            "samples": [{"working_set_bytes": 1024, "private_bytes": 2048}],
            "peak_working_set_bytes": 1024,
        },
        "receipt_prepared_event_id": event_id(6),
        "receipt_attestation_event_id": event_id(7),
        "critical_audit_acknowledgements": acknowledgements,
    }
    encoded = (
        json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    digest = sha256_bytes(encoded)
    _write_no_overwrite_json(
        path,
        receipt,
        before_rename=lambda _raw: ledger.record_critical_event(
            "RECEIPT_PREPARED",
            details={"receipt_sha256": digest},
            event_id=event_id(6),
        ),
        after_rename=lambda _raw: ledger.record_critical_event(
            "RECEIPT_PERSISTED",
            details={"receipt_sha256": digest},
            event_id=event_id(7),
        ),
    )
    return path.name, digest


def _synthetic_g1(
    context, manifest: dict[str, object], manifest_sha256: str,
    ledger: S9OperationalLedger,
) -> dict[str, object]:
    supervisor_file, supervisor_hash = _record_supervisor_receipt(
        context.run_directory, ledger, run_id=context.run_id, stage="discovery",
    )
    evidence: dict[str, object] = {
        "schema_version": 1,
        "gate": "G1",
        "run_id": context.run_id,
        "manifest_sha256": manifest_sha256,
        "evidence_origin": "SYNTHETIC",
        "authentication": "AUTHENTICATED",
        "discovery_complete": True,
        "channel_id": manifest["channel_id"],
        "channel_alias": manifest["channel_alias"],
        "target_alias_match": True,
        "discovered_count": 1,
        "target_match_count": 1,
        "cleanup_complete": True,
        "status": "OFFLINE_SYNTHETIC_PASS",
        "reason": "SYNTHETIC_GATEWAY_ONLY",
    }
    worker = _canonical(evidence) + b"\n"
    (context.run_directory / G1_WORKER_RECEIPT).write_bytes(worker)
    gate_receipt = evidence | {
        "supervisor_stage": "discovery",
        "supervisor_receipt_file": supervisor_file,
        "supervisor_receipt_sha256": supervisor_hash,
        "worker_evidence_sha256": sha256_bytes(worker),
    }
    persist_gate_receipt(context.run_directory, ledger, gate_receipt)
    ledger.update_execution(
        gate="G1", status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result="OFFLINE_SYNTHETIC_PASS",
    )
    return gate_receipt


def _create_dataset(
    path: Path,
    *,
    scan_status: str = "COMPLETE",
    stop_reason: str | None = None,
    message_count: int = 2,
) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(
            "CREATE TABLE channels(telegram_chat_id INTEGER PRIMARY KEY);"
            "CREATE TABLE messages(channel_id INTEGER,telegram_message_id INTEGER,"
            "body TEXT,PRIMARY KEY(channel_id,telegram_message_id));"
            "CREATE TABLE scan_runs(id TEXT PRIMARY KEY,channel_id INTEGER,status TEXT,"
            "messages_seen INTEGER,stop_reason TEXT,sync_mode TEXT,sync_max_messages INTEGER,"
            "sync_reconcile_window INTEGER NOT NULL DEFAULT 0,started_at TEXT);"
            "CREATE TABLE catalog_runs(id TEXT PRIMARY KEY,channel_id INTEGER,status TEXT,"
            "source_message_count INTEGER,catalog_node_count INTEGER,unresolved_count INTEGER);"
            "CREATE TABLE catalog_nodes(id INTEGER PRIMARY KEY,channel_id INTEGER,parent_id INTEGER,"
            "kind TEXT,is_active INTEGER);"
            "CREATE TABLE catalog_unresolved_sources(run_id TEXT);"
        )
        db.execute("INSERT INTO channels VALUES(?)", (CHANNEL_ID,))
        db.executemany(
            "INSERT INTO messages VALUES(?,?,?)",
            (
                (CHANNEL_ID, index, f"fixture-{index}")
                for index in range(1, message_count + 1)
            ),
        )
        db.execute(
            "INSERT INTO scan_runs VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "db-scan-1", CHANNEL_ID, scan_status, message_count, stop_reason, "FULL",
                None, 0, datetime.now(UTC).isoformat(),
            ),
        )
    finally:
        db.commit()
        db.close()


def _add_catalog(path: Path, *, modules: int = 2) -> None:
    db = sqlite3.connect(path)
    try:
        nodes = [
            (1, CHANNEL_ID, None, "TRACK", 1),
            (2, CHANNEL_ID, 1, "COURSE", 1),
            (3, CHANNEL_ID, 1, "COURSE", 1),
        ]
        nodes.extend(
            (4 + index, CHANNEL_ID, 2 if index % 2 == 0 else 3, "MODULE", 1)
            for index in range(modules)
        )
        db.executemany("INSERT INTO catalog_nodes VALUES(?,?,?,?,?)", nodes)
        db.execute(
            "INSERT INTO catalog_runs VALUES(?,?,?,?,?,?)",
            ("db-catalog-1", CHANNEL_ID, "COMPLETE", 2, len(nodes), 0),
        )
        db.commit()
    finally:
        db.close()


def _synthetic_g2(
    context,
    manifest: dict[str, object],
    manifest_sha256: str,
    ledger: S9OperationalLedger,
    g1_receipt: dict[str, object],
    database_path: Path,
    *,
    scan_status: str = "COMPLETE",
    stop_reason: str | None = None,
    max_messages: int = 200,
    observed_messages: int = 2,
    message_count: int = 2,
    application_exit_code: int = 0,
    external_exit_code: int | None = None,
    ledger_observed: int | None = None,
) -> dict[str, object]:
    before = ledger.snapshot()
    database_ids_before = read_sqlite_ids(
        context.run_directory, database_path, "scan_runs",
    ) if database_path.exists() else set()
    scan_id = ledger.begin_scan(max_messages=max_messages)
    ledger.finish_scan(
        scan_id,
        observed_messages if ledger_observed is None else ledger_observed,
    )
    _create_dataset(
        database_path, scan_status=scan_status, stop_reason=stop_reason,
        message_count=message_count,
    )
    _supervisor_file, supervisor_hash = _record_supervisor_receipt(
        context.run_directory, ledger, run_id=context.run_id, stage="scan",
        exit_code=application_exit_code,
        external_exit_code=external_exit_code,
    )
    after = ledger.snapshot()
    evidence = reconcile_g2_scan(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence=g1_receipt,
        database_scan_ids_before=database_ids_before,
        ledger_before=before,
        ledger_after=after,
        requested_max_messages=max_messages,
        application_exit_code=application_exit_code,
        external_exit_code=(
            application_exit_code if external_exit_code is None else external_exit_code
        ),
        stage_started_ns=time.time_ns() - 5_000_000_000,
        stage_finished_ns=time.time_ns() + 5_000_000_000,
    )
    evidence.update({
        "supervisor_stage": "scan",
        "supervisor_receipt_file": "g2-scan-supervisor-receipt.json",
        "supervisor_receipt_sha256": supervisor_hash,
    })
    persist_gate_receipt(context.run_directory, ledger, evidence)
    if evidence["status"] == "OFFLINE_SYNTHETIC_PASS":
        ledger.update_execution(
            gate="G2", status="RUNNING",
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
            deadline_ns=context.deadline_ns, process_state="EXITED",
            result="OFFLINE_SYNTHETIC_PASS",
        )
    else:
        ledger.update_execution(
            gate="G2", status="BLOCKED",
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
            deadline_ns=context.deadline_ns, process_state="EXITED",
            result="BLOCKED", cause="LEDGER",
        )
    return evidence


def _add_s7_schema(database_path: Path) -> None:
    db = sqlite3.connect(database_path)
    try:
        db.executescript(
            "ALTER TABLE scan_runs ADD COLUMN watermark_message_id INTEGER;"
            "ALTER TABLE scan_runs ADD COLUMN finished_at TEXT;"
            "ALTER TABLE scan_runs ADD COLUMN sync_baseline_confirmed INTEGER NOT NULL DEFAULT 0;"
            "ALTER TABLE scan_runs ADD COLUMN sync_high_water_before INTEGER;"
            "ALTER TABLE scan_runs ADD COLUMN sync_reconcile_floor_message_id INTEGER;"
            "ALTER TABLE scan_runs ADD COLUMN sync_snapshot_head_message_id INTEGER;"
            "ALTER TABLE scan_runs ADD COLUMN messages_unverified INTEGER;"
            "CREATE TABLE sync_checkpoints(scan_run_id TEXT PRIMARY KEY,channel_id INTEGER,"
            "watermark_message_id INTEGER,last_message_id INTEGER,last_message_date_utc TEXT,"
            "status TEXT,updated_at TEXT);"
        )
        now = datetime.now(UTC).isoformat()
        db.execute(
            "UPDATE scan_runs SET watermark_message_id=10,finished_at=? WHERE id='db-scan-1'",
            (now,),
        )
        db.execute(
            "INSERT INTO sync_checkpoints VALUES(?,?,?,?,?,?,?)",
            ("db-scan-1", CHANNEL_ID, 10, 10, None, "COMPLETE", now),
        )
        db.commit()
    finally:
        db.close()


def _synthetic_g6(
    context,
    manifest: dict[str, object],
    manifest_sha256: str,
    ledger: S9OperationalLedger,
    database_path: Path,
) -> dict[str, object]:
    receipt = {
        "gate": "G6",
        "status": "OFFLINE_SYNTHETIC_PASS",
        "evidence_origin": "SYNTHETIC",
        "reason": "SYNTHETIC_FIXTURE_ONLY",
        "run_id": context.run_id,
        "manifest_sha256": manifest_sha256,
        "channel_id": manifest["channel_id"],
        "database_file": database_path.name,
        "database_sha256": _database_sha256(database_path),
        "database_integrity": "ok",
    }
    persist_gate_receipt(context.run_directory, ledger, receipt)
    ledger.update_execution(
        gate="G6",
        status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns,
        process_state="EXITED",
        result="OFFLINE_SYNTHETIC_PASS",
    )
    return receipt


def test_g5_queue_receipt_reopens_with_supervisor_and_ledger_binding(
    tmp_path: Path,
) -> None:
    context, _manifest_value, manifest_sha256, ledger = _start_run(tmp_path)
    ledger.update_execution(
        gate="G5", status="RUNNING", elapsed_ms=1,
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result="OFFLINE_SYNTHETIC_PASS",
    )
    supervisor_file, supervisor_hash = _record_supervisor_receipt(
        context.run_directory, ledger, run_id=context.run_id,
        stage="queue_f", receipt_name=g5_supervisor_receipt_filename("F", 1),
    )
    receipt = {
        "schema": "telegram-courses-s9-g5-queue-receipt-v1",
        "version": 1,
        "gate": "G5",
        "run_id": context.run_id,
        "manifest_sha256": manifest_sha256,
        "channel_id": CHANNEL_ID,
        "database_file": "catalog.sqlite3",
        "download_root": "downloads",
        "profile": "F",
        "pass_index": 1,
        "stage": "queue_f",
        "status": "OFFLINE_SYNTHETIC_PASS",
        "evidence_origin": "SYNTHETIC",
        "measurement_source": "SYNTHETIC_TEST",
        "supervisor_receipt_file": supervisor_file,
        "supervisor_receipt_sha256": supervisor_hash,
        "observed_bytes": 0,
        "max_media_items": 1,
        "max_transfer_bytes": 1,
        "workers": 1,
        "attempts_per_media": 1,
        "all_items_already_valid": False,
    }
    queue_receipt_path = context.run_directory / g5_queue_receipt_filename("F", 1)
    checkpoint_calls: list[bool] = []
    original_checkpoint = ledger.checkpoint

    def checkpoint() -> object:
        snapshot = ledger.snapshot()
        assert any(
            event["event_type"] == "RECEIPT_PREPARED"
            and json.loads(event["details_json"]).get("gate") == "G5"
            for event in snapshot["critical_audit"]["events"]
        ), "G5 checkpoint must follow durable RECEIPT_PREPARED"
        assert not queue_receipt_path.exists(), "G5 checkpoint must precede rename"
        checkpoint_calls.append(True)
        return original_checkpoint()

    persist_g5_queue_receipt(
        context.run_directory, ledger, receipt,
        before_rename_checkpoint=checkpoint,
    )
    assert checkpoint_calls == [True]
    assert queue_receipt_path.is_file()
    ledger.update_execution(
        gate="G5", status="RUNNING", elapsed_ms=2,
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result="OFFLINE_SYNTHETIC_PASS", observed_bytes=0,
    )

    reopened = read_validated_g5_queue_receipt(
        context.run_directory, ledger.snapshot(), run_id=context.run_id,
        manifest_sha256=manifest_sha256, profile="F", pass_index=1,
    )
    assert reopened == receipt
    assert (context.run_directory / g5_queue_receipt_filename("F", 1)).is_file()


@pytest.mark.parametrize(
    ("status", "origin", "checkpoint_expected"),
    [
        ("PASS", "REAL_CONTRACTUAL", True),
        ("OFFLINE_SYNTHETIC_PASS", "SYNTHETIC", True),
        ("BLOCKED", "SYNTHETIC", False),
    ],
)
def test_g7_receipt_checkpoint_runs_after_prepared_before_rename_only_for_pass(
    tmp_path: Path,
    status: str,
    origin: str,
    checkpoint_expected: bool,
) -> None:
    context, _manifest, _manifest_sha256, ledger = _start_run(tmp_path)
    path = context.run_directory / _g7_receipt_filename(1)
    original_checkpoint = ledger.checkpoint
    checkpoint_calls: list[bool] = []

    def checkpoint() -> object:
        snapshot = ledger.snapshot()
        assert any(
            event["event_type"] == "RECEIPT_PREPARED"
            and json.loads(event["details_json"]).get("gate") == "G7"
            for event in snapshot["critical_audit"]["events"]
        ), "G7 checkpoint must follow durable RECEIPT_PREPARED"
        assert not path.exists(), "G7 checkpoint must precede rename"
        checkpoint_calls.append(True)
        return original_checkpoint()

    persisted_path, _digest = persist_gate_receipt(
        context.run_directory,
        ledger,
        {
            "gate": "G7",
            "run_id": context.run_id,
            "status": status,
            "evidence_origin": origin,
        },
        before_rename_checkpoint=checkpoint,
    )

    assert persisted_path == path
    assert path.is_file()
    assert bool(checkpoint_calls) is checkpoint_expected


def test_g6_real_status_from_caller_is_not_accepted_without_g5_and_physical_proof(
    tmp_path: Path,
) -> None:
    context, _manifest_value, manifest_sha256, ledger = _start_run(tmp_path)
    receipt = {
        "gate": "G6",
        "status": "PASS",
        "evidence_origin": "REAL_CONTRACTUAL",
        "reason": "CALLER_ASSERTED_PASS",
        "run_id": context.run_id,
        "manifest_sha256": manifest_sha256,
        "channel_id": CHANNEL_ID,
        "database_file": "catalog.sqlite3",
        "database_sha256": "a" * 64,
        "database_integrity": "ok",
    }
    persist_gate_receipt(context.run_directory, ledger, receipt)
    ledger.update_execution(
        gate="G6", status="RUNNING", elapsed_ms=1,
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result="PASS",
    )
    with pytest.raises(GateEvidenceError, match="G6_RECEIPT_CONTENT_INVALID"):
        read_validated_gate_receipt(
            context.run_directory, ledger.snapshot(), "G6",
            run_id=context.run_id, manifest_sha256=manifest_sha256,
        )


def test_g6_chain_accepts_synthetic_g0_only_with_synthetic_downstream() -> None:
    g0 = {
        "status": "OFFLINE_SYNTHETIC_PASS",
        "evidence_origin": "SYNTHETIC",
        "confirmation_source": "SYNTHETIC_TEST",
    }
    synthetic_predecessors = {
        gate: {"evidence_origin": "SYNTHETIC"} for gate in ("G1", "G2", "G3")
    }
    synthetic_passes = [
        {"evidence_origin": "SYNTHETIC"} for _ in range(4)
    ]
    assert _g6_chain_origin(
        g0, synthetic_predecessors, synthetic_passes,
    ) == "SYNTHETIC"

    mixed_passes = [*synthetic_passes[:-1], {"evidence_origin": "REAL_CONTRACTUAL"}]
    with pytest.raises(GateEvidenceError, match="G6_EVIDENCE_ORIGIN_MISMATCH"):
        _g6_chain_origin(g0, synthetic_predecessors, mixed_passes)


def test_g6_chain_rejects_synthetic_g0_for_real_downstream() -> None:
    g0 = {
        "status": "OFFLINE_SYNTHETIC_PASS",
        "evidence_origin": "SYNTHETIC",
        "confirmation_source": "SYNTHETIC_TEST",
    }
    real_predecessors = {
        gate: {"evidence_origin": "REAL_CONTRACTUAL"}
        for gate in ("G1", "G2", "G3")
    }
    real_passes = [
        {"evidence_origin": "REAL_CONTRACTUAL"} for _ in range(4)
    ]
    with pytest.raises(GateEvidenceError, match="G6_EVIDENCE_ORIGIN_MISMATCH"):
        _g6_chain_origin(g0, real_predecessors, real_passes)


def _build_synthetic_g6_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_m: bool = True,
    unresolved_m: bool = False,
):
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g0 = _synthetic_g0(context, manifest, manifest_sha256, ledger, monkeypatch)
    assert g0["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert g0["evidence_origin"] == "SYNTHETIC"
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database_path = context.run_directory / "isolated.sqlite3"
    g2 = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database_path,
    )

    catalog_ids_before = read_sqlite_ids(
        context.run_directory, database_path, "catalog_runs",
    )
    _add_catalog(database_path)
    _catalog_supervisor, catalog_supervisor_hash = _record_supervisor_receipt(
        context.run_directory, ledger, run_id=context.run_id, stage="catalog",
    )
    g3 = reconcile_g3_catalog(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g2_receipt=g2,
        ledger_snapshot=ledger.snapshot(),
        database_catalog_ids_before=catalog_ids_before,
    )
    g3.update({
        "supervisor_stage": "catalog",
        "supervisor_receipt_file": "g3-catalog-supervisor-receipt.json",
        "supervisor_receipt_sha256": catalog_supervisor_hash,
    })
    persist_gate_receipt(context.run_directory, ledger, g3)
    ledger.update_execution(
        gate="G3", status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result="OFFLINE_SYNTHETIC_PASS",
    )
    assert g3["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert g3["evidence_origin"] == "SYNTHETIC"

    media = [
        {
            "id": 1, "profile": "F", "message_id": 1,
            "telegram_media_id": "synthetic-f-media",
            "filename": "f.bin", "payload": b"synthetic F bytes\n",
        },
    ]
    if include_m:
            media.append({
                "id": 2, "profile": "M", "message_id": 2,
                "telegram_media_id": "synthetic-m-media",
                "filename": "m.bin", "payload": None,
            })
    download_root = context.run_directory / "downloads"
    download_root_guard = _create_private_directory(download_root)
    download_root_guard.close()
    for item in media:
        expected_bytes = (
            len(item["payload"]) if item["payload"] is not None else GIB
        )
        item["expected_bytes"] = expected_bytes
        alias = ledger.register_media(
            f"{CHANNEL_ID}:{item['message_id']}:0",
            profile=str(item["profile"]), expected_bytes=expected_bytes,
        )
        item["alias"] = alias
        ledger.begin_attempt(alias)
        reservation_id = ledger.reserve_bytes(alias, expected_bytes)
        ledger.settle_bytes(
            reservation_id, observed=expected_bytes,
            measurement_source="SYNTHETIC_TEST",
        )

    db = sqlite3.connect(database_path)
    try:
        db.execute("ALTER TABLE catalog_nodes ADD COLUMN title TEXT")
        db.executemany(
            "INSERT INTO catalog_nodes(id,channel_id,parent_id,kind,is_active,title) "
            "VALUES(?,?,?,?,?,?)",
            (
                (100, CHANNEL_ID, None, "track", 1, "t"),
                (101, CHANNEL_ID, 100, "course", 1, "c"),
                (102, CHANNEL_ID, 101, "module", 1, "m"),
                (103, CHANNEL_ID, 102, "lesson", 1, "l"),
            ),
        )
        db.executescript(
            "CREATE TABLE media_items(id INTEGER PRIMARY KEY,channel_id INTEGER," 
            "telegram_message_id INTEGER,media_ordinal INTEGER,telegram_media_id TEXT," 
            "kind TEXT,file_size_bytes INTEGER,original_filename TEXT,catalog_node_id INTEGER," 
            "remote_observation_state TEXT);"
            "CREATE TABLE downloads(media_item_id INTEGER PRIMARY KEY,state TEXT," 
            "final_path TEXT,partial_path TEXT,expected_bytes INTEGER,downloaded_bytes INTEGER," 
            "sha256 TEXT,attempts INTEGER,owner_pid INTEGER,remote_identity_media_id TEXT," 
            "remote_identity_kind TEXT,remote_identity_size INTEGER,remote_identity_provenance TEXT);"
        )
        for item in media:
            lineage = (
                ("track", "t"), ("course", "c"),
                ("module", "m"), ("lesson", "l"),
            )
            candidate = DownloadCandidate(
                media_item_id=int(item["id"]), channel_id=CHANNEL_ID,
                telegram_message_id=int(item["message_id"]), media_ordinal=0,
                telegram_media_id=str(item["telegram_media_id"]),
                expected_bytes=int(item["expected_bytes"]),
                original_filename=str(item["filename"]), lineage=(lineage[-1],),
            )
            final_path, partial_path = destination_paths(download_root, candidate)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if item["payload"] is None:
                file_sha256 = _write_synthetic_sparse_zero_file(
                    final_path, int(item["expected_bytes"]),
                )
            else:
                payload = bytes(item["payload"])
                final_path.write_bytes(payload)
                file_sha256 = hashlib.sha256(payload).hexdigest()
            db.execute(
                "INSERT INTO media_items VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    item["id"], CHANNEL_ID, item["message_id"], 0,
                    item["telegram_media_id"], "DOCUMENT", item["expected_bytes"],
                    item["filename"], 103, "OBSERVED",
                ),
            )
            db.execute(
                "INSERT INTO downloads VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["id"], "DOWNLOADED", str(final_path), str(partial_path),
                    item["expected_bytes"], item["expected_bytes"], file_sha256,
                    1, None, item["telegram_media_id"], "DOCUMENT",
                    item["expected_bytes"], "CAPTURED_AT_START",
                ),
            )
            if unresolved_m:
                assert not include_m
                db.execute(
                    "INSERT INTO media_items VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        99, CHANNEL_ID, 2, 0, "synthetic-unresolved-m",
                        "DOCUMENT", GIB, "m-unknown.bin", 103, "UNKNOWN",
                    ),
                )
        db.commit()
    finally:
        db.close()

    for profile in (("F", "M") if include_m else ("F",)):
        profile_media = [item for item in media if item["profile"] == profile]
        for pass_index in (1, 2):
            stage = "queue_f" if profile == "F" else "queue_m"
            supervisor_file, supervisor_hash = _record_supervisor_receipt(
                context.run_directory, ledger, run_id=context.run_id,
                stage=stage,
                receipt_name=g5_supervisor_receipt_filename(profile, pass_index),
            )
            first_pass_bytes = sum(
                int(item["expected_bytes"]) for item in profile_media
            )
            transfer_cap = (
                F_CAP if profile == "F"
                else media_m_cap(int(profile_media[0]["expected_bytes"]))
            )
            receipt = {
                "schema": "telegram-courses-s9-g5-queue-receipt-v1",
                "version": 1,
                "gate": "G5",
                "run_id": context.run_id,
                "manifest_sha256": manifest_sha256,
                "channel_id": CHANNEL_ID,
                "database_file": database_path.name,
                "download_root": download_root.name,
                "profile": profile,
                "pass_index": pass_index,
                "stage": stage,
                "status": "OFFLINE_SYNTHETIC_PASS",
                "evidence_origin": "SYNTHETIC",
                "measurement_source": "SYNTHETIC_TEST",
                "supervisor_receipt_file": supervisor_file,
                "supervisor_receipt_sha256": supervisor_hash,
                "observed_bytes": first_pass_bytes if pass_index == 1 else 0,
                "max_media_items": len(profile_media),
                "max_transfer_bytes": transfer_cap if pass_index == 1 else 1,
                "workers": 1,
                "attempts_per_media": 1,
                "all_items_already_valid": pass_index == 2,
            }
            persist_g5_queue_receipt(context.run_directory, ledger, receipt)
            ledger.update_execution(
                gate="G5", status="RUNNING",
                elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
                deadline_ns=context.deadline_ns, process_state="EXITED",
                result="OFFLINE_SYNTHETIC_PASS",
                observed_bytes=receipt["observed_bytes"],
            )

    g6 = reconcile_g6_downloads(
        context.run_directory,
        database_path,
        download_root,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        ledger=ledger,
        ledger_snapshot=ledger.snapshot(),
    )
    if unresolved_m:
        assert g6["status"] == "BLOCKED"
        return context, manifest, manifest_sha256, ledger, g1, g2, g6, database_path
    expected_g6_status = "OFFLINE_SYNTHETIC_PASS" if include_m else "PARTIAL"
    assert g6["status"] == expected_g6_status
    assert g6["evidence_origin"] == "SYNTHETIC"
    assert len(g6["g5_queue_receipts"]) == (4 if include_m else 2)
    assert g6["real_evidence_status"] == "REAL_EVIDENCE_PENDING"
    if not include_m:
        assert g6["g5_m_status"] == "BLOCKED_DATASET"
        assert g6["g6_aggregate_status"] == "PARTIAL"
        assert g6["g7_real_eligible"] is False
        assert g6["nfr02_real"] == "NOT_TESTED"

    persist_gate_receipt(context.run_directory, ledger, g6)
    ledger.update_execution(
        gate="G6", status="PARTIAL" if not include_m else "RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result="PARTIAL" if not include_m else "OFFLINE_SYNTHETIC_PASS",
    )
    reopened = read_validated_gate_receipt(
        context.run_directory, S9OperationalLedger(context.ledger_path).snapshot(),
        "G6", run_id=context.run_id, manifest_sha256=manifest_sha256,
    )
    assert reopened["status"] == expected_g6_status
    assert reopened["evidence_origin"] == "SYNTHETIC"
    assert reopened["status"] != "PASS"
    assert reopened["real_evidence_status"] == "REAL_EVIDENCE_PENDING"
    assert {
        (row["profile"], row["pass_index"])
        for row in reopened["g5_queue_receipts"]
    } == {
        (profile, pass_index)
        for profile in (("F", "M") if include_m else ("F",))
        for pass_index in (1, 2)
    }
    return context, manifest, manifest_sha256, ledger, g1, g2, reopened, database_path


def test_synthetic_g6_reconciles_and_reopens_physical_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build_synthetic_g6_fixture(tmp_path, monkeypatch, include_m=True)


def test_g6_partial_without_m_requires_proven_f_and_blocks_g7(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, manifest, manifest_sha256, ledger, g1, g2, g6, database_path = (
        _build_synthetic_g6_fixture(tmp_path, monkeypatch, include_m=False)
    )
    assert g6["status"] == "PARTIAL"
    assert g6["g5_m_status"] == "BLOCKED_DATASET"
    assert g6["g6_aggregate_status"] == "PARTIAL"
    assert g6["g7_real_eligible"] is False
    assert g6["nfr02_real"] == "NOT_TESTED"
    assert {
        (row["profile"], row["pass_index"])
        for row in g6["g5_queue_receipts"]
    } == {("F", 1), ("F", 2)}
    assert not (context.run_directory / g5_queue_receipt_filename("M", 1)).exists()
    assert not (context.run_directory / g5_queue_receipt_filename("M", 2)).exists()

    snapshot = ledger.snapshot()
    blocked = reconcile_g7_scan(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence=g1,
        g2_evidence=g2,
        g6_evidence=g6,
        baseline_scan_run_id="not-started",
        database_scan_ids_before=set(),
        database_sha256_before="a" * 64,
        ledger_before=snapshot,
        ledger_after=snapshot,
        requested_max_messages=1,
        application_exit_code=0,
        external_exit_code=0,
        stage_started_ns=1,
        stage_finished_ns=2,
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["reason"] == "PREDECESSOR_PROVENANCE_OR_BASELINE_INVALID"


def test_g6_without_m_stays_blocked_when_m_sized_metadata_is_unresolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _context, _manifest_value, _manifest_sha256, _ledger, _g1, _g2, g6, _database = (
        _build_synthetic_g6_fixture(
            tmp_path, monkeypatch, include_m=False, unresolved_m=True,
        )
    )
    assert g6["status"] == "BLOCKED"


def _synthetic_g7(
    context,
    manifest: dict[str, object],
    manifest_sha256: str,
    ledger: S9OperationalLedger,
    g1: dict[str, object],
    g2: dict[str, object],
    g6: dict[str, object],
    database_path: Path,
    *,
    terminal: str = "COMPLETE",
    external_exit_code: int | None = None,
    database_high_water_before: int | None = None,
    database_window: int = 50,
    sync_index: int = 1,
    previous_g7_evidence: dict[str, object] | None = None,
) -> dict[str, object]:
    baseline_id, high_water = read_g7_baseline(
        context.run_directory, database_path, channel_id=manifest["channel_id"],
    )
    database_sha256_before = _database_sha256(database_path)
    ids_before = read_sqlite_ids(context.run_directory, database_path, "scan_runs")
    ledger_before = ledger.snapshot()
    ledger_scan_id = ledger.begin_scan(
        max_messages=2, incremental=True, reconcile_window=50,
    )
    now = datetime.now(UTC).isoformat()
    complete = terminal == "COMPLETE"
    scan_status = "COMPLETE" if complete else "PARTIAL"
    stop_reason = None if complete else "MESSAGE_LIMIT"
    recorded_before = (
        high_water if database_high_water_before is None
        else database_high_water_before
    )
    watermark_after = 12 if complete else high_water
    snapshot_head = 12
    db = sqlite3.connect(database_path)
    try:
        db.execute(
            "INSERT INTO scan_runs(id,channel_id,status,started_at,finished_at,"
            "watermark_message_id,messages_seen,stop_reason,sync_mode,"
            "sync_baseline_confirmed,sync_high_water_before,"
            "sync_reconcile_floor_message_id,sync_reconcile_window,"
            "sync_snapshot_head_message_id,sync_max_messages,messages_unverified) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"db-sync-{sync_index}", CHANNEL_ID, scan_status, now, now, watermark_after,
                2, stop_reason, "INCREMENTAL", 1, recorded_before,
                max(1, recorded_before - database_window + 1),
                database_window, snapshot_head, 2, 0,
            ),
        )
        db.execute(
            "INSERT INTO sync_checkpoints VALUES(?,?,?,?,?,?,?)",
            (f"db-sync-{sync_index}", CHANNEL_ID, watermark_after, 2, None, scan_status, now),
        )
        db.commit()
    finally:
        db.close()
    ledger.finish_scan(ledger_scan_id, 2)
    supervisor_name, supervisor_hash = _record_supervisor_receipt(
        context.run_directory,
        ledger,
        run_id=context.run_id,
        stage="scan",
        receipt_name=f"g7-scan-supervisor-receipt-{sync_index:02d}.json",
        exit_code=0 if complete else 4,
        external_exit_code=external_exit_code,
    )
    ledger_after = ledger.snapshot()
    stage_started_ns = time.time_ns() - 5_000_000_000
    evidence = reconcile_g7_scan(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence=g1,
        g2_evidence=g2,
        g6_evidence=g6,
        baseline_scan_run_id=baseline_id,
        database_scan_ids_before=ids_before,
        database_sha256_before=database_sha256_before,
        ledger_before=ledger_before,
        ledger_after=ledger_after,
        requested_max_messages=2,
        application_exit_code=0 if complete else 4,
        external_exit_code=(
            (0 if complete else 4)
            if external_exit_code is None else external_exit_code
        ),
        stage_started_ns=stage_started_ns,
        stage_finished_ns=time.time_ns() + 5_000_000_000,
        sync_index=sync_index,
        previous_g7_evidence=previous_g7_evidence,
    )
    evidence.update({
        "supervisor_stage": "scan",
        "supervisor_receipt_file": supervisor_name,
        "supervisor_receipt_sha256": supervisor_hash,
    })
    persist_gate_receipt(context.run_directory, ledger, evidence)
    if evidence["status"] == "PARTIAL":
        ledger.update_execution(
            gate="G7", status="PARTIAL",
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
            deadline_ns=context.deadline_ns, process_state="EXITED",
            result="PARTIAL", cause="PROCESS",
        )
    else:
        ledger.update_execution(
            gate="G7", status="RUNNING",
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
            deadline_ns=context.deadline_ns, process_state="EXITED",
            result="OFFLINE_SYNTHETIC_PASS",
        )
    return evidence


def _g7_fixture(
    tmp_path: Path,
    *,
    duplicate_messages: bool = False,
):
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database_path = context.run_directory / "g7-fixture.sqlite3"
    g2 = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database_path,
    )
    _add_s7_schema(database_path)
    if duplicate_messages:
        db = sqlite3.connect(database_path)
        try:
            db.executescript(
                "ALTER TABLE messages RENAME TO messages_legacy;"
                "CREATE TABLE messages(channel_id INTEGER,telegram_message_id INTEGER,body TEXT);"
                "INSERT INTO messages SELECT channel_id,telegram_message_id,body FROM messages_legacy;"
                "INSERT INTO messages SELECT channel_id,telegram_message_id,body "
                "FROM messages_legacy LIMIT 1;"
                "DROP TABLE messages_legacy;"
            )
            db.commit()
        finally:
            db.close()
    g6 = _synthetic_g6(
        context, manifest, manifest_sha256, ledger, database_path,
    )
    return context, manifest, manifest_sha256, ledger, g1, g2, g6, database_path


async def _collect(gateway: object, *, run_id: str = "run-1") -> dict[str, object]:
    manifest = _manifest()
    return await collect_g1_evidence(
        run_id=run_id,
        manifest=manifest,
        manifest_sha256=sha256_bytes(_canonical(manifest)),
        gateway_factory=lambda _credentials: gateway,
        credentials_loader=lambda: TelegramCredentials(12345, "a" * 32),
    )


class _FakeGateway:
    def __init__(self, state: AuthState, result: DiscoveryResult | None = None) -> None:
        self.state = state
        self.result = result
        self.closed = False

    async def restore(self):
        return self.state

    async def discover_channels(self, _request):
        if self.result is None:
            raise RuntimeError("synthetic adapter failure")
        return self.result

    async def close(self):
        self.closed = True


def _discovery(
    channel_id: int = CHANNEL_ID, *, complete: bool = True,
    title: str = "SYNTHETIC_CHANNEL",
) -> DiscoveryResult:
    return DiscoveryResult(
        channels=(ChannelSummary(
            telegram_chat_id=channel_id,
            title=title,
            username=None,
            kind=ChannelKind.BROADCAST_CHANNEL,
        ),),
        complete=complete,
        stop_reason=None if complete else __import__(
            "telegram_courses.channel_discovery", fromlist=["DiscoveryStopReason"],
        ).DiscoveryStopReason.PAGE_LIMIT,
        stats=DiscoveryStats(
            pages_requested=1, pages_received=1, raw_dialogs_received=1,
            unique_candidates=1, elapsed_seconds=0.01, limits=DiscoveryLimits(),
        ),
    )


def test_g1_valid_authenticated_gateway_remains_synthetic() -> None:
    gateway = _FakeGateway(AuthState.AUTHENTICATED, _discovery())
    evidence = asyncio.run(_collect(gateway))
    assert evidence["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert evidence["evidence_origin"] == "SYNTHETIC"
    assert evidence["cleanup_complete"] is True
    assert gateway.closed is True
    manifest = _manifest()
    status, _reason = validate_g1_evidence(
        evidence, run_id="run-1", manifest=manifest,
        manifest_sha256=sha256_bytes(_canonical(manifest)),
    )
    assert status == "OFFLINE_SYNTHETIC_PASS"


def test_g1_blocks_selected_channel_when_alias_does_not_match() -> None:
    gateway = _FakeGateway(
        AuthState.AUTHENTICATED,
        _discovery(title="Different private channel"),
    )
    evidence = asyncio.run(_collect(gateway))
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == "TARGET_CHANNEL_ALIAS_MISMATCH"
    assert gateway.closed is True


@pytest.mark.parametrize(
    ("state", "result", "reason"),
    [
        (AuthState.AUTH_REQUIRED, _discovery(), "AUTHENTICATION_REQUIRED"),
        (AuthState.AUTHENTICATED, _discovery(CHANNEL_ID - 1), "TARGET_CHANNEL_NOT_UNIQUELY_DISCOVERED"),
        (AuthState.AUTHENTICATED, _discovery(complete=False), "CHANNEL_DISCOVERY_INCOMPLETE"),
        (AuthState.AUTHENTICATED, None, "DISCOVERY_ADAPTER_FAILURE"),
    ],
)
def test_g1_auth_channel_and_discovery_failures_block(state, result, reason) -> None:
    gateway = _FakeGateway(state, result)
    evidence = asyncio.run(_collect(gateway))
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == reason
    assert evidence["evidence_origin"] == "SYNTHETIC"
    assert gateway.closed is True


def test_g1_missing_provenance_identity_and_legacy_evidence_block() -> None:
    manifest = _manifest()
    manifest_sha256 = sha256_bytes(_canonical(manifest))
    legacy = {
        "schema_version": 1,
        "gate": "G1",
        "run_id": "run-1",
        "manifest_sha256": manifest_sha256,
        "authentication": "AUTHENTICATED",
        "discovery_complete": True,
        "channel_id": CHANNEL_ID,
        "channel_alias": "SYNTHETIC_CHANNEL",
        "target_match_count": 1,
        "cleanup_complete": True,
        "status": "PASS",
    }
    status, _reason = validate_g1_evidence(
        legacy, run_id="run-1", manifest=manifest, manifest_sha256=manifest_sha256,
    )
    assert status == "BLOCKED"
    legacy["evidence_origin"] = "SYNTHETIC"
    legacy["run_id"] = "different-run"
    status, _reason = validate_g1_evidence(
        legacy, run_id="run-1", manifest=manifest, manifest_sha256=manifest_sha256,
    )
    assert status == "BLOCKED"
    legacy["run_id"] = "run-1"
    legacy["channel_id"] = CHANNEL_ID - 1
    status, _reason = validate_g1_evidence(
        legacy, run_id="run-1", manifest=manifest, manifest_sha256=manifest_sha256,
    )
    assert status == "BLOCKED"


def test_synthetic_g1_g2_g3_receipts_reopen_without_real_promotion(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    assert read_validated_gate_receipt(
        context.run_directory, ledger.snapshot(), "G1",
        run_id=context.run_id, manifest_sha256=manifest_sha256,
    )["status"] == "OFFLINE_SYNTHETIC_PASS"

    database_path = context.run_directory / "isolated.sqlite3"
    g2 = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database_path,
    )
    assert g2["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert g2["evidence_origin"] == "SYNTHETIC"
    assert ledger.snapshot()["run"]["result"] == "OFFLINE_SYNTHETIC_PASS"

    catalog_ids_before = read_sqlite_ids(
        context.run_directory, database_path, "catalog_runs",
    )
    _add_catalog(database_path)
    _file, supervisor_hash = _record_supervisor_receipt(
        context.run_directory, ledger, run_id=context.run_id, stage="catalog",
    )
    g3_snapshot = ledger.snapshot()
    g3 = reconcile_g3_catalog(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g2_receipt=g2,
        ledger_snapshot=g3_snapshot,
        database_catalog_ids_before=catalog_ids_before,
    )
    g3.update({
        "supervisor_stage": "catalog",
        "supervisor_receipt_file": "g3-catalog-supervisor-receipt.json",
        "supervisor_receipt_sha256": supervisor_hash,
    })
    persist_gate_receipt(context.run_directory, ledger, g3)
    ledger.update_execution(
        gate="G3", status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result=g3["status"],
    )
    reopened = S9OperationalLedger(context.ledger_path)
    for gate in ("G1", "G2", "G3"):
        receipt = read_validated_gate_receipt(
            context.run_directory, reopened.snapshot(), gate,
            run_id=context.run_id, manifest_sha256=manifest_sha256,
        )
        assert receipt["status"] == "OFFLINE_SYNTHETIC_PASS"
        assert receipt["evidence_origin"] == "SYNTHETIC"
        assert receipt["status"] != "PASS"
    assert g3["hierarchy"] == {"TRACK": 1, "COURSE": 2, "MODULE": 2}


@pytest.mark.parametrize(
    ("observed_modules", "expected_status", "expected_reason"),
    [
        (3, "OFFLINE_SYNTHETIC_PASS", "SYNTHETIC_GATEWAY_ONLY"),
        (1, "BLOCKED", "BLOCKED_DATASET"),
    ],
)
def test_g3_planned_catalog_expectation_checks_realized_minimums(
    tmp_path: Path, observed_modules: int,
    expected_status: str, expected_reason: str,
) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(
        tmp_path, module_count=observed_modules, planned_catalog=True,
    )
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database_path = context.run_directory / "isolated.sqlite3"
    g2 = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database_path,
    )
    catalog_ids_before = read_sqlite_ids(
        context.run_directory, database_path, "catalog_runs",
    )
    _add_catalog(database_path, modules=observed_modules)
    _file, supervisor_hash = _record_supervisor_receipt(
        context.run_directory, ledger, run_id=context.run_id, stage="catalog",
    )

    g3 = reconcile_g3_catalog(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g2_receipt=g2,
        ledger_snapshot=ledger.snapshot(),
        database_catalog_ids_before=catalog_ids_before,
    )
    assert g3["status"] == expected_status
    assert g3["reason"] == expected_reason
    if observed_modules >= 2:
        assert g3["hierarchy"] == {
            "TRACK": 1, "COURSE": 2, "MODULE": observed_modules,
        }


def test_g3_accepts_audited_synthetic_g2_message_limit_sample(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database_path = context.run_directory / "isolated.sqlite3"
    g2 = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database_path,
        scan_status="PARTIAL", stop_reason="MESSAGE_LIMIT",
        max_messages=2, observed_messages=2, message_count=2,
        application_exit_code=4,
    )
    assert g2["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert g2["application_exit_code"] == 4

    catalog_ids_before = read_sqlite_ids(
        context.run_directory, database_path, "catalog_runs",
    )
    _add_catalog(database_path)
    _file, supervisor_hash = _record_supervisor_receipt(
        context.run_directory, ledger, run_id=context.run_id, stage="catalog",
    )
    g3 = reconcile_g3_catalog(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g2_receipt=g2,
        ledger_snapshot=ledger.snapshot(),
        database_catalog_ids_before=catalog_ids_before,
    )
    assert g3["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert g3["evidence_origin"] == "SYNTHETIC"
    g3.update({
        "supervisor_stage": "catalog",
        "supervisor_receipt_file": "g3-catalog-supervisor-receipt.json",
        "supervisor_receipt_sha256": supervisor_hash,
    })
    persist_gate_receipt(context.run_directory, ledger, g3)
    ledger.update_execution(
        gate="G3", status="RUNNING",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
        deadline_ns=context.deadline_ns, process_state="EXITED",
        result=g3["status"],
    )

    reopened = S9OperationalLedger(context.ledger_path)
    g2_reopened = read_validated_gate_receipt(
        context.run_directory, reopened.snapshot(), "G2",
        run_id=context.run_id, manifest_sha256=manifest_sha256,
    )
    g3_reopened = read_validated_gate_receipt(
        context.run_directory, reopened.snapshot(), "G3",
        run_id=context.run_id, manifest_sha256=manifest_sha256,
    )
    assert g2_reopened["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert g3_reopened["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert g3_reopened["evidence_origin"] == "SYNTHETIC"

    bad_context, bad_manifest, bad_hash, bad_ledger = _start_run(
        tmp_path / "changed-scan",
    )
    bad_g1 = _synthetic_g1(
        bad_context, bad_manifest, bad_hash, bad_ledger,
    )
    bad_database = bad_context.run_directory / "isolated.sqlite3"
    bad_g2 = _synthetic_g2(
        bad_context, bad_manifest, bad_hash, bad_ledger, bad_g1, bad_database,
    )
    db = sqlite3.connect(bad_database)
    try:
        db.execute(
            "UPDATE scan_runs SET status='PARTIAL', stop_reason='TIMEOUT' "
            "WHERE id=?",
            (bad_g2["scan_run_id"],),
        )
        db.commit()
    finally:
        db.close()
    bad_catalog_ids = read_sqlite_ids(
        bad_context.run_directory, bad_database, "catalog_runs",
    )
    _add_catalog(bad_database)
    _record_supervisor_receipt(
        bad_context.run_directory, bad_ledger,
        run_id=bad_context.run_id, stage="catalog",
    )
    rejected = reconcile_g3_catalog(
        bad_context.run_directory,
        bad_database,
        run_id=bad_context.run_id,
        manifest=bad_manifest,
        manifest_sha256=bad_hash,
        g2_receipt=bad_g2,
        ledger_snapshot=bad_ledger.snapshot(),
        database_catalog_ids_before=bad_catalog_ids,
    )
    assert rejected["status"] == "BLOCKED"
    assert rejected["reason"] == "PREDECESSOR_RECEIPT_INVALID"


def test_g2_requires_audited_g1_and_persisted_scan(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    database_path = context.run_directory / "missing.sqlite3"
    result = reconcile_g2_scan(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence={},
        database_scan_ids_before=set(),
        ledger_before=ledger.snapshot(),
        ledger_after=ledger.snapshot(),
        requested_max_messages=200,
        stage_started_ns=time.time_ns(),
        stage_finished_ns=time.time_ns() + 1,
    )
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "G1_RECEIPT_INVALID"


def test_g2_blocks_missing_database_scan_and_invalid_limits(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database_path = context.run_directory / "isolated.sqlite3"
    before = ledger.snapshot()
    scan_id = ledger.begin_scan(max_messages=200)
    ledger.finish_scan(scan_id, 2)
    _create_dataset(database_path)
    (context.run_directory / "isolated.sqlite3").unlink()
    result = reconcile_g2_scan(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence=g1,
        database_scan_ids_before=set(),
        ledger_before=before,
        ledger_after=ledger.snapshot(),
        requested_max_messages=201,
        stage_started_ns=time.time_ns(),
        stage_finished_ns=time.time_ns() + 1,
    )
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "SCAN_LIMIT_INVALID"
    missing_scan = reconcile_g2_scan(
        context.run_directory,
        database_path,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence=g1,
        database_scan_ids_before=set(),
        ledger_before=before,
        ledger_after=ledger.snapshot(),
        requested_max_messages=200,
        external_exit_code=0,
        stage_started_ns=time.time_ns(),
        stage_finished_ns=time.time_ns() + 1,
    )
    assert missing_scan["status"] == "BLOCKED"
    assert missing_scan["reason"] in {"DATABASE_UNAVAILABLE", "DATABASE_NOT_PRIVATE"}


def test_g2_unknown_scan_status_and_fourth_reservation_block(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database_path = context.run_directory / "isolated.sqlite3"
    evidence = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database_path,
        scan_status="RUNNING",
    )
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == "SCAN_TERMINAL_STATE_INVALID"


def test_g2_accepts_only_exact_message_limit_partial_with_exit_four(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path / "valid")
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database = context.run_directory / "limited.sqlite3"
    accepted = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database,
        scan_status="PARTIAL", stop_reason="MESSAGE_LIMIT",
        max_messages=2, observed_messages=2, message_count=2,
        application_exit_code=4,
    )
    assert accepted["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert accepted["evidence_origin"] == "SYNTHETIC"
    assert accepted["reason"] == "SYNTHETIC_GATEWAY_ONLY"
    reopened = read_validated_gate_receipt(
        context.run_directory, S9OperationalLedger(context.ledger_path).snapshot(), "G2",
        run_id=context.run_id, manifest_sha256=manifest_sha256,
    )
    assert reopened["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert reopened["observed_messages"] == 2
    assert _read_supervisor_receipt_evidence(
        context.run_directory / "g2-scan-supervisor-receipt.json",
        ledger.snapshot(), run_id=context.run_id, stage="scan",
    ) == accepted["supervisor_receipt_sha256"]

    timeout_context, timeout_manifest, timeout_hash, timeout_ledger = _start_run(
        tmp_path / "timeout",
    )
    timeout_g1 = _synthetic_g1(
        timeout_context, timeout_manifest, timeout_hash, timeout_ledger,
    )
    timeout = _synthetic_g2(
        timeout_context, timeout_manifest, timeout_hash, timeout_ledger,
        timeout_g1, timeout_context.run_directory / "timed-out.sqlite3",
        scan_status="PARTIAL", stop_reason="TIMEOUT",
        max_messages=2, observed_messages=2, message_count=2,
        application_exit_code=4,
    )
    assert timeout["status"] == "BLOCKED"
    assert timeout["reason"] == "SCAN_TERMINAL_STATE_INVALID"

    mismatch_context, mismatch_manifest, mismatch_hash, mismatch_ledger = _start_run(
        tmp_path / "exit-mismatch",
    )
    mismatch_g1 = _synthetic_g1(
        mismatch_context, mismatch_manifest, mismatch_hash, mismatch_ledger,
    )
    mismatch = _synthetic_g2(
        mismatch_context, mismatch_manifest, mismatch_hash, mismatch_ledger,
        mismatch_g1, mismatch_context.run_directory / "wrong-exit.sqlite3",
        scan_status="PARTIAL", stop_reason="MESSAGE_LIMIT",
        max_messages=2, observed_messages=2, message_count=2,
        application_exit_code=0,
    )
    assert mismatch["status"] == "BLOCKED"
    assert mismatch["reason"] == "SCAN_TERMINAL_STATE_INVALID"


@pytest.mark.parametrize(
    ("application_exit_code", "external_exit_code"),
    ((0, 4), (4, 0)),
)
def test_g2_blocks_application_and_supervisor_exit_code_divergence(
    tmp_path: Path,
    application_exit_code: int,
    external_exit_code: int,
) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    evidence = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1,
        context.run_directory / "exit-divergence.sqlite3",
        application_exit_code=application_exit_code,
        external_exit_code=external_exit_code,
    )
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == "APPLICATION_EXTERNAL_EXIT_MISMATCH"


@pytest.mark.parametrize(
    ("application_exit_code", "external_exit_code", "expected_reason"),
    ((0, None, "APPLICATION_EXTERNAL_EXIT_MISMATCH"),
     (5, 5, "SCAN_EXIT_CODE_INVALID")),
)
def test_g2_blocks_missing_or_unexpected_exit_codes(
    tmp_path: Path,
    application_exit_code: int,
    external_exit_code: int | None,
    expected_reason: str,
) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    evidence = reconcile_g2_scan(
        context.run_directory,
        context.run_directory / "not-created.sqlite3",
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence=g1,
        database_scan_ids_before=set(),
        ledger_before=ledger.snapshot(),
        ledger_after=ledger.snapshot(),
        requested_max_messages=200,
        application_exit_code=application_exit_code,
        external_exit_code=external_exit_code,
        stage_started_ns=time.time_ns(),
        stage_finished_ns=time.time_ns() + 1,
    )
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == expected_reason


def test_g2_counter_divergence_and_stale_run_receipt_fail_closed(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    divergent = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1,
        context.run_directory / "counter-divergence.sqlite3",
        observed_messages=2,
        ledger_observed=1,
    )
    assert divergent["status"] == "BLOCKED"
    assert divergent["reason"] == "SCAN_COUNTER_DIVERGENCE"

    fresh, fresh_manifest, fresh_hash, fresh_ledger = _start_run(
        tmp_path / "stale-target",
    )
    (fresh.run_directory / "g2-gate-receipt.json").write_bytes(
        (context.run_directory / "g2-gate-receipt.json").read_bytes(),
    )
    (fresh.run_directory / "g2-scan-supervisor-receipt.json").write_bytes(
        (context.run_directory / "g2-scan-supervisor-receipt.json").read_bytes(),
    )
    with pytest.raises(GateEvidenceError):
        read_validated_gate_receipt(
            fresh.run_directory,
            fresh_ledger.snapshot(),
            "G2",
            run_id=fresh.run_id,
            manifest_sha256=fresh_hash,
        )


def test_g2_receipt_reopen_rejects_exit_code_tampering(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    evidence = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1,
        context.run_directory / "reopen.sqlite3",
    )
    assert evidence["status"] == "OFFLINE_SYNTHETIC_PASS"
    path = context.run_directory / "g2-gate-receipt.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["application_exit_code"] = 4
    path.write_bytes(_canonical(receipt) + b"\n")
    with pytest.raises(GateEvidenceError):
        read_validated_gate_receipt(
            context.run_directory,
            S9OperationalLedger(context.ledger_path).snapshot(),
            "G2",
            run_id=context.run_id,
            manifest_sha256=manifest_sha256,
        )


def test_g7_complete_incremental_reconciliation_reopens_as_synthetic_only(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, ledger, _g1, _g2, _g6, _db = _g7_fixture(
        tmp_path,
    )
    evidence = _synthetic_g7(
        context, manifest, manifest_sha256, ledger,
        read_validated_gate_receipt(
            context.run_directory, ledger.snapshot(), "G1",
            run_id=context.run_id, manifest_sha256=manifest_sha256,
        ),
        read_validated_gate_receipt(
            context.run_directory, ledger.snapshot(), "G2",
            run_id=context.run_id, manifest_sha256=manifest_sha256,
        ),
        read_validated_gate_receipt(
            context.run_directory, ledger.snapshot(), "G6",
            run_id=context.run_id, manifest_sha256=manifest_sha256,
        ),
        _db,
    )
    assert evidence["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert evidence["evidence_origin"] == "SYNTHETIC"
    assert evidence["window_size"] == 50
    assert evidence["high_water_before"] == 10
    assert evidence["high_water_after"] == 12
    assert evidence["deletions_inferred"] is False
    reopened = read_validated_gate_receipt(
        context.run_directory,
        S9OperationalLedger(context.ledger_path).snapshot(),
        "G7",
        run_id=context.run_id,
        manifest_sha256=manifest_sha256,
    )
    assert reopened == evidence


def test_g7_supports_two_distinct_idempotent_syncs_with_reopen(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, ledger, g1, g2, g6, database = _g7_fixture(
        tmp_path,
    )
    first = _synthetic_g7(
        context, manifest, manifest_sha256, ledger, g1, g2, g6, database,
        sync_index=1,
    )
    first_reopened = read_validated_gate_receipt(
        context.run_directory,
        ledger.snapshot(),
        "G7",
        run_id=context.run_id,
        manifest_sha256=manifest_sha256,
        receipt_index=1,
    )
    second = _synthetic_g7(
        context, manifest, manifest_sha256, ledger, g1, g2, g6, database,
        sync_index=2,
        previous_g7_evidence=first_reopened,
    )

    assert first["status"] == second["status"] == "OFFLINE_SYNTHETIC_PASS"
    assert first["incremental_scan_run_id"] != second["incremental_scan_run_id"]
    assert second["baseline_scan_run_id"] == first["incremental_scan_run_id"]
    assert second["high_water_before"] == first["high_water_after"] == 12
    assert second["high_water_after"] == 12
    assert second["previous_g7_receipt_sha256"]
    assert (context.run_directory / "g7-gate-receipt-01.json").is_file()
    assert (context.run_directory / "g7-gate-receipt-02.json").is_file()

    latest = read_validated_gate_receipt(
        context.run_directory,
        ledger.snapshot(),
        "G7",
        run_id=context.run_id,
        manifest_sha256=manifest_sha256,
    )
    assert latest["sync_index"] == 2
    assert latest["status"] == "OFFLINE_SYNTHETIC_PASS"


def test_g7_message_limit_is_partial_without_confirmed_high_water_promotion(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, ledger, g1, g2, g6, database = _g7_fixture(
        tmp_path,
    )
    evidence = _synthetic_g7(
        context, manifest, manifest_sha256, ledger, g1, g2, g6, database,
        terminal="PARTIAL",
    )
    assert evidence["status"] == "PARTIAL"
    assert evidence["application_exit_code"] == 4
    assert evidence["external_exit_code"] == 4
    assert evidence["high_water_before"] == 10
    assert evidence["confirmed_high_water_after"] == 10
    reopened = read_validated_gate_receipt(
        context.run_directory,
        S9OperationalLedger(context.ledger_path).snapshot(),
        "G7",
        run_id=context.run_id,
        manifest_sha256=manifest_sha256,
    )
    assert reopened["status"] == "PARTIAL"
    assert reopened["evidence_origin"] == "SYNTHETIC"


@pytest.mark.parametrize(
    ("fixture_overrides", "expected_reason"),
    (
        ({"database_window": 51}, "G7_INCREMENTAL_PERSISTENCE_DIVERGENCE"),
        ({"database_high_water_before": 11}, "G7_INCREMENTAL_PERSISTENCE_DIVERGENCE"),
        ({"external_exit_code": 4}, "APPLICATION_EXTERNAL_EXIT_MISMATCH"),
    ),
)
def test_g7_rejects_window_high_water_and_exit_code_divergence(
    tmp_path: Path,
    fixture_overrides: dict[str, object],
    expected_reason: str,
) -> None:
    context, manifest, manifest_sha256, ledger, g1, g2, g6, database = _g7_fixture(
        tmp_path,
    )
    evidence = _synthetic_g7(
        context, manifest, manifest_sha256, ledger, g1, g2, g6, database,
        **fixture_overrides,
    )
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == expected_reason


def test_g7_requires_attested_g6_and_rejects_synthetic_relabeling(
    tmp_path: Path,
) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database = context.run_directory / "missing-g6.sqlite3"
    g2 = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database,
    )
    _add_s7_schema(database)
    missing = reconcile_g7_scan(
        context.run_directory,
        database,
        run_id=context.run_id,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        g1_evidence=g1,
        g2_evidence=g2,
        g6_evidence={},
        baseline_scan_run_id="db-scan-1",
        database_scan_ids_before={"db-scan-1"},
        database_sha256_before=_database_sha256(database),
        ledger_before=ledger.snapshot(),
        ledger_after=ledger.snapshot(),
        requested_max_messages=2,
        application_exit_code=0,
        external_exit_code=0,
        stage_started_ns=time.time_ns(),
        stage_finished_ns=time.time_ns() + 1,
    )
    assert missing["status"] == "BLOCKED"
    assert missing.get("evidence_origin") != "REAL_CONTRACTUAL"

    # A synthetic receipt relabeled by the caller cannot release a real G7.
    context2, manifest2, hash2, ledger2, g1_2, g2_2, g6_2, database2 = _g7_fixture(
        tmp_path / "mislabelled",
    )
    forged_g6 = dict(g6_2) | {
        "status": "PASS",
        "evidence_origin": "REAL_CONTRACTUAL",
    }
    forged = _synthetic_g7(
        context2, manifest2, hash2, ledger2, g1_2, g2_2, forged_g6,
        database2,
    )
    assert forged["status"] == "BLOCKED"
    assert forged["reason"] == "PREDECESSOR_PROVENANCE_OR_BASELINE_INVALID"


def test_g7_rejects_duplicate_messages_and_stale_receipts(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger, g1, g2, g6, database = _g7_fixture(
        tmp_path / "duplicates", duplicate_messages=True,
    )
    duplicate = _synthetic_g7(
        context, manifest, manifest_sha256, ledger, g1, g2, g6, database,
    )
    assert duplicate["status"] == "BLOCKED"
    assert duplicate["reason"] == "G7_MESSAGE_DEDUPLICATION_FAILED"

    fresh, fresh_manifest, fresh_hash, fresh_ledger, _g1, _g2, _g6, fresh_db = _g7_fixture(
        tmp_path / "stale-source",
    )
    accepted = _synthetic_g7(
        fresh, fresh_manifest, fresh_hash, fresh_ledger, _g1, _g2, _g6, fresh_db,
    )
    assert accepted["status"] == "OFFLINE_SYNTHETIC_PASS"
    other, _other_manifest, other_hash, other_ledger = _start_run(
        tmp_path / "stale-target",
    )
    (other.run_directory / "g7-gate-receipt-01.json").write_bytes(
        (fresh.run_directory / "g7-gate-receipt-01.json").read_bytes(),
    )
    (other.run_directory / "g7-scan-supervisor-receipt-01.json").write_bytes(
        (fresh.run_directory / "g7-scan-supervisor-receipt-01.json").read_bytes(),
    )
    with pytest.raises(GateEvidenceError):
        read_validated_gate_receipt(
            other.run_directory,
            other_ledger.snapshot(),
            "G7",
            run_id=other.run_id,
            manifest_sha256=other_hash,
        )


def test_g7_rejects_incomplete_baseline_and_scan_limits(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger, _g1, _g2, _g6, database = _g7_fixture(
        tmp_path,
    )
    db = sqlite3.connect(database)
    try:
        db.execute("UPDATE scan_runs SET status='PARTIAL' WHERE id='db-scan-1'")
        db.execute("UPDATE sync_checkpoints SET status='PARTIAL' WHERE scan_run_id='db-scan-1'")
        db.commit()
    finally:
        db.close()
    with pytest.raises(GateEvidenceError, match="G7_COMPLETE_BASELINE_UNAVAILABLE"):
        read_g7_baseline(context.run_directory, database, channel_id=manifest["channel_id"])
    with pytest.raises(LedgerError, match="INVALID_NUMBER|SCAN_LIMIT_INVALID"):
        ledger.begin_scan(max_messages=201, incremental=True, reconcile_window=50)


def test_g3_blocks_mixed_provenance_and_insufficient_hierarchy(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    database_path = context.run_directory / "isolated.sqlite3"
    g2 = _synthetic_g2(
        context, manifest, manifest_sha256, ledger, g1, database_path,
    )
    # A synthetically tagged predecessor cannot be relabeled as a real pass.
    fake_real = dict(g2) | {"status": "PASS", "evidence_origin": "REAL_CONTRACTUAL"}
    before = read_sqlite_ids(context.run_directory, database_path, "catalog_runs")
    result = reconcile_g3_catalog(
        context.run_directory, database_path,
        run_id=context.run_id, manifest=manifest,
        manifest_sha256=manifest_sha256, g2_receipt=fake_real,
        ledger_snapshot=ledger.snapshot(), database_catalog_ids_before=before,
    )
    assert result["status"] == "BLOCKED"

    insufficient_context, insufficient_manifest, insufficient_hash, insufficient_ledger = _start_run(
        tmp_path / "insufficient", module_count=1,
    )
    insufficient_g1 = _synthetic_g1(
        insufficient_context, insufficient_manifest, insufficient_hash,
        insufficient_ledger,
    )
    insufficient_db = insufficient_context.run_directory / "isolated.sqlite3"
    insufficient_g2 = _synthetic_g2(
        insufficient_context, insufficient_manifest, insufficient_hash,
        insufficient_ledger, insufficient_g1, insufficient_db,
    )
    insufficient_before = read_sqlite_ids(
        insufficient_context.run_directory, insufficient_db, "catalog_runs",
    )
    _add_catalog(insufficient_db, modules=1)
    _record_supervisor_receipt(
        insufficient_context.run_directory, insufficient_ledger,
        run_id=insufficient_context.run_id, stage="catalog",
    )
    result = reconcile_g3_catalog(
        insufficient_context.run_directory, insufficient_db,
        run_id=insufficient_context.run_id, manifest=insufficient_manifest,
        manifest_sha256=insufficient_hash,
        g2_receipt=insufficient_g2,
        ledger_snapshot=insufficient_ledger.snapshot(),
        database_catalog_ids_before=insufficient_before,
    )
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "BLOCKED_DATASET"


def test_repeated_gate_receipt_and_stale_run_receipt_are_rejected(tmp_path: Path) -> None:
    context, manifest, manifest_sha256, ledger = _start_run(tmp_path)
    g1 = _synthetic_g1(context, manifest, manifest_sha256, ledger)
    with pytest.raises(SupervisorError):
        persist_gate_receipt(context.run_directory, ledger, g1)

    other_context, _manifest2, _manifest_sha256_2, other_ledger = _start_run(
        tmp_path / "second",
    )
    stale = context.run_directory / "g1-gate-receipt.json"
    (other_context.run_directory / "g1-gate-receipt.json").write_bytes(stale.read_bytes())
    with pytest.raises(GateEvidenceError):
        read_validated_gate_receipt(
            other_context.run_directory,
            other_ledger.snapshot(),
            "G1",
            run_id=other_context.run_id,
            manifest_sha256=manifest_sha256,
        )


def test_supervised_g1_requires_interactive_g0_before_supervisor(
    tmp_path: Path,
) -> None:
    context, _manifest, _manifest_sha256, ledger = _start_run(tmp_path)
    supervisor_called = False

    class NeverRunSupervisor:
        def __init__(self, **_kwargs) -> None:
            pass

        def run(self, *_args, **_kwargs):
            nonlocal supervisor_called
            supervisor_called = True
            raise AssertionError("G1 supervisor must not run without interactive G0")

    with pytest.raises(OfflineRunnerError, match="G0_CONFIRMATION_REQUIRED"):
        run_supervised_g1(
            context, tmp_path / "g1-work", supervisor_type=NeverRunSupervisor,
        )

    snapshot = ledger.snapshot()
    assert supervisor_called is False
    assert snapshot["run"]["gate"] == "G0"
    assert snapshot["run"]["status"] == "BLOCKED"
    assert any(
        event["event_type"] == "G0_CONFIRMATION_BLOCKED"
        for event in snapshot["critical_audit"]["events"]
    )
    assert not (context.run_directory / "g1-gate-receipt.json").exists()


def test_s9_ledger_caps_total_scan_budget_at_three_times_two_hundred(tmp_path: Path) -> None:
    context, _manifest, _manifest_sha256, ledger = _start_run(tmp_path)
    for _ in range(3):
        scan_id = ledger.begin_scan(max_messages=200)
        ledger.finish_scan(scan_id, 200)
    snapshot = ledger.snapshot()
    assert len(snapshot["scans"]) == 3
    assert sum(item["observed"] for item in snapshot["scans"]) == 600
    with pytest.raises(LedgerError, match="SCAN_LIMIT"):
        ledger.begin_scan(max_messages=1)
