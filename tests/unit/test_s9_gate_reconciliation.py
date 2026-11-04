from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from telegram_courses.s9_gate_reconciliation import (
    DISK_RESERVE,
    MIB,
    ReconciliationError,
    _persist_gate,
    _validate_queue_disk,
    reconcile_offline_evidence,
)
from telegram_courses.s9_operational_ledger import LedgerError, S9OperationalLedger
from telegram_courses.s9_supervisor import STAGE_TIMEOUTS_SECONDS
from telegram_courses.s9_supervisor_cli import start_supervised_run

pytestmark = pytest.mark.skipif(os.name != "nt", reason="S9 private-run validation is Windows-specific")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _snapshot_alias(
    ledger: S9OperationalLedger, channel_id: int, message_id: int, ordinal: int,
) -> str:
    return ledger.pseudonym(f"{channel_id}:{message_id}:{ordinal}")


def _write_database(
    path: Path, channel_id: int, *, modules: int = 2,
    final_path: Path, payload: bytes,
) -> None:
    db = sqlite3.connect(path)
    try:
        db.executescript(
            "CREATE TABLE messages(channel_id INTEGER,telegram_message_id INTEGER,"
            "message_date_utc TEXT,created_at TEXT,updated_at TEXT,last_seen_run_id TEXT,"
            "PRIMARY KEY(channel_id,telegram_message_id));"
            "CREATE TABLE scan_runs(id TEXT PRIMARY KEY,channel_id INTEGER,status TEXT,"
            "started_at TEXT,finished_at TEXT,watermark_message_id INTEGER,"
            "messages_seen INTEGER,stop_reason TEXT,sync_mode TEXT,sync_baseline_confirmed INTEGER,"
            "sync_high_water_before INTEGER,sync_reconcile_floor_message_id INTEGER,"
            "sync_reconcile_window INTEGER,sync_max_messages INTEGER,"
            "sync_snapshot_head_message_id INTEGER,messages_unverified INTEGER);"
            "CREATE TABLE sync_checkpoints(scan_run_id TEXT,channel_id INTEGER,"
            "watermark_message_id INTEGER,last_message_id INTEGER,status TEXT,updated_at TEXT);"
            "CREATE TABLE catalog_nodes(id INTEGER PRIMARY KEY,channel_id INTEGER,kind TEXT,is_active INTEGER);"
            "CREATE TABLE catalog_runs(id TEXT PRIMARY KEY,channel_id INTEGER,status TEXT,"
            "source_message_count INTEGER,catalog_node_count INTEGER,unresolved_count INTEGER);"
            "CREATE TABLE catalog_unresolved_sources(run_id TEXT);"
            "CREATE TABLE media_items(id INTEGER PRIMARY KEY,channel_id INTEGER,"
            "telegram_message_id INTEGER,media_ordinal INTEGER,kind TEXT,"
            "telegram_media_id TEXT,file_size_bytes INTEGER,remote_observation_state TEXT);"
            "CREATE TABLE downloads(id INTEGER PRIMARY KEY,media_item_id INTEGER,state TEXT,"
            "final_path TEXT,expected_bytes INTEGER,downloaded_bytes INTEGER,sha256 TEXT,"
            "remote_identity_media_id TEXT,remote_identity_kind TEXT,remote_identity_size INTEGER,"
            "remote_identity_provenance TEXT);"
        )
        channel_id = -1000000000123
        scan_started_at = datetime.now(timezone.utc).isoformat()
        for message_id in range(1, 6):
            db.execute(
                "INSERT INTO messages VALUES(?,?,?,?,?,?)",
                (channel_id, message_id, "2026-01-01T00:00:00+00:00", "synthetic", "synthetic", "scan-synthetic-1"),
            )
        db.execute(
            "INSERT INTO scan_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("scan-synthetic-1", channel_id, "COMPLETE", scan_started_at, "synthetic", 5, 5, None,
             "FULL", 0, None, None, 0, None, None, 0),
        )
        db.execute(
            "INSERT INTO sync_checkpoints VALUES(?,?,?,?,?,?)",
            ("scan-synthetic-1", channel_id, 5, 5, "COMPLETE", "synthetic"),
        )
        db.execute(
            "INSERT INTO scan_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("scan-synthetic-incremental-1", channel_id, "COMPLETE", scan_started_at, "synthetic", 5, 0, None,
             "INCREMENTAL", 1, 5, 1, 50, 200, 5, 0),
        )
        db.execute(
            "INSERT INTO sync_checkpoints VALUES(?,?,?,?,?,?)",
            ("scan-synthetic-incremental-1", channel_id, 5, 5, "COMPLETE", "synthetic"),
        )
        nodes = [(1, "TRACK"), (2, "COURSE"), (3, "COURSE")]
        nodes.extend((index + 4, "MODULE") for index in range(modules))
        db.executemany(
            "INSERT INTO catalog_nodes VALUES(?,?,?,1)",
            ((node_id, channel_id, kind) for node_id, kind in nodes),
        )
        db.execute(
            "INSERT INTO catalog_runs VALUES(?,?,?,?,?,?)",
            ("catalog-synthetic-1", channel_id, "COMPLETE", 5, len(nodes), 0),
        )
        media_id = "synthetic-remote-media-id"
        media_size = len(payload)
        db.execute(
            "INSERT INTO media_items VALUES(?,?,?,?,?,?,?,?)",
            (1, channel_id, 5, 0, "DOCUMENT", media_id, media_size, "OBSERVED"),
        )
        db.execute(
            "INSERT INTO downloads VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (1, 1, "DOWNLOADED", str(final_path.resolve()), media_size, media_size,
             hashlib.sha256(payload).hexdigest(), media_id, "DOCUMENT", media_size,
             "CAPTURED_AT_START"),
        )
        db.commit()
    finally:
        db.close()


def _attach_stage_and_disk_proofs(
    context: object, ledger: S9OperationalLedger, gates: dict[str, dict[str, object]],
    *, disk_shortfall: int = 0,
) -> None:
    queue = gates["G5"]
    g2_ids = [row["scan_run_id"] for row in gates["G2"]["invocations"]]
    g7_ids = [gates["G7"]["baseline_scan_run_id"], gates["G7"]["incremental_scan_run_id"]]
    scan_ids = list(dict.fromkeys([*g2_ids, *g7_ids]))
    stages: list[tuple[str, str | None]] = [("scan", scan_id) for scan_id in scan_ids]
    stages.extend([("catalog", None), ("inspection", None), ("queue_f", None)])
    if any(item["profile"] == "M" for item in gates["G4"]["plan"]["media"]):
        stages.append(("queue_m", None))
    stages.append(("verification_local", None))
    entries: list[dict[str, object]] = []
    for index, (stage, scan_id) in enumerate(stages):
        baseline = [
            {
                "timestamp_utc": "2026-10-30T12:00:00+00:00",
                "elapsed_seconds": sample_index * 0.25,
                "process_count": 1,
                "working_set_bytes": 100 * MIB,
                "private_bytes": 80 * MIB,
            }
            for sample_index in range(9)
        ]
        memory_samples = [
            *baseline,
            {
                "timestamp_utc": "2026-10-30T12:00:02.250000+00:00",
                "elapsed_seconds": 2.25,
                "process_count": 1,
                "working_set_bytes": 120 * MIB,
                "private_bytes": 95 * MIB,
            },
        ]
        receipt: dict[str, object] = {
            "schema": "telegram-courses-s9-supervisor-receipt-v1",
            "run_id": context.run_id,
            "ledger_run_id": context.run_id,
            "stage": stage,
            "result": "COMPLETED",
            "external_exit_code": 0,
            "process_tree_termination_confirmed": True,
            "elapsed_seconds": 1.0,
            "stage_timeout_seconds": STAGE_TIMEOUTS_SECONDS[stage],
            "critical_audit_gate": "PASS",
            "supervisor_offline_gate": "PASS",
            "process_control_offline_gate": "PASS",
            "memory_monitoring_offline_gate": "PASS",
            "limit_check_result": "PASS" if stage in {"queue_f", "queue_m"} else "UNKNOWN",
            "preconfirmation_prompt_signal_available": stage in {"queue_f", "queue_m"},
            "preconfirmation_release_callback_available": stage in {"queue_f", "queue_m"},
            "preconfirmation_confirmation_released": stage in {"queue_f", "queue_m"},
            "memory": {
                "baseline_status": (
                    "PASS_PROMPT_SIGNAL_AND_TWO_SECOND_WINDOW"
                    if stage in {"queue_f", "queue_m"} else "NOT_APPLICABLE_STAGE"
                ),
                "baseline_samples": baseline if stage in {"queue_f", "queue_m"} else [],
                "baseline_working_set_bytes": 100 * MIB if stage in {"queue_f", "queue_m"} else None,
                "baseline_private_bytes": 80 * MIB if stage in {"queue_f", "queue_m"} else None,
                "samples": memory_samples if stage in {"queue_f", "queue_m"} else [],
                "target_sampling_interval_ms": 250,
                "peak_working_set_bytes": 120 * MIB if stage in {"queue_f", "queue_m"} else 0,
                "memory_source": "WINDOWS_PROCESS_MEMORY_COUNTERS_EX",
            },
        }
        receipt["receipt_attestation_event_id"] = uuid.uuid4().hex
        filename = f"stage-{stage}-{index}.json"
        encoded = _canonical(receipt) + b"\n"
        (context.run_directory / filename).write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        ledger.record_critical_event(
            "RECEIPT_PERSISTED", details={"receipt_sha256": digest},
            event_id=receipt["receipt_attestation_event_id"],
        )
        entry: dict[str, object] = {
            "stage": stage, "filename": filename, "sha256": digest,
        }
        if scan_id is not None:
            entry["scan_run_id"] = scan_id
        entries.append(entry)
    queue["stage_receipts"] = entries

    media = gates["G4"]["plan"]["media"]
    check_entries: list[dict[str, object]] = []
    for item in media:
        pending = int(item["expected_bytes"])
        others: list[dict[str, object]] = []
        for other in media:
            if other["identity_alias"] == item["identity_alias"]:
                continue
            pending += int(other["expected_bytes"])
            others.append({
                "identity_alias": other["identity_alias"],
                "bytes": int(other["expected_bytes"]),
            })
        required = pending + max(1024 * MIB, (pending + 9) // 10) + DISK_RESERVE
        try:
            ledger.check_disk(
                context.run_directory, pending_bytes=pending,
                free_space=lambda _path, value=required - disk_shortfall: value,
            )
        except LedgerError:
            if not disk_shortfall:
                raise
        disk_row = ledger.snapshot()["disk_checks"][-1]
        check_entries.append({
            "check_id": disk_row["check_id"],
            "current_item_alias": item["identity_alias"],
            "current_item_bytes": int(item["expected_bytes"]),
            "other_pending_items": others,
        })
    queue["disk"] = {"extra_reserve_bytes": DISK_RESERVE, "checks": check_entries}


def _mutate_attested_stage_receipt(
    context: object, bundle: dict[str, object], stage: str,
    updates: dict[str, object],
) -> None:
    entry = next(
        item for item in bundle["gates"]["G5"]["stage_receipts"]
        if item["stage"] == stage
    )
    path = context.run_directory / entry["filename"]
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt.update(updates)
    receipt["receipt_attestation_event_id"] = uuid.uuid4().hex
    encoded = _canonical(receipt) + b"\n"
    path.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    S9OperationalLedger(context.ledger_path).record_critical_event(
        "RECEIPT_PERSISTED", details={"receipt_sha256": digest},
        event_id=receipt["receipt_attestation_event_id"],
    )
    entry["sha256"] = digest


def _fixture(
    tmp_path: Path,
    *,
    module_count: int = 2,
    planned_catalog: bool = False,
    include_m: bool = True,
    disk_shortfall: int = 0,
    gate_overrides: dict[str, dict[str, object]] | None = None,
) -> tuple[object, Path, dict[str, object]]:
    run_dir = tmp_path / "private-run"
    context = start_supervised_run(run_dir)
    database_path = run_dir / "synthetic-catalog.sqlite3"
    media_path = run_dir / "synthetic-media.bin"
    payload = b"synthetic media bytes only"
    media_path.write_bytes(payload)
    channel_id = -1000000000123
    ledger = S9OperationalLedger(context.ledger_path)
    media_identity_alias = _snapshot_alias(ledger, channel_id, 5, 0)
    logical_m_alias = ledger.pseudonym("SYNTHETIC_M:logical-fixture")
    _write_database(
        database_path, channel_id, modules=module_count,
        final_path=media_path, payload=payload,
    )
    database_sha256 = hashlib.sha256(database_path.read_bytes()).hexdigest()
    media_sha256 = hashlib.sha256(media_path.read_bytes()).hexdigest()
    scope: dict[str, object] = (
        {
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
        if planned_catalog else {"target_alias": "SYNTHETIC_RASMOO"}
    )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "channel_id": channel_id,
        "channel_alias": "RASMOO" if planned_catalog else "SYNTHETIC_CHANNEL",
        "scope": scope,
        "hierarchy": (
            {"TRACK": 1, "COURSE": 2, "MODULE": 2}
            if planned_catalog
            else {"TRACK": 1, "COURSE": 2, "MODULE": module_count}
        ),
        "unresolved_count": None if planned_catalog else 0,
    }
    if planned_catalog:
        manifest["catalog_expectation"] = {
            "state": "PENDING_G3",
            "hierarchy_semantics": "MINIMUMS",
            "unresolved_semantics": "OBSERVE_AND_REVIEW",
        }
    manifest_sha256 = _digest(manifest)
    scope_sha256 = _digest(manifest["scope"])
    gates: dict[str, dict[str, object]] = {
        "G1": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "scope_sha256": scope_sha256,
            "authentication": "SYNTHETIC_AUTHENTICATED",
            "target_selected": True, "cleanup_complete": True,
        },
        "G2": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "invocations": [{
                "scan_run_id": "scan-synthetic-1", "max_messages": 200,
                "observed": 5, "status": "COMPLETE", "stop_reason": None,
                "persisted": True, "errors": 0,
            }],
            "deletions_inferred": False,
            "high_water_before": 0, "high_water_after": 5,
        },
        "G3": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "database_sha256": database_sha256, "unresolved_reviewed": True,
        },
        "G4": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "fresh": True, "limit_check_result": "PASS",
            "synthetic_tty_confirmation": True, "confirm_bypass": False,
            "reservations_before_payload": True, "workers": 1,
            "attempts_per_media": 1, "disk_reserve_bytes": DISK_RESERVE,
            "plan": {
                "manifest_sha256": manifest_sha256,
                "media": [{
                    "identity_alias": media_identity_alias, "profile": "F",
                    "expected_bytes": len(payload), "kind": "DOCUMENT", "fresh": True,
                }, {
                    "identity_alias": logical_m_alias, "profile": "M",
                    "expected_bytes": MIB * 1024, "kind": "DOCUMENT", "fresh": True,
                }],
            },
        },
        "G5": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "limit_check_result": "PASS", "flood_wait": False,
            "supervisor": {
                "supervisor_gate": "PASS", "process_gate": "PASS",
                "memory_gate": "PASS", "audit_gate": "PASS",
                "process_exit_code": 0, "receipt_persisted": True,
                "receipt_attested": True, "tree_contained": True,
                "active_children": 0, "cancelled": False, "elapsed_seconds": 3,
                "working_set_baseline_bytes": 100 * MIB,
                "peak_working_set_bytes": 120 * MIB,
                "sample_interval_ms": 250,
            },
            "disk": {"extra_reserve_bytes": DISK_RESERVE},
            "reservations": [{
                "identity_alias": media_identity_alias, "profile": "F",
                "expected_bytes": len(payload), "reserved_bytes": len(payload),
                "observed_bytes": len(payload), "measurement_source": "SYNTHETIC_TEST",
                "state": "OBSERVED",
            }, {
                "identity_alias": logical_m_alias, "profile": "M",
                "expected_bytes": MIB * 1024, "reserved_bytes": MIB * 1024,
                "observed_bytes": 0, "measurement_source": "SYNTHETIC_TEST",
                "state": "OBSERVED",
            }],
            "attempts": [
                {"identity_alias": media_identity_alias, "profile": "F", "expected_bytes": len(payload), "attempt": 1},
                {"identity_alias": logical_m_alias, "profile": "M", "expected_bytes": MIB * 1024, "attempt": 1},
            ],
            "observed_bytes": len(payload), "m_expected_bytes": MIB * 1024,
            "m_execution": "LOGICAL_FIXTURE_ONLY",
        },
        "G6": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "database_sha256": database_sha256,
            "artifacts": [{
                "filename": media_path.name, "media_item_id": 1,
                "identity_alias": media_identity_alias,
                "size_bytes": media_path.stat().st_size,
                "sha256": media_sha256, "checkpoint_sha256": media_sha256,
            }],
            "m_logical_fixture_only": True, "m_logical_item_count": 1,
            "ownership_confirmed": True, "no_overwrite_confirmed": True,
            "hash_verified": True,
            "second_queue": {"new_payload_bytes": 0, "all_items_already_valid": True},
        },
        "G7": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "baseline_status": "COMPLETE", "baseline_verified": True,
            "database_sha256": database_sha256,
            "baseline_scan_run_id": "scan-synthetic-1",
            "incremental_scan_run_id": "scan-synthetic-incremental-1",
            "window_size": 50, "baseline_high_water": 5,
            "high_water_before": 5, "high_water_after": 5,
            "deletions_inferred": False,
        },
        "G8": {
            "origin": "SYNTHETIC", "manifest_sha256": manifest_sha256,
            "interruption_count": 1, "recovery_count": 1, "profile": "F",
            "part_preserved": True, "ownership_confirmed": True,
            "containment_proven": True, "remote_hash_policy": "REMOTE_HASH_REQUIRED",
            "synthetic_remote_prefix_verified": True,
            "remote_hash_origin": "SYNTHETIC_TEST",
            "real_prefix_hash_proven": False, "uncertainty_bytes": 0,
        },
    }
    if gate_overrides:
        for gate, updates in gate_overrides.items():
            gates[gate].update(updates)
    if not include_m:
        gates["G4"]["plan"]["media"] = [
            item for item in gates["G4"]["plan"]["media"]
            if item["profile"] != "M"
        ]
        gates["G5"]["reservations"] = [
            item for item in gates["G5"]["reservations"]
            if item["profile"] != "M"
        ]
        gates["G5"]["attempts"] = [
            item for item in gates["G5"]["attempts"]
            if item["profile"] != "M"
        ]
        gates["G5"]["m_expected_bytes"] = 0
        gates["G6"]["m_logical_item_count"] = 0
    _attach_stage_and_disk_proofs(
        context, ledger, gates, disk_shortfall=disk_shortfall,
    )
    bundle: dict[str, object] = {
        "schema_version": 1, "evidence_origin": "SYNTHETIC",
        "run_id": context.run_id, "database_file": database_path.name,
        "manifest": manifest, "gates": gates,
    }
    evidence_path = run_dir / "offline-evidence.json"
    evidence_path.write_bytes(_canonical(bundle) + b"\n")
    return context, evidence_path, bundle


def _refresh_database_binding(
    context: object, evidence_path: Path, bundle: dict[str, object],
) -> None:
    database_path = context.run_directory / bundle["database_file"]
    database_sha256 = hashlib.sha256(database_path.read_bytes()).hexdigest()
    for gate in ("G3", "G6", "G7"):
        bundle["gates"][gate]["database_sha256"] = database_sha256
    evidence_path.write_bytes(_canonical(bundle) + b"\n")


def _add_second_f_item(
    context: object, evidence_path: Path, bundle: dict[str, object],
) -> str:
    channel_id = bundle["manifest"]["channel_id"]
    payload = b"second synthetic media payload"
    media_path = context.run_directory / "synthetic-media-two.bin"
    media_path.write_bytes(payload)
    ledger = S9OperationalLedger(context.ledger_path)
    alias = _snapshot_alias(ledger, channel_id, 4, 1)
    media_sha256 = hashlib.sha256(payload).hexdigest()
    db_path = context.run_directory / bundle["database_file"]
    db = sqlite3.connect(db_path)
    try:
        db.execute(
            "INSERT INTO media_items VALUES(?,?,?,?,?,?,?,?)",
            (2, channel_id, 4, 1, "DOCUMENT", "synthetic-remote-media-two", len(payload), "OBSERVED"),
        )
        db.execute(
            "INSERT INTO downloads VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (2, 2, "DOWNLOADED", str(media_path.resolve()), len(payload), len(payload),
             media_sha256, "synthetic-remote-media-two", "DOCUMENT", len(payload),
             "CAPTURED_AT_START"),
        )
        db.commit()
    finally:
        db.close()
    bundle["gates"]["G4"]["plan"]["media"].insert(1, {
        "identity_alias": alias, "profile": "F", "expected_bytes": len(payload),
        "kind": "DOCUMENT", "fresh": True,
    })
    bundle["gates"]["G5"]["reservations"].insert(1, {
        "identity_alias": alias, "profile": "F", "expected_bytes": len(payload),
        "reserved_bytes": len(payload), "observed_bytes": len(payload),
        "measurement_source": "SYNTHETIC_TEST", "state": "OBSERVED",
    })
    bundle["gates"]["G5"]["attempts"].insert(1, {
        "identity_alias": alias, "profile": "F", "expected_bytes": len(payload), "attempt": 1,
    })
    bundle["gates"]["G5"]["observed_bytes"] += len(payload)
    required = len(payload) + max(1024 * MIB, (len(payload) + 9) // 10) + DISK_RESERVE
    ledger.check_disk(
        context.run_directory, pending_bytes=len(payload),
        free_space=lambda _path: required,
    )
    disk_row = ledger.snapshot()["disk_checks"][-1]
    bundle["gates"]["G5"]["disk"]["checks"].append({
        "check_id": disk_row["check_id"],
        "current_item_alias": alias,
        "current_item_bytes": len(payload),
        "other_pending_items": [],
    })
    bundle["gates"]["G6"]["artifacts"].append({
        "filename": media_path.name, "media_item_id": 2, "identity_alias": alias,
        "size_bytes": len(payload), "sha256": media_sha256,
        "checkpoint_sha256": media_sha256,
    })
    _refresh_database_binding(context, evidence_path, bundle)
    return alias


def test_full_synthetic_orchestration_persists_audited_receipts_and_keeps_real_pending(
    tmp_path: Path,
) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "OFFLINE_SYNTHETIC_PASS"
    assert [gate.status for gate in outcome.gates] == ["PASS"] * 9
    final_receipt = json.loads(outcome.receipt_path.read_text(encoding="utf-8"))
    assert final_receipt["summary"]["offline_result"] == "OFFLINE_SYNTHETIC_PASS"
    assert final_receipt["summary"]["real_g1_status"] == "REAL_G1_NOT_ASSESSED"
    assert final_receipt["summary"]["real_evidence_status"] == "REAL_EVIDENCE_PENDING"
    assert final_receipt["summary"]["no_pending_children"] is True
    assert {f"g{i}-receipt.json" for i in range(1, 10)} <= {
        path.name for path in context.run_directory.iterdir()
    }
    ledger = S9OperationalLedger(context.ledger_path)
    snapshot = ledger.snapshot()
    assert snapshot["run"]["gate"] == "G9"
    assert snapshot["run"]["status"] == "COMPLETED"
    assert snapshot["run"]["result"] == "OFFLINE_SYNTHETIC_PASS"
    assert snapshot["run"]["result_provenance"] == {
        "evidence_origin": "OFFLINE_SYNTHETIC",
        "offline_result": "OFFLINE_SYNTHETIC_PASS",
        "real_evidence_status": "REAL_EVIDENCE_PENDING",
    }


def test_stale_plan_fails_and_never_becomes_offline_pass(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G4"]["plan"]["manifest_sha256"] = "0" * 64
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[3].reason == "PLAN_MANIFEST_STALE"
    assert outcome.gates[4].status == "BLOCKED"


def test_insufficient_synthetic_dataset_is_blocked_without_expanding_scan_cap(
    tmp_path: Path,
) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path, module_count=1)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[2].reason == "BLOCKED_DATASET"


def test_g3_reconciles_catalog_run_node_count_to_active_nodes(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db_path = context.run_directory / bundle["database_file"]
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE catalog_runs SET catalog_node_count=catalog_node_count+1")
        db.commit()
    finally:
        db.close()
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[2].reason == "CATALOG_NODE_COUNT_MISMATCH"
    assert outcome.gates[3].status == "BLOCKED"


def test_g3_accepts_observed_catalog_above_planned_minimums(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(
        tmp_path, module_count=3, planned_catalog=True,
    )

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.gates[2].status == "PASS"
    assert outcome.gates[2].summary["hierarchy"] == {
        "TRACK": 1, "COURSE": 2, "MODULE": 3,
    }


def test_g3_blocks_planned_catalog_below_minimums(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(
        tmp_path, module_count=1, planned_catalog=True,
    )

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[2].reason == "BLOCKED_DATASET"


def test_g5_missing_m_profile_is_partial_while_f_can_reach_g6_and_g7(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path, include_m=False)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "PARTIAL"
    assert outcome.gates[4].status == "PARTIAL"
    assert outcome.gates[4].summary["profile_statuses"] == {
        "F": "PASS", "M": "BLOCKED_DATASET",
    }
    assert outcome.gates[5].status == "PASS"
    assert outcome.gates[6].status == "PASS"
    assert outcome.gates[8].summary["real_evidence_status"] == "REAL_EVIDENCE_PENDING"


@pytest.mark.parametrize("entry_kind", ["reservation", "attempt"])
def test_g5_entries_must_match_plan_identity_profile_and_size(
    tmp_path: Path, entry_kind: str,
) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    entry = bundle["gates"]["G5"]["reservations"][0] if entry_kind == "reservation" else bundle["gates"]["G5"]["attempts"][0]
    entry["expected_bytes"] += 1
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[4].reason == (
        "RESERVATION_PLAN_MISMATCH" if entry_kind == "reservation" else "ATTEMPT_PLAN_MISMATCH"
    )


def test_uncertain_bytes_are_charged_conservatively_and_make_result_partial(
    tmp_path: Path,
) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    queue = bundle["gates"]["G5"]
    queue["reservations"][0].update({"state": "UNCERTAIN", "observed_bytes": None})
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "UNCERTAIN_BYTES_CHARGED_CONSERVATIVELY"
    assert outcome.gates[5].reason == "PREDECESSOR_NOT_PASS"
    receipt = json.loads((context.run_directory / "g5-receipt.json").read_text(encoding="utf-8"))
    assert receipt["summary"]["unknown_bytes"] == len(b"synthetic media bytes only")


def test_subprocess_zero_without_containment_cannot_pass_g5_or_g9(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _mutate_attested_stage_receipt(
        context, bundle, "queue_f", {"process_tree_termination_confirmed": False},
    )
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "STAGE_PROCESS_STATE_UNPROVEN"
    assert outcome.gates[8].status == "BLOCKED"


def test_flood_wait_blocks_offline_queue_and_final_result(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G5"]["flood_wait"] = True
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "FLOODWAIT_OR_UNKNOWN"
    assert outcome.gates[8].summary["offline_result"] == "BLOCKED"


def test_cancelled_process_is_not_a_successful_queue(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _mutate_attested_stage_receipt(context, bundle, "queue_f", {"result": "CANCELLED"})
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "STAGE_PROCESS_STATE_UNPROVEN"
    assert outcome.gates[5].status == "BLOCKED"


def test_g5_reservation_cannot_exceed_the_planned_size(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    reservation = bundle["gates"]["G5"]["reservations"][0]
    reservation.update({
        "reserved_bytes": reservation["reserved_bytes"] + 1,
        "observed_bytes": reservation["observed_bytes"] + 1,
    })
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[4].reason == "RESERVATION_SIZE_MISMATCH"


def test_missing_predecessor_blocks_following_gate(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    del bundle["gates"]["G1"]
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[0].reason == "EVIDENCE_MISSING"
    assert outcome.gates[1].reason == "PREDECESSOR_NOT_PASS"


def test_manifest_change_invalidates_bound_gate_approvals(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["manifest"]["scope"]["target_alias"] = "CHANGED_SYNTHETIC_SCOPE"
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[0].reason == "MANIFEST_BINDING_MISMATCH"
    assert outcome.gates[1].reason == "MANIFEST_BINDING_MISMATCH"


def test_invalid_audit_chain_is_quarantined_before_gate_receipts(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)
    db = sqlite3.connect(context.ledger_path)
    try:
        db.execute("UPDATE audit_events SET event_type='INVALID' WHERE sequence=1")
        db.commit()
    finally:
        db.close()

    with pytest.raises(LedgerError):
        reconcile_offline_evidence(context.run_directory, evidence_path)

    assert not (context.run_directory / "g1-receipt.json").exists()


def test_preexisting_duplicate_receipt_is_never_overwritten(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)
    receipt = context.run_directory / "g1-receipt.json"
    original = b"preexisting receipt bytes\n"
    receipt.write_bytes(original)

    with pytest.raises(ReconciliationError, match="RECEIPT_"):
        reconcile_offline_evidence(context.run_directory, evidence_path)

    assert receipt.read_bytes() == original


def test_expired_global_deadline_is_recorded_as_partial(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)
    deadline = S9OperationalLedger(context.ledger_path).snapshot()["run"]["deadline_ns"]

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path, now_ns=deadline + 1)

    assert outcome.result == "PARTIAL"
    assert outcome.gates[8].status == "PARTIAL"
    assert outcome.gates[8].summary["global_deadline_status"] == "EXPIRED"


def test_g7_requires_a_verified_complete_baseline(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G7"]["baseline_status"] = "PARTIAL"
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[6].reason == "BLOCKED_BASELINE_INCOMPLETE"


def test_g7_reconciles_window_and_high_water_to_s7_rows(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db_path = context.run_directory / bundle["database_file"]
    db = sqlite3.connect(db_path)
    try:
        db.execute(
            "UPDATE scan_runs SET sync_reconcile_window=49 "
            "WHERE id='scan-synthetic-incremental-1'"
        )
        db.commit()
    finally:
        db.close()
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[6].reason == "S7_INCREMENTAL_RUN_DIVERGENCE"


def test_g7_declared_high_water_cannot_override_s7_checkpoint(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G7"]["high_water_before"] = 4
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[6].reason == "HIGH_WATER_DIVERGENCE"


def test_synthetic_remote_prefix_cannot_be_claimed_as_real(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G8"]["real_prefix_hash_proven"] = True
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[7].reason == "SYNTHETIC_PREFIX_CLAIMED_AS_REAL"
    assert outcome.gates[8].summary["real_evidence_status"] == "REAL_EVIDENCE_PENDING"


def test_real_origin_is_rejected_before_any_synthetic_gate_receipt(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["evidence_origin"] = "REAL"
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(ReconciliationError, match="REAL_EVIDENCE_NOT_AUTHORIZED"):
        reconcile_offline_evidence(context.run_directory, evidence_path)

    assert not (context.run_directory / "g1-receipt.json").exists()


def test_database_scan_identity_and_message_count_are_reconciled(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)
    db_path = context.run_directory / "synthetic-catalog.sqlite3"
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE scan_runs SET messages_seen=4 WHERE id='scan-synthetic-1'")
        db.commit()
    finally:
        db.close()

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[1].reason == "SCAN_LIMIT_OR_COUNT_MISMATCH"
    assert outcome.gates[2].status == "BLOCKED"


def test_g2_aggregate_scan_budget_counts_g7_rows_and_repeated_observations(
    tmp_path: Path,
) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db_path = context.run_directory / bundle["database_file"]
    channel_id = bundle["manifest"]["channel_id"]
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE scan_runs SET messages_seen=200 WHERE id='scan-synthetic-1'")
        db.execute("UPDATE scan_runs SET messages_seen=200 WHERE id='scan-synthetic-incremental-1'")
        db.execute(
            "INSERT INTO scan_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("scan-synthetic-extra-1", channel_id, "COMPLETE", datetime.now(timezone.utc).isoformat(), "synthetic", 5, 200, None,
             "FULL", 0, None, None, 0, None, None, 0),
        )
        db.commit()
    finally:
        db.close()
    bundle["gates"]["G2"]["invocations"][0]["observed"] = 200
    bundle["gates"]["G2"]["invocations"].append({
        "scan_run_id": "scan-synthetic-incremental-1", "max_messages": 200,
        "observed": 200, "status": "COMPLETE", "stop_reason": None,
        "persisted": True, "errors": 0,
    })
    bundle["gates"]["G2"]["invocations"].append({
        "scan_run_id": "scan-synthetic-extra-1", "max_messages": 200,
        "observed": 200, "status": "COMPLETE", "stop_reason": None,
        "persisted": True, "errors": 0,
    })
    evidence_path.write_bytes(_canonical(bundle) + b"\n")
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[1].status == "PASS"
    assert outcome.gates[1].summary["observations"] == 600
    assert len(outcome.gates[1].summary["scan_run_ids"]) == 3


def test_g2_rejects_an_omitted_persisted_scan_for_the_bound_channel(
    tmp_path: Path,
) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db = sqlite3.connect(context.run_directory / bundle["database_file"])
    try:
        db.execute(
            "INSERT INTO scan_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("scan-synthetic-omitted", bundle["manifest"]["channel_id"], "COMPLETE",
             datetime.now(timezone.utc).isoformat(), "synthetic", 5, 1, None, "FULL", 0, None, None, 0,
             None, None, 0),
        )
        db.commit()
    finally:
        db.close()

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[1].reason == "SCAN_AGGREGATE_COUNT_MISMATCH"


def test_g2_rejects_incremental_scan_limit_above_contract_cap(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db = sqlite3.connect(context.run_directory / bundle["database_file"])
    try:
        db.execute(
            "UPDATE scan_runs SET sync_max_messages=201 "
            "WHERE id='scan-synthetic-incremental-1'"
        )
        db.commit()
    finally:
        db.close()
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[1].reason == "SCAN_INCREMENTAL_LIMIT_OR_COUNT_MISMATCH"
    assert outcome.gates[6].status == "BLOCKED"


def test_g5_requires_each_stage_timeout_from_attested_receipts(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _mutate_attested_stage_receipt(
        context, bundle, "queue_f", {"stage_timeout_seconds": 601},
    )
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[4].reason == "STAGE_TIMEOUT_CONTRACT_MISMATCH"


@pytest.mark.parametrize(
    ("stage", "elapsed"), [("queue_f", 600.1), ("queue_m", 1800.1)],
)
def test_g5_enforces_f_and_m_timeout_limits_individually(
    tmp_path: Path, stage: str, elapsed: float,
) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _mutate_attested_stage_receipt(
        context, bundle, stage, {"elapsed_seconds": elapsed},
    )
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[4].reason == "STAGE_TIMEOUT_EXCEEDED"


def test_g5_accepts_f_and_m_at_their_individual_timeout_boundaries(
    tmp_path: Path,
) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _mutate_attested_stage_receipt(context, bundle, "queue_f", {"elapsed_seconds": 600.0})
    _mutate_attested_stage_receipt(context, bundle, "queue_m", {"elapsed_seconds": 1800.0})
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "OFFLINE_SYNTHETIC_PASS"
    assert outcome.gates[4].summary["deadline_seconds"] == 2405.0


def test_g5_blocks_when_a_stage_duration_is_unknown(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _mutate_attested_stage_receipt(
        context, bundle, "queue_f", {"elapsed_seconds": None},
    )
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[4].reason == "STAGE_TIMEOUT_CONTRACT_MISMATCH"


def test_g5_blocks_when_a_required_stage_receipt_is_omitted(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G5"]["stage_receipts"] = [
        entry for entry in bundle["gates"]["G5"]["stage_receipts"]
        if entry["stage"] != "inspection"
    ]
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "STAGE_RECEIPT_SET_INCOMPLETE"


def test_g5_reconciles_preconfirmation_memory_window_from_raw_receipt(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    entry = next(
        item for item in bundle["gates"]["G5"]["stage_receipts"]
        if item["stage"] == "queue_f"
    )
    receipt_path = context.run_directory / entry["filename"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    memory = receipt["memory"]
    memory["baseline_samples"] = memory["baseline_samples"][:8]
    _mutate_attested_stage_receipt(context, bundle, "queue_f", {"memory": memory})
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "MEMORY_BASELINE_UNPROVEN"


def test_g5_blocks_when_the_memory_baseline_window_has_a_gap(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    entry = next(
        item for item in bundle["gates"]["G5"]["stage_receipts"]
        if item["stage"] == "queue_f"
    )
    receipt_path = context.run_directory / entry["filename"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    memory = receipt["memory"]
    memory["baseline_samples"][4]["elapsed_seconds"] = 1.6
    _mutate_attested_stage_receipt(context, bundle, "queue_f", {"memory": memory})
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "MEMORY_BASELINE_WINDOW_UNPROVEN"


def test_g5_requires_disk_measurement_ids_to_match_the_plan(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G5"]["disk"]["checks"][0]["current_item_bytes"] += 1
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[4].reason == "DISK_CHECK_SET_MISMATCH"


def test_g5_fails_when_measured_disk_space_is_insufficient(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path, disk_shortfall=1)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[4].reason == "DISK_RESERVE_EXCEEDED"


def test_g5_requires_the_s9_disk_reserve_in_evidence(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    bundle["gates"]["G5"]["disk"]["extra_reserve_bytes"] = DISK_RESERVE - 1
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[4].reason == "DISK_RESERVE_UNPROVEN"


@pytest.mark.parametrize(
    ("field", "value"), [("margin", 0), ("available_origin", "UNKNOWN")],
)
def test_g5_requires_the_s5_margin_and_measured_disk_source(
    tmp_path: Path, field: str, value: object,
) -> None:
    context, _evidence_path, bundle = _fixture(tmp_path)
    ledger = S9OperationalLedger(context.ledger_path)
    snapshot = ledger.snapshot()
    media = bundle["gates"]["G4"]["plan"]["media"]
    snapshot["disk_checks"][0][field] = value

    _summary, reason = _validate_queue_disk(
        bundle["gates"]["G5"]["disk"], snapshot, media,
    )

    assert reason == "DISK_MEASUREMENT_UNPROVEN"


def test_legacy_terminal_g9_pass_without_provenance_is_pending(tmp_path: Path) -> None:
    context = start_supervised_run(tmp_path / "legacy-pass")
    ledger = S9OperationalLedger(context.ledger_path)
    before = ledger.snapshot()
    ledger.update_execution(
        gate="G9", status="COMPLETED",
        elapsed_ms=S9OperationalLedger.execution_elapsed_ms(before),
        deadline_ns=before["run"]["deadline_ns"],
        process_state="EXITED", result="PASS", cause="NONE",
    )

    run = ledger.snapshot()["run"]

    assert run["result"] == "REAL_EVIDENCE_PENDING"
    assert run["result_provenance"]["real_evidence_status"] == "REAL_EVIDENCE_PENDING"


def test_g6_reconciles_persisted_download_bytes_and_hash(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db_path = context.run_directory / bundle["database_file"]
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE downloads SET downloaded_bytes=downloaded_bytes-1")
        db.commit()
    finally:
        db.close()
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[5].reason == "DOWNLOAD_LEDGER_ARTIFACT_DIVERGENCE"
    assert outcome.gates[6].status == "BLOCKED"


def test_g6_reconciles_s7_remote_identity_snapshot(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db_path = context.run_directory / bundle["database_file"]
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE downloads SET remote_identity_media_id='changed-synthetic-id'")
        db.commit()
    finally:
        db.close()
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[5].reason == "S7_MEDIA_IDENTITY_SNAPSHOT_DIVERGENCE"


def test_g6_reconciles_every_physical_f_artifact_in_the_plan(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _add_second_f_item(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "OFFLINE_SYNTHETIC_PASS"
    assert outcome.gates[5].summary["verified_f_item_count"] == 2
    assert outcome.gates[5].summary["logical_m_item_count"] == 1


def test_g6_blocks_when_any_planned_f_artifact_is_omitted(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    _add_second_f_item(context, evidence_path, bundle)
    bundle["gates"]["G6"]["artifacts"].pop()
    evidence_path.write_bytes(_canonical(bundle) + b"\n")

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[5].reason == "ARTIFACT_PLAN_COVERAGE_MISMATCH"


def test_g6_alias_must_match_s7_snapshot_pseudonym(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    db_path = context.run_directory / bundle["database_file"]
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE media_items SET telegram_message_id=4 WHERE id=1")
        db.commit()
    finally:
        db.close()
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "FAIL"
    assert outcome.gates[5].reason == "S7_MEDIA_IDENTITY_SNAPSHOT_DIVERGENCE"


def test_g6_rejects_download_path_outside_the_private_run(tmp_path: Path) -> None:
    context, evidence_path, bundle = _fixture(tmp_path)
    outside_path = tmp_path / "outside-synthetic.bin"
    outside_path.write_bytes(b"synthetic media bytes only")
    db_path = context.run_directory / bundle["database_file"]
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE downloads SET final_path=?", (str(outside_path.resolve()),))
        db.commit()
    finally:
        db.close()
    _refresh_database_binding(context, evidence_path, bundle)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert outcome.result == "BLOCKED"
    assert outcome.gates[5].reason == "DOWNLOAD_FINAL_PATH_OUTSIDE_RUN"


def test_g9_receipt_does_not_expose_database_media_ids(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)

    outcome = reconcile_offline_evidence(context.run_directory, evidence_path)

    receipt = outcome.receipt_path.read_text(encoding="utf-8")
    assert "media_item_id" not in receipt
    assert "telegram_message_id" not in receipt
    assert "synthetic-remote-media-id" not in receipt


def test_g9_receipt_before_ledger_terminal_is_recovered_after_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)
    original = S9OperationalLedger.update_execution

    def stop_before_terminal(self: S9OperationalLedger, **kwargs: object) -> None:
        if kwargs.get("gate") == "G9":
            raise LedgerErrorForTest("synthetic crash before terminal update")
        original(self, **kwargs)

    class LedgerErrorForTest(RuntimeError):
        pass

    monkeypatch.setattr(S9OperationalLedger, "update_execution", stop_before_terminal)
    with pytest.raises(LedgerErrorForTest):
        reconcile_offline_evidence(context.run_directory, evidence_path)
    assert (context.run_directory / "g9-receipt.json").exists()
    assert S9OperationalLedger(context.ledger_path).snapshot()["run"]["status"] == "RUNNING"

    monkeypatch.setattr(S9OperationalLedger, "update_execution", original)
    recovered = reconcile_offline_evidence(context.run_directory, evidence_path)

    assert recovered.result == "OFFLINE_SYNTHETIC_PASS"
    assert S9OperationalLedger(context.ledger_path).snapshot()["run"]["status"] == "COMPLETED"


def test_cli_offline_reconcile_command_never_invokes_stage(tmp_path: Path) -> None:
    context, evidence_path, _bundle = _fixture(tmp_path)

    exit_code = __import__("telegram_courses.s9_supervisor_cli", fromlist=["main"]).main([
        "reconcile-offline", "--run-directory", str(context.run_directory),
        "--evidence-file", str(evidence_path),
    ])

    assert exit_code == 0
    assert (context.run_directory / "g9-receipt.json").exists()


@pytest.mark.parametrize(
    ("gate", "status", "checkpoint_expected"),
    [
        ("G1", "PASS", False),
        ("G4", "PASS", False),
        ("G5", "PASS", True),
        ("G6", "PASS", True),
        ("G7", "PASS", True),
        ("G8", "PASS", True),
        ("G9", "PASS", True),
        ("G9", "BLOCKED", False),
    ],
)
def test_gate_receipt_checkpoint_is_after_prepared_and_before_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate: str,
    status: str,
    checkpoint_expected: bool,
) -> None:
    context, _evidence_path, _bundle = _fixture(tmp_path)
    ledger = S9OperationalLedger(context.ledger_path)
    receipt_path = context.run_directory / f"{gate.lower()}-receipt.json"
    original_checkpoint = ledger.checkpoint
    checkpoint_calls: list[str] = []

    def checkpoint() -> object:
        snapshot = ledger.snapshot()
        prepared = [
            event for event in snapshot["critical_audit"]["events"]
            if event["event_type"] == "RECEIPT_PREPARED"
        ]
        assert prepared, "checkpoint must follow durable RECEIPT_PREPARED"
        assert not receipt_path.exists(), "checkpoint must precede receipt rename"
        checkpoint_calls.append(gate)
        return original_checkpoint()

    monkeypatch.setattr(ledger, "checkpoint", checkpoint)
    _persist_gate(
        ledger,
        context.run_directory,
        context.run_id,
        gate,
        status,
        "SYNTHETIC_TEST",
        None,
        "a" * 64,
        "b" * 64,
        {},
    )

    assert receipt_path.is_file()
    assert checkpoint_calls == ([gate] if checkpoint_expected else [])

