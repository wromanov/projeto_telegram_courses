"""Offline-only pytest worker for the S6 V2 regression gate.

The PowerShell launcher is the external wall-clock supervisor. This process
owns pytest, faulthandler, collection validation, and the durable receipt.
"""

from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

PROFILE_SETTINGS = {
    "Affected": {
        "deadline_seconds": 25,
        "dump_seconds": 12,
        "node": (
            "tests/manual_proofs/test_s6_v2_proof_harness.py::"
            "test_unaligned_preparation_uses_controlled_application_stream_and_reconciles_wire"
        ),
        "expected_tests": 1,
    },
    "Harness": {
        "deadline_seconds": 150,
        "dump_seconds": 120,
        "node": "tests/manual_proofs/test_s6_v2_proof_harness.py",
        "expected_tests": None,
    },
}
SANDBOX_SIGNATURE = r"AppData[\\/]+Local[\\/]+Packages[\\/]+sandbox\."
MAX_BASETEMP_PATH_CHARS = 80
MAX_OBSERVED_DERIVED_PART_PATH_CHARS = 231
MAX_DERIVED_PATH_GUARD_CHARS = 240
PYTEST_PLUGIN_MODULE = "tools.manual_proofs.s6_v2_offline_regression_runner"
PYTEST_PROFILE_ENV = "S6_OFFLINE_REGRESSION_PROFILE"
PYTEST_METADATA_ENV = "S6_OFFLINE_REGRESSION_METADATA"
_pytest_collected_nodeids: list[str] = []
_pytest_reported_nodeids: set[str] = set()
_pytest_xfailed = 0
_pytest_xpassed = 0


@dataclass(frozen=True)
class RunSpec:
    """Immutable description of one allowlisted offline regression run."""

    run_id: str
    profile: str
    manifest_sha256: str
    python: str
    powershell: str
    cwd: str
    run_dir: str
    basetemp: str
    junit: str
    selection: str
    diagnostic_seconds: int
    hard_deadline_seconds: int
    environment_sha256: str
    isolation: str

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _input_snapshot(repo_root: Path) -> dict[str, str]:
    paths = (
        "tools/manual_proofs/s6_v2_offline_regression_runner.py",
        "tools/manual_proofs/s6_v2_proof_harness.py",
        "tools/manual_proofs/Invoke-S6V2OfflineRegression.ps1",
        "tests/manual_proofs/test_s6_v2_offline_regression_runner.py",
        "tests/manual_proofs/test_s6_v2_proof_harness.py",
    )
    snapshot = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("RUN_SPEC_INPUT_MISSING_OR_UNSAFE")
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _environment_digest(environment: dict[str, str]) -> str:
    payload = json.dumps(sorted(environment.items()), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8", errors="surrogatepass")).hexdigest()


def build_run_spec(
    *, repo_root: Path, run_id: str, profile: str, python: Path,
    run_dir: Path, basetemp: Path, junit_path: Path, environment: dict[str, str],
    powershell_version: str = "not-observed",
) -> tuple[RunSpec, dict[str, str]]:
    if profile not in PROFILE_SETTINGS or re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
        raise ValueError("RUN_SPEC_PROFILE_OR_ID_INVALID")
    snapshot = _input_snapshot(repo_root)
    manifest_payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    settings = PROFILE_SETTINGS[profile]
    spec = RunSpec(
        run_id=run_id,
        profile=profile,
        manifest_sha256=hashlib.sha256(manifest_payload.encode("utf-8")).hexdigest(),
        python=str(python),
        powershell=powershell_version,
        cwd=str(repo_root),
        run_dir=str(run_dir),
        basetemp=str(basetemp),
        junit=str(junit_path),
        selection=str(settings["node"]),
        diagnostic_seconds=int(settings["dump_seconds"]),
        hard_deadline_seconds=int(settings["deadline_seconds"]),
        environment_sha256=_environment_digest(environment),
        isolation="SANDBOX_ADMISSION_FAIL_CLOSED;TREE_BOUNDARY_UNPROVEN",
    )
    return spec, snapshot


def is_sandbox_environment(environment: dict[str, str] | os._Environ[str]) -> bool:
    import re

    signature = re.compile(SANDBOX_SIGNATURE, re.IGNORECASE)
    return any(signature.search(environment.get(name, "")) for name in ("TEMP", "LOCALAPPDATA"))


def summarize_junit(path: Path) -> dict[str, int] | None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        return None
    return {
        "tests": sum(int(suite.attrib.get("tests", 0)) for suite in suites),
        "passed": sum(
            int(suite.attrib.get("tests", 0))
            - int(suite.attrib.get("failures", 0))
            - int(suite.attrib.get("errors", 0))
            - int(suite.attrib.get("skipped", 0))
            for suite in suites
        ),
        "failed": sum(
            int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0))
            for suite in suites
        ),
        "skipped": sum(int(suite.attrib.get("skipped", 0)) for suite in suites),
        "xfail": 0,
    }


def terminate_process_tree(process: subprocess.Popen[bytes]) -> bool:
    """Request tree termination but never infer a tree boundary from root exit."""
    deadline = time.monotonic() + 5.0
    if os.name == "nt" and process.poll() is None:
        tree_kill_succeeded = False
        try:
            result = subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(0.001, deadline - time.monotonic()),
                check=False,
            )
            tree_kill_succeeded = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            tree_kill_succeeded = False
        if not tree_kill_succeeded:
            try:
                if process.poll() is None:
                    process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
            return False
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            return False
        # taskkill /T plus root exit does not prove that every descendant exited.
        # Until this runner owns a verified non-breakaway Job Object, fail closed.
        return False

    if os.name != "nt":
        try:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except (OSError, subprocess.TimeoutExpired):
            pass
        # Root exit on its own does not prove that descendants were terminated.
        return False
    return False


def timeout_outcome(termination_confirmed: bool) -> tuple[str, str, int]:
    if termination_confirmed:
        return "INCOMPLETE", "WORKER_TIMEOUT", 4
    return "BLOCKED", "PROCESS_EXIT_UNCONFIRMED", 3


def supervise_process(
    command: list[str],
    *,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float,
    env: dict[str, str] | None = None,
    popen=subprocess.Popen,
    terminate_tree=terminate_process_tree,
) -> dict[str, object]:
    """Run an offline child with file-backed streams and a bounded kill grace."""
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    start = time.monotonic()
    with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
        try:
            process = popen(
                command,
                cwd=cwd,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                creationflags=flags,
            )
        except OSError as exc:
            return {
                "pid": None,
                "exit_code": None,
                "timed_out": False,
                "termination_confirmed": False,
                "elapsed_seconds": time.monotonic() - start,
                "launch_error": type(exc).__name__,
            }
        try:
            exit_code = process.wait(timeout=timeout_seconds)
            return {
                "pid": process.pid,
                "exit_code": exit_code,
                "timed_out": False,
                "termination_confirmed": False,
                "tree_boundary_verified": False,
                "elapsed_seconds": time.monotonic() - start,
            }
        except subprocess.TimeoutExpired:
            confirmed = terminate_tree(process)
            return {
                "pid": process.pid,
                "exit_code": process.poll(),
                "timed_out": True,
                "termination_confirmed": confirmed,
                "tree_boundary_verified": False,
                "elapsed_seconds": time.monotonic() - start,
            }


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, indent=2, sort_keys=True))
    os.replace(temporary, path)


def schedule_diagnostic_dump(profile: str, output) -> None:
    faulthandler.dump_traceback_later(
        int(PROFILE_SETTINGS[profile]["dump_seconds"]), file=output
    )


def pytest_configure(config) -> None:  # pytest plugin hook
    profile = os.environ.get(PYTEST_PROFILE_ENV)
    if profile in PROFILE_SETTINGS:
        schedule_diagnostic_dump(profile, sys.stderr)


def pytest_collection_finish(session) -> None:  # pytest plugin hook
    if os.environ.get(PYTEST_PROFILE_ENV) in PROFILE_SETTINGS:
        _pytest_collected_nodeids[:] = [item.nodeid for item in session.items]


def pytest_runtest_logreport(report) -> None:  # pytest plugin hook
    global _pytest_xfailed, _pytest_xpassed
    if os.environ.get(PYTEST_PROFILE_ENV) not in PROFILE_SETTINGS:
        return
    nodeid = getattr(report, "nodeid", None)
    if type(nodeid) is str:
        _pytest_reported_nodeids.add(nodeid)
    if report.when == "call" and getattr(report, "wasxfail", False):
        if report.skipped:
            _pytest_xfailed += 1
        elif report.passed:
            _pytest_xpassed += 1


def pytest_sessionfinish(session, exitstatus) -> None:  # pytest plugin hook
    profile = os.environ.get(PYTEST_PROFILE_ENV)
    metadata_path = os.environ.get(PYTEST_METADATA_ENV)
    if profile not in PROFILE_SETTINGS or not metadata_path:
        return
    metadata = {
        "profile": profile,
        "pid": os.getpid(),
        "deadline_configured_seconds": PROFILE_SETTINGS[profile]["deadline_seconds"],
        "deadline_applied_seconds": PROFILE_SETTINGS[profile]["deadline_seconds"],
        "exit_code": int(exitstatus),
        "termination_confirmed": True,
        "collected_nodeids": _pytest_collected_nodeids,
        "executed_nodeids": sorted(_pytest_reported_nodeids),
        "xfail": _pytest_xfailed,
        "xpass": _pytest_xpassed,
    }
    try:
        _atomic_json(Path(metadata_path), metadata)
    except OSError:
        pass
    finally:
        faulthandler.cancel_dump_traceback_later()


def _is_redirected(path: Path) -> bool:
    """Detect symlinks and Windows reparse points without following them."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _reject_redirected_components(repo_root: Path, *paths: Path) -> None:
    root = repo_root.resolve()
    for path in paths:
        try:
            relative = path.absolute().relative_to(root)
        except ValueError as exc:
            raise ValueError("ALLOCATION_PATH_OUTSIDE_REPOSITORY") from exc
        current = root
        for part in relative.parts:
            current = current / part
            if _is_redirected(current):
                raise ValueError("REDIRECTED_ALLOCATION_PATH")


def _validate_run_directory(repo_root: Path, run_dir: Path) -> Path:
    root = repo_root.resolve()
    allowed_root = root / ".s6r"
    _reject_redirected_components(root, allowed_root, run_dir)
    resolved_allowed_root = allowed_root.resolve()
    resolved_run_dir = run_dir.resolve()
    if resolved_allowed_root != allowed_root or resolved_run_dir.parent.parent != resolved_allowed_root:
        raise ValueError("RUN_DIRECTORY_OUTSIDE_ALLOWED_ROOT")
    if re.fullmatch(r"[0-9a-f]{12}", resolved_run_dir.parent.name) is None or resolved_run_dir.name != "t":
        raise ValueError("RUN_DIRECTORY_LAYOUT_INVALID")
    if len(str(resolved_run_dir / "p")) > MAX_BASETEMP_PATH_CHARS:
        raise ValueError("PYTEST_BASETEMP_PATH_TOO_LONG")
    return resolved_run_dir


def allocate_invocation(repo_root: Path, *, token_factory=None, run_id_factory=None) -> tuple[str, Path]:
    """Exclusively reserve a fresh <repo>/.s6r/<12-char-token>/t invocation."""
    root = repo_root.resolve()
    allocation_root = root / ".s6r"
    _reject_redirected_components(root, allocation_root)
    try:
        allocation_root.mkdir()
    except FileExistsError:
        if _is_redirected(allocation_root) or not allocation_root.is_dir():
            raise ValueError("REDIRECTED_ALLOCATION_ROOT")
    _reject_redirected_components(root, allocation_root)
    token_factory = token_factory or (lambda: secrets.token_hex(6))
    run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
    run_id = run_id_factory()
    if not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
        raise ValueError("RUN_ID_INVALID")
    for _ in range(128):
        token = token_factory()
        if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{12}", token) is None:
            raise ValueError("ALLOCATION_TOKEN_INVALID")
        token_dir = allocation_root / token
        try:
            token_dir.mkdir()
        except FileExistsError:
            _reject_redirected_components(root, token_dir)
            continue
        _reject_redirected_components(root, token_dir)
        try:
            (token_dir / "t").mkdir()
        except FileExistsError as exc:
            raise ValueError("INVOCATION_DIRECTORY_COLLISION") from exc
        run_dir = token_dir / "t"
        _validate_run_directory(root, run_dir)
        return run_id, run_dir
    raise ValueError("ALLOCATION_COLLISION_RETRY_EXHAUSTED")


def validated_pytest_basetemp(repo_root: Path, run_dir: Path) -> Path:
    """Keep pytest's cleanup area short and inside the exclusively owned run."""
    resolved_run_dir = _validate_run_directory(repo_root, run_dir)
    basetemp_candidate = resolved_run_dir / "p"
    _reject_redirected_components(repo_root.resolve(), basetemp_candidate)
    basetemp = basetemp_candidate.resolve()
    try:
        basetemp.relative_to(resolved_run_dir)
    except ValueError as exc:
        raise ValueError("PYTEST_BASETEMP_OUTSIDE_RUN_DIRECTORY") from exc
    if len(str(basetemp)) > MAX_BASETEMP_PATH_CHARS:
        raise ValueError("PYTEST_BASETEMP_PATH_TOO_LONG")
    return basetemp


def contained_artifact_path(repo_root: Path, run_dir: Path, filename: str) -> Path:
    """Resolve one runner artifact and reject redirection or path escape."""
    resolved_run_dir = _validate_run_directory(repo_root, run_dir)
    candidate = resolved_run_dir / filename
    _reject_redirected_components(repo_root.resolve(), candidate)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_run_dir)
    except ValueError as exc:
        raise ValueError("ARTIFACT_OUTSIDE_RUN_DIRECTORY") from exc
    return resolved


def build_pytest_args(profile: str, junit_path: Path, basetemp: Path) -> list[str]:
    return [
        "-q",
        "--junitxml",
        str(junit_path),
        "--basetemp",
        str(basetemp),
        str(PROFILE_SETTINGS[profile]["node"]),
    ]


def build_pytest_command(
    python: Path, profile: str, junit_path: Path, basetemp: Path
) -> list[str]:
    """Build the same module-based pytest invocation used by native validation."""
    return [
        str(python),
        "-m",
        "pytest",
        "-p",
        PYTEST_PLUGIN_MODULE,
        *build_pytest_args(profile, junit_path, basetemp),
    ]


def build_pytest_environment(profile: str, metadata_path: Path) -> dict[str, str]:
    """Preserve the inherited process environment and clear pytest arg injection."""
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    environment[PYTEST_PROFILE_ENV] = profile
    environment[PYTEST_METADATA_ENV] = str(metadata_path)
    return environment


def classify_worker_result(
    profile: str,
    *,
    exit_code: int,
    collected_nodeids: list[str],
    counts: dict[str, int] | None,
    xfail: int = 0,
    xpass: int = 0,
) -> tuple[str, bool]:
    """Return outcome and collection validity without requiring pytest execution."""
    expected = PROFILE_SETTINGS[profile]["expected_tests"]
    if counts is None:
        return "INCOMPLETE", False
    if expected is not None:
        collection_ok = len(collected_nodeids) == expected and bool(collected_nodeids) and (
            collected_nodeids[0] == PROFILE_SETTINGS[profile]["node"]
        )
    else:
        module = str(PROFILE_SETTINGS[profile]["node"])
        collection_ok = bool(collected_nodeids) and all(
            nodeid.startswith(module + "::") for nodeid in collected_nodeids
        )
    if not collection_ok:
        return "INCOMPLETE", False
    if counts["skipped"] or xfail or xpass:
        return "FAIL", True
    if counts["failed"] or exit_code != 0:
        return ("FAIL" if counts["failed"] else "BLOCKED"), True
    if counts["tests"] > 0 and counts["passed"] == counts["tests"]:
        return "PASS", True
    return "INCOMPLETE", True


def _receipt_from_worker(
    profile: str, run_dir: Path, exit_code: int, run_id: str | None = None
) -> dict[str, object]:
    settings = PROFILE_SETTINGS[profile]
    receipt_path = run_dir / "worker-result.json"
    junit_path = run_dir / "junit.xml"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        receipt = None
    if not isinstance(receipt, dict):
        receipt = {
            "profile": profile,
            "pid": None,
            "deadline_configured_seconds": settings["deadline_seconds"],
            "deadline_applied_seconds": None,
            "exit_code": exit_code,
            "termination_confirmed": True,
            "result": "INCOMPLETE",
        }
    else:
        counts = summarize_junit(junit_path)
        nodeids = receipt.get("collected_nodeids")
        executed = receipt.get("executed_nodeids")
        xfail = receipt.get("xfail")
        xpass = receipt.get("xpass")
        if (
            counts is None or type(nodeids) is not list or type(executed) is not list
            or any(type(nodeid) is not str for nodeid in (*nodeids, *executed))
            or len(set(nodeids)) != len(nodeids) or len(set(executed)) != len(executed)
            or set(nodeids) != set(executed) or counts["tests"] != len(nodeids)
            or type(xfail) is not int or type(xpass) is not int
            or xfail < 0 or xpass < 0
        ):
            receipt["result"] = "INCOMPLETE"
        else:
            worker_exit_code = receipt.get("exit_code")
            if type(worker_exit_code) is not int:
                receipt["result"] = "INCOMPLETE"
            else:
                outcome, collection_ok = classify_worker_result(
                    profile,
                    exit_code=worker_exit_code,
                    collected_nodeids=nodeids,
                    counts=counts,
                    xfail=xfail,
                    xpass=xpass,
                )
                receipt.update(counts)
                receipt["collection_ok"] = collection_ok
                receipt["result"] = outcome
                if worker_exit_code != exit_code:
                    receipt["result"] = "INCOMPLETE"
                    receipt["reason"] = "WORKER_EXIT_CODE_MISMATCH"
    if not junit_path.is_file():
        receipt["result"] = "INCOMPLETE"
    receipt["junit_present"] = junit_path.is_file()
    receipt["receipt_path"] = str(run_dir / "receipt.json")
    if run_id is not None:
        receipt["run_id"] = run_id
    return receipt


def _attach_run_spec_evidence(
    receipt: dict[str, object], *, spec: RunSpec, before: dict[str, str], repo_root: Path,
) -> None:
    receipt["run_spec"] = asdict(spec)
    receipt["run_spec_sha256"] = spec.digest()
    receipt["input_sha256_before"] = before
    try:
        after = _input_snapshot(repo_root)
    except (OSError, ValueError):
        receipt["input_sha256_after"] = None
        receipt["input_drift_detected"] = None
        receipt["result"] = "INCOMPLETE"
        receipt["reason"] = "RUN_SPEC_INPUT_SNAPSHOT_UNAVAILABLE"
        return
    receipt["input_sha256_after"] = after
    receipt["input_drift_detected"] = before != after
    if before != after:
        receipt["result"] = "INCOMPLETE"
        receipt["reason"] = "RUN_SPEC_INPUT_DRIFT"


def main(argv: list[str] | None = None) -> int:
    # This legacy one-shot worker has no MXC host controller or verified OS
    # process-tree boundary. Keep its helper API for offline inspection, but do
    # not let direct invocation bypass the new executor/gate.
    print("BLOCKED: MXC_HOST_EXECUTOR_REQUIRED", file=sys.stderr)
    return 3

    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILE_SETTINGS), required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--powershell-version", choices=("5.1",), default="not-observed")
    parser.add_argument("--allocate", action="store_true")
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    if args.allocate:
        try:
            run_id, allocated_dir = allocate_invocation(root)
        except (OSError, ValueError) as exc:
            print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 3
        print(json.dumps({"run_id": run_id, "run_dir": str(allocated_dir)}))
        return 0
    if args.run_dir is None or not args.run_id:
        print("BLOCKED: RUN_DIRECTORY_AND_ID_REQUIRED", file=sys.stderr)
        return 3
    run_dir = args.run_dir
    try:
        run_dir = _validate_run_directory(root, run_dir)
        validated_pytest_basetemp(root, run_dir)

        def artifact(name: str) -> Path:
            return contained_artifact_path(root, run_dir, name)

    except (OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 3
    deadline = int(PROFILE_SETTINGS[args.profile]["deadline_seconds"])
    python = root / ".venv" / "Scripts" / "python.exe"
    # Reserve one second for durable receipt finalization before the external
    # PowerShell deadline; the external hard limits remain 25s/150s.
    child_timeout = max(1, deadline - 1)
    junit_path = artifact("junit.xml")
    metadata_path = artifact("worker-result.json")
    environment = build_pytest_environment(args.profile, metadata_path)
    worker_command = build_pytest_command(
        python, args.profile, junit_path, validated_pytest_basetemp(root, run_dir)
    )
    try:
        run_spec, snapshot_before = build_run_spec(
            repo_root=root, run_id=args.run_id, profile=args.profile, python=python,
            run_dir=run_dir, basetemp=validated_pytest_basetemp(root, run_dir),
            junit_path=junit_path, environment=environment,
            powershell_version=args.powershell_version,
        )
    except (OSError, ValueError) as exc:
        receipt = {
            "profile": args.profile, "pid": None,
            "deadline_configured_seconds": deadline,
            "deadline_applied_seconds": 0, "exit_code": None,
            "termination_confirmed": True, "result": "BLOCKED",
            "reason": "RUN_SPEC_UNAVAILABLE", "run_id": args.run_id,
        }
        _atomic_json(artifact("receipt.json"), receipt)
        print("BLOCKED: immutable run specification could not be captured")
        return 3
    if is_sandbox_environment(os.environ):
        receipt = {
            "profile": args.profile, "pid": None,
            "deadline_configured_seconds": deadline,
            "deadline_applied_seconds": 0, "exit_code": None,
            "termination_confirmed": True, "result": "BLOCKED",
            "reason": "SANDBOX_ENVIRONMENT", "run_id": args.run_id,
        }
        _attach_run_spec_evidence(receipt, spec=run_spec, before=snapshot_before, repo_root=root)
        _atomic_json(artifact("receipt.json"), receipt)
        print("BLOCKED: sandbox runtime detected; no test worker started")
        return 3
    if not python.is_file():
        receipt = {
            "profile": args.profile, "pid": None,
            "deadline_configured_seconds": deadline,
            "deadline_applied_seconds": 0, "exit_code": None,
            "termination_confirmed": True, "result": "BLOCKED",
            "reason": "VENV_PYTHON_MISSING", "run_id": args.run_id,
        }
        _attach_run_spec_evidence(receipt, spec=run_spec, before=snapshot_before, repo_root=root)
        _atomic_json(artifact("receipt.json"), receipt)
        print("BLOCKED: repository .venv Python is missing")
        return 3
    process_result = supervise_process(
        worker_command,
        cwd=root,
        stdout_path=artifact("worker.stdout.log"),
        stderr_path=artifact("worker.stderr.log"),
        timeout_seconds=child_timeout,
        env=environment,
    )
    if process_result.get("launch_error"):
        receipt = {
            "profile": args.profile,
            "pid": None,
            "deadline_configured_seconds": deadline,
            "deadline_applied_seconds": process_result["elapsed_seconds"],
            "exit_code": None,
            "termination_confirmed": True,
            "result": "BLOCKED",
            "reason": "WORKER_LAUNCH_ERROR",
            "run_id": args.run_id,
        }
        _attach_run_spec_evidence(receipt, spec=run_spec, before=snapshot_before, repo_root=root)
        _atomic_json(artifact("receipt.json"), receipt)
        return 3
    if process_result["timed_out"]:
        outcome, reason, exit_code = timeout_outcome(
            bool(process_result["termination_confirmed"])
        )
        receipt = {
            "profile": args.profile,
            "pid": process_result["pid"],
            "deadline_configured_seconds": deadline,
            "deadline_applied_seconds": process_result["elapsed_seconds"],
            "exit_code": process_result["exit_code"],
            "termination_confirmed": process_result["termination_confirmed"],
            "result": outcome,
            "reason": reason,
            "run_id": args.run_id,
        }
        _attach_run_spec_evidence(receipt, spec=run_spec, before=snapshot_before, repo_root=root)
        _atomic_json(artifact("receipt.json"), receipt)
        return exit_code
    receipt = _receipt_from_worker(
        args.profile, run_dir, int(process_result.get("exit_code") or 0), args.run_id
    )
    receipt["worker_pid"] = process_result["pid"]
    receipt["deadline_applied_seconds"] = process_result["elapsed_seconds"]
    receipt["termination_confirmed"] = False
    receipt["tree_boundary_verified"] = False
    if receipt.get("result") == "PASS":
        receipt["result"] = "BLOCKED"
        receipt["reason"] = "PROCESS_EXIT_UNCONFIRMED"
    _attach_run_spec_evidence(receipt, spec=run_spec, before=snapshot_before, repo_root=root)
    _atomic_json(artifact("receipt.json"), receipt)
    print(f"{receipt['result']}: profile={args.profile}; receipt={run_dir / 'receipt.json'}")
    return 0 if receipt["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
