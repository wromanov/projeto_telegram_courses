from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
from pathlib import Path

import pytest
from tools.manual_proofs import s6_v2_offline_regression_runner as runner


def test_launcher_avoids_split_path_literal_ambiguous_parameter_set() -> None:
    launcher = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "manual_proofs"
        / "Invoke-S6V2OfflineRegression.ps1"
    )
    source = launcher.read_text(encoding="utf-8")
    function_marker = "function Assert-SafeInvocationDirectory {"
    function_source = source.split(function_marker, maxsplit=1)[1].split("\n}", maxsplit=1)[0]

    assert "[System.IO.Path]::GetDirectoryName($runDirectory)" in function_source
    assert "[System.IO.Path]::GetFileName($tokenDirectory)" in function_source
    assert re.search(r"\bSplit-Path\b", function_source, flags=re.IGNORECASE) is None


class FakeProcess:
    pid = 43210

    def __init__(self, exit_code: int | None = 0, *, timeout: bool = False) -> None:
        self.exit_code = exit_code
        self.timeout = timeout
        self.wait_calls = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.timeout and self.exit_code is None:
            raise subprocess.TimeoutExpired("fake-worker", timeout)
        return int(self.exit_code or 0)

    def poll(self) -> int | None:
        return self.exit_code

    def kill(self) -> None:
        self.exit_code = -9


def _supervise(tmp_path: Path, process: FakeProcess, *, terminate_tree=None):
    def popen(*_args, **_kwargs):
        return process

    return runner.supervise_process(
        ["fake-worker"],
        cwd=tmp_path,
        stdout_path=tmp_path / "stdout.log",
        stderr_path=tmp_path / "stderr.log",
        timeout_seconds=1,
        popen=popen,
        terminate_tree=terminate_tree or runner.terminate_process_tree,
    )


def test_supervisor_records_normal_exit_and_file_backed_streams(tmp_path: Path) -> None:
    result = _supervise(tmp_path, FakeProcess(0))

    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert result["termination_confirmed"] is True
    assert (tmp_path / "stdout.log").is_file()
    assert (tmp_path / "stderr.log").is_file()


def test_supervisor_preserves_nonzero_exit(tmp_path: Path) -> None:
    result = _supervise(tmp_path, FakeProcess(7))

    assert result["exit_code"] == 7
    assert result["timed_out"] is False


def test_supervisor_times_out_kills_tree_and_confirms_termination(tmp_path: Path) -> None:
    process = FakeProcess(None, timeout=True)
    grace: list[int] = []

    def terminate(fake_process: FakeProcess) -> bool:
        grace.append(5)
        fake_process.kill()
        return fake_process.poll() is not None

    result = _supervise(tmp_path, process, terminate_tree=terminate)

    assert result["timed_out"] is True
    assert result["termination_confirmed"] is True
    assert result["exit_code"] == -9
    assert grace == [5]
    assert runner.timeout_outcome(True) == ("INCOMPLETE", "WORKER_TIMEOUT", 4)


def test_unconfirmed_termination_classifies_timeout_as_blocked(tmp_path: Path) -> None:
    process = FakeProcess(None, timeout=True)
    result = _supervise(tmp_path, process, terminate_tree=lambda _process: False)

    assert result["timed_out"] is True
    assert result["termination_confirmed"] is False
    assert runner.timeout_outcome(False) == ("BLOCKED", "PROCESS_EXIT_UNCONFIRMED", 3)


def test_profile_diagnostic_dumps_use_bounded_profile_intervals(monkeypatch) -> None:
    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(
        runner.faulthandler,
        "dump_traceback_later",
        lambda seconds, *, file: calls.append((seconds, file)),
    )
    output = object()

    runner.schedule_diagnostic_dump("Affected", output)
    runner.schedule_diagnostic_dump("Harness", output)

    assert calls == [(12, output), (120, output)]


def test_receipt_absence_and_junit_absence_are_incomplete(tmp_path: Path) -> None:
    receipt = runner._receipt_from_worker("Affected", tmp_path, 0)

    assert receipt["result"] == "INCOMPLETE"
    assert receipt["junit_present"] is False
    assert receipt["tests"] == 0


def test_receipt_retains_full_run_id(tmp_path: Path) -> None:
    run_id = "0123456789abcdef0123456789abcdef"
    receipt = runner._receipt_from_worker("Affected", tmp_path, 0, run_id)

    assert receipt["run_id"] == run_id


def test_skip_and_xfail_never_pass(tmp_path: Path) -> None:
    node = runner.PROFILE_SETTINGS["Affected"]["node"]
    outcome_skip, collection_skip = runner.classify_worker_result(
        "Affected",
        exit_code=0,
        collected_nodeids=[node],
        counts={"tests": 1, "passed": 0, "failed": 0, "skipped": 1, "xfail": 0},
    )
    outcome_xfail, collection_xfail = runner.classify_worker_result(
        "Affected",
        exit_code=0,
        collected_nodeids=[node],
        counts={"tests": 1, "passed": 1, "failed": 0, "skipped": 0, "xfail": 0},
        xfail=1,
    )

    assert (outcome_skip, collection_skip) == ("FAIL", True)
    assert (outcome_xfail, collection_xfail) == ("FAIL", True)


def test_unexpected_collection_and_missing_junit_are_incomplete() -> None:
    affected_node = runner.PROFILE_SETTINGS["Affected"]["node"]
    unexpected, collection_ok = runner.classify_worker_result(
        "Affected",
        exit_code=0,
        collected_nodeids=[affected_node, affected_node + "[extra]"],
        counts={"tests": 2, "passed": 2, "failed": 0, "skipped": 0, "xfail": 0},
    )
    missing_junit, _ = runner.classify_worker_result(
        "Affected", exit_code=0, collected_nodeids=[affected_node], counts=None
    )

    assert unexpected == "INCOMPLETE"
    assert collection_ok is False
    assert missing_junit == "INCOMPLETE"


def test_profile_commands_are_fixed_and_harness_has_no_exclusion_filter() -> None:
    assert runner.PROFILE_SETTINGS["Affected"]["node"] == (
        "tests/manual_proofs/test_s6_v2_proof_harness.py::"
        "test_unaligned_preparation_uses_controlled_application_stream_and_reconciles_wire"
    )
    assert runner.PROFILE_SETTINGS["Harness"]["node"] == (
        "tests/manual_proofs/test_s6_v2_proof_harness.py"
    )
    assert runner.PROFILE_SETTINGS["Affected"]["deadline_seconds"] == 25
    assert runner.PROFILE_SETTINGS["Harness"]["deadline_seconds"] == 150
    assert "expected_tests" not in runner.PROFILE_SETTINGS["Harness"] or (
        runner.PROFILE_SETTINGS["Harness"]["expected_tests"] is None
    )


def _short_repo_run() -> tuple[Path, Path]:
    repo_root = Path.cwd()
    token = secrets.token_hex(6)
    while runner._is_redirected(repo_root / ".s6r" / token):
        token = secrets.token_hex(6)
    return repo_root, repo_root / ".s6r" / token / "t"


def test_pytest_basetemp_is_short_under_run_root_and_passed_to_pytest() -> None:
    repo_root, run_dir = _short_repo_run()

    basetemp = runner.validated_pytest_basetemp(repo_root, run_dir)
    args = runner.build_pytest_args(
        "Affected", run_dir / "junit.xml", basetemp
    )

    assert basetemp == (run_dir / "p").resolve()
    assert basetemp.is_relative_to(run_dir.resolve())
    assert len(str(basetemp)) <= 80
    assert args[args.index("--basetemp") + 1] == str(basetemp)


def test_pytest_basetemp_rejects_outside_root_and_overlong_path(monkeypatch) -> None:
    repo_root, allowed_run = _short_repo_run()
    outside_run = repo_root / "other" / "run-03"
    with pytest.raises(ValueError, match="RUN_DIRECTORY_OUTSIDE_ALLOWED_ROOT"):
        runner.validated_pytest_basetemp(repo_root, outside_run)

    invalid_layout = repo_root / ".s6r" / "too-long-token" / "t"
    with pytest.raises(ValueError, match="RUN_DIRECTORY_LAYOUT_INVALID"):
        runner.validated_pytest_basetemp(repo_root, invalid_layout)
    monkeypatch.setattr(runner, "MAX_BASETEMP_PATH_CHARS", 1)
    with pytest.raises(ValueError, match="PYTEST_BASETEMP_PATH_TOO_LONG"):
        runner.validated_pytest_basetemp(repo_root, allowed_run)


def test_allocation_uses_exclusive_token_with_collision_retry_and_full_run_id(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(runner, "MAX_BASETEMP_PATH_CHARS", 1024)
    allocation_root = repo_root / ".s6r"

    old_token_name = secrets.token_hex(6)
    while (allocation_root / old_token_name).exists():
        old_token_name = secrets.token_hex(6)
    new_token_name = secrets.token_hex(6)
    while new_token_name == old_token_name or (allocation_root / new_token_name).exists():
        new_token_name = secrets.token_hex(6)
    old_token = allocation_root / old_token_name
    sentinel = old_token / "historical.receipt.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("historical", encoding="utf-8")
    tokens = iter((old_token_name, new_token_name))
    run_id = "f" * 32

    allocated_run_id, run_dir = runner.allocate_invocation(
        repo_root,
        token_factory=lambda: next(tokens),
        run_id_factory=lambda: run_id,
    )

    assert allocated_run_id == run_id
    assert run_dir == allocation_root / new_token_name / "t"
    assert run_dir.is_dir()
    assert sentinel.read_text(encoding="utf-8") == "historical"
    assert len(run_dir.parent.name) == 12


def test_allocation_rejects_redirected_root_and_run_components(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    monkeypatch.setattr(runner, "MAX_BASETEMP_PATH_CHARS", 1024)
    allocation_root = repo_root / ".s6r"
    allocation_root.mkdir(parents=True)
    original = runner._is_redirected
    monkeypatch.setattr(
        runner,
        "_is_redirected",
        lambda path: path == allocation_root or original(path),
    )

    with pytest.raises(ValueError, match="REDIRECTED_ALLOCATION_PATH"):
        runner.allocate_invocation(repo_root)

    monkeypatch.setattr(runner, "_is_redirected", original)
    _run_id, run_dir = runner.allocate_invocation(repo_root)
    redirected_token = run_dir.parent
    monkeypatch.setattr(
        runner,
        "_is_redirected",
        lambda path: path == redirected_token or original(path),
    )
    with pytest.raises(ValueError, match="REDIRECTED_ALLOCATION_PATH"):
        runner.validated_pytest_basetemp(repo_root, run_dir)


def test_basetemp_observed_part_budget_is_at_most_231_characters() -> None:
    repo_root, run_dir = _short_repo_run()
    basetemp = runner.validated_pytest_basetemp(repo_root, run_dir)
    observed_tail = "\\" + ("x" * 145) + ".part"
    part_path = Path(f"{basetemp}{observed_tail}")

    assert len(observed_tail) == 151
    assert runner.MAX_BASETEMP_PATH_CHARS + len(observed_tail) == 231
    assert len(str(part_path)) == len(str(basetemp)) + len(observed_tail)
    assert len(str(part_path)) <= runner.MAX_OBSERVED_DERIVED_PART_PATH_CHARS
    assert len(str(part_path)) <= runner.MAX_DERIVED_PATH_GUARD_CHARS


def test_artifact_resolution_rejects_escape_and_redirected_file(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(runner, "MAX_BASETEMP_PATH_CHARS", 1024)
    _run_id, run_dir = runner.allocate_invocation(repo_root)
    inside = runner.contained_artifact_path(repo_root, run_dir, "receipt.json")
    assert inside == run_dir / "receipt.json"

    with pytest.raises(ValueError):
        runner.contained_artifact_path(repo_root, run_dir, "../../outside.json")

    redirected = run_dir / "receipt.json"
    original = runner._is_redirected
    monkeypatch.setattr(
        runner,
        "_is_redirected",
        lambda path: path == redirected or original(path),
    )
    with pytest.raises(ValueError, match="REDIRECTED_ALLOCATION_PATH"):
        runner.contained_artifact_path(repo_root, run_dir, "receipt.json")


def test_sandbox_signature_checks_both_environment_roots() -> None:
    assert runner.is_sandbox_environment(
        {"TEMP": r"C:\other\Temp", "LOCALAPPDATA": r"C:\Users\test\AppData\Local\Packages\sandbox.{x}"}
    )
    assert not runner.is_sandbox_environment(
        {"TEMP": r"C:\other\Temp", "LOCALAPPDATA": r"C:\Users\test\AppData\Local"}
    )


def test_sandbox_admission_writes_blocked_receipt_without_worker_or_env_substitution(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    monkeypatch.setattr(runner, "MAX_BASETEMP_PATH_CHARS", 1024)
    run_dir = repo_root / ".s6r" / "0123456789ae" / "t"
    run_dir.mkdir(parents=True)
    run_id = "0123456789abcdef0123456789abcdef"
    temp_value = r"C:\Users\test\AppData\Local\Packages\sandbox.{runtime}\Temp"
    local_value = r"C:\Users\test\AppData\Local\Packages\sandbox.{runtime}"
    monkeypatch.setenv("TEMP", temp_value)
    monkeypatch.setenv("LOCALAPPDATA", local_value)
    monkeypatch.setattr(
        runner,
        "supervise_process",
        lambda *_args, **_kwargs: pytest.fail("sandbox admission started worker"),
    )

    exit_code = runner.main(
        [
            "--profile",
            "Affected",
            "--repo-root",
            str(repo_root),
            "--run-dir",
            str(run_dir),
            "--run-id",
            run_id,
        ]
    )
    receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))

    assert exit_code == 3
    assert receipt["result"] == "BLOCKED"
    assert receipt["reason"] == "SANDBOX_ENVIRONMENT"
    assert receipt["run_id"] == run_id
    assert os.environ["TEMP"] == temp_value
    assert os.environ["LOCALAPPDATA"] == local_value


def test_receipt_is_json_and_retains_incomplete_status(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    runner._atomic_json(path, {"result": "INCOMPLETE", "termination_confirmed": True})

    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert receipt == {"result": "INCOMPLETE", "termination_confirmed": True}
