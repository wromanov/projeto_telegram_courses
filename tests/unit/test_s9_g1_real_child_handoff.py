from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from telegram_courses.s9_operational_ledger import (
    S9OperationalLedger,
    _create_private_directory,
)
from telegram_courses.s9_supervisor import _creation_time, _windows_api
from telegram_courses.s9_supervisor_cli import (
    OfflineRunnerError,
    _trusted_python_command,
)


@pytest.mark.skipif(os.name != "nt", reason="Windows interpreter isolation test")
def test_direct_interpreter_preserves_venv_and_excludes_base_site(
    tmp_path: Path,
) -> None:
    script = """
import os, sys
from pathlib import Path
import telethon
import telegram_courses.s9_real_gate_producers as producer
assert os.path.normcase(os.path.realpath(sys.prefix)) == os.path.normcase(os.path.realpath(sys.argv[1]))
assert os.path.normcase(os.path.realpath(producer.__file__)) == os.path.normcase(os.path.realpath(sys.argv[2]))
base_site = os.path.normcase(os.path.realpath(str(Path(sys.base_prefix) / 'Lib' / 'site-packages')))
assert all(os.path.normcase(os.path.realpath(path)) != base_site for path in sys.path)
print('ISOLATION=PASS')
"""
    from telegram_courses import s9_real_gate_producers

    result = subprocess.run(
        [*_trusted_python_command(script), sys.prefix, s9_real_gate_producers.__file__],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ISOLATION=PASS"


@pytest.mark.skipif(os.name != "nt", reason="Windows interpreter isolation test")
def test_direct_interpreter_rejects_site_outside_venv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import telegram_courses.s9_supervisor_cli as supervisor

    if sys.prefix == sys.base_prefix:
        pytest.skip("Requires a virtual environment")
    monkeypatch.setattr(supervisor.sysconfig, "get_path", lambda _name: str(tmp_path))
    with pytest.raises(OfflineRunnerError, match="TRUSTED_PYTHON_ENVIRONMENT_INVALID"):
        _trusted_python_command("pass")


@pytest.mark.skipif(os.name != "nt", reason="Windows process identity test")
@pytest.mark.parametrize("mode", ["launcher", "direct", "direct_wrong_identity"])
def test_child_handoff_matches_supervised_interpreter(
    tmp_path: Path,
    mode: str,
) -> None:
    direct_interpreter = mode != "launcher"
    guard = _create_private_directory(tmp_path / "run")
    run = guard.path
    guard.close()
    ledger_path = run / "operational-ledger.sqlite3"
    ledger = S9OperationalLedger.create(ledger_path)
    deadline = ledger.start_global_deadline()
    ledger.update_execution(
        gate="G1",
        status="RUNNING",
        elapsed_ms=0,
        deadline_ns=deadline,
        process_state="RUNNING",
        result="UNKNOWN",
    )
    child_source = """
import json, os, sys
import telethon
from telegram_courses.s9_supervisor import _windows_api, _creation_time
from telegram_courses.s9_operational_ledger import S9OperationalLedger, LedgerError
api = _windows_api()
pid = os.getpid()
created = _creation_time(api[13], api[14], api[6], pid)
print(json.dumps({"pid": pid, "created": created}), flush=True)
sys.stdin.readline()
try:
    ledger = S9OperationalLedger(sys.argv[1])
    print("ADMISSION=PASS", flush=True)
    ledger.close()
except LedgerError as error:
    print("ADMISSION=" + str(error), flush=True)
    raise SystemExit(4)
"""
    env = os.environ.copy()
    env.update(
        {
            "TELEGRAM_COURSES_S9_SUPERVISED_CHILD": "1",
            "TELEGRAM_COURSES_S9_LEDGER_PATH": str(ledger_path),
            "TELEGRAM_COURSES_S9_STAGE": "discovery",
        }
    )
    command = (
        _trusted_python_command(child_source)
        if direct_interpreter
        else [sys.executable, "-I", "-c", child_source]
    )
    child = subprocess.Popen(
        [*command, str(ledger_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        assert child.stdout is not None and child.stdin is not None
        identity = json.loads(child.stdout.readline())
        if not direct_interpreter and identity["pid"] == child.pid:
            pytest.skip("This Python venv uses no launcher process")
        assert (identity["pid"] == child.pid) is direct_interpreter
        api = _windows_api()
        confirmed_pid = os.getpid() if mode == "direct_wrong_identity" else child.pid
        launcher_created = _creation_time(api[13], api[14], api[6], confirmed_pid)
        ledger.record_critical_event(
            "CHILD_PROCESS_CONFIRMED",
            details={
                "stage": "discovery",
                "pid": confirmed_pid,
                "process_creation_time": launcher_created,
            },
            event_id="a" * 32,
        )
        ledger.release_writer_ownership()
        stdout, stderr = child.communicate("continue\n", timeout=30)
        admitted = mode == "direct"
        assert child.returncode == (0 if admitted else 4), (stdout, stderr)
        assert (
            "ADMISSION=PASS" if admitted else "ADMISSION=LEDGER_CHILD_IDENTITY_INVALID"
        ) in stdout
        ledger.reacquire_writer_ownership()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        ledger.close()
