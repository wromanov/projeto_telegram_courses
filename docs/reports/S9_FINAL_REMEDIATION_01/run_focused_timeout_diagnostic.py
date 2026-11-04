from __future__ import annotations

import json
import os
import re
import sys
import uuid
import argparse
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = Path(__file__).resolve().parent
TEST_FILES = [
    "tests/integration/test_s9_queue_flow.py",
    "tests/unit/test_s9_gate_reconciliation.py",
    "tests/unit/test_s9_operational_ledger.py",
    "tests/unit/test_s9_queue_integration.py",
    "tests/unit/test_s9_supervisor_cli.py",
    "tests/unit/test_s9_supervisor_handshake.py",
    "tests/unit/test_s9_supervisor.py",
]


def _private_directory(path: Path) -> Path:
    from telegram_courses.s9_operational_ledger import (
        _create_private_directory,
        _open_private_directory_guard,
    )

    guard = (
        _open_private_directory_guard(path)
        if path.exists()
        else _create_private_directory(path)
    )
    resolved = guard.path
    guard.close()
    return resolved


def main() -> int:
    if os.name != "nt":
        raise SystemExit("WINDOWS_NATIVE_DIAGNOSTIC_REQUIRED")

    sys.path.insert(0, str(ROOT / "src"))
    from telegram_courses.s9_operational_ledger import S9OperationalLedger
    from telegram_courses.s9_supervisor import WindowsCliSupervisor

    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("tests", nargs="*")
    args = parser.parse_args()
    selected_tests = args.tests or TEST_FILES
    if not 1 <= args.timeout_seconds <= 45:
        raise SystemExit("DIAGNOSTIC_TIMEOUT_MUST_BE_BETWEEN_1_AND_45_SECONDS")

    selected_files = [argument.split("::", maxsplit=1)[0] for argument in selected_tests]
    if any(relative not in TEST_FILES for relative in selected_files):
        raise SystemExit("TEST_SELECTION_OUTSIDE_FOCUSED_S9_ALLOWLIST")

    for relative in selected_files:
        if "manual_proofs" in Path(relative).parts or not (ROOT / relative).is_file():
            raise SystemExit(f"UNSAFE_OR_MISSING_TEST_SELECTION:{relative}")

    direct_client = re.compile(r"\bTelegramClient\s*\(")
    gateway_ctor = re.compile(r"\bTelethonGateway\s*\(")
    constructor_files: list[Path] = []
    for relative in selected_files:
        path = ROOT / relative
        source = path.read_text(encoding="utf-8")
        if direct_client.search(source):
            raise SystemExit(f"DIRECT_TELEGRAM_CLIENT_CONSTRUCTION:{relative}")
        if gateway_ctor.search(source):
            constructor_files.append(path)
            if not re.search(r"\bclient_factory\s*=", source):
                raise SystemExit(f"GATEWAY_FACTORY_NOT_INJECTED:{relative}")

    run_id = uuid.uuid4().hex[:8]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = REPORT_DIR / f"timeout-diagnostic-{stamp}-{run_id}"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    temporary_dir = evidence_dir / "temp"
    basetemp_dir = evidence_dir / "pytest-basetemp"
    temporary_dir.mkdir()
    basetemp_dir.mkdir()
    private_dir = _private_directory(evidence_dir / "supervisor-private")

    events_path = evidence_dir / "pytest-events.jsonl"
    environment = os.environ.copy()
    environment["TEMP"] = str(temporary_dir)
    environment["TMP"] = str(temporary_dir)
    environment["S9_DIAGNOSTIC_EVENTS"] = str(events_path)
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(evidence_dir), environment.get("PYTHONPATH", "")) if part
    )
    environment["PYTHONUNBUFFERED"] = "1"

    command = [
        sys.executable,
        "-u",
        str(REPORT_DIR / "run_pytest_progress.py"),
        "-vv",
        "-s",
        "--disable-warnings",
        "--basetemp",
        str(basetemp_dir),
        "-o",
        "faulthandler_timeout=5",
        *selected_tests,
    ]

    ledger = S9OperationalLedger.create(private_dir / "supervisor-ledger.sqlite3")
    ledger_snapshot = ledger.snapshot()
    supervisor = WindowsCliSupervisor(
        receipt_path=private_dir / "receipt.json",
        require_tty=False,
        critical_audit_writer=ledger.record_critical_event,
        ledger_run_id=ledger_snapshot["run"]["run_id"],
        cooperative_cancel_seconds=0.1,
        tree_containment_seconds=5.0,
    )

    print(f"TIMEOUT_DIAGNOSTIC_EVIDENCE={evidence_dir}", flush=True)
    print(f"TEMP_ISOLATED={temporary_dir}", flush=True)
    print("PYTEST_MODE=VERBOSE_PROGRESS / FOCUSED_S9_ONLY / OFFLINE_GATEWAYS", flush=True)
    print(
        f"EXTERNAL_TIMEOUT_SECONDS={args.timeout_seconds} / WINDOWS_JOB_OBJECT=REQUIRED",
        flush=True,
    )
    result = supervisor.run(
        command,
        stage="scan",
        timeout_seconds=args.timeout_seconds,
        cwd=ROOT,
        environment=environment,
    )

    summary = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "python_version": sys.version,
        "pytest_command": [
            "python", "-u", "run_pytest_progress.py", "-vv", "-s"
        ],
        "selected_tests": selected_tests,
        "direct_telegram_client_constructions": 0,
        "telethon_gateway_constructor_files": [
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in constructor_files
        ],
        "temp_directory": str(temporary_dir),
        "pytest_basetemp_directory": str(basetemp_dir),
        "timeout_seconds": args.timeout_seconds,
        "supervisor_result": result.result,
        "supervisor_reason": result.reason,
        "pytest_exit_code": result.exit_code,
        "process_tree_termination_confirmed": result.receipt_persisted
        and json.loads(result.receipt_path.read_text(encoding="utf-8")).get(
            "process_tree_termination_confirmed"
        )
        is True,
        "receipt_path": str(result.receipt_path),
        "progress_events_path": str(events_path),
    }
    (evidence_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"SUPERVISOR_RESULT={result.result}", flush=True)
    print(f"SUPERVISOR_REASON={result.reason}", flush=True)
    print(f"PYTEST_EXIT_CODE={result.exit_code}", flush=True)
    print(f"PROCESS_TREE_TERMINATION_CONFIRMED={summary['process_tree_termination_confirmed']}", flush=True)
    print(f"SUMMARY={evidence_dir / 'summary.json'}", flush=True)
    return 0 if result.result == "COMPLETED" and result.exit_code == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
