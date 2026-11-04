from __future__ import annotations

import hashlib
import io
import json
import inspect
import os
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.manual_proofs import s6_v2_mxc_host_executor as host


def _request(op: str, request_id: str = "request-1", **fields: object) -> str:
    if op == "submit":
        fields.setdefault("scenario", "suite")
    return json.dumps({"op": op, "request_id": request_id, **fields}, separators=(",", ":"))


def _seed_job(
    executor: host.HostExecutor,
    job_id: str,
    *,
    state: str = "RUNNING",
    result: dict[str, object] | None = None,
    scenario: str = "suite",
    run_root: str = "",
) -> host.Job:
    now = time.monotonic()
    job = host.Job(
        job_id=job_id,
        profile=host.PROFILE_NAME,
        run_root=run_root,
        state=state,
        submitted_monotonic=now,
        deadline_monotonic=now + host.HARD_DEADLINE_SECONDS,
        result=result,
        scenario=scenario,
    )
    executor._jobs[job_id] = job
    return job


def test_protocol_profile_is_fixed_to_infrastructure_protocol_tests() -> None:
    assert set(host.PROFILE_ALLOWLIST) == {"Infrastructure"}
    assert host.PROFILE_ALLOWLIST["Infrastructure"]["selection"] == (
        "tests/manual_proofs/test_s6_v2_mxc_host_executor.py"
    )
    assert host.PROFILE_ALLOWLIST["Infrastructure"]["deadline_seconds"] == 150
    assert host.PROFILE_ALLOWLIST["Infrastructure"]["diagnostic_seconds"] == 120
    assert set(host.SCENARIO_ALLOWLIST) == {
        "suite", "controlled_failure", "timeout_child", "cancel_child",
    }
    assert host.SCENARIO_ALLOWLIST["suite"]["pytest_selector"] is None
    assert host.SCENARIO_ALLOWLIST["controlled_failure"]["pytest_selector"] == (
        "test_s6_v2_mxc_synthetic_failure"
    )
    assert host.SCENARIO_ALLOWLIST["timeout_child"]["pytest_selector"] == (
        "test_s6_v2_mxc_timeout_child"
    )
    assert host.SCENARIO_ALLOWLIST["cancel_child"]["pytest_selector"] == (
        "test_s6_v2_mxc_cancel_child"
    )
    assert callable(globals()[host.SCENARIO_ALLOWLIST["controlled_failure"]["pytest_selector"]])
    assert callable(globals()[host.SCENARIO_ALLOWLIST["timeout_child"]["pytest_selector"]])
    assert callable(globals()[host.SCENARIO_ALLOWLIST["cancel_child"]["pytest_selector"]])


def test_parse_request_accepts_bounded_jsonl_submit_frame() -> None:
    frame = _request("submit", profile="Infrastructure")

    assert host.parse_request(frame) == {
        "op": "submit",
        "request_id": "request-1",
        "profile": "Infrastructure",
        "scenario": "suite",
    }


@pytest.mark.parametrize(
    ("frame", "error"),
    [
        ("{bad json", "INVALID_JSONL_FRAME"),
        ("[]", "REQUEST_MUST_BE_OBJECT"),
        (_request("status", job_id="A" * 32), "JOB_ID_INVALID"),
        (_request("unknown"), "REQUEST_SCHEMA_INVALID"),
        (_request("submit", profile="Affected"), "PROFILE_NOT_ALLOWLISTED"),
        (_request("submit", profile="Harness"), "PROFILE_NOT_ALLOWLISTED"),
        (_request("submit", profile="Infrastructure", command="pytest"), "REQUEST_SCHEMA_INVALID"),
        (_request("submit", profile="Infrastructure", path="C:/outside"), "REQUEST_SCHEMA_INVALID"),
        (_request("submit", profile="Infrastructure", plugin="anything"), "REQUEST_SCHEMA_INVALID"),
        (_request("submit", profile="Infrastructure", scenario="custom"), "SCENARIO_NOT_ALLOWLISTED"),
        (_request("submit", profile="Infrastructure", scenario="suite", selection="tests/elsewhere.py"), "REQUEST_SCHEMA_INVALID"),
        (json.dumps({"op": "submit", "request_id": "", "profile": "Infrastructure", "scenario": "suite"}), "REQUEST_ID_INVALID"),
    ],
)
def test_parse_request_rejects_invalid_or_arbitrary_execution_fields(frame: str, error: str) -> None:
    with pytest.raises(host.ProtocolError, match=error):
        host.parse_request(frame)


def test_parse_request_rejects_oversized_frame_before_interpreting_it() -> None:
    frame = " " * (host.MAX_REQUEST_BYTES + 1)

    with pytest.raises(host.ProtocolError, match="FRAME_TOO_LARGE"):
        host.parse_request(frame)


def test_serve_emits_one_jsonl_reply_per_frame_and_preserves_request_identity() -> None:
    frames = "\n".join(
        [
            _request("status", "status-req", job_id="a" * 32),
            "{invalid",
            "",
        ]
    )
    output = io.StringIO()

    exit_code = host.serve(io.StringIO(frames), output)
    replies = [json.loads(line) for line in output.getvalue().splitlines()]

    assert exit_code == 0
    assert len(replies) == 3
    assert replies[0]["request_id"] == "status-req"
    assert replies[0]["ok"] is False
    assert replies[0]["error"] == "JOB_NOT_FOUND"
    assert replies[1]["request_id"] == "unknown"
    assert replies[1]["ok"] is False
    assert replies[1]["error"] == "INVALID_JSONL_FRAME"
    assert replies[2]["request_id"] == "shutdown"
    assert replies[2]["status"] == "CLOSED"
    assert replies[2]["ok"] is True


def test_handle_echoes_request_and_job_identity_for_status_cancel_and_result(tmp_path: Path) -> None:
    executor = host.HostExecutor(tmp_path)
    job_id = "a" * 32
    job = _seed_job(executor, job_id)

    status = executor.handle(host.parse_request(_request("status", "status-1", job_id=job_id)))
    cancel = executor.handle(host.parse_request(_request("cancel", "cancel-1", job_id=job_id)))
    assert status["request_id"] == "status-1"
    assert status["job_id"] == job_id
    assert status["state"] == "RUNNING"
    assert cancel["request_id"] == "cancel-1"
    assert cancel["job_id"] == job_id
    assert cancel["state"] == "CANCELLING"
    assert job.cancel_requested is True

    job.state = "COMPLETED"
    job.run_root = str(tmp_path)
    job.result = {
        "schema": "s6-v2-mxc-job-receipt-v1",
        "job_id": job_id,
        "result": "BLOCKED",
        "reason": "SYNTHETIC_FIXTURE",
    }
    receipt_path = tmp_path / "receipt.json"
    host._atomic_json(receipt_path, job.result)
    job.receipt_sha256 = host._sha256(receipt_path)
    result = executor.handle(host.parse_request(_request("result", "result-1", job_id=job_id)))
    assert result["request_id"] == "result-1"
    assert result["job_id"] == job_id
    assert result["result"] == job.result


def test_result_is_fail_closed_until_job_is_final_and_result_exists(tmp_path: Path) -> None:
    executor = host.HostExecutor(tmp_path)
    job_id = "b" * 32
    job = _seed_job(executor, job_id, state="RUNNING")
    request = host.parse_request(_request("result", "result-2", job_id=job_id))

    not_final = executor.handle(request)
    assert not_final["ok"] is False
    assert not_final["error"] == "JOB_NOT_FINAL"

    job.state = "FAILED"
    missing_result = executor.handle(request)
    assert missing_result["ok"] is False
    assert missing_result["error"] == "FINAL_RESULT_MISSING"


def test_submit_uses_only_fixed_infrastructure_profile_without_starting_a_job_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = host.HostExecutor(tmp_path)

    def synthetic_worker(job: host.Job) -> None:
        job.result = {
            "job_id": job.job_id,
            "profile": job.profile,
            "result": "BLOCKED",
            "reason": "SYNTHETIC_PROTOCOL_TEST",
        }
        job.state = "BLOCKED"

    monkeypatch.setattr(executor, "_run_job", synthetic_worker)
    request = host.parse_request(_request("submit", "submit-1", profile="Infrastructure", scenario="suite"))
    reply = executor.handle(request)
    job_id = reply["job_id"]
    executor._jobs[job_id].thread.join(timeout=1)

    assert reply["request_id"] == "submit-1"
    assert len(job_id) == 32
    assert reply["state"] == "QUEUED"
    assert executor._jobs[job_id].profile == "Infrastructure"
    assert executor._jobs[job_id].scenario == "suite"
    assert executor._jobs[job_id].state == "BLOCKED"
    assert executor._jobs[job_id].result["reason"] == "SYNTHETIC_PROTOCOL_TEST"


def _write_junit(
    path: Path,
    job_id: str | None,
    *,
    scenario: str = "suite",
    selection: str = host.PROFILE_SELECTION,
    child: str = "<testcase name=\"protocol\"/>",
) -> None:
    properties = "<properties>"
    if job_id is not None:
        properties += f"<property name=\"s6_job_id\" value=\"{job_id}\"/>"
    properties += (
        f"<property name=\"s6_scenario\" value=\"{scenario}\"/>"
        f"<property name=\"s6_selection\" value=\"{selection}\"/>"
        "</properties>"
    )
    path.write_text(f"<testsuite tests=\"1\">{properties}{child}</testsuite>", encoding="utf-8")


def test_junit_reconciliation_requires_exact_job_identity_and_separate_streams(tmp_path: Path) -> None:
    job_id = "c" * 32
    junit = tmp_path / "junit.xml"
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    _write_junit(junit, job_id)
    stdout.write_text("synthetic stdout", encoding="utf-8")
    stderr.write_text("synthetic stderr", encoding="utf-8")

    worker_outcome = host._reconcile_junit(
        junit, stdout, stderr, job_id=job_id, scenario="suite",
        selection=host.PROFILE_SELECTION, exit_code=0,
    )
    wrong_identity = host._reconcile_junit(
        junit, stdout, stderr, job_id="d" * 32, scenario="suite",
        selection=host.PROFILE_SELECTION, exit_code=0,
    )
    junit_bytes = junit.read_bytes()
    stdout.unlink()
    missing_stream = host._reconcile_junit(
        junit, stdout, stderr, job_id=job_id, scenario="suite",
        selection=host.PROFILE_SELECTION, exit_code=0,
    )

    assert worker_outcome == ("PASS", "WORKER_PASS_ISOLATION_GATE_PENDING")
    assert wrong_identity == ("INCOMPLETE", "JUNIT_IDENTITY_MISMATCH")
    assert missing_stream == ("INCOMPLETE", "JOB_STREAM_MISSING")
    assert junit.read_bytes() == junit_bytes


@pytest.mark.parametrize(
    ("junit_state", "exit_code", "expected"),
    [
        ("missing", 0, ("INCOMPLETE", "JUNIT_MISSING")),
        ("malformed", 0, ("INCOMPLETE", "JUNIT_INVALID")),
        ("empty", 0, ("INCOMPLETE", "JUNIT_EMPTY")),
        ("skipped", 0, ("FAIL", "JUNIT_SKIPPED")),
        ("failed", 0, ("FAIL", "JUNIT_OR_EXIT_FAILURE")),
        ("success", 5, ("FAIL", "JUNIT_OR_EXIT_FAILURE")),
    ],
)
def test_junit_reconciliation_fails_closed_on_incomplete_or_failed_evidence(
    tmp_path: Path, junit_state: str, exit_code: int, expected: tuple[str, str],
) -> None:
    job_id = "e" * 32
    junit = tmp_path / "junit.xml"
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    if junit_state == "malformed":
        junit.write_text("<testsuite", encoding="utf-8")
    elif junit_state == "empty":
        junit.write_text("<testsuite tests=\"0\"/>", encoding="utf-8")
    elif junit_state == "skipped":
        _write_junit(junit, job_id, child="<testcase name=\"protocol\"><skipped/></testcase>")
    elif junit_state == "failed":
        _write_junit(junit, job_id, child="<testcase name=\"protocol\"><failure/></testcase>")
    elif junit_state == "success":
        _write_junit(junit, job_id)

    outcome = host._reconcile_junit(
        junit, stdout, stderr, job_id=job_id, scenario="suite",
        selection=host.PROFILE_SELECTION, exit_code=exit_code,
    )

    assert outcome == expected


def test_atomic_receipt_publication_leaves_one_complete_json_file(tmp_path: Path) -> None:
    receipt = tmp_path / "run" / "receipt.json"
    payload = {"job_id": "f" * 32, "result": "BLOCKED", "reason": "SYNTHETIC"}

    host._atomic_json(receipt, payload)

    assert json.loads(receipt.read_text(encoding="utf-8")) == payload
    assert list(receipt.parent.iterdir()) == [receipt]


def test_worker_bootstrap_emits_identity_on_original_junit_reports(tmp_path: Path) -> None:
    job_id = "1" * 32
    bootstrap = host._pytest_bootstrap(
        tmp_path / "snapshot",
        tmp_path / "artifacts" / "junit.xml",
        [],
        job_id=job_id,
        scenario="suite",
        selection=host.PROFILE_SELECTION,
    )

    assert "pytest_runtest_makereport" in bootstrap
    assert "report.user_properties.extend" in bootstrap
    assert "('s6_job_id', _job_id)" in bootstrap or '("s6_job_id", _job_id)' in bootstrap
    assert "('s6_scenario', _scenario)" in bootstrap or '("s6_scenario", _scenario)' in bootstrap
    assert "('s6_selection', _selection)" in bootstrap or '("s6_selection", _selection)' in bootstrap
    assert "plugins=[_S6IdentityPlugin()]" in bootstrap
    assert job_id in bootstrap
    assert bootstrap.index("socket.create_connection") < bootstrap.index("raise SystemExit")
    assert "os.replace(_canary_tmp, _canary_path)" in bootstrap


@pytest.mark.parametrize("identity", [None, "2" * 32])
def test_host_rejects_missing_or_divergent_junit_identity_without_rewriting(
    tmp_path: Path, identity: str | None,
) -> None:
    job_id = "3" * 32
    junit = tmp_path / "junit.xml"
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("synthetic stdout", encoding="utf-8")
    stderr.write_text("synthetic stderr", encoding="utf-8")
    _write_junit(junit, identity)
    before = junit.read_bytes()

    outcome = host._reconcile_junit(
        junit, stdout, stderr, job_id=job_id, scenario="suite",
        selection=host.PROFILE_SELECTION, exit_code=0,
    )

    assert outcome == ("INCOMPLETE", "JUNIT_IDENTITY_MISMATCH")
    assert junit.read_bytes() == before


def _synthetic_worker_canary(
    job_id: str, scenario: str, host_name: str, port: int,
) -> dict[str, object]:
    """Represent a mocked denial without opening a real socket or listener."""
    assert host_name == "127.0.0.1"
    assert type(port) is int and 0 < port < 65536
    try:
        socket.create_connection((host_name, port), timeout=0.1)
    except PermissionError as exc:
        # The test patches create_connection with an in-memory denial fixture.
        exc.winerror = 10013
        return {
            "schema": "s6-v2-loopback-network-canary-v1",
            "job_id": job_id,
            "scenario": scenario,
            "host": host_name,
            "port": port,
            "attempted": True,
            "connected": False,
            "error_class": type(exc).__name__,
            "errno": 13,
            "winerror": 10013,
        }


def test_mocked_loopback_canary_requires_positive_host_control_and_worker_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "4" * 32
    scenario = "suite"
    expected_host = "127.0.0.1"
    expected_port = 43127
    attempted: list[tuple[tuple[str, int], float]] = []

    def denied_loopback_connect(address: tuple[str, int], *, timeout: float) -> object:
        attempted.append((address, timeout))
        denial = PermissionError(13, "synthetic loopback denial")
        denial.winerror = 10013
        raise denial

    monkeypatch.setattr(socket, "create_connection", denied_loopback_connect)
    evidence = _synthetic_worker_canary(job_id, scenario, expected_host, expected_port)
    evidence_path = tmp_path / "network-canary-worker.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    reloaded = json.loads(evidence_path.read_text(encoding="utf-8"))

    outcome = host._reconcile_network_canary(
        reloaded,
        host_control_positive=True,
        worker_connections=0,
        expected_host=expected_host,
        expected_port=expected_port,
        expected_job_id=job_id,
        expected_scenario=scenario,
        listener_clean=True,
    )

    assert outcome == ("PASS", "LOOPBACK_NETWORK_DENIAL_CONFIRMED")
    assert reloaded["host"] == "127.0.0.1"
    assert reloaded["attempted"] is True
    assert reloaded["connected"] is False
    assert reloaded["error_class"] == "PermissionError"
    assert reloaded["errno"] == 13
    assert reloaded["winerror"] == 10013
    assert attempted == [(("127.0.0.1", expected_port), 0.1)]


@pytest.mark.parametrize(
    ("changes", "host_control_positive", "worker_connections", "listener_clean", "expected"),
    [
        ({}, False, 0, True, ("BLOCKED", "NETWORK_CANARY_CONTROL_FAILED")),
        ({}, True, 1, True, ("FAIL", "NETWORK_ISOLATION_VIOLATION")),
        ({}, True, 0, False, ("BLOCKED", "NETWORK_CANARY_LISTENER_UNCONFIRMED")),
        ({"job_id": "5" * 32}, True, 0, True, ("BLOCKED", "NETWORK_CANARY_EVIDENCE_INVALID")),
        ({"connected": True}, True, 0, True, ("FAIL", "NETWORK_ISOLATION_VIOLATION")),
        ({"connected": None}, True, 0, True, ("BLOCKED", "NETWORK_CANARY_OUTCOME_AMBIGUOUS")),
        ({"error_class": "OSError"}, True, 0, True, ("BLOCKED", "NETWORK_CANARY_DENIAL_UNCLASSIFIED")),
    ],
)
def test_mocked_loopback_canary_rejects_missing_or_unsafe_evidence(
    changes: dict[str, object],
    host_control_positive: bool,
    worker_connections: int,
    listener_clean: bool,
    expected: tuple[str, str],
) -> None:
    job_id = "6" * 32
    scenario = "controlled_failure"
    evidence = {
        "schema": "s6-v2-loopback-network-canary-v1",
        "job_id": job_id,
        "scenario": scenario,
        "host": "127.0.0.1",
        "port": 43128,
        "attempted": True,
        "connected": False,
        "error_class": "PermissionError",
        "errno": 13,
        "winerror": 10013,
    }
    evidence.update(changes)

    outcome = host._reconcile_network_canary(
        evidence,
        host_control_positive=host_control_positive,
        worker_connections=worker_connections,
        expected_host="127.0.0.1",
        expected_port=43128,
        expected_job_id=job_id,
        expected_scenario=scenario,
        listener_clean=listener_clean,
    )

    assert outcome == expected


def test_loopback_canary_source_is_pinned_to_localhost_and_never_public_bind() -> None:
    source = inspect.getsource(host.LoopbackNetworkCanary)

    assert 'HOST = "127.0.0.1"' in source
    assert "self.listener.bind((self.HOST, 0))" in source
    assert '"S6_MXC_LOOPBACK_HOST": self.HOST' in source
    assert "0.0.0.0" not in source
    assert "::" not in source


def test_runtime_canary_test_only_validates_atomic_bootstrap_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "8" * 32
    scenario = "suite"
    evidence_path = tmp_path / "network-canary-worker.json"
    evidence = {
        "schema": "s6-v2-loopback-network-canary-v1",
        "host": "127.0.0.1",
        "job_id": job_id,
        "scenario": scenario,
        "port": 43129,
        "attempted": True,
        "connected": False,
        "error_class": "PermissionError",
        "errno": 13,
        "winerror": 10013,
    }
    evidence_path.write_text(json.dumps(evidence, sort_keys=True), encoding="utf-8")
    before = evidence_path.read_bytes()

    monkeypatch.setenv("S6_MXC_LOOPBACK_HOST", "127.0.0.1")
    monkeypatch.setenv("S6_MXC_LOOPBACK_PORT", "43129")
    monkeypatch.setenv("S6_MXC_LOOPBACK_EVIDENCE", str(evidence_path))
    monkeypatch.setenv("S6_MXC_JOB_ID", job_id)
    monkeypatch.setenv("S6_MXC_SCENARIO", scenario)

    def forbidden_retry(*args: object, **kwargs: object) -> object:
        raise AssertionError("bootstrap canary must not be repeated by the test")

    monkeypatch.setattr(socket, "create_connection", forbidden_retry)
    _assert_bootstrap_loopback_canary_evidence()

    assert evidence_path.read_bytes() == before


def _assert_bootstrap_loopback_canary_evidence() -> None:
    """Validate the atomically published bootstrap evidence without retrying its socket call."""
    host_name = os.environ.get("S6_MXC_LOOPBACK_HOST")
    port_text = os.environ.get("S6_MXC_LOOPBACK_PORT")
    evidence_text = os.environ.get("S6_MXC_LOOPBACK_EVIDENCE")
    job_id = os.environ.get("S6_MXC_JOB_ID")
    scenario = os.environ.get("S6_MXC_SCENARIO")
    if not all((host_name, port_text, evidence_text, job_id, scenario)):
        pytest.skip("MXC loopback canary endpoint was not supplied")

    assert host_name == "127.0.0.1"
    assert len(job_id) == 32 and all(character in "0123456789abcdef" for character in job_id)
    assert scenario in host.SCENARIO_ALLOWLIST
    assert port_text.isdecimal()
    port = int(port_text)
    assert 0 < port < 65536
    evidence_path = Path(evidence_text)
    if not evidence_path.is_file():
        pytest.fail("MXC bootstrap canary evidence is missing", pytrace=False)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert type(evidence) is dict
    assert evidence.get("schema") == "s6-v2-loopback-network-canary-v1"
    assert evidence.get("host") == "127.0.0.1"
    assert evidence.get("job_id") == job_id
    assert evidence.get("scenario") == scenario
    assert type(evidence.get("port")) is int and evidence.get("port") == port
    assert evidence.get("attempted") is True
    assert evidence.get("connected") is False
    assert evidence.get("error_class") == "PermissionError"
    assert type(evidence.get("errno")) is int and evidence.get("errno") == 13
    assert type(evidence.get("winerror")) is int and evidence.get("winerror") == 10013


def test_s6_v2_mxc_worker_loopback_canary() -> None:
    """Validate bootstrap's worker canary, without a second attempt or evidence rewrite."""
    _assert_bootstrap_loopback_canary_evidence()


def _active_executor_scenario(expected: str) -> bool:
    return os.environ.get("S6_MXC_SCENARIO") == expected


def test_s6_v2_mxc_synthetic_failure() -> None:
    if not _active_executor_scenario("controlled_failure"):
        return
    _assert_bootstrap_loopback_canary_evidence()
    job_id = os.environ.get("S6_MXC_JOB_ID", "missing-job-id")
    pytest.fail(f"S6_MXC_EXPECTED_CONTROLLED_FAILURE job_id={job_id}", pytrace=False)


_FIXED_SLEEPING_CHILD = "import time; time.sleep(300)"


def _write_pretermination_worker_evidence(
    request: pytest.FixtureRequest, *, job_id: str, scenario: str, child_pid: int,
) -> None:
    junit_arg = request.config.option.xmlpath
    assert junit_arg, "pytest JUnit output path is required for executor scenario"
    junit_path = Path(junit_arg)
    selection = host._scenario_selection(scenario)
    suite = ET.Element("testsuite", {"tests": "1", "failures": "0", "errors": "0", "skipped": "0"})
    testcase = ET.SubElement(
        suite, "testcase", {"classname": "test_s6_v2_mxc_host_executor", "name": selection.rsplit("::", 1)[-1]},
    )
    properties = ET.SubElement(testcase, "properties")
    for name, value in (
        ("s6_job_id", job_id),
        ("s6_scenario", scenario),
        ("s6_selection", selection),
    ):
        ET.SubElement(properties, "property", {"name": name, "value": value})
    ET.SubElement(testcase, "system-out").text = (
        f"S6_EXPECTED_EVENT=child_started;job_id={job_id};scenario={scenario};child_pid={child_pid}"
    )
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    junit_temporary = junit_path.with_name(junit_path.name + ".worker.tmp")
    junit_temporary.write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))
    junit_temporary.replace(junit_path)

    event_path = junit_path.with_name("scenario-event.json")
    event = {
        "schema": "s6-v2-mxc-scenario-event-v1",
        "job_id": job_id,
        "scenario": scenario,
        "event": "child_started",
        "child_pid": child_pid,
        "started": True,
    }
    event_temporary = event_path.with_name(event_path.name + ".tmp")
    event_temporary.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
    event_temporary.replace(event_path)


@pytest.mark.parametrize("scenario", ["timeout_child", "cancel_child"])
def test_special_scenario_worker_junit_and_event_are_self_identifying(
    tmp_path: Path, scenario: str,
) -> None:
    job_id = "7" * 32
    junit = tmp_path / "junit.xml"
    request = SimpleNamespace(
        config=SimpleNamespace(option=SimpleNamespace(xmlpath=str(junit))),
    )

    _write_pretermination_worker_evidence(
        request, job_id=job_id, scenario=scenario, child_pid=12345,
    )

    root = ET.parse(junit).getroot()
    properties = {
        item.attrib["name"]: item.attrib["value"]
        for item in root.findall("testcase/properties/property")
    }
    expected_selection = host._scenario_selection(scenario)
    event = json.loads((tmp_path / "scenario-event.json").read_text(encoding="utf-8"))
    marker = root.findtext("testcase/system-out")
    junit_before_reconciliation = junit.read_bytes()
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text("", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    reconciled = host._reconcile_junit(
        junit,
        stdout,
        stderr,
        job_id=job_id,
        scenario=scenario,
        selection=expected_selection,
        exit_code=0,
    )
    assert properties == {
        "s6_job_id": job_id,
        "s6_scenario": scenario,
        "s6_selection": expected_selection,
    }
    assert root.attrib == {"tests": "1", "failures": "0", "errors": "0", "skipped": "0"}
    assert host._junit_declared_counts_match(root)
    assert reconciled == ("PASS", "WORKER_PASS_WITH_CANARY")
    assert junit.read_bytes() == junit_before_reconciliation
    assert root.find("testcase").attrib["name"] == expected_selection.rsplit("::", 1)[-1]
    assert marker == f"S6_EXPECTED_EVENT=child_started;job_id={job_id};scenario={scenario};child_pid=12345"
    assert event == {
        "schema": "s6-v2-mxc-scenario-event-v1",
        "job_id": job_id,
        "scenario": scenario,
        "event": "child_started",
        "child_pid": 12345,
        "started": True,
    }


def _run_fixed_sleeping_child_scenario(
    request: pytest.FixtureRequest, expected_scenario: str,
) -> None:
    if not _active_executor_scenario(expected_scenario):
        return
    _assert_bootstrap_loopback_canary_evidence()
    job_id = os.environ.get("S6_MXC_JOB_ID", "")
    assert len(job_id) == 32 and all(character in "0123456789abcdef" for character in job_id)
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", _FIXED_SLEEPING_CHILD],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    try:
        assert child.poll() is None, "fixed sleeping child exited before start evidence"
        _write_pretermination_worker_evidence(
            request, job_id=job_id, scenario=expected_scenario, child_pid=child.pid,
        )
        expires = time.monotonic() + 110.0
        while child.poll() is None and time.monotonic() < expires:
            time.sleep(0.1)
        pytest.fail(f"MXC supervisor did not terminate {expected_scenario} within the fixture bound", pytrace=False)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2.0)


def test_s6_v2_mxc_timeout_child(request: pytest.FixtureRequest) -> None:
    _run_fixed_sleeping_child_scenario(request, "timeout_child")


def test_s6_v2_mxc_cancel_child(request: pytest.FixtureRequest) -> None:
    _run_fixed_sleeping_child_scenario(request, "cancel_child")


def _seed_child_scenario_artifacts(
    tmp_path: Path, *, scenario: str, job_id: str = "9" * 32, child_pid: int = 20202,
) -> tuple[Path, Path, str]:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "junit.xml"
    request = SimpleNamespace(
        config=SimpleNamespace(option=SimpleNamespace(xmlpath=str(junit))),
    )
    _write_pretermination_worker_evidence(
        request, job_id=job_id, scenario=scenario, child_pid=child_pid,
    )
    event = artifacts / "scenario-event.json"
    digest = hashlib.sha256(event.read_bytes()).hexdigest()
    return junit, event, digest


def _reconcile_child(
    junit: Path,
    event: Path,
    *,
    scenario: str,
    job_id: str = "9" * 32,
    child_pid: int = 20202,
    worker_pid: int = 10101,
    process_exit: int | None = 1,
    active_process_count: int | None = 0,
    timed_out: bool | None = None,
    cancel_requested: bool | None = None,
    expected_event_sha256: str | None = None,
    expected_child_pid: int | None = None,
    expected_child_creation_time: int | None = 606060,
) -> tuple[str, str]:
    if timed_out is None:
        timed_out = scenario == "timeout_child"
    if cancel_requested is None:
        cancel_requested = scenario == "cancel_child"
    return host._reconcile_child_scenario(
        junit,
        event,
        job_id=job_id,
        scenario=scenario,
        selection=host._scenario_selection(scenario),
        process_exit=process_exit,
        active_process_count=active_process_count,
        worker_pid=worker_pid,
        timed_out=timed_out,
        cancel_requested=cancel_requested,
        expected_event_sha256=expected_event_sha256,
        expected_child_pid=expected_child_pid,
        expected_child_creation_time=expected_child_creation_time,
    )


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("timeout_child", ("TIMED_OUT", "EXPECTED_TIMEOUT_CHILD_REAPED")),
        ("cancel_child", ("CANCELLED", "EXPECTED_CANCEL_CHILD_REAPED")),
    ],
)
def test_child_scenario_reconciler_accepts_only_expected_supervisor_outcome(
    tmp_path: Path, scenario: str, expected: tuple[str, str],
) -> None:
    job_id = "9" * 32
    child_pid = 20202
    junit, event, digest = _seed_child_scenario_artifacts(
        tmp_path, scenario=scenario, job_id=job_id, child_pid=child_pid,
    )

    accepted = _reconcile_child(
        junit, event, scenario=scenario, job_id=job_id, child_pid=child_pid,
        expected_event_sha256=digest, expected_child_pid=child_pid,
        expected_child_creation_time=606060,
    )
    active_tree = _reconcile_child(
        junit, event, scenario=scenario, job_id=job_id, child_pid=child_pid,
        active_process_count=1, expected_event_sha256=digest, expected_child_pid=child_pid,
        expected_child_creation_time=606060,
    )
    child_still_active = _reconcile_child(
        junit, event, scenario=scenario, job_id=job_id, child_pid=child_pid,
        active_process_count=2, expected_event_sha256=digest, expected_child_pid=child_pid,
        expected_child_creation_time=606060,
    )
    no_exit = _reconcile_child(
        junit, event, scenario=scenario, job_id=job_id, child_pid=child_pid,
        process_exit=None, expected_event_sha256=digest, expected_child_pid=child_pid,
        expected_child_creation_time=606060,
    )

    assert accepted == expected
    assert active_tree == ("BLOCKED", "CHILD_PROCESS_TREE_UNCONFIRMED")
    assert child_still_active == ("BLOCKED", "CHILD_PROCESS_TREE_UNCONFIRMED")
    assert no_exit == ("BLOCKED", "CHILD_PROCESS_TREE_UNCONFIRMED")


@pytest.mark.parametrize(
    ("scenario", "timed_out", "cancel_requested", "expected"),
    [
        ("timeout_child", False, False, ("BLOCKED", "CHILD_SCENARIO_TIMEOUT_NOT_OBSERVED")),
        ("timeout_child", True, True, ("BLOCKED", "CHILD_SCENARIO_TIMEOUT_NOT_OBSERVED")),
        ("cancel_child", False, False, ("BLOCKED", "CHILD_SCENARIO_CANCEL_NOT_OBSERVED")),
        ("cancel_child", True, True, ("BLOCKED", "CHILD_SCENARIO_CANCEL_NOT_OBSERVED")),
    ],
)
def test_child_scenario_reconciler_rejects_wrong_supervisor_flags(
    tmp_path: Path,
    scenario: str,
    timed_out: bool,
    cancel_requested: bool,
    expected: tuple[str, str],
) -> None:
    job_id = "a" * 32
    child_pid = 30303
    junit, event, digest = _seed_child_scenario_artifacts(
        tmp_path, scenario=scenario, job_id=job_id, child_pid=child_pid,
    )

    outcome = _reconcile_child(
        junit,
        event,
        scenario=scenario,
        job_id=job_id,
        child_pid=child_pid,
        timed_out=timed_out,
        cancel_requested=cancel_requested,
        expected_event_sha256=digest,
        expected_child_pid=child_pid,
        expected_child_creation_time=606060,
    )

    assert outcome == expected


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("missing", ("BLOCKED", "CHILD_SCENARIO_EVENT_MISSING")),
        ("job_identity", ("BLOCKED", "CHILD_SCENARIO_EVENT_IDENTITY_MISMATCH")),
        ("scenario_identity", ("BLOCKED", "CHILD_SCENARIO_EVENT_IDENTITY_MISMATCH")),
        ("event_hash", ("BLOCKED", "CHILD_SCENARIO_EVENT_HASH_MISMATCH")),
        ("child_pid", ("BLOCKED", "CHILD_SCENARIO_EVENT_IDENTITY_MISMATCH")),
        ("worker_pid", ("BLOCKED", "CHILD_SCENARIO_EVENT_IDENTITY_MISMATCH")),
        ("cancel_unobserved", ("BLOCKED", "CHILD_JOB_MEMBERSHIP_NOT_OBSERVED")),
        ("creation_time_missing", ("BLOCKED", "CHILD_JOB_MEMBERSHIP_NOT_OBSERVED")),
        ("junit_identity", ("BLOCKED", "CHILD_SCENARIO_JUNIT_IDENTITY_MISMATCH")),
        ("junit_event", ("BLOCKED", "CHILD_SCENARIO_JUNIT_EVENT_MISMATCH")),
    ],
)
def test_child_scenario_reconciler_rejects_missing_or_conflicting_identity(
    tmp_path: Path, mutation: str, expected: tuple[str, str],
) -> None:
    job_id = "b" * 32
    child_pid = 40404
    junit, event_path, digest = _seed_child_scenario_artifacts(
        tmp_path, scenario="cancel_child", job_id=job_id, child_pid=child_pid,
    )
    kwargs: dict[str, object] = {
        "scenario": "cancel_child",
        "job_id": job_id,
        "child_pid": child_pid,
        "expected_event_sha256": digest,
        "expected_child_pid": child_pid,
        "expected_child_creation_time": 606060,
    }
    if mutation == "missing":
        event_path.unlink()
    elif mutation in {"job_identity", "scenario_identity", "child_pid"}:
        event = json.loads(event_path.read_text(encoding="utf-8"))
        if mutation == "job_identity":
            event["job_id"] = "c" * 32
        elif mutation == "scenario_identity":
            event["scenario"] = "timeout_child"
        else:
            event["child_pid"] = child_pid + 1
        event_path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
        kwargs["expected_event_sha256"] = hashlib.sha256(event_path.read_bytes()).hexdigest()
    elif mutation == "event_hash":
        kwargs["expected_event_sha256"] = "0" * 64
    elif mutation == "worker_pid":
        kwargs["worker_pid"] = child_pid
    elif mutation == "cancel_unobserved":
        kwargs["expected_event_sha256"] = None
    elif mutation == "creation_time_missing":
        kwargs["expected_child_creation_time"] = None
    elif mutation in {"junit_identity", "junit_event"}:
        root = ET.parse(junit).getroot()
        if mutation == "junit_identity":
            root.find("testcase/properties/property[@name='s6_job_id']").set("value", "c" * 32)
        else:
            root.find("testcase/system-out").text = "S6_EXPECTED_EVENT=wrong"
        junit.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))

    outcome = _reconcile_child(junit, event_path, **kwargs)

    assert outcome == expected


@pytest.mark.parametrize(
    ("active_count", "job_pids", "child_creation_times", "worker_pid", "worker_verified", "expected_stage"),
    [
        (3, {70707, 70708, 80808}, [606060, 606060], 70708, True, "RUNNING"),  # count >= 3, child absent
        (2, {70707, 70708, 60606}, [606060, 606060], 70708, True, "RUNNING"),  # insufficient count
        (3, {70707, 70708, 60606}, [606060, 606060], 70708, True, "CHILD_STARTED"),
        (3, {70707, 70708, 60606}, [606060, 606061], 70708, True, "RUNNING"),  # child FILETIME changed
        (3, {70707, 70708, 60606}, [None, None], 70708, True, "RUNNING"),
        (3, {70707, 60606, 80808}, [202020, 202020], 60606, True, "RUNNING"),  # event PID aliases worker
        (3, {70707, 70708, 60606}, [606060, 606060], 70708, False, "RUNNING"),  # worker not confirmed
    ],
)
def test_status_marks_child_started_only_after_job_object_confirms_child_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    active_count: int,
    job_pids: set[int],
    child_creation_times: list[int | None],
    worker_pid: int,
    worker_verified: bool,
    expected_stage: str,
) -> None:
    job_id = "d" * 32
    event_child_pid = 60606
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    event_path = artifacts / "scenario-event.json"
    event_path.write_text(json.dumps({
        "schema": "s6-v2-mxc-scenario-event-v1",
        "job_id": job_id,
        "scenario": "timeout_child",
        "event": "child_started",
        "child_pid": event_child_pid,
        "started": True,
    }, sort_keys=True), encoding="utf-8")
    executor = host.HostExecutor(tmp_path)
    job = _seed_job(
        executor, job_id, state="RUNNING", scenario="timeout_child", run_root=str(tmp_path),
    )
    job.process = SimpleNamespace(pid=70707, poll=lambda: None)
    job.os_job_handle = object()
    job.job_api = (object(), object(), object())
    job.worker_pid = worker_pid
    job.worker_creation_time = 707080
    job.worker_membership_verified = worker_verified
    calls: list[str] = []
    child_creation_values = iter(child_creation_times)

    def synthetic_creation_time(pid: int) -> int | None:
        calls.append(str(pid))
        if pid == job.process.pid:
            return 707070
        if pid == job.worker_pid:
            return job.worker_creation_time
        if pid == event_child_pid:
            return next(child_creation_values)
        return 808080

    def synthetic_job_pids(query: object, handle: object) -> set[int]:
        assert handle is job.os_job_handle
        calls.append("pid_list")
        return job_pids

    monkeypatch.setattr(host, "_active_process_count", lambda query, handle: active_count)
    monkeypatch.setattr(host, "_job_process_ids", synthetic_job_pids)
    monkeypatch.setattr(host, "_process_creation_time", synthetic_creation_time)

    response = executor.handle(host.parse_request(_request("status", "child-status", job_id=job_id)))

    assert response["stage"] == expected_stage
    if expected_stage == "CHILD_STARTED":
        assert response["child_pid"] == event_child_pid
        assert response["child_creation_time"] == 606060
        assert response["scenario_event_sha256"] == hashlib.sha256(event_path.read_bytes()).hexdigest()
        assert calls == ["70707", "70708", "60606", "pid_list", "70707", "70708", "60606"]
    else:
        assert response["child_pid"] is None
        assert response["child_creation_time"] is None
        assert response["scenario_event_sha256"] is None


def test_cancel_child_requires_status_observation_of_child_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "e" * 32
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "scenario-event.json").write_text(json.dumps({
        "schema": "s6-v2-mxc-scenario-event-v1",
        "job_id": job_id,
        "scenario": "cancel_child",
        "event": "child_started",
        "child_pid": 80808,
        "started": True,
    }, sort_keys=True), encoding="utf-8")
    executor = host.HostExecutor(tmp_path)
    job = _seed_job(
        executor, job_id, state="RUNNING", scenario="cancel_child", run_root=str(tmp_path),
    )
    job.process = SimpleNamespace(pid=90909, poll=lambda: None)
    job.os_job_handle = object()
    job.job_api = (object(), object(), object())
    job.worker_pid = 90908
    job.worker_creation_time = 909080
    job.worker_membership_verified = True
    job_pids = {90909, 90908}
    monkeypatch.setattr(host, "_active_process_count", lambda query, handle: len(job_pids))
    monkeypatch.setattr(host, "_job_process_ids", lambda query, handle: set(job_pids))
    creation_times = {90909: 909090, 90908: 909080, 80808: 808080}
    monkeypatch.setattr(host, "_process_creation_time", lambda pid: creation_times.get(pid))

    rejected = executor.handle(host.parse_request(_request("cancel", "cancel-too-early", job_id=job_id)))
    job_pids.add(80808)
    observed = executor.handle(host.parse_request(_request("status", "status-child", job_id=job_id)))
    job_pids.remove(80808)
    stale_rejected = executor.handle(host.parse_request(_request("cancel", "cancel-stale-status", job_id=job_id)))
    job_pids.add(80808)
    observed_again = executor.handle(host.parse_request(_request("status", "status-child-again", job_id=job_id)))
    accepted = executor.handle(host.parse_request(_request("cancel", "cancel-after-status", job_id=job_id)))

    assert rejected["ok"] is False
    assert rejected["error"] == "CANCEL_REQUIRES_OBSERVED_CHILD_STARTED"
    assert observed["stage"] == "CHILD_STARTED"
    assert observed["child_creation_time"] == 808080
    assert observed["scenario_event_sha256"] is not None
    assert stale_rejected["ok"] is False
    assert stale_rejected["error"] == "CANCEL_REQUIRES_OBSERVED_CHILD_STARTED"
    assert observed_again["stage"] == "CHILD_STARTED"
    assert accepted["ok"] is True
    assert accepted["state"] == "CANCELLING"


def test_status_does_not_promote_child_without_a_job_object_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "1" * 32
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "scenario-event.json").write_text(json.dumps({
        "schema": "s6-v2-mxc-scenario-event-v1",
        "job_id": job_id,
        "scenario": "timeout_child",
        "event": "child_started",
        "child_pid": 10102,
        "started": True,
    }, sort_keys=True), encoding="utf-8")
    executor = host.HostExecutor(tmp_path)
    job = _seed_job(
        executor, job_id, state="RUNNING", scenario="timeout_child", run_root=str(tmp_path),
    )
    job.process = SimpleNamespace(pid=10101, poll=lambda: None)
    job.os_job_handle = None
    job.job_api = (object(), object(), object())
    job.worker_pid = 10103
    job.worker_creation_time = 101030
    job.worker_membership_verified = True
    monkeypatch.setattr(host, "_active_process_count", lambda query, handle: 2)

    response = executor.handle(host.parse_request(_request("status", "child-no-job-object", job_id=job_id)))

    assert response["stage"] == "RUNNING"
    assert response["child_pid"] is None
    assert response["scenario_event_sha256"] is None


def test_controlled_failure_reconciler_accepts_only_exact_marked_failure(tmp_path: Path) -> None:
    job_id = "f" * 32
    scenario = "controlled_failure"
    selection = host._scenario_selection(scenario)
    junit = tmp_path / "controlled-failure.xml"
    suite = ET.Element("testsuite", {"tests": "1", "failures": "1", "errors": "0", "skipped": "0"})
    testcase = ET.SubElement(
        suite, "testcase", {"classname": "test_s6_v2_mxc_host_executor", "name": selection.rsplit("::", 1)[-1]},
    )
    properties = ET.SubElement(testcase, "properties")
    for name, value in (("s6_job_id", job_id), ("s6_scenario", scenario), ("s6_selection", selection)):
        ET.SubElement(properties, "property", {"name": name, "value": value})
    ET.SubElement(testcase, "failure", {
        "message": f"S6_MXC_EXPECTED_CONTROLLED_FAILURE job_id={job_id}",
    }).text = "synthetic expected failure"
    junit.write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))

    accepted = host._reconcile_controlled_failure(
        junit, job_id=job_id, scenario=scenario, selection=selection, exit_code=1,
    )
    wrong_exit = host._reconcile_controlled_failure(
        junit, job_id=job_id, scenario=scenario, selection=selection, exit_code=0,
    )
    wrong_marker = junit.read_bytes().replace(job_id.encode(), b"0" * 32)
    junit.write_bytes(wrong_marker)
    wrong_identity_marker = host._reconcile_controlled_failure(
        junit, job_id=job_id, scenario=scenario, selection=selection, exit_code=1,
    )

    assert accepted == ("FAIL", "EXPECTED_CONTROLLED_FAILURE")
    assert wrong_exit == ("BLOCKED", "CONTROLLED_FAILURE_OUTCOME_UNEXPECTED")
    assert wrong_identity_marker == ("BLOCKED", "CONTROLLED_FAILURE_JUNIT_FAILURE_MISMATCH")


def test_cancel_reconciliation_succeeds_after_reap_but_finalization_obeys_hard_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "2" * 32
    child_pid = 22222
    junit, event, digest = _seed_child_scenario_artifacts(
        tmp_path, scenario="cancel_child", job_id=job_id, child_pid=child_pid,
    )
    cancelled = _reconcile_child(
        junit,
        event,
        scenario="cancel_child",
        job_id=job_id,
        child_pid=child_pid,
        process_exit=3,
        active_process_count=0,
        timed_out=False,
        cancel_requested=True,
        expected_event_sha256=digest,
        expected_child_pid=child_pid,
        expected_child_creation_time=606060,
    )
    digest_path = tmp_path / "post-cancel-manifest"
    digest_path.write_bytes(b"synthetic finalized input")
    deadline = 500.0
    monkeypatch.setattr(host, "time", SimpleNamespace(monotonic=lambda: deadline - 0.001))

    assert cancelled == ("CANCELLED", "EXPECTED_CANCEL_CHILD_REAPED")
    assert host._sha256(
        digest_path, deadline=deadline, cancelled=lambda: True, finalizing=True,
    ) == hashlib.sha256(digest_path.read_bytes()).hexdigest()

    monkeypatch.setattr(host, "time", SimpleNamespace(monotonic=lambda: deadline))
    with pytest.raises(host.ProtocolError, match="HARD_DEADLINE_EXCEEDED_DURING_FINALIZATION"):
        host._check_finalization_budget(deadline)
    with pytest.raises(host.ProtocolError, match="HARD_DEADLINE_EXCEEDED_DURING_FINALIZATION"):
        host._sha256(digest_path, deadline=deadline, cancelled=lambda: True, finalizing=True)


def test_child_reconciliation_uses_confirmed_worker_pid_not_codex_launcher_pid(
    tmp_path: Path,
) -> None:
    job_id = "3" * 32
    launcher_pid = 31313
    worker_pid = 41414
    junit, event, digest = _seed_child_scenario_artifacts(
        tmp_path, scenario="cancel_child", job_id=job_id, child_pid=launcher_pid,
    )
    outcome = _reconcile_child(
        junit,
        event,
        scenario="cancel_child",
        job_id=job_id,
        child_pid=launcher_pid,
        worker_pid=worker_pid,
        process_exit=3,
        active_process_count=0,
        timed_out=False,
        cancel_requested=True,
        expected_event_sha256=digest,
        expected_child_pid=launcher_pid,
        expected_child_creation_time=313131,
    )
    if_process_pid_was_misused = _reconcile_child(
        junit,
        event,
        scenario="cancel_child",
        job_id=job_id,
        child_pid=launcher_pid,
        worker_pid=launcher_pid,
        process_exit=3,
        active_process_count=0,
        timed_out=False,
        cancel_requested=True,
        expected_event_sha256=digest,
        expected_child_pid=launcher_pid,
        expected_child_creation_time=313131,
    )
    callsite = inspect.getsource(host.HostExecutor._run_job)

    assert outcome == ("CANCELLED", "EXPECTED_CANCEL_CHILD_REAPED")
    assert if_process_pid_was_misused == ("BLOCKED", "CHILD_SCENARIO_EVENT_IDENTITY_MISMATCH")
    assert "worker_pid=job.worker_pid" in callsite
    assert "worker_pid=process.pid" not in callsite
