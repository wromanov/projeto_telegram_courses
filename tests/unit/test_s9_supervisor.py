from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from telegram_courses import s9_supervisor
from telegram_courses.s9_operational_ledger import (
    LedgerError,
    S9OperationalLedger,
    _create_private_directory,
    _open_private_directory_guard,
)
from telegram_courses.s9_supervisor import WindowsCliSupervisor

pytestmark = pytest.mark.skipif(os.name != "nt", reason="S9 process control is Windows-specific")


def _private_run_directory(tmp_path: Path) -> Path:
    path = tmp_path / "s9-private"
    guard = (
        _open_private_directory_guard(path)
        if path.exists()
        else _create_private_directory(path)
    )
    resolved = guard.path
    guard.close()
    return resolved


def _audit_ledger(tmp_path: Path) -> S9OperationalLedger:
    return S9OperationalLedger.create(
        _private_run_directory(tmp_path) / "supervisor-ledger.sqlite3"
    )


def _supervisor(tmp_path: Path, **kwargs: object) -> WindowsCliSupervisor:
    ledger = _audit_ledger(tmp_path)
    kwargs.setdefault("critical_audit_writer", ledger.record_critical_event)
    kwargs.setdefault("ledger_run_id", ledger.snapshot()["run"]["run_id"])
    kwargs.setdefault("cooperative_cancel_seconds", 0.1)
    kwargs.setdefault("tree_containment_seconds", 5.0)
    require_tty = bool(kwargs.pop("require_tty", False))
    return WindowsCliSupervisor(
        receipt_path=_private_run_directory(tmp_path) / "receipt.json",
        require_tty=require_tty,
        **kwargs,
    )


def _read_receipt(result: object) -> dict[str, object]:
    path = result.receipt_path  # type: ignore[attr-defined]
    assert result.receipt_persisted  # type: ignore[attr-defined]
    return json.loads(path.read_text(encoding="utf-8"))


def test_normal_synthetic_process_has_observed_exit_and_process_tree(tmp_path: Path) -> None:
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "print('synthetic-ok')"], stage="scan"
    )

    receipt = _read_receipt(result)
    assert result.result == "COMPLETED"
    assert result.exit_code == 0
    assert receipt["external_exit_code"] == 0
    assert receipt["process_tree_termination_confirmed"] is True
    assert receipt["process_control_offline_gate"] == "PASS"
    assert receipt["command_recorded"] is False
    assert result.critical_audit_gate == "PASS"
    assert result.receipt_attested is True
    assert receipt["ledger_run_id"] == result.run_id
    events = S9OperationalLedger(
        _private_run_directory(tmp_path) / "supervisor-ledger.sqlite3"
    ).snapshot()["critical_audit"]["events"]
    assert {event["event_type"] for event in events} >= {
        "RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "CHILD_PROCESS_CONFIRMED",
        "SUPERVISOR_RUN_FINISHED", "RECEIPT_PREPARED", "RECEIPT_PERSISTED",
    }
    persisted_event = next(event for event in events if event["event_id"] == receipt["receipt_attestation_event_id"])
    assert json.loads(persisted_event["details_json"])["receipt_sha256"] == hashlib.sha256(
        result.receipt_path.read_bytes()
    ).hexdigest()


def test_g2_message_limit_exit_is_only_a_supervised_candidate(tmp_path: Path) -> None:
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "raise SystemExit(4)"],
        stage="scan",
        allow_message_limit_exit=True,
    )

    receipt = _read_receipt(result)
    assert result.result == "COMPLETED"
    assert result.reason == "EXPECTED_MESSAGE_LIMIT_EXIT"
    assert result.exit_code == 4
    assert result.supervisor_gate == "PASS"
    assert receipt["external_exit_code"] == 4
    assert receipt["message_limit_exit_allowed"] is True
    assert receipt["process_tree_termination_confirmed"] is True


def test_message_limit_exit_is_rejected_without_explicit_policy(tmp_path: Path) -> None:
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "raise SystemExit(4)"], stage="scan",
    )

    receipt = _read_receipt(result)
    assert result.result == "FAILED"
    assert result.exit_code == 4
    assert result.supervisor_gate == "BLOCKED"
    assert receipt["message_limit_exit_allowed"] is False


def test_multiple_supervised_stages_use_unique_audit_event_ids(tmp_path: Path) -> None:
    run_root = _private_run_directory(tmp_path)
    ledger = S9OperationalLedger.create(run_root / "multi-stage-ledger.sqlite3")
    run_id = ledger.snapshot()["run"]["run_id"]
    for stage in ("scan", "catalog"):
        result = WindowsCliSupervisor(
            receipt_path=run_root / f"{stage}-receipt.json",
            require_tty=False,
            critical_audit_writer=ledger.record_critical_event,
            ledger_run_id=run_id,
            cooperative_cancel_seconds=0.1,
            tree_containment_seconds=5.0,
        ).run([sys.executable, "-c", "raise SystemExit(0)"], stage=stage)
        assert result.result == "COMPLETED"
        assert result.critical_audit_gate == "PASS"
    events = ledger.snapshot()["critical_audit"]["events"]
    event_ids = [event["event_id"] for event in events]
    assert len(event_ids) == len(set(event_ids))


def test_nonzero_external_exit_is_not_reported_as_success(tmp_path: Path) -> None:
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "raise SystemExit(7)"], stage="scan"
    )

    receipt = _read_receipt(result)
    assert result.result == "FAILED"
    assert result.exit_code == 7
    assert receipt["external_exit_code"] == 7
    assert receipt["supervisor_offline_gate"] == "BLOCKED"


def test_queue_without_prompt_handshake_fails_before_launch(tmp_path: Path) -> None:
    marker = tmp_path / "launched"
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
        stage="queue_f",
    )

    receipt = _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason == "PRECONFIRMATION_PROMPT_SIGNAL_UNAVAILABLE"
    assert result.exit_code is None
    assert not marker.exists()
    assert receipt["preconfirmation_confirmation_released"] is False
    assert receipt["memory_monitoring_offline_gate"] == "BLOCKED"


def test_queue_baseline_is_measured_after_prompt_and_before_release(tmp_path: Path) -> None:
    ready = tmp_path / "prompt.ready"
    released = tmp_path / "prompt.continue"
    script = "\n".join((
        "from pathlib import Path",
        "import sys, time",
        "ready=Path(sys.argv[1]); released=Path(sys.argv[2]); ready.write_text(str(time.monotonic()))",
        "deadline=time.monotonic()+8",
        "while not released.exists() and time.monotonic()<deadline:",
        "    time.sleep(.02)",
        "raise SystemExit(0 if released.exists() else 4)",
    ))
    supervisor_started = time.monotonic()
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", script, str(ready), str(released)],
        stage="queue_f",
        baseline_prompt_ready=ready.exists,
        release_confirmation=released.touch,
        timeout_seconds=10,
    )

    receipt = _read_receipt(result)
    memory = receipt["memory"]
    assert result.result == "COMPLETED"
    assert released.exists()
    assert receipt["preconfirmation_confirmation_released"] is True
    assert memory["baseline_status"] == "PASS_PROMPT_SIGNAL_AND_TWO_SECOND_WINDOW"
    assert len(memory["baseline_samples"]) >= 4
    assert memory["target_sampling_interval_ms"] == 250
    assert memory["baseline_working_set_bytes"] > 0
    assert memory["baseline_private_bytes"] > 0
    assert memory["baseline_samples"][0]["elapsed_seconds"] >= float(ready.read_text()) - supervisor_started
    assert memory["sample_count"] >= len(memory["baseline_samples"])
    assert memory["peak_working_set_bytes"] >= memory["peak_observed_working_set_bytes"]
    assert memory["sampled_peak_private_bytes"] == memory["peak_observed_private_bytes"]
    assert memory["effective_sampling_interval_max_ms"] <= 500
    assert receipt["memory_monitoring_offline_gate"] == "PASS"


def test_stage_timeout_terminates_synthetic_process_tree(tmp_path: Path) -> None:
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stage="scan",
        timeout_seconds=1,
    )

    receipt = _read_receipt(result)
    assert result.result == "TIMED_OUT"
    assert result.reason == "STAGE_TIMEOUT"
    assert result.exit_code is not None
    assert receipt["cooperative_cancel_signal_sent"] is True or receipt["hard_containment_attempted"] is True
    assert receipt["process_tree_termination_confirmed"] is True
    assert receipt["process_control_offline_gate"] == "PASS"


def test_surviving_descendant_is_contained_even_after_root_exit(tmp_path: Path) -> None:
    child_script = "import time; time.sleep(60)"
    parent_script = (
        "import subprocess,sys; subprocess.Popen([sys.executable,'-c',sys.argv[1]])"
    )
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", parent_script, child_script], stage="scan", timeout_seconds=10
    )

    receipt = _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason in {
        "DESCENDANT_REMAINS_AFTER_ROOT_EXIT",
        "ORPHAN_DESCENDANT_TERMINATED",
        "PROCESS_TREE_CONTAINMENT_UNCONFIRMED",
    }
    assert receipt["cooperative_cancel_signal_sent"] is True or receipt["hard_containment_attempted"] is True
    assert receipt["process_tree_termination_confirmed"] is True
    assert receipt["process_control_offline_gate"] == "PASS"
    assert len(receipt["observed_process_identities"]) >= 2


def test_unavailable_containment_mechanisms_leave_gate_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_pid_path = tmp_path / "child.pid"
    child_script = "import os,sys,time; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    parent_script = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); time.sleep(60)"
    )
    monkeypatch.setattr(s9_supervisor, "_send_cooperative_cancel", lambda *_args: False)
    monkeypatch.setattr(s9_supervisor, "_terminate_job", lambda *_args: False)
    result = _supervisor(
        tmp_path,
        cooperative_cancel_seconds=0.1, tree_containment_seconds=0.3,
    ).run(
        [sys.executable, "-c", parent_script, child_script, str(child_pid_path)],
        stage="scan",
        timeout_seconds=1,
    )

    receipt = _read_receipt(result)
    assert child_pid_path.exists()
    assert result.result == "BLOCKED"
    assert result.reason == "PROCESS_TREE_CONTAINMENT_UNCONFIRMED"
    assert receipt["process_tree_termination_confirmed"] is False
    assert receipt["process_control_offline_gate"] == "BLOCKED"
    # Closing the kill-on-close Job Object is a final containment fallback;
    # wait briefly so the synthetic child is not left running by this test.
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    time.sleep(0.2)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    open_process.restype = ctypes.c_void_p
    handle = open_process(0x1000, False, child_pid)
    if handle:
        exit_code = ctypes.c_uint32()
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        get_exit_code.restype = ctypes.c_int
        try:
            assert get_exit_code(handle, ctypes.byref(exit_code))
            assert exit_code.value != 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)


def test_memory_working_set_limit_triggers_containment(tmp_path: Path) -> None:
    script = (
        "import ctypes,time; data=(ctypes.c_char*(32*1024*1024))(); "
        "ctypes.memset(data,1,len(data)); time.sleep(30)"
    )
    result = _supervisor(tmp_path, max_working_set_bytes=20 * 1024 * 1024).run(
        [sys.executable, "-c", script], stage="scan", timeout_seconds=10
    )

    receipt = _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason == "WORKING_SET_LIMIT_EXCEEDED"
    assert receipt["cooperative_cancel_signal_sent"] is True or receipt["hard_containment_attempted"] is True
    assert receipt["process_tree_termination_confirmed"] is True
    assert receipt["memory_monitoring_offline_gate"] == "PASS"


def test_native_process_peak_enforces_cap_even_below_sampled_current_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def measured_sample(_api: object, _job: object, started: float):
        sample = s9_supervisor.ProcessSample(
            timestamp_utc="2026-10-29T00:00:00+00:00",
            elapsed_seconds=time.monotonic() - started,
            process_count=1,
            working_set_bytes=5 * 1024 * 1024,
            private_bytes=6 * 1024 * 1024,
        )
        metrics = {(1, 1): (sample.working_set_bytes, sample.private_bytes, 40 * 1024 * 1024)}
        return sample, metrics

    monkeypatch.setattr(s9_supervisor, "_sample_tree", measured_sample)
    result = _supervisor(tmp_path, max_working_set_bytes=20 * 1024 * 1024).run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stage="scan", timeout_seconds=10,
    )

    receipt = _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason == "WORKING_SET_LIMIT_EXCEEDED"
    assert receipt["memory"]["peak_working_set_bytes"] == 40 * 1024 * 1024
    assert receipt["process_tree_termination_confirmed"] is True


def test_tree_peak_does_not_accumulate_peaks_of_disjoint_processes() -> None:
    monitor = s9_supervisor.MemoryMonitor()
    first = s9_supervisor.ProcessSample("2026-10-29T00:00:00+00:00", 0.25, 1, 4, 5)
    second = s9_supervisor.ProcessSample("2026-10-29T00:00:01+00:00", 0.50, 1, 6, 7)
    monitor.add(first, {(11, 101): (4, 5, 20)})
    monitor.add(second, {(22, 202): (6, 7, 30)})
    assert monitor.peak_sum_process_working_set_bytes == 30


def test_working_set_growth_limit_is_measured_from_prompt_baseline(tmp_path: Path) -> None:
    ready = tmp_path / "prompt.ready"
    released = tmp_path / "prompt.continue"
    script = "\n".join((
        "from pathlib import Path",
        "import ctypes, sys, time",
        "ready=Path(sys.argv[1]); released=Path(sys.argv[2]); ready.touch()",
        "deadline=time.monotonic()+10",
        "while not released.exists() and time.monotonic()<deadline:",
        "    time.sleep(.02)",
        "data=(ctypes.c_char*(48*1024*1024))()",
        "ctypes.memset(data,1,len(data))",
        "time.sleep(20)",
    ))
    result = _supervisor(
        tmp_path,
        max_working_set_bytes=200 * 1024 * 1024,
        max_working_set_growth_bytes=2 * 1024 * 1024,
    ).run(
        [sys.executable, "-c", script, str(ready), str(released)],
        stage="queue_m",
        baseline_prompt_ready=ready.exists,
        release_confirmation=released.touch,
        timeout_seconds=10,
    )

    receipt = _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason == "WORKING_SET_GROWTH_LIMIT_EXCEEDED"
    assert receipt["memory_monitoring_offline_gate"] == "PASS"
    assert receipt["process_tree_termination_confirmed"] is True


def test_global_deadline_prevents_launch_when_already_expired(tmp_path: Path) -> None:
    marker = tmp_path / "launched"
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
        stage="scan",
        global_deadline_monotonic=time.monotonic() - 1,
    )

    _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason == "GLOBAL_DEADLINE_EXCEEDED_BEFORE_LAUNCH"
    assert result.exit_code is None


def test_global_deadline_expiring_during_run_contains_process_tree(tmp_path: Path) -> None:
    deadline = time.monotonic() + 1.0
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stage="scan", timeout_seconds=10,
        global_started_monotonic=deadline - 1.0,
        global_deadline_monotonic=deadline,
    )

    receipt = _read_receipt(result)
    assert result.result == "TIMED_OUT"
    assert result.reason == "GLOBAL_DEADLINE_EXCEEDED"
    assert receipt["process_tree_termination_confirmed"] is True
    assert receipt["process_control_offline_gate"] == "PASS"


def test_unavailable_windows_supervisor_fails_closed_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "launched"

    def unavailable() -> tuple[object, ...]:
        raise s9_supervisor.SupervisorError("WINDOWS_JOB_OBJECT_REQUIRED")

    monkeypatch.setattr(s9_supervisor, "_windows_api", unavailable)
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
        stage="scan",
    )

    receipt = _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason == "WINDOWS_JOB_OBJECT_REQUIRED"
    assert result.exit_code is None
    assert not marker.exists()
    assert receipt["supervisor_offline_gate"] == "BLOCKED"


def test_receipt_refuses_overwrite(tmp_path: Path) -> None:
    receipt_path = _private_run_directory(tmp_path) / "receipt.json"
    receipt_path.write_text('{"preserve": true}', encoding="utf-8")
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "pass"], stage="scan"
    )

    assert result.result == "BLOCKED"
    assert result.reason == "RECEIPT_ALREADY_EXISTS"
    assert receipt_path.read_text(encoding="utf-8") == '{"preserve": true}'


def test_tty_is_required_by_default_and_process_is_not_started_without_it(tmp_path: Path) -> None:
    marker = tmp_path / "launched"
    result = _supervisor(tmp_path, require_tty=True).run(
        [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
        stage="queue_f",
    )

    receipt = _read_receipt(result)
    assert result.result == "BLOCKED"
    assert result.reason == "TTY_REQUIRED_BUT_UNAVAILABLE"
    assert result.exit_code is None
    assert not marker.exists()
    assert receipt["tty_required"] is True


def test_cancel_event_stops_synthetic_process(tmp_path: Path) -> None:
    event = threading.Event()
    timer = threading.Timer(1.0, event.set)
    timer.start()
    try:
        result = _supervisor(
            tmp_path,
            cancel_event=event,
            cooperative_cancel_seconds=0.1,
            tree_containment_seconds=5.0,
        ).run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stage="scan",
            timeout_seconds=10,
        )
    finally:
        timer.cancel()

    receipt = _read_receipt(result)
    assert result.result == "CANCELLED"
    assert result.reason == "USER_CANCELLATION_REQUESTED"
    assert receipt["process_tree_termination_confirmed"] is True
    assert receipt["process_control_offline_gate"] == "PASS"


def test_critical_audit_failure_blocks_before_child_launch_and_redacts_exception(
    tmp_path: Path,
) -> None:
    ledger = _audit_ledger(tmp_path)
    marker = tmp_path / "launched"

    def failed_writer(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise LedgerError("synthetic-canary-secret")

    run_id = str(ledger.snapshot()["run"]["run_id"])
    result = WindowsCliSupervisor(
        receipt_path=_private_run_directory(tmp_path) / "receipt.json", require_tty=False,
        critical_audit_writer=failed_writer, ledger_run_id=run_id,
    ).run(
        [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)],
        stage="scan",
    )

    assert result.result == "BLOCKED"
    assert result.reason == "CRITICAL_AUDIT_ACK_FAILED"
    assert result.critical_audit_gate == "BLOCKED"
    assert result.receipt_persisted is False
    assert not marker.exists()
    assert not (_private_run_directory(tmp_path) / "receipt.json").exists()
    assert "synthetic-canary-secret" not in repr(result)


def test_audit_failure_during_cancellation_stays_blocked(tmp_path: Path) -> None:
    ledger = _audit_ledger(tmp_path)
    run_id = str(ledger.snapshot()["run"]["run_id"])
    cancel_event = threading.Event()

    def writer(event_type: str, *, details: dict[str, object], event_id: str):
        if event_type == "RUN_CANCELLED":
            raise RuntimeError("secret-canary-audit-cancel")
        return ledger.record_critical_event(
            event_type, details=details, event_id=event_id,
        )

    supervisor = WindowsCliSupervisor(
        receipt_path=_private_run_directory(tmp_path) / "cancel-audit-receipt.json",
        cancel_event=cancel_event,
        require_tty=False,
        critical_audit_writer=writer,
        ledger_run_id=run_id,
        cooperative_cancel_seconds=0.1,
        tree_containment_seconds=5.0,
    )
    timer = threading.Timer(0.2, cancel_event.set)
    timer.start()
    result = supervisor.run(
        [sys.executable, "-c", "import time; time.sleep(60)"], stage="scan",
    )
    timer.join(timeout=2)
    assert result.result == "BLOCKED"
    assert result.supervisor_gate == "BLOCKED"
    assert result.critical_audit_gate == "BLOCKED"


def test_receipt_persisted_without_final_audit_ack_is_incomplete_and_blocked(
    tmp_path: Path,
) -> None:
    ledger = _audit_ledger(tmp_path)
    run_id = str(ledger.snapshot()["run"]["run_id"])

    def fail_persisted_event(event_type: str, *, details: dict[str, object], event_id: str):
        if event_type == "RECEIPT_PERSISTED":
            raise LedgerError("AUDIT_SYNC_FAILED")
        return ledger.record_critical_event(event_type, details=details, event_id=event_id)

    result = WindowsCliSupervisor(
        receipt_path=_private_run_directory(tmp_path) / "receipt.json", require_tty=False,
        critical_audit_writer=fail_persisted_event, ledger_run_id=run_id,
    ).run([sys.executable, "-c", "pass"], stage="scan")

    assert result.result == "BLOCKED"
    assert result.critical_audit_gate == "BLOCKED"
    assert result.receipt_persisted is True
    assert result.receipt_attested is False
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["receipt_attestation_event_id"]


def test_global_deadline_cannot_start_in_future_or_exceed_one_hour(tmp_path: Path) -> None:
    result = _supervisor(tmp_path).run(
        [sys.executable, "-c", "pass"], stage="scan",
        global_started_monotonic=time.monotonic() + 10,
        global_deadline_monotonic=time.monotonic() + 3600,
    )
    assert result.result == "BLOCKED"
    assert result.reason == "GLOBAL_DEADLINE_INVALID"
    assert result.exit_code is None
    assert result.critical_audit_gate == "PASS"


def test_supervisor_cannot_relax_frozen_memory_and_baseline_limits(tmp_path: Path) -> None:
    with pytest.raises(s9_supervisor.SupervisorError, match="SUPERVISOR_LIMIT_CONFIGURATION_INVALID"):
        _supervisor(tmp_path, max_working_set_bytes=513 * 1024 * 1024)
