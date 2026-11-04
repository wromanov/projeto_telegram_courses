from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import telegram_courses.s9_operational_ledger as ledger_module
import telegram_courses.s9_supervisor_cli as supervisor_cli_module
from telegram_courses.s9_operational_ledger import (
    F_CAP,
    S9OperationalLedger,
    _create_private_directory,
    _open_private_directory_guard,
)
from telegram_courses.s9_real_gate_producers import canonical_bytes, sha256_bytes
from telegram_courses.s9_supervisor import SupervisorResult
from telegram_courses.s9_supervisor_cli import (
    _TRUSTED_CLI_BOOTSTRAP,
    OfflineRunnerError,
    _child_environment,
    _ledger_writer_handoff_callbacks,
    _safe_output_directory,
    _trusted_cli_module_origin,
    _trusted_python_command,
    _validate_queue_storage_paths,
    _validate_supervised_queue_arguments,
    _validate_supervised_stage_arguments,
    classify_s9_gate,
    load_supervised_run_context,
    main,
    run_offline_smoke,
    run_supervised_cli_stage,
    run_supervised_g1,
    run_supervised_g8,
    run_supervised_queue,
    start_supervised_run,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="S9 process control is Windows-specific")


def test_restricted_smoke_integrates_cli_supervisor_and_separate_ledger(tmp_path: Path) -> None:
    output = tmp_path / "offline-run"
    outcome = run_offline_smoke(output, require_tty=False)

    receipt = json.loads((output / "supervisor-receipt.json").read_text(encoding="utf-8"))
    ledger = S9OperationalLedger(outcome.ledger_path)
    snapshot = ledger.snapshot()
    assert outcome.supervisor.result == "COMPLETED"
    assert outcome.supervisor.exit_code == 0
    assert outcome.supervisor.supervisor_gate == "PASS"
    assert outcome.ledger_status == "COMPLETED"
    assert outcome.ledger_result == "UNKNOWN"
    assert snapshot["run"]["gate"] == "G0"
    assert snapshot["run"]["process_state"] == "EXITED"
    assert snapshot["run"]["result"] == "UNKNOWN"
    assert receipt["external_exit_code"] == 0
    assert receipt["process_tree_termination_confirmed"] is True
    assert receipt["command_recorded"] is False
    assert receipt["limit_check_result"] == "UNKNOWN"
    assert outcome.supervisor.critical_audit_gate == "PASS"
    assert outcome.supervisor.receipt_attested is True
    assert receipt["ledger_run_id"] == snapshot["run"]["run_id"]
    events = snapshot["critical_audit"]["events"]
    persisted_event = next(
        event for event in events
        if event["event_id"] == receipt["receipt_attestation_event_id"]
    )
    assert json.loads(persisted_event["details_json"])["receipt_sha256"] == hashlib.sha256(
        (output / "supervisor-receipt.json").read_bytes()
    ).hexdigest()
    assert not (output / "data" / "catalog.sqlite3").exists()
    assert not (output / "downloads").exists()
    assert {entry.name for entry in output.iterdir()} <= {
        "operational-ledger.sqlite3", "operational-ledger.sqlite3-wal",
        "operational-ledger.sqlite3-shm", "operational-ledger.sqlite3.writer.lock",
        "supervisor-receipt.json",
    }


@pytest.mark.parametrize(
    "extra_arguments",
    [
        ["--confirm"],
        ["--v2-global"],
        ["--integrity-mode", "OPERATIONAL_ONLY"],
        ["auth"],
        ["scan", "--channel-id", "123", "--max-messages", "1", "--timeout-seconds", "1"],
    ],
)
def test_runner_rejects_real_commands_and_incompatible_flags(
    tmp_path: Path, extra_arguments: list[str],
) -> None:
    output = tmp_path / "must-not-launch"
    with pytest.raises(SystemExit):
        main(["--output-directory", str(output), *extra_arguments])
    assert not output.exists()


def test_exit_zero_with_limit_check_failure_cannot_pass_s9_gate(tmp_path: Path) -> None:
    result = SupervisorResult(
        run_id="a" * 32, result="COMPLETED", reason="PROCESS_EXITED", exit_code=0,
        receipt_path=tmp_path / "receipt.json", receipt_persisted=True,
        supervisor_gate="PASS", process_control_gate="PASS",
        memory_monitoring_gate="PASS", critical_audit_gate="PASS",
        receipt_attested=True,
    )
    assert classify_s9_gate(result, "FAIL") == "BLOCKED"
    assert classify_s9_gate(result, "UNKNOWN") == "BLOCKED"
    assert classify_s9_gate(result, "PASS") == "PASS"
    assert classify_s9_gate(
        SupervisorResult(
            run_id=result.run_id, result="COMPLETED", reason="PROCESS_EXITED", exit_code=0,
            receipt_path=result.receipt_path, receipt_persisted=True,
            supervisor_gate="PASS", process_control_gate="PASS",
            memory_monitoring_gate="PASS", critical_audit_gate="BLOCKED",
            receipt_attested=True,
        ), "PASS",
    ) == "BLOCKED"
    assert classify_s9_gate(
        SupervisorResult(
            run_id=result.run_id, result="COMPLETED", reason="PROCESS_EXITED", exit_code=0,
            receipt_path=result.receipt_path, receipt_persisted=False,
            supervisor_gate="PASS", process_control_gate="PASS",
            memory_monitoring_gate="PASS", critical_audit_gate="PASS", receipt_attested=False,
        ), "PASS",
    ) == "BLOCKED"


def test_child_environment_omits_telegram_credentials_and_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_API_ID", "synthetic-canary-id")
    monkeypatch.setenv("TELEGRAM_API_HASH", "synthetic-canary-secret")
    monkeypatch.setenv("TELEGRAM_COURSES_DATABASE_PATH", "private/catalog.sqlite")
    environment = _child_environment()
    assert not any(key.upper().startswith("TELEGRAM_") for key in environment)
    assert "PYTHONNOUSERSITE" in environment
    assert "PYTHONPATH" not in environment
    assert "synthetic-canary-secret" not in repr(environment)


def test_isolated_child_ignores_output_module_shadow_and_pythonpath(
    tmp_path: Path,
) -> None:
    output = _safe_output_directory(tmp_path / "private-output")
    shadow = output / "telegram_courses"
    shadow.mkdir()
    marker = tmp_path / "shadow-imported.txt"
    (shadow / "cli.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('shadow')\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            *_trusted_python_command(_TRUSTED_CLI_BOOTSTRAP),
            str(_trusted_cli_module_origin()), "smoke",
        ],
        cwd=output,
        env={**_child_environment(), "PYTHONPATH": str(output)},
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    assert not marker.exists()


def test_isolated_child_rejects_unexpected_trusted_module_origin(
    tmp_path: Path,
) -> None:
    output = _safe_output_directory(tmp_path / "private-output")
    expected = tmp_path / "not-the-installed-cli.py"
    expected.write_text("# synthetic path only\n", encoding="utf-8")
    completed = subprocess.run(
        [
            *_trusted_python_command(_TRUSTED_CLI_BOOTSTRAP),
            str(expected), "smoke",
        ],
        cwd=output,
        env=_child_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 125
    assert "trusted CLI module origin unavailable" in completed.stderr


def test_parent_rejects_module_origin_outside_loaded_package(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    fake = tmp_path / "foreign-cli.py"
    fake.write_text("# synthetic only\n", encoding="utf-8")
    monkeypatch.setattr(
        supervisor_cli_module.importlib.util,
        "find_spec",
        lambda _name: SimpleNamespace(origin=str(fake)),
    )
    with pytest.raises(RuntimeError, match="TRUSTED_CLI_MODULE_UNAVAILABLE"):
        _trusted_cli_module_origin()


def test_safe_output_directory_is_new_and_acl_validated(tmp_path: Path) -> None:
    output = _safe_output_directory(tmp_path / "private-output")
    assert output.is_dir()
    guard = _open_private_directory_guard(output)
    guard.close()


def test_safe_output_directory_rejects_synthetic_reparse_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    selected = parent / "output"
    original_lstat = supervisor_cli_module.os.lstat

    def synthetic_lstat(path):
        if Path(path) == parent:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o700,
                st_file_attributes=0x400,
            )
        return original_lstat(path)

    monkeypatch.setattr(supervisor_cli_module.os, "lstat", synthetic_lstat)
    with pytest.raises(RuntimeError, match="OUTPUT_PARENT_UNSAFE"):
        _safe_output_directory(selected)
    assert not selected.exists()


def test_existing_reparse_output_is_rejected_without_changing_content_or_acl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    output = tmp_path / "existing-reparse"
    guard = _create_private_directory(output)
    guard.close()
    evidence = output / "keep.txt"
    evidence.write_text("preserve", encoding="utf-8")
    acl_before = ledger_module._windows_api().inspect_acl(output)
    original_lstat = supervisor_cli_module.os.lstat

    def synthetic_lstat(path):
        if Path(path) == output:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o700,
                st_file_attributes=0x400,
            )
        return original_lstat(path)

    monkeypatch.setattr(supervisor_cli_module.os, "lstat", synthetic_lstat)
    with pytest.raises(RuntimeError, match="OUTPUT_DIRECTORY_PRIVATE_OR_CREATE_FAILED"):
        _safe_output_directory(output)
    monkeypatch.undo()
    assert evidence.read_text(encoding="utf-8") == "preserve"
    assert ledger_module._windows_api().inspect_acl(output) == acl_before


def test_existing_output_directory_is_never_reused(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    guard = _create_private_directory(output)
    guard.close()
    evidence = output / "keep.txt"
    evidence.write_text("preserve", encoding="utf-8")
    acl_before = ledger_module._windows_api().inspect_acl(output)

    with pytest.raises(RuntimeError, match="OUTPUT_DIRECTORY_NOT_EMPTY"):
        run_offline_smoke(output, require_tty=False)
    assert evidence.read_text(encoding="utf-8") == "preserve"
    assert ledger_module._windows_api().inspect_acl(output) == acl_before


def test_existing_private_empty_output_directory_is_accepted(tmp_path: Path) -> None:
    output = tmp_path / "existing-private"
    guard = _create_private_directory(output)
    guard.close()
    acl_before = ledger_module._windows_api().inspect_acl(output)

    assert _safe_output_directory(output) == output
    assert list(output.iterdir()) == []
    assert ledger_module._windows_api().inspect_acl(output) == acl_before


def test_existing_shared_output_is_rejected_without_content_or_acl_change(
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing-shared"
    output.mkdir()
    evidence = output / "keep.txt"
    evidence.write_text("preserve", encoding="utf-8")
    acl_before = ledger_module._windows_api().inspect_acl(output)

    with pytest.raises(RuntimeError, match="OUTPUT_DIRECTORY_PRIVATE_OR_CREATE_FAILED"):
        _safe_output_directory(output)
    assert evidence.read_text(encoding="utf-8") == "preserve"
    assert ledger_module._windows_api().inspect_acl(output) == acl_before


def test_supervised_stage_validator_rejects_commands_and_unbounded_values(
    tmp_path: Path,
) -> None:
    database = str(tmp_path / "catalog.sqlite3")
    scan = [
        "scan", "--channel-id", "-1001234567890", "--database", database,
        "--max-messages", "200", "--timeout-seconds", "120",
    ]
    assert _validate_supervised_stage_arguments(scan)[:2] == ("scan", "G2")
    incremental_scan = [
        *scan, "--incremental", "--reconcile-window", "50",
    ]
    assert _validate_supervised_stage_arguments(incremental_scan)[:2] == ("scan", "G7")
    with pytest.raises(RuntimeError, match="STAGE_LIMIT_INVALID"):
        _validate_supervised_stage_arguments([
            *scan, "--incremental", "--reconcile-window", "49",
        ])
    with pytest.raises(RuntimeError, match="STAGE_COMMAND_NOT_ALLOWLISTED"):
        _validate_supervised_stage_arguments(["smoke"])
    with pytest.raises(RuntimeError, match="STAGE_COMMAND_NOT_ALLOWLISTED"):
        _validate_supervised_stage_arguments(["auth"])
    with pytest.raises(RuntimeError, match="STAGE_COMMAND_NOT_ALLOWLISTED"):
        _validate_supervised_stage_arguments([
            "download", "queue", "--channel-id", "123",
        ])
    with pytest.raises(RuntimeError, match="STAGE_LIMIT_INVALID"):
        _validate_supervised_stage_arguments([
            "scan", "--channel-id", "123", "--database", database,
            "--max-messages", "201", "--timeout-seconds", "120",
        ])
    with pytest.raises(RuntimeError, match="STAGE_ARGUMENTS_INVALID"):
        _validate_supervised_stage_arguments([
            "catalog", "build", "--channel-id", "123", "--database", database,
            "--parser-key", "unbounded-parser",
        ])
    rasmoo_catalog = [
        "catalog", "build", "--channel-id", "123", "--database", database,
        "--parser-key", "rasmoo",
    ]
    assert _validate_supervised_stage_arguments(rasmoo_catalog)[:2] == ("catalog", "G3")
    with pytest.raises(RuntimeError, match="STAGE_ARGUMENTS_INVALID"):
        _validate_supervised_stage_arguments([
            "catalog", "show", "--channel-id", "123", "--database", database,
            "--parser-key", "rasmoo",
        ])


def test_supervised_queue_storage_is_bound_to_private_run_root(
    tmp_path: Path,
) -> None:
    context = start_supervised_run(tmp_path / "run")
    database = context.run_directory / "catalog.sqlite3"
    download_root = context.run_directory / "downloads"
    arguments = [
        "download", "queue", "--channel-id", "123", "--database", str(database),
        "--download-dir", str(download_root), "--workers", "1",
        "--attempts-per-media", "1", "--max-media-items", "8",
        "--max-transfer-bytes", str(F_CAP),
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
    ]
    checked = _validate_supervised_queue_arguments(arguments, "F")

    selected_database, selected_download_root = _validate_queue_storage_paths(
        checked, context.ledger_path,
    )
    assert selected_database == database
    assert selected_download_root == download_root
    guard = _open_private_directory_guard(download_root)
    guard.close()

    outside = [
        *arguments,
    ]
    outside[outside.index(str(database))] = str(tmp_path / "outside.sqlite3")
    with pytest.raises(RuntimeError, match="QUEUE_STORAGE_MUST_BE_PRIVATE_RUN_CHILD"):
        _validate_queue_storage_paths(outside, context.ledger_path)


class _SyntheticStageSupervisor:
    response = "COMPLETED"
    reason = "PROCESS_EXITED"
    exit_code = 0

    def __init__(self, *, receipt_path: Path, **kwargs) -> None:
        self.receipt_path = receipt_path
        self.ledger_run_id = kwargs["ledger_run_id"]
        self.run_options = None

    def run(self, command, **kwargs):
        self.run_options = {"command": command, **kwargs}
        self.receipt_path.write_text(
            json.dumps({
                "memory": {
                    "samples": [{
                        "working_set_bytes": 128,
                        "private_bytes": 96,
                    }],
                    "peak_working_set_bytes": 128,
                },
            }),
            encoding="utf-8",
        )
        return SupervisorResult(
            run_id=self.ledger_run_id,
            result=self.response,
            reason=self.reason,
            exit_code=self.exit_code,
            receipt_path=self.receipt_path,
            receipt_persisted=True,
            supervisor_gate="PASS",
            process_control_gate="PASS",
            memory_monitoring_gate="PASS",
            critical_audit_gate="PASS",
            receipt_attested=True,
        )


class _HandoffSyntheticStageSupervisor(_SyntheticStageSupervisor):
    def __init__(self, *, receipt_path: Path, **kwargs) -> None:
        super().__init__(receipt_path=receipt_path, **kwargs)
        self.critical_audit_writer = kwargs["critical_audit_writer"]
        self.handoff_calls: list[str] = []

    def run(self, command, **kwargs):
        stage = kwargs["stage"]
        event_id = hashlib.sha256(
            f"handoff:{self.ledger_run_id}:{stage}:{self.receipt_path.name}".encode("ascii"),
        ).hexdigest()[:32]
        child_pid = 12345
        creation_time = 67890
        ack = self.critical_audit_writer(
            "CHILD_PROCESS_CONFIRMED",
            details={
                "stage": stage,
                "pid": child_pid,
                "process_creation_time": creation_time,
            },
            event_id=event_id,
        )
        identity = {
            "run_id": ack["run_id"],
            "event_id": ack["event_id"],
            "sequence": ack["sequence"],
            "event_hash": ack["event_hash"],
            "child_pid": child_pid,
            "creation_time": creation_time,
            "stage": stage,
        }
        kwargs["release_ledger_writer"](identity)
        self.handoff_calls.append("release")
        result = super().run(command, **kwargs)
        kwargs["readmit_ledger_writer"](identity)
        self.handoff_calls.append("readmit")
        return result


def _write_synthetic_approved_manifest(run_directory: Path) -> None:
    scope = {"target_alias": "SYNTHETIC_TARGET"}
    manifest = {
        "schema_version": 1,
        "channel_id": -1001234567890,
        "channel_alias": "SYNTHETIC_CHANNEL",
        "scope": scope,
        "hierarchy": {"TRACK": 1, "COURSE": 2, "MODULE": 2},
        "unresolved_count": 0,
        "scope_approval": {
            "decision": "APPROVED",
            "confirmation_source": "G0_HUMAN_CONFIRMATION",
            "scope_sha256": sha256_bytes(canonical_bytes(scope)),
        },
    }
    (run_directory / "approved-manifest.json").write_bytes(
        canonical_bytes(manifest) + b"\n",
    )


def test_supervised_scan_requires_audited_real_g1_before_launch(
    tmp_path: Path,
) -> None:
    context = start_supervised_run(tmp_path / "run")
    loaded = load_supervised_run_context(context.run_directory)
    ledger = S9OperationalLedger(context.ledger_path)
    ledger.update_execution(
        gate="G1", status="RUNNING", elapsed_ms=0,
        deadline_ns=context.deadline_ns, process_state="RUNNING", result="PASS",
    )
    database = str(context.run_directory / "catalog.sqlite3")
    fake_instances: list[_SyntheticStageSupervisor] = []

    class FakeSupervisor(_SyntheticStageSupervisor):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            fake_instances.append(self)

    with pytest.raises(
        OfflineRunnerError, match="REAL_GATE_PREDECESSOR_OR_MANIFEST_INVALID",
    ):
        run_supervised_cli_stage(
            loaded,
            context.run_directory / "stage-scan",
            [
                "scan", "--channel-id", "-1001234567890", "--database", database,
                "--max-messages", "200", "--timeout-seconds", "120",
            ],
            require_tty=False,
            supervisor_type=FakeSupervisor,
        )
    snapshot = ledger.snapshot()
    starts = [
        event for event in snapshot["critical_audit"]["events"]
        if event["event_type"] == "RUN_DEADLINE_STARTED"
    ]

    assert fake_instances == []
    assert context.deadline_ns == loaded.deadline_ns
    assert snapshot["run"]["deadline_ns"] == context.deadline_ns
    assert snapshot["run"]["gate"] == "G1"
    assert snapshot["run"]["status"] == "RUNNING"
    assert snapshot["run"]["result"] == "PASS"
    assert len(starts) == 1

    with pytest.raises(OfflineRunnerError, match="STAGE_ORDER_INVALID"):
        run_supervised_cli_stage(
            loaded,
            context.run_directory / "stage-catalog-not-assessed",
            [
                "catalog", "build", "--channel-id", "123",
                "--database", database,
            ],
            require_tty=False,
            supervisor_type=FakeSupervisor,
        )


def test_supervised_scan_rejects_synthetic_g0_before_legacy_g1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = start_supervised_run(tmp_path / "run")
    _write_synthetic_approved_manifest(context.run_directory)
    ledger = S9OperationalLedger(context.ledger_path)
    ledger.update_execution(
        gate="G1", status="RUNNING", elapsed_ms=0,
        deadline_ns=context.deadline_ns, process_state="RUNNING", result="PASS",
    )
    gates_read: list[str] = []
    fake_instances: list[_SyntheticStageSupervisor] = []

    def fake_receipt(_root, _snapshot, gate, **_kwargs):
        gates_read.append(gate)
        if gate == "G0":
            return {
                "status": "OFFLINE_SYNTHETIC_PASS",
                "evidence_origin": "SYNTHETIC",
                "confirmation_source": "SYNTHETIC_TEST",
            }
        return {"status": "PASS", "evidence_origin": "REAL_CONTRACTUAL"}

    class NeverLaunch(_SyntheticStageSupervisor):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            fake_instances.append(self)

    monkeypatch.setattr(
        "telegram_courses.s9_real_gate_producers.read_validated_gate_receipt",
        fake_receipt,
    )
    with pytest.raises(
        OfflineRunnerError, match="REAL_GATE_PREDECESSOR_OR_MANIFEST_INVALID",
    ):
        run_supervised_cli_stage(
            load_supervised_run_context(context.run_directory),
            context.run_directory / "stage-scan",
            [
                "scan", "--channel-id", "-1001234567890",
                "--database", str(context.run_directory / "catalog.sqlite3"),
                "--max-messages", "200", "--timeout-seconds", "120",
            ],
            require_tty=False,
            supervisor_type=NeverLaunch,
        )
    assert gates_read == ["G0"]
    assert fake_instances == []


def test_supervised_queue_requires_human_g0_before_download_rpc(
    tmp_path: Path,
) -> None:
    context = start_supervised_run(tmp_path / "run")
    _write_synthetic_approved_manifest(context.run_directory)
    ledger = S9OperationalLedger(context.ledger_path)
    ledger.update_execution(
        gate="G3", status="RUNNING", elapsed_ms=0,
        deadline_ns=context.deadline_ns, process_state="RUNNING", result="PASS",
    )
    database = context.run_directory / "catalog.sqlite3"
    download_root = context.run_directory / "downloads"
    arguments = [
        "download", "queue", "--channel-id", "-1001234567890",
        "--database", str(database), "--download-dir", str(download_root),
        "--workers", "1", "--attempts-per-media", "1",
        "--max-media-items", "8", "--max-transfer-bytes", str(F_CAP),
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
    ]
    fake_instances: list[_SyntheticStageSupervisor] = []

    class NeverLaunch(_SyntheticStageSupervisor):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            fake_instances.append(self)

    with pytest.raises(OfflineRunnerError, match="G0_CONFIRMATION_REQUIRED"):
        run_supervised_queue(
            context.run_directory / "queue-output",
            context.ledger_path,
            arguments,
            profile="F",
            require_tty=False,
            supervisor_type=NeverLaunch,
        )
    assert fake_instances == []


def test_supervised_stage_timeout_cannot_bypass_missing_audited_g1(
    tmp_path: Path,
) -> None:
    context = start_supervised_run(tmp_path / "run")
    ledger = S9OperationalLedger(context.ledger_path)
    original_deadline = ledger.active_global_deadline()
    ledger.update_execution(
        gate="G1", status="RUNNING", elapsed_ms=0,
        deadline_ns=original_deadline, process_state="RUNNING", result="PASS",
    )

    class TimeoutSupervisor(_SyntheticStageSupervisor):
        response = "TIMED_OUT"
        reason = "STAGE_TIMEOUT_EXCEEDED"
        exit_code = None

    fake_instances: list[_SyntheticStageSupervisor] = []

    class NeverLaunchTimeoutSupervisor(TimeoutSupervisor):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            fake_instances.append(self)

    with pytest.raises(
        OfflineRunnerError, match="REAL_GATE_PREDECESSOR_OR_MANIFEST_INVALID",
    ):
        run_supervised_cli_stage(
            context,
            context.run_directory / "stage-scan-timeout",
            [
                "scan", "--channel-id", "-1001234567890",
                "--database", str(context.run_directory / "catalog.sqlite3"),
                "--max-messages", "1", "--timeout-seconds", "120",
            ],
            require_tty=False,
            supervisor_type=NeverLaunchTimeoutSupervisor,
        )
    snapshot = ledger.snapshot()

    assert fake_instances == []
    assert snapshot["run"]["deadline_ns"] == original_deadline
    assert snapshot["run"]["gate"] == "G1"
    assert snapshot["run"]["status"] == "RUNNING"
    assert snapshot["run"]["result"] == "PASS"


@pytest.mark.parametrize(
    ("logical_gate", "stage"),
    [("G1", "discovery"), ("G5", "queue_f"), ("G8", "queue_f")],
)
def test_writer_epoch_handoff_replays_and_binds_confirmed_child(
    tmp_path: Path, logical_gate: str, stage: str,
) -> None:
    context = start_supervised_run(tmp_path / f"handoff-{logical_gate.lower()}")
    ledger = S9OperationalLedger(context.ledger_path)
    child_pid = os.getpid()
    creation_time = 1
    event_id = hashlib.sha256(
        f"{logical_gate}:{context.run_id}:{stage}".encode("ascii"),
    ).hexdigest()[:32]
    ack = ledger.record_critical_event(
        "CHILD_PROCESS_CONFIRMED",
        details={
            "stage": stage,
            "pid": child_pid,
            "process_creation_time": creation_time,
        },
        event_id=event_id,
    )
    identity = {
        "run_id": ack["run_id"],
        "event_id": ack["event_id"],
        "sequence": ack["sequence"],
        "event_hash": ack["event_hash"],
        "child_pid": child_pid,
        "creation_time": creation_time,
        "stage": stage,
    }
    release, readmit, state = _ledger_writer_handoff_callbacks(ledger)

    release(identity)
    assert state["handoff"] == identity
    assert state["parent_readmitted"] is False
    readmit(identity)

    assert state["parent_readmitted"] is True
    snapshot = ledger.snapshot()
    confirmed = [
        event for event in snapshot["critical_audit"]["events"]
        if event["event_id"] == event_id
    ]
    assert len(confirmed) == 1
    assert confirmed[0]["event_type"] == "CHILD_PROCESS_CONFIRMED"
    assert confirmed[0]["details_json"]


@pytest.mark.parametrize(
    ("gate", "status", "checkpoint_expected"),
    [
        ("G7", "PASS", True),
        ("G7", "OFFLINE_SYNTHETIC_PASS", True),
        ("G7", "BLOCKED", False),
        ("G3", "PASS", False),
    ],
)
def test_evidence_receipt_checkpoint_is_limited_to_g7_pass_and_precedes_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate: str,
    status: str,
    checkpoint_expected: bool,
) -> None:
    context = start_supervised_run(tmp_path / f"receipt-{gate.lower()}-{status.lower()}")
    ledger = S9OperationalLedger(context.ledger_path)
    order: list[str] = []
    receipt_path = context.run_directory / f"{gate.lower()}-synthetic-receipt.json"
    original_checkpoint = ledger.checkpoint

    def checkpoint() -> object:
        snapshot = ledger.snapshot()
        assert any(
            event["event_type"] == "RECEIPT_PREPARED"
            for event in snapshot["critical_audit"]["events"]
        ), "G7 checkpoint must follow durable RECEIPT_PREPARED"
        assert not receipt_path.exists(), "G7 checkpoint must precede rename"
        order.append("checkpoint")
        return original_checkpoint()

    def persist_gate_receipt(_run_directory, target_ledger, evidence, **kwargs) -> None:
        order.append("prepared")
        target_ledger.record_critical_event(
            "RECEIPT_PREPARED",
            details={"receipt_sha256": "a" * 64},
            event_id=hashlib.sha256(
                f"{gate}:{status}:{context.run_id}".encode("ascii"),
            ).hexdigest()[:32],
        )
        callback = kwargs.get("before_rename_checkpoint")
        if callback is not None:
            callback()
        order.append("rename")
        receipt_path.write_bytes(b"synthetic receipt")

    monkeypatch.setattr(ledger, "checkpoint", checkpoint)
    monkeypatch.setattr(
        "telegram_courses.s9_real_gate_producers.persist_gate_receipt",
        persist_gate_receipt,
    )
    monkeypatch.setattr(
        supervisor_cli_module,
        "_update_gate_result",
        lambda _ledger, **kwargs: ("RUNNING", kwargs["evidence_result"]),
    )

    outcome = supervisor_cli_module._persist_and_update_evidence_gate(
        ledger,
        context,
        {"gate": gate, "status": status},
        deadline_ns=context.deadline_ns,
        process_state="EXITED",
        measurements=(None, None, None),
    )

    assert outcome == ("RUNNING", status)
    assert receipt_path.is_file()
    assert order == (
        ["prepared", "checkpoint", "rename"]
        if checkpoint_expected else ["prepared", "rename"]
    )


def _assert_handoff_was_wired(instance: _HandoffSyntheticStageSupervisor) -> None:
    assert instance.run_options is not None
    assert callable(instance.run_options.get("release_ledger_writer"))
    assert callable(instance.run_options.get("readmit_ledger_writer"))
    assert instance.handoff_calls == ["release", "readmit"]


def _queue_arguments(run_directory: Path) -> list[str]:
    return [
        "download", "queue", "--channel-id", "-1001234567890",
        "--database", str(run_directory / "catalog.sqlite3"),
        "--download-dir", str(run_directory / "downloads"),
        "--workers", "1", "--attempts-per-media", "1",
        "--max-media-items", "8", "--max-transfer-bytes", str(F_CAP),
        "--integrity-mode", "REMOTE_HASH_REQUIRED",
    ]


def test_g1_wrapper_passes_writer_handoff_callbacks_to_fake_supervisor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegram_courses import s9_g0_confirmation, s9_real_gate_producers

    context = start_supervised_run(tmp_path / "g1-run")
    _write_synthetic_approved_manifest(context.run_directory)
    instances: list[_HandoffSyntheticStageSupervisor] = []

    class FakeSupervisor(_HandoffSyntheticStageSupervisor):
        _s9_g1_gateway_factory = staticmethod(lambda: object())
        _s9_g1_credentials_loader = staticmethod(lambda: object())

        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            instances.append(self)

    confirmation = {
        "status": "OFFLINE_SYNTHETIC_PASS",
        "evidence_origin": "SYNTHETIC",
    }
    monkeypatch.setattr(
        s9_g0_confirmation,
        "request_g0_confirmation",
        lambda *_args, **_kwargs: dict(confirmation),
    )
    monkeypatch.setattr(
        s9_real_gate_producers,
        "read_validated_gate_receipt",
        lambda *_args, **_kwargs: dict(confirmation),
    )

    async def collect_g1_evidence(**_kwargs):
        return {
            "evidence_origin": "SYNTHETIC",
            "status": "OFFLINE_SYNTHETIC_PASS",
        }

    monkeypatch.setattr(s9_real_gate_producers, "collect_g1_evidence", collect_g1_evidence)
    monkeypatch.setattr(
        s9_real_gate_producers,
        "validate_g1_evidence",
        lambda *_args, **_kwargs: ("OFFLINE_SYNTHETIC_PASS", ""),
    )
    monkeypatch.setattr(supervisor_cli_module, "_synthetic_test_seam_enabled", lambda _type: True)
    monkeypatch.setattr(supervisor_cli_module, "_localappdata_for_child", lambda: None)
    monkeypatch.setattr(
        supervisor_cli_module,
        "_read_supervisor_receipt_evidence",
        lambda *_args, **_kwargs: "a" * 64,
    )
    monkeypatch.setattr(
        supervisor_cli_module,
        "_persist_and_update_evidence_gate",
        lambda _ledger, _context, evidence, **_kwargs: ("RUNNING", str(evidence["status"])),
    )

    outcome = run_supervised_g1(
        context,
        context.run_directory / "g1-output",
        require_tty=False,
        supervisor_type=FakeSupervisor,
    )

    assert len(instances) == 1
    assert instances[0].run_options is not None, (
        f"supervisor.run was not reached: reason={outcome.supervisor.reason} "
        f"handoff_calls={instances[0].handoff_calls}"
    )
    assert instances[0].run_options["stage"] == "discovery"
    _assert_handoff_was_wired(instances[0])


def test_g5_queue_wrapper_passes_writer_handoff_callbacks_to_fake_supervisor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegram_courses import s9_real_gate_producers

    context = start_supervised_run(tmp_path / "g5-run")
    _write_synthetic_approved_manifest(context.run_directory)
    ledger = S9OperationalLedger(context.ledger_path)
    ledger.update_execution(
        gate="G3", status="RUNNING", elapsed_ms=0,
        deadline_ns=context.deadline_ns, process_state="RUNNING", result="PASS",
    )
    ledger.close()
    download_guard = _create_private_directory(context.run_directory / "downloads")
    download_guard.close()
    instances: list[_HandoffSyntheticStageSupervisor] = []

    class FakeSupervisor(_HandoffSyntheticStageSupervisor):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            instances.append(self)

    monkeypatch.setattr(
        s9_real_gate_producers,
        "read_validated_gate_receipt",
        lambda *_args, **_kwargs: {
            "status": "OFFLINE_SYNTHETIC_PASS",
            "evidence_origin": "SYNTHETIC",
            "confirmation_source": "SYNTHETIC_TEST",
        },
    )
    monkeypatch.setattr(supervisor_cli_module, "_synthetic_test_seam_enabled", lambda _type: True)
    monkeypatch.setattr(
        supervisor_cli_module,
        "confirmation_callbacks",
        lambda *_args, **_kwargs: (lambda: True, lambda: None),
    )
    monkeypatch.setattr(supervisor_cli_module, "_queue_child_environment", lambda **_kwargs: {})

    run_supervised_queue(
        context.run_directory / "g5-output",
        context.ledger_path,
        _queue_arguments(context.run_directory),
        profile="F",
        require_tty=False,
        supervisor_type=FakeSupervisor,
    )

    assert len(instances) == 1
    assert instances[0].run_options["stage"] == "queue_f"
    _assert_handoff_was_wired(instances[0])


def test_g8_wrapper_passes_writer_handoff_callbacks_to_fake_supervisor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from telegram_courses import s9_operational_reconciliation, s9_real_gate_producers

    context = start_supervised_run(tmp_path / "g8-run")
    ledger = S9OperationalLedger(context.ledger_path)
    ledger.update_execution(
        gate="G7", status="RUNNING", elapsed_ms=0,
        deadline_ns=context.deadline_ns, process_state="RUNNING",
        result="OFFLINE_SYNTHETIC_PASS",
    )
    ledger.close()
    download_guard = _create_private_directory(context.run_directory / "downloads")
    download_guard.close()
    instances: list[_HandoffSyntheticStageSupervisor] = []

    class FakeSupervisor(_HandoffSyntheticStageSupervisor):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            instances.append(self)

    monkeypatch.setattr(supervisor_cli_module, "_synthetic_test_seam_enabled", lambda _type: True)
    monkeypatch.setattr(
        supervisor_cli_module,
        "confirmation_callbacks",
        lambda *_args, **_kwargs: (lambda: True, lambda: None),
    )
    monkeypatch.setattr(supervisor_cli_module, "_queue_child_environment", lambda **_kwargs: {})
    monkeypatch.setattr(
        supervisor_cli_module,
        "_validate_queue_storage_paths",
        lambda _args, _ledger: (
            context.run_directory / "catalog.sqlite3",
            context.run_directory / "downloads",
        ),
    )
    monkeypatch.setattr(
        s9_operational_reconciliation,
        "_g8_source_evidence",
        lambda *_args, **_kwargs: ({}, "a" * 64, {}, "SYNTHETIC"),
    )
    monkeypatch.setattr(
        s9_real_gate_producers,
        "_database_sha256",
        lambda _path: "b" * 64,
    )
    monkeypatch.setattr(
        s9_operational_reconciliation,
        "record_g8_database_baseline",
        lambda *_args, **_kwargs: None,
    )

    run_supervised_g8(
        context,
        context.run_directory / "g8-output",
        _queue_arguments(context.run_directory),
        phase="interrupt",
        require_tty=False,
        supervisor_type=FakeSupervisor,
    )

    assert len(instances) == 1
    assert instances[0].run_options["stage"] == "queue_f"
    _assert_handoff_was_wired(instances[0])
