from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_courses.downloads import RemoteFileHash, S6PrefixProofObservation
from telegram_courses.s9_operational_ledger import (
    S9OperationalLedger,
    _create_private_directory,
)
from telegram_courses.s9_operational_reconciliation import (
    OperationalReconciliationError,
    _database_file_sha256,
    _is_no_m_partial,
    _open_private_download_root,
    _persist_receipt,
    _validate_sanitized_report,
    persist_s6_prefix_proof,
    validate_g8_database_transition,
)
from telegram_courses.s9_real_gate_producers import (
    _database_sha256,
    canonical_bytes,
    load_approved_manifest,
    sha256_bytes,
)
from telegram_courses.s9_supervisor_cli import start_supervised_run

pytestmark = pytest.mark.skipif(os.name != "nt", reason="S9 private-run validation is Windows-specific")


def test_operational_snapshot_hash_uses_shared_database_and_wal_digest(
    tmp_path: Path,
) -> None:
    database = tmp_path / "catalog.sqlite3"
    database.write_bytes(b"main database")
    Path(str(database) + "-wal").write_bytes(b"committed WAL")
    Path(str(database) + "-shm").write_bytes(b"transient SHM")

    expected = _database_sha256(database)
    assert _database_file_sha256(database) == expected
    Path(str(database) + "-shm").write_bytes(b"changed transient SHM")
    assert _database_file_sha256(database) == expected


@pytest.mark.parametrize("part", ["main", "wal", "shm", "journal"])
def test_g8_database_reader_rejects_reparse_files_before_sqlite_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    part: str,
) -> None:
    import telegram_courses.s9_operational_reconciliation as reconciliation

    context = start_supervised_run(tmp_path / "run")
    database = context.run_directory / "catalog.sqlite3"
    database.write_bytes(b"main database")
    target = database if part == "main" else Path(str(database) + f"-{part}")
    original_lstat = Path.lstat
    opened: list[object] = []

    def fake_lstat(path: Path):
        if path == target:
            return SimpleNamespace(
                st_mode=stat.S_IFREG,
                st_size=12,
                st_file_attributes=0x400,
            )
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    monkeypatch.setattr(
        reconciliation.sqlite3,
        "connect",
        lambda *args, **kwargs: opened.append((args, kwargs)),
    )

    with pytest.raises(
        OperationalReconciliationError,
        match="RECOVERY_DATABASE_UNAVAILABLE",
    ):
        reconciliation._read_database_download(
            database,
            context.run_directory / "downloads",
            None,  # type: ignore[arg-type]
            "a" * 64,
            1,
            -1000000000789,
            1,
            1,
            remote_ranges=(),
        )
    assert opened == []


def test_g8_transition_rejects_reparse_sidecar_before_database_reopen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import telegram_courses.s9_operational_reconciliation as reconciliation

    context, (manifest, manifest_sha256, _scope_sha256) = _run_with_manifest(tmp_path)
    database = context.run_directory / "catalog.sqlite3"
    database.write_bytes(b"main database")
    sidecar = Path(str(database) + "-wal")
    original_lstat = Path.lstat
    opened: list[object] = []

    def fake_lstat(path: Path):
        if path == sidecar:
            return SimpleNamespace(
                st_mode=stat.S_IFREG,
                st_size=12,
                st_file_attributes=0x400,
            )
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    monkeypatch.setattr(
        reconciliation,
        "read_g8_database_baseline",
        lambda *_args, **_kwargs: {"database_file": database.name},
    )
    monkeypatch.setattr(
        reconciliation.sqlite3,
        "connect",
        lambda *args, **kwargs: opened.append((args, kwargs)),
    )

    with pytest.raises(
        OperationalReconciliationError,
        match="DATABASE_FILE_UNAVAILABLE",
    ):
        validate_g8_database_transition(
            context.run_directory,
            {"run": {"run_id": "synthetic-run"}},
            run_id="synthetic-run",
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            database_path=database,
        )
    assert opened == []


def _approved_manifest() -> dict[str, object]:
    scope = {"target_alias": "SYNTHETIC_G8"}
    return {
        "schema_version": 1,
        "channel_id": -1000000000789,
        "channel_alias": "SYNTHETIC_G8_CHANNEL",
        "scope": scope,
        "hierarchy": {"TRACK": 1, "COURSE": 2, "MODULE": 2},
        "unresolved_count": 0,
        "scope_approval": {
            "decision": "APPROVED",
            "confirmation_source": "G0_HUMAN_CONFIRMATION",
            "scope_sha256": sha256_bytes(canonical_bytes(scope)),
        },
    }


def _run_with_manifest(tmp_path: Path):
    context = start_supervised_run(tmp_path / "run")
    (context.run_directory / "approved-manifest.json").write_bytes(
        canonical_bytes(_approved_manifest()) + b"\n",
    )
    return context, load_approved_manifest(context.run_directory)


def test_g8_source_evidence_returns_manifest_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import telegram_courses.s9_operational_reconciliation as reconciliation

    run_root = tmp_path / "run"
    run_root.mkdir()
    download_root = run_root / "downloads"
    download_root.mkdir()
    manifest = _approved_manifest()
    manifest_sha256 = "a" * 64
    snapshot = {"run": {"run_id": "synthetic-run"}}
    channel_id = manifest["channel_id"]
    gate_evidence = {
        gate: {
            "channel_id": channel_id,
            "status": "OFFLINE_SYNTHETIC_PASS",
            "evidence_origin": "SYNTHETIC",
        }
        for gate in ("G0", "G1", "G2", "G3", "G6", "G7")
    }
    gate_evidence["G6"]["database_file"] = "catalog.sqlite3"
    gate_evidence["G7"]["sync_index"] = 1
    queue_receipt = {
        "status": "OFFLINE_SYNTHETIC_PASS",
        "evidence_origin": "SYNTHETIC",
        "channel_id": channel_id,
        "database_file": "catalog.sqlite3",
        "download_root": "downloads",
    }

    monkeypatch.setattr(
        reconciliation,
        "load_approved_manifest",
        lambda _root: (manifest, manifest_sha256, "b" * 64),
    )
    monkeypatch.setattr(
        reconciliation,
        "_validated_gate",
        lambda _root, _snapshot, *, gate, **_kwargs: gate_evidence[gate],
    )
    monkeypatch.setattr(
        reconciliation,
        "read_validated_g5_queue_receipt",
        lambda *_args, **_kwargs: queue_receipt,
    )
    monkeypatch.setattr(
        reconciliation,
        "_audit_gate_status",
        lambda _snapshot, _gate: ("UNKNOWN", None),
    )

    class _Ledger:
        def snapshot(self) -> dict[str, object]:
            return snapshot

    result = reconciliation._g8_source_evidence(
        run_root, run_root / "catalog.sqlite3", download_root, _Ledger(),
    )

    assert result[1] == manifest_sha256
    assert type(result[1]) is str


def test_synthetic_no_m_state_is_partial_without_real_eligibility() -> None:
    partial = {
        "status": "PARTIAL",
        "evidence_origin": "SYNTHETIC",
        "g5_m_status": "BLOCKED_DATASET",
        "g6_aggregate_status": "PARTIAL",
        "g7_real_eligible": False,
        "nfr02_real": "NOT_TESTED",
    }

    assert _is_no_m_partial(partial)
    for key, invalid_value in (
        ("g5_m_status", "PASS"),
        ("g6_aggregate_status", "PASS"),
        ("g7_real_eligible", True),
        ("nfr02_real", "PASS"),
        ("status", "OFFLINE_SYNTHETIC_PASS"),
    ):
        assert not _is_no_m_partial(partial | {key: invalid_value})


def test_prefix_proof_api_rejects_caller_asserted_boolean() -> None:
    with pytest.raises(
        OperationalReconciliationError,
        match="PREFIX_PROOF_OBSERVATION_INVALID",
    ):
        persist_s6_prefix_proof(
            Path("unused-run"),  # validation rejects before filesystem access
            None,  # type: ignore[arg-type]
            {"passed": True},  # type: ignore[arg-type]
            measurement_source="SYNTHETIC_TEST",
        )


def test_valid_s6_prefix_observation_persists_with_manifest_channel_binding(
    tmp_path: Path,
) -> None:
    context, (manifest, _manifest_sha256, _scope_sha256) = _run_with_manifest(tmp_path)
    ledger = S9OperationalLedger(context.ledger_path)
    ledger.update_execution(
        gate="G8",
        status="RUNNING",
        elapsed_ms=0,
        deadline_ns=context.deadline_ns,
        process_state="RUNNING",
        result="UNKNOWN",
    )
    identity = (int(manifest["channel_id"]), 123456, 0)
    expected_bytes = 128 * 1024
    alias = ledger.register_media(
        ":".join(str(value) for value in identity),
        profile="F",
        expected_bytes=expected_bytes,
    )
    ledger.begin_attempt(alias)
    ledger.record_interruption(
        alias, part_bytes=64 * 1024, expected_bytes=expected_bytes,
    )
    ledger.begin_attempt(alias, recovery=True)
    observation = S6PrefixProofObservation(
        candidate_identity=identity,
        expected_bytes=expected_bytes,
        physical_prefix_bytes=64 * 1024,
        local_prefix_sha256="a" * 64,
        remote_ranges=(
            RemoteFileHash(0, 64 * 1024, bytes.fromhex("b" * 64)),
        ),
        verification_payload_bytes=32 * 1024,
    )

    path, digest = persist_s6_prefix_proof(
        context.run_directory,
        ledger,
        observation,
        measurement_source="SYNTHETIC_TEST",
    )

    payload = json.loads(path.read_text("utf-8"))
    assert digest == sha256_bytes(path.read_bytes())
    assert payload["channel_id"] == manifest["channel_id"]
    assert payload["identity_alias"] == alias
    assert payload["physical_prefix_bytes"] == 64 * 1024
    assert payload["evidence_origin"] == "SYNTHETIC"
    assert payload["status"] == "OFFLINE_SYNTHETIC_PASS"


def test_g8_transition_validator_fails_closed_without_baseline(
    tmp_path: Path,
) -> None:
    context, (manifest, manifest_sha256, _scope_sha256) = _run_with_manifest(tmp_path)
    ledger = S9OperationalLedger(context.ledger_path)

    with pytest.raises(
        OperationalReconciliationError,
        match="G8_DATABASE_BASELINE_MISSING",
    ):
        validate_g8_database_transition(
            context.run_directory,
            ledger.snapshot(),
            run_id=context.run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            database_path=context.run_directory / "catalog.sqlite3",
        )


def test_g8_download_root_is_reopened_as_a_pinned_private_child(
    tmp_path: Path,
) -> None:
    context, _ = _run_with_manifest(tmp_path)
    download_path = context.run_directory / "downloads"
    creator = _create_private_directory(download_path)
    creator.close()

    selected, guard = _open_private_download_root(context.run_directory, "downloads")
    try:
        assert selected == download_path
        guard.verify(download_path)
    finally:
        guard.close()

    outside = tmp_path / "outside"
    outside.mkdir()
    link = context.run_directory / "redirected"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable in this Windows environment")
    with pytest.raises(OperationalReconciliationError, match="G8_DOWNLOAD_ROOT_UNSAFE"):
        _open_private_download_root(context.run_directory, "redirected")


@pytest.mark.parametrize(
    ("database_sha256_before", "database_file", "download_root", "origin"),
    [
        ("not-a-hash", "catalog.sqlite3", "downloads", "REAL_CONTRACTUAL"),
        ("a" * 64, "..\\outside.sqlite3", "downloads", "REAL_CONTRACTUAL"),
        ("a" * 64, "catalog.sqlite3", "..\\outside", "REAL_CONTRACTUAL"),
        ("a" * 64, "catalog.sqlite3", "downloads", "SYNTHETIC_TEST"),
    ],
)
def test_g8_baseline_rejects_untrusted_identity_fields(
    database_sha256_before: str,
    database_file: str,
    download_root: str,
    origin: str,
) -> None:
    from telegram_courses.s9_operational_reconciliation import (
        record_g8_database_baseline,
    )

    with pytest.raises(OperationalReconciliationError, match="G8_DATABASE_BASELINE_INVALID"):
        record_g8_database_baseline(
            Path("unused-run"),
            None,  # type: ignore[arg-type]
            database_sha256_before=database_sha256_before,
            database_file=database_file,
            download_root=download_root,
            manifest_sha256="b" * 64,
            evidence_origin=origin,  # type: ignore[arg-type]
            predecessors={},
        )


def test_sanitized_g9_report_rejects_file_hashes_and_local_paths(
    tmp_path: Path,
) -> None:
    report = tmp_path / "g9-report.md"
    report.write_text("Outcome: PARTIAL\n", encoding="utf-8")
    digest = sha256_bytes(report.read_bytes())
    _validate_sanitized_report(
        report,
        expected_sha256=digest,
        forbidden_values=(str(tmp_path / "private"),),
    )

    report.write_text(f"Leaked hash: {'c' * 64}\n", encoding="utf-8")
    with pytest.raises(OperationalReconciliationError, match="REPORT_SANITIZATION_INVALID"):
        _validate_sanitized_report(
            report,
            expected_sha256=sha256_bytes(report.read_bytes()),
            forbidden_values=(),
        )


@pytest.mark.parametrize(
    ("gate", "status", "origin"),
    [
        ("G8", "PASS", "REAL_CONTRACTUAL"),
        ("G9", "OFFLINE_SYNTHETIC_PASS", "SYNTHETIC"),
    ],
)
def test_operational_pass_receipt_checkpoint_follows_prepared_before_rename_and_reopen(
    tmp_path: Path,
    gate: str,
    status: str,
    origin: str,
) -> None:
    context, _ = _run_with_manifest(tmp_path)
    ledger = S9OperationalLedger(context.ledger_path)
    filename = f"{gate.lower()}-checkpoint-receipt.json"
    receipt_path = context.run_directory / filename
    payload = {
        "schema": f"telegram-courses-s9-{gate.lower()}-operational-receipt-v1",
        "version": 1,
        "gate": gate,
        "run_id": context.run_id,
        "evidence_origin": origin,
        "status": status,
    }
    original_checkpoint = ledger.checkpoint
    observed_path_states: list[bool] = []

    def checkpoint() -> object:
        snapshot = ledger.snapshot()
        assert any(
            event["event_type"] == "RECEIPT_PREPARED"
            and json.loads(event["details_json"]).get("gate") == gate
            for event in snapshot["critical_audit"]["events"]
        ), "checkpoint must follow durable RECEIPT_PREPARED"
        observed_path_states.append(receipt_path.exists())
        return original_checkpoint()

    _persist_receipt(
        context.run_directory,
        ledger,
        payload,
        filename=filename,
        before_rename_checkpoint=checkpoint,
    )

    assert observed_path_states == [False]
    assert receipt_path.is_file()
    persisted_bytes = receipt_path.read_bytes()
    ledger.close()
    reopened = S9OperationalLedger(context.ledger_path)
    recovered_events = [
        event for event in reopened.snapshot()["critical_audit"]["events"]
        if event["event_type"] in {"RECEIPT_PREPARED", "RECEIPT_PERSISTED"}
        and json.loads(event["details_json"]).get("gate") == gate
    ]
    assert [event["event_type"] for event in recovered_events] == [
        "RECEIPT_PREPARED", "RECEIPT_PERSISTED",
    ]
    assert receipt_path.read_bytes() == persisted_bytes


def test_blocked_operational_receipt_does_not_checkpoint(tmp_path: Path) -> None:
    context, _ = _run_with_manifest(tmp_path)
    ledger = S9OperationalLedger(context.ledger_path)
    checkpoint_calls: list[bool] = []
    _persist_receipt(
        context.run_directory,
        ledger,
        {
            "schema": "telegram-courses-s9-g8-operational-receipt-v1",
            "version": 1,
            "gate": "G8",
            "run_id": context.run_id,
            "evidence_origin": "SYNTHETIC",
            "status": "BLOCKED",
        },
        filename="g8-blocked-checkpoint-receipt.json",
        before_rename_checkpoint=lambda: checkpoint_calls.append(True),
    )
    assert checkpoint_calls == []
