"""Fail-closed JSONL host controller for the offline S6 V2 MXC gate.

Only the fixed Infrastructure profile is exposed before the infrastructure
gate.  The service is intentionally standard-library-only so its protocol
helpers can be inspected and tested without starting Codex or a child process.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO


PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 16_384
MAX_STDIO_BYTES = 8 * 1024 * 1024
MAX_RUNTIME_FILES = 100_000
MAX_RUNTIME_BYTES = 1_500_000_000
COPY_CHUNK_BYTES = 1024 * 1024
HARD_DEADLINE_SECONDS = 150
DIAGNOSTIC_SECONDS = 120
REAP_RESERVE_SECONDS = 5
CREATE_SUSPENDED = 0x00000004  # Win32 CREATE_SUSPENDED; not exported by all Python versions.
CREATE_NO_WINDOW = 0x08000000  # Win32 CREATE_NO_WINDOW.
PROFILE_NAME = "Infrastructure"
PROFILE_SELECTION = "tests/manual_proofs/test_s6_v2_mxc_host_executor.py"
PROFILE_ALLOWLIST = {
    PROFILE_NAME: {
        "selection": PROFILE_SELECTION,
        "deadline_seconds": HARD_DEADLINE_SECONDS,
        "diagnostic_seconds": DIAGNOSTIC_SECONDS,
        "worker_seconds": HARD_DEADLINE_SECONDS - REAP_RESERVE_SECONDS,
    }
}
SCENARIO_ALLOWLIST = {
    "suite": {
        "pytest_selector": None, "worker_seconds": HARD_DEADLINE_SECONDS - REAP_RESERVE_SECONDS,
        "diagnostic_seconds": DIAGNOSTIC_SECONDS,
    },
    "controlled_failure": {
        "pytest_selector": "test_s6_v2_mxc_synthetic_failure",
        "worker_seconds": HARD_DEADLINE_SECONDS - REAP_RESERVE_SECONDS,
        "diagnostic_seconds": DIAGNOSTIC_SECONDS,
    },
    "timeout_child": {
        "pytest_selector": "test_s6_v2_mxc_timeout_child", "worker_seconds": 8,
        "diagnostic_seconds": 4,
    },
    "cancel_child": {
        "pytest_selector": "test_s6_v2_mxc_cancel_child",
        "worker_seconds": HARD_DEADLINE_SECONDS - REAP_RESERVE_SECONDS,
        "diagnostic_seconds": DIAGNOSTIC_SECONDS,
    },
}


class ProtocolError(ValueError):
    """A request cannot be interpreted without weakening the contract."""


def parse_request(line: str) -> dict[str, Any]:
    """Parse one bounded JSONL frame and reject all caller-supplied execution data."""
    try:
        encoded = line.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ProtocolError("INVALID_JSONL_FRAME") from exc
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ProtocolError("FRAME_TOO_LARGE")
    try:
        value = json.loads(line)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ProtocolError("INVALID_JSONL_FRAME") from exc
    if type(value) is not dict:
        raise ProtocolError("REQUEST_MUST_BE_OBJECT")
    operation = value.get("op")
    if type(operation) is not str:
        raise ProtocolError("REQUEST_SCHEMA_INVALID")
    schemas = {
        "submit": {"op", "request_id", "profile", "scenario"},
        "status": {"op", "request_id", "job_id"},
        "cancel": {"op", "request_id", "job_id"},
        "result": {"op", "request_id", "job_id"},
    }
    expected = schemas.get(operation)
    if expected is None or set(value) != expected:
        raise ProtocolError("REQUEST_SCHEMA_INVALID")
    for field in ("request_id",):
        if type(value.get(field)) is not str or not value[field] or len(value[field]) > 128:
            raise ProtocolError("REQUEST_ID_INVALID")
    if operation == "submit":
        if type(value.get("profile")) is not str:
            raise ProtocolError("PROFILE_NOT_ALLOWLISTED")
        if value.get("profile") not in PROFILE_ALLOWLIST:
            raise ProtocolError("PROFILE_NOT_ALLOWLISTED")
        if type(value.get("scenario")) is not str or value.get("scenario") not in SCENARIO_ALLOWLIST:
            raise ProtocolError("SCENARIO_NOT_ALLOWLISTED")
    elif type(value.get("job_id")) is not str or not _valid_id(value["job_id"]):
        raise ProtocolError("JOB_ID_INVALID")
    return value


def _valid_id(value: str) -> bool:
    return len(value) == 32 and all(ch in "0123456789abcdef" for ch in value)


def _scenario_selection(scenario: str) -> str:
    spec = SCENARIO_ALLOWLIST.get(scenario)
    if spec is None:
        raise ProtocolError("SCENARIO_NOT_ALLOWLISTED")
    test_name = spec["pytest_selector"]
    return PROFILE_SELECTION if test_name is None else f"{PROFILE_SELECTION}::{test_name}"


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(
    path: Path, *, deadline: float | None = None, cancelled: Callable[[], bool] | None = None,
    finalizing: bool = False,
) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            if deadline is not None and cancelled is not None:
                if finalizing:
                    _check_finalization_budget(deadline)
                else:
                    _check_preparation_budget(deadline, cancelled)
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    data = _json_bytes(payload)
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _is_redirected(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _ensure_plain_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if _is_redirected(path) or not path.is_dir():
        raise ProtocolError("RUN_ROOT_REDIRECTED")
    current = path
    while current != current.parent:
        if _is_redirected(current):
            raise ProtocolError("RUN_ROOT_REDIRECTED")
        current = current.parent


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _allocate_run(repo_root: Path, job_id: str) -> Path:
    root = repo_root / ".s6mxc"
    _ensure_plain_directory(root)
    run_root = root / job_id
    run_root.mkdir()
    _ensure_plain_directory(run_root)
    return run_root.resolve()


def _check_preparation_budget(deadline: float, cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise ProtocolError("CANCELLED_DURING_PREPARATION")
    if time.monotonic() >= deadline - REAP_RESERVE_SECONDS:
        raise ProtocolError("DEADLINE_REACHED_DURING_PREPARATION")


def _check_finalization_budget(deadline: float) -> None:
    """Permit post-cancel reconciliation only within the original hard deadline."""
    if time.monotonic() >= deadline:
        raise ProtocolError("HARD_DEADLINE_EXCEEDED_DURING_FINALIZATION")


def _copy_file(
    source: Path, destination: Path, *, deadline: float, cancelled: Callable[[], bool],
) -> str:
    _check_preparation_budget(deadline, cancelled)
    if _is_redirected(source) or not source.is_file():
        raise ProtocolError("SNAPSHOT_INPUT_UNSAFE_OR_MISSING")
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with source.open("rb") as reader, destination.open("xb") as writer:
        while True:
            _check_preparation_budget(deadline, cancelled)
            chunk = reader.read(COPY_CHUNK_BYTES)
            if not chunk:
                break
            writer.write(chunk)
            digest.update(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    try:
        destination.chmod(0o444)
    except OSError:
        pass
    _check_preparation_budget(deadline, cancelled)
    return digest.hexdigest()


def _snapshot_inputs(
    repo_root: Path, run_root: Path, *, deadline: float, cancelled: Callable[[], bool],
) -> tuple[Path, dict[str, str]]:
    """Copy fixed test sources plus only pytest and its allowlisted dependencies."""
    snapshot = run_root / "snapshot"
    snapshot.mkdir()
    entries = {
        "tools/manual_proofs/s6_v2_mxc_host_executor.py": repo_root / "tools/manual_proofs/s6_v2_mxc_host_executor.py",
        PROFILE_SELECTION: repo_root / PROFILE_SELECTION,
    }
    manifest: dict[str, str] = {}
    for relative, source in entries.items():
        _check_preparation_budget(deadline, cancelled)
        manifest[relative] = _copy_file(
            source, snapshot / relative, deadline=deadline, cancelled=cancelled,
        )
    python = (repo_root / ".venv" / "Scripts" / "python.exe").resolve(strict=True)
    site_packages = python.parents[1] / "Lib" / "site-packages"
    package_names = ("pytest", "_pytest", "pluggy", "iniconfig", "packaging", "pygments")
    file_count = 0
    byte_count = 0
    for package in package_names:
        _check_preparation_budget(deadline, cancelled)
        source_root = site_packages / package
        if not source_root.exists() and package == "pygments":
            continue
        if _is_redirected(source_root) or not source_root.is_dir():
            raise ProtocolError("PYTEST_RUNTIME_DEPENDENCY_MISSING_OR_UNSAFE")
        for source in source_root.rglob("*"):
            _check_preparation_budget(deadline, cancelled)
            relative_inside = source.relative_to(site_packages)
            destination = snapshot / "runtime" / "site-packages" / relative_inside
            if _is_redirected(source):
                raise ProtocolError("PYTEST_RUNTIME_DEPENDENCY_REDIRECTED")
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if not source.is_file():
                raise ProtocolError("PYTEST_RUNTIME_DEPENDENCY_UNSUPPORTED_ENTRY")
            file_count += 1
            byte_count += source.stat().st_size
            if file_count > MAX_RUNTIME_FILES or byte_count > MAX_RUNTIME_BYTES:
                raise ProtocolError("PYTEST_RUNTIME_ALLOWLIST_LIMIT_EXCEEDED")
            manifest[str(Path("runtime/site-packages") / relative_inside)] = _copy_file(
                source, destination, deadline=deadline, cancelled=cancelled,
            )
        metadata = next(site_packages.glob(f"{package}-*.dist-info"), None)
        if metadata is not None:
            if _is_redirected(metadata) or not metadata.is_dir():
                raise ProtocolError("PYTEST_RUNTIME_METADATA_UNSAFE")
            for source in metadata.rglob("*"):
                _check_preparation_budget(deadline, cancelled)
                relative_inside = source.relative_to(site_packages)
                destination = snapshot / "runtime" / "site-packages" / relative_inside
                if _is_redirected(source):
                    raise ProtocolError("PYTEST_RUNTIME_METADATA_REDIRECTED")
                if source.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                file_count += 1
                byte_count += source.stat().st_size
                if file_count > MAX_RUNTIME_FILES or byte_count > MAX_RUNTIME_BYTES:
                    raise ProtocolError("PYTEST_RUNTIME_ALLOWLIST_LIMIT_EXCEEDED")
                manifest[str(Path("runtime/site-packages") / relative_inside)] = _copy_file(
                    source, destination, deadline=deadline, cancelled=cancelled,
                )
    _check_preparation_budget(deadline, cancelled)
    (snapshot / "manifest.json").write_bytes(_json_bytes(manifest))
    _check_preparation_budget(deadline, cancelled)
    return snapshot, manifest


def _manifest_digest(manifest: dict[str, str]) -> str:
    return hashlib.sha256(_json_bytes(manifest)).hexdigest()


def _reconcile_network_canary(
    worker_evidence: object, *, host_control_positive: bool, worker_connections: int,
    expected_host: str, expected_port: int, expected_job_id: str, expected_scenario: str,
    listener_clean: bool,
) -> tuple[str, str]:
    """Accept only a specific OS network-denial result plus a live host control."""
    if not listener_clean:
        return "BLOCKED", "NETWORK_CANARY_LISTENER_UNCONFIRMED"
    if worker_connections > 0:
        return "FAIL", "NETWORK_ISOLATION_VIOLATION"
    if not host_control_positive:
        return "BLOCKED", "NETWORK_CANARY_CONTROL_FAILED"
    if type(worker_evidence) is not dict:
        return "BLOCKED", "NETWORK_CANARY_EVIDENCE_MISSING"
    evidence = worker_evidence
    if (
        evidence.get("schema") != "s6-v2-loopback-network-canary-v1"
        or evidence.get("host") != expected_host
        or evidence.get("job_id") != expected_job_id
        or evidence.get("scenario") != expected_scenario
        or type(evidence.get("port")) is not int
        or evidence.get("port") != expected_port
        or evidence.get("attempted") is not True
    ):
        return "BLOCKED", "NETWORK_CANARY_EVIDENCE_INVALID"
    if evidence.get("connected") is True:
        return "FAIL", "NETWORK_ISOLATION_VIOLATION"
    if evidence.get("connected") is not False:
        return "BLOCKED", "NETWORK_CANARY_OUTCOME_AMBIGUOUS"
    if (
        evidence.get("error_class") != "PermissionError"
        or type(evidence.get("errno")) is not int
        or evidence.get("errno") != 13
        or type(evidence.get("winerror")) is not int
        or evidence.get("winerror") != 10013
    ):
        return "BLOCKED", "NETWORK_CANARY_DENIAL_UNCLASSIFIED"
    return "PASS", "LOOPBACK_NETWORK_DENIAL_CONFIRMED"


class LoopbackNetworkCanary:
    """Host-owned listener bound only to IPv4 loopback for an offline denial check."""

    HOST = "127.0.0.1"
    CONTROL_MARKER = b"S6_MXC_HOST_CONTROL_V1"

    def __init__(self, output_root: Path, job_id: str, scenario: str) -> None:
        self.output_root = output_root
        self.job_id = job_id
        self.scenario = scenario
        self.worker_start_nonce = secrets.token_hex(16)
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        self.listener.bind((self.HOST, 0))
        self.listener.listen(4)
        self.listener.settimeout(0.1)
        self.host, self.port = self.listener.getsockname()
        if self.host != self.HOST or type(self.port) is not int or not (0 < self.port < 65536):
            self.listener.close()
            raise ProtocolError("NETWORK_CANARY_ENDPOINT_INVALID")
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._connections: list[dict[str, object]] = []
        self._control_seen = False
        self._thread = threading.Thread(target=self._accept_loop, name="s6-loopback-canary", daemon=False)
        self._started = False
        self._closed = False

    def start_and_control(self) -> None:
        self._thread.start()
        self._started = True
        try:
            with socket.create_connection((self.HOST, self.port), timeout=1.0) as control:
                control.sendall(self.CONTROL_MARKER)
        except OSError as exc:
            self.close()
            raise ProtocolError("NETWORK_CANARY_CONTROL_CONNECT_FAILED") from exc
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            with self._lock:
                if any(item.get("control") is True for item in self._connections):
                    return
            time.sleep(0.01)
        self.close()
        raise ProtocolError("NETWORK_CANARY_CONTROL_NOT_ACCEPTED")

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                connection, peer = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    return
                with self._lock:
                    self._connections.append({"control": False, "peer": "LISTENER_ERROR"})
                return
            try:
                connection.settimeout(0.25)
                try:
                    marker = connection.recv(128)
                except OSError:
                    marker = b""
                with self._lock:
                    is_control = marker == self.CONTROL_MARKER and not self._control_seen
                    if is_control:
                        self._control_seen = True
                    record = {"control": is_control, "peer": str(peer[0])}
                    self._connections.append(record)
            finally:
                connection.close()

    def worker_environment(self) -> dict[str, str]:
        return {
            "S6_MXC_LOOPBACK_HOST": self.HOST,
            "S6_MXC_LOOPBACK_PORT": str(self.port),
            "S6_MXC_LOOPBACK_EVIDENCE": str(self.output_root / "network-canary-worker.json"),
            "S6_MXC_JOB_ID": self.job_id,
            "S6_MXC_SCENARIO": self.scenario,
            "S6_MXC_WORKER_IDENTITY": str(self.output_root / "worker-identity.json"),
            "S6_MXC_WORKER_START": str(self.output_root / "worker-start.json"),
            "S6_MXC_WORKER_START_NONCE": self.worker_start_nonce,
        }

    def finish(self, worker_evidence_path: Path) -> dict[str, object]:
        if self._closed:
            raise ProtocolError("NETWORK_CANARY_ALREADY_CLOSED")
        time.sleep(0.05)
        self._stop.set()
        self.listener.close()
        if self._started:
            self._thread.join(timeout=0.5)
        self._closed = True
        with self._lock:
            records = list(self._connections)
        controls = [item for item in records if item.get("control") is True and item.get("peer") == self.HOST]
        worker_connections = [
            item for item in records
            if item.get("peer") != "LISTENER_ERROR"
            and not (item.get("control") is True and item.get("peer") == self.HOST)
        ]
        worker_evidence: object = None
        try:
            if worker_evidence_path.is_file() and worker_evidence_path.stat().st_size <= 16_384:
                worker_evidence = json.loads(worker_evidence_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            worker_evidence = None
        outcome, reason = _reconcile_network_canary(
            worker_evidence, host_control_positive=len(controls) == 1,
            worker_connections=len(worker_connections), expected_host=self.HOST, expected_port=self.port,
            expected_job_id=self.job_id, expected_scenario=self.scenario,
            listener_clean=not self._thread.is_alive()
            and all(item.get("peer") != "LISTENER_ERROR" for item in records),
        )
        evidence = {
            "schema": "s6-v2-loopback-network-canary-host-v1", "host": self.HOST, "port": self.port,
            "network_enabled": False, "host_control_positive": len(controls) == 1,
            "host_control_connections": len(controls), "worker_connection_count": len(worker_connections),
            "listener_clean": not self._thread.is_alive()
            and all(item.get("peer") != "LISTENER_ERROR" for item in records),
            "worker_connections": worker_connections, "worker_evidence": worker_evidence,
            "result": outcome, "reason": reason,
        }
        _atomic_json(self.output_root / "network-canary.json", evidence)
        return evidence

    def close(self) -> None:
        if self._closed:
            return
        self._stop.set()
        try:
            self.listener.close()
        finally:
            if self._started:
                self._thread.join(timeout=0.5)
            self._closed = True


def _runtime_allowlist(python: Path) -> list[Path]:
    """Allow the venv and its base CPython runtime, never the repository root."""
    executable = python.resolve(strict=True)
    if executable.name.lower() not in {"python.exe", "python3.exe"}:
        raise ProtocolError("PYTHON_EXECUTABLE_UNEXPECTED")
    if ".venv" not in {part.lower() for part in executable.parts}:
        raise ProtocolError("PYTHON_NOT_FROM_REPOSITORY_VENV")
    venv = executable.parents[1]
    cfg = venv / "pyvenv.cfg"
    if _is_redirected(cfg) or not cfg.is_file():
        raise ProtocolError("PYTHON_VENV_CONFIGURATION_UNAVAILABLE")
    base_home: Path | None = None
    for line in cfg.read_text(encoding="utf-8", errors="strict").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip().lower() == "home":
            base_home = Path(value.strip()).resolve(strict=True)
            break
    if base_home is None or not (base_home / "python.exe").is_file():
        raise ProtocolError("PYTHON_BASE_RUNTIME_UNAVAILABLE")
    try:
        expected_base = Path(sys.base_prefix).resolve(strict=True)
    except OSError as exc:
        raise ProtocolError("PYTHON_BASE_RUNTIME_UNAVAILABLE") from exc
    if base_home != expected_base:
        raise ProtocolError("PYTHON_BASE_RUNTIME_MISMATCH")
    site_packages = venv / "Lib" / "site-packages"
    required = ("pytest", "_pytest", "pluggy", "iniconfig", "packaging")
    base_lib = base_home / "Lib"
    base_dlls = base_home / "DLLs"
    if (
        not base_lib.is_dir() or not base_dlls.is_dir()
        or _is_redirected(base_lib) or _is_redirected(base_dlls)
    ):
        raise ProtocolError("PYTHON_BASE_RUNTIME_DIRECTORIES_UNAVAILABLE_OR_UNSAFE")
    dlls = {path.name.lower(): path for path in base_home.glob("python3*.dll")}
    expected_dll_names = {"python3.dll", "python314.dll"}
    if set(dlls) != expected_dll_names:
        raise ProtocolError("PYTHON_RUNTIME_DLL_AMBIGUOUS")
    runtime = [
        executable, cfg, base_home / "python.exe", dlls["python3.dll"], dlls["python314.dll"],
        base_lib, base_dlls,
    ]
    for package in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging", "pygments"):
        candidate = site_packages / package
        if candidate.exists():
            runtime.append(candidate)
        elif package in required:
            raise ProtocolError("PYTEST_RUNTIME_DEPENDENCY_MISSING")
    if site_packages.is_dir():
        for pattern in ("pytest-*.dist-info", "pluggy-*.dist-info", "iniconfig-*.dist-info", "packaging-*.dist-info"):
            runtime.extend(site_packages.glob(pattern))
    existing_runtime = [path for path in runtime if path.exists()]
    if any(_is_redirected(path) for path in existing_runtime):
        raise ProtocolError("PYTHON_RUNTIME_REDIRECTED")
    resolved_runtime = [path.resolve(strict=True) for path in existing_runtime]
    return resolved_runtime


def _clean_environment(run_root: Path, python: Path, canary: LoopbackNetworkCanary) -> dict[str, str]:
    """Build a small non-credential environment; do not inherit user secrets."""
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if not system_root or not Path(system_root).is_dir():
        raise ProtocolError("WINDOWS_SYSTEM_ROOT_UNAVAILABLE")
    system_drive = os.environ.get("SystemDrive")
    root_drive = Path(system_root).drive
    if (
        not system_drive or len(system_drive) != 2 or system_drive[1] != ":"
        or not system_drive[0].isascii() or not system_drive[0].isalpha()
        or not root_drive or root_drive.casefold() != system_drive.casefold()
    ):
        raise ProtocolError("WINDOWS_SYSTEM_DRIVE_INVALID")
    local_app_data = os.environ.get("LOCALAPPDATA")
    try:
        if (
            not local_app_data or "\x00" in local_app_data or len(local_app_data) > 32_767
            or not local_app_data.encode("utf-8", errors="strict")
        ):
            raise ProtocolError("WINDOWS_LOCALAPPDATA_INVALID")
        local_app_data_path = Path(local_app_data)
        if not local_app_data_path.is_absolute() or not local_app_data_path.is_dir():
            raise ProtocolError("WINDOWS_LOCALAPPDATA_INVALID")
        local_app_data_path.resolve(strict=True)
    except (UnicodeError, OSError, ValueError) as exc:
        raise ProtocolError("WINDOWS_LOCALAPPDATA_INVALID") from exc
    env = {
        "SystemRoot": system_root,
        "SystemDrive": system_drive,
        "LOCALAPPDATA": local_app_data,
        "WINDIR": system_root,
        "COMSPEC": str(Path(system_root) / "System32" / "cmd.exe"),
        "PATH": os.pathsep.join((str(python.parent), str(Path(system_root) / "System32"))),
        "TEMP": str(run_root / "artifacts" / "tmp"),
        "TMP": str(run_root / "artifacts" / "tmp"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "CODEX_HOME": str(run_root / "codex-home"),
        **canary.worker_environment(),
    }
    if not (run_root / "artifacts" / "tmp").is_dir():
        raise ProtocolError("JOB_TEMP_DIRECTORY_UNAVAILABLE")
    return env


def _permission_override(
    runtime: list[Path], snapshot: Path, output_root: Path, codex_home: Path,
) -> str:
    """Build one immutable per-command permission profile override."""
    if PROFILE_NAME not in PROFILE_ALLOWLIST:
        raise ProtocolError("PROFILE_NOT_ALLOWLISTED")
    paths = {str(path.resolve()): "read" for path in runtime}
    paths[str(snapshot.resolve())] = "read"
    paths[str(output_root.resolve())] = "write"
    paths[str(codex_home.resolve())] = "write"
    filesystem_entries = {":minimal": "read", **paths}
    filesystem = ", ".join(
        f"{json.dumps(path)} = {json.dumps(access)}" for path, access in sorted(filesystem_entries.items())
    )
    return (
        "permissions.Infrastructure = { "
        f"filesystem = {{ {filesystem} }}, network = {{ enabled = false }} }}"
    )


def _pytest_bootstrap(
    snapshot: Path, junit_path: Path, selector_args: list[str], *, job_id: str,
    scenario: str, selection: str, diagnostic_seconds: int,
) -> str:
    """Build the fixed in-worker pytest entrypoint and original JUnit identity hook."""
    args = ["pytest", "-q", "--junitxml", str(junit_path), *selector_args, selection]
    packages = [str(snapshot), str(snapshot / "runtime" / "site-packages")]
    return f'''import ctypes, faulthandler, json, os, socket, sys, time
faulthandler.dump_traceback_later({diagnostic_seconds}, repeat=False)
sys.path[:0] = {packages!r}
sys.argv = {args!r}
_job_id = {job_id!r}
_scenario = {scenario!r}
_selection = {selection!r}
_identity_path = os.environ.get("S6_MXC_WORKER_IDENTITY", "")
_start_path = os.environ.get("S6_MXC_WORKER_START", "")
_start_nonce = os.environ.get("S6_MXC_WORKER_START_NONCE", "")
class _S6FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_get_process_times = _kernel32.GetProcessTimes
_get_process_times.argtypes = [ctypes.c_void_p, ctypes.POINTER(_S6FileTime), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_get_process_times.restype = ctypes.c_int
_created = _S6FileTime()
if not _get_process_times(ctypes.c_void_p(-1), ctypes.byref(_created), None, None, None):
    raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
_pid = os.getpid()
_creation_time = (_created.high << 32) | _created.low
if not _identity_path or not _start_path or not _start_nonce:
    raise RuntimeError("WORKER_START_CONFIGURATION_INVALID")
_identity = {{
    "schema": "s6-v2-mxc-worker-identity-v1", "job_id": _job_id,
    "scenario": _scenario, "pid": _pid, "creation_time": _creation_time,
}}
_identity_tmp = _identity_path + ".tmp"
with open(_identity_tmp, "x", encoding="utf-8") as _stream:
    json.dump(_identity, _stream, sort_keys=True, separators=(",", ":"))
    _stream.flush()
    os.fsync(_stream.fileno())
os.replace(_identity_tmp, _identity_path)
_start_deadline = time.monotonic() + 3.0
while time.monotonic() < _start_deadline:
    try:
        with open(_start_path, "r", encoding="utf-8") as _stream:
            _start = json.load(_stream)
        if (
            type(_start) is dict and _start.get("schema") == "s6-v2-mxc-worker-start-v1"
            and _start.get("job_id") == _job_id and _start.get("scenario") == _scenario
            and _start.get("pid") == _pid and _start.get("creation_time") == _creation_time
            and _start.get("nonce") == _start_nonce
        ):
            break
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    time.sleep(0.025)
else:
    raise RuntimeError("WORKER_JOB_MEMBERSHIP_NOT_CONFIRMED")
import pytest
_canary_host = os.environ.get("S6_MXC_LOOPBACK_HOST", "")
_canary_port_text = os.environ.get("S6_MXC_LOOPBACK_PORT", "")
_canary_path = os.environ.get("S6_MXC_LOOPBACK_EVIDENCE", "")
_evidence = {{
    "schema": "s6-v2-loopback-network-canary-v1", "host": _canary_host,
    "job_id": os.environ.get("S6_MXC_JOB_ID", ""), "scenario": os.environ.get("S6_MXC_SCENARIO", ""),
    "port": None, "attempted": False, "connected": None,
    "error_class": None, "errno": None, "winerror": None,
}}
try:
    _canary_port = int(_canary_port_text)
    if _canary_host != "127.0.0.1" or not (0 < _canary_port < 65536) or not _canary_path:
        raise ValueError("CANARY_CONFIGURATION_INVALID")
    _evidence["port"] = _canary_port
    _evidence["attempted"] = True
    try:
        with socket.create_connection((_canary_host, _canary_port), timeout=1.0):
            _evidence["connected"] = True
    except OSError as _exc:
        _evidence["connected"] = False
        _evidence["error_class"] = type(_exc).__name__
        _evidence["errno"] = getattr(_exc, "errno", None)
        _evidence["winerror"] = getattr(_exc, "winerror", None)
except BaseException as _exc:
    _evidence["error_class"] = type(_exc).__name__
    _evidence["errno"] = getattr(_exc, "errno", None)
    _evidence["winerror"] = getattr(_exc, "winerror", None)
if _canary_path:
    _canary_tmp = _canary_path + ".tmp"
    with open(_canary_tmp, "x", encoding="utf-8") as _stream:
        json.dump(_evidence, _stream, sort_keys=True, separators=(",", ":"))
        _stream.flush()
        os.fsync(_stream.fileno())
    os.replace(_canary_tmp, _canary_path)
class _S6IdentityPlugin:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        report.user_properties.extend((
            ("s6_job_id", _job_id),
            ("s6_scenario", _scenario),
            ("s6_selection", _selection),
        ))
raise SystemExit(pytest.main(sys.argv[1:], plugins=[_S6IdentityPlugin()]))
'''


def _codex_executable() -> Path:
    found = shutil.which("codex")
    if not found:
        raise ProtocolError("CODEX_EXECUTABLE_UNAVAILABLE")
    path = Path(found).resolve(strict=True)
    if path.suffix.lower() not in {".exe", ".com"} or not path.is_file():
        raise ProtocolError("CODEX_EXECUTABLE_NOT_NATIVE")
    return path


def _job_object_api() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    if os.name != "nt":
        raise ProtocolError("WINDOWS_JOB_OBJECT_REQUIRED")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_job = kernel32.CreateJobObjectW
    create_job.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    create_job.restype = ctypes.c_void_p
    set_info = kernel32.SetInformationJobObject
    set_info.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    set_info.restype = ctypes.c_int
    assign = kernel32.AssignProcessToJobObject
    assign.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    assign.restype = ctypes.c_int
    query = kernel32.QueryInformationJobObject
    query.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    query.restype = ctypes.c_int
    terminate = kernel32.TerminateJobObject
    terminate.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    terminate.restype = ctypes.c_int
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    return kernel32, create_job, set_info, assign, query, terminate, close


class _BasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64),
        ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64),
        ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", ctypes.c_uint32),
        ("TotalProcesses", ctypes.c_uint32),
        ("ActiveProcesses", ctypes.c_uint32),
        ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


def _active_process_count(query, job_handle) -> int:
    info = _BasicAccountingInformation()
    if not query(job_handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
        raise OSError(ctypes.get_last_error(), "QueryInformationJobObject failed")
    return int(info.ActiveProcesses)


def _job_process_ids(query, job_handle) -> set[int]:
    """Read the Job Object PID list with a bounded buffer growth loop."""
    class _BasicProcessIdList(ctypes.Structure):
        _fields_ = [
            ("NumberOfAssignedProcesses", ctypes.c_uint32),
            ("NumberOfProcessIdsInList", ctypes.c_uint32),
            ("ProcessIdList", ctypes.c_size_t * 1),
        ]

    prefix = _BasicProcessIdList.ProcessIdList.offset
    capacity = 256
    while capacity <= 65_536:
        size = prefix + capacity * ctypes.sizeof(ctypes.c_size_t)
        buffer = ctypes.create_string_buffer(size)
        returned = ctypes.c_uint32()
        ok = query(job_handle, 3, ctypes.byref(buffer), size, ctypes.byref(returned))
        header = ctypes.cast(buffer, ctypes.POINTER(_BasicProcessIdList)).contents
        assigned = int(header.NumberOfAssignedProcesses)
        count = int(header.NumberOfProcessIdsInList)
        if count > capacity or assigned > capacity:
            capacity = min(65_537, max(capacity * 2, assigned, count))
            continue
        if not ok:
            raise OSError(ctypes.get_last_error(), "Job Object PID list query failed")
        values = (ctypes.c_size_t * count).from_address(ctypes.addressof(buffer) + prefix)
        return {int(values[index]) for index in range(count)}
    raise ProtocolError("JOB_OBJECT_PID_LIST_LIMIT_EXCEEDED")


def _process_creation_time(pid: int) -> int | None:
    """Return the Windows process creation FILETIME for an exact live PID."""
    if os.name != "nt" or type(pid) is not int or pid <= 0:
        return None

    class _FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    open_process.restype = ctypes.c_void_p
    get_times = kernel32.GetProcessTimes
    get_times.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_FileTime), ctypes.POINTER(_FileTime),
        ctypes.POINTER(_FileTime), ctypes.POINTER(_FileTime),
    ]
    get_times.restype = ctypes.c_int
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int
    handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    created = _FileTime()
    try:
        if not get_times(handle, ctypes.byref(created), None, None, None):
            return None
        return (int(created.high) << 32) | int(created.low)
    finally:
        close_handle(handle)


def _confirm_worker_membership(
    job: Job, *, output_root: Path, job_handle: Any, query: Any,
    start_nonce: str, deadline: float, cancelled: Callable[[], bool],
) -> list[int]:
    """Hold the trusted bootstrap before pytest until worker PID membership is proven."""
    identity_path = output_root / "worker-identity.json"
    start_path = output_root / "worker-start.json"
    confirm_deadline = min(deadline - REAP_RESERVE_SECONDS, time.monotonic() + 2.5)
    while time.monotonic() < confirm_deadline:
        _check_preparation_budget(deadline, cancelled)
        if _is_redirected(identity_path):
            raise ProtocolError("WORKER_IDENTITY_REDIRECTED")
        if identity_path.is_file():
            try:
                raw = identity_path.read_bytes()
                if not raw or len(raw) > 16_384:
                    raise ProtocolError("WORKER_IDENTITY_INVALID")
                identity = json.loads(raw.decode("utf-8", errors="strict"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ProtocolError("WORKER_IDENTITY_INVALID") from exc
            expected_keys = {"schema", "job_id", "scenario", "pid", "creation_time"}
            if (
                type(identity) is not dict or set(identity) != expected_keys
                or identity.get("schema") != "s6-v2-mxc-worker-identity-v1"
                or identity.get("job_id") != job.job_id
                or identity.get("scenario") != job.scenario
                or type(identity.get("pid")) is not int or identity["pid"] <= 0
                or type(identity.get("creation_time")) is not int or identity["creation_time"] <= 0
            ):
                raise ProtocolError("WORKER_IDENTITY_MISMATCH")
            worker_pid = identity["pid"]
            creation_time = identity["creation_time"]
            job.worker_pid = worker_pid
            job.worker_creation_time = creation_time
            actual_creation = _process_creation_time(worker_pid)
            if actual_creation != creation_time:
                raise ProtocolError("WORKER_CREATION_IDENTITY_UNCONFIRMED")
            process_ids = _job_process_ids(query, job_handle)
            if worker_pid in process_ids:
                job.worker_job_pids = sorted(process_ids)
                job.worker_identity_sha256 = hashlib.sha256(raw).hexdigest()
                job.worker_membership_verified = True
                _atomic_json(start_path, {
                    "schema": "s6-v2-mxc-worker-start-v1", "job_id": job.job_id,
                    "scenario": job.scenario, "pid": worker_pid,
                    "creation_time": creation_time, "nonce": start_nonce,
                })
                return job.worker_job_pids
            if job.process is None or job.process.poll() is not None:
                raise ProtocolError("WORKER_EXITED_BEFORE_JOB_MEMBERSHIP")
        if job.process is None or job.process.poll() is not None:
            raise ProtocolError("WORKER_IDENTITY_NOT_PUBLISHED")
        time.sleep(0.025)
    raise ProtocolError("WORKER_JOB_MEMBERSHIP_UNCONFIRMED")


def _launch_suspended_in_job(
    command: list[str], *, cwd: Path, env: dict[str, str], stdout_path: Path, stderr_path: Path,
) -> tuple[subprocess.Popen[bytes], Any, tuple[Any, ...]]:
    """Create a suspended child, attach its Job Object, then release it."""
    if os.name != "nt":
        raise ProtocolError("WINDOWS_JOB_OBJECT_REQUIRED")
    kernel32, create_job, set_info, assign, query, terminate, close = _job_object_api()
    job = create_job(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32),
        ]
    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]
    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation), ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]
    limits = _ExtendedLimitInformation()
    limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not set_info(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        close(job)
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")

    startup = subprocess.STARTUPINFO()
    with stdout_path.open("xb") as stdout_stream, stderr_path.open("xb") as stderr_stream:
        stdout_stream.flush()
        stderr_stream.flush()
        creation_flags = CREATE_SUSPENDED | CREATE_NO_WINDOW
        try:
            process = subprocess.Popen(
                command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=stdout_stream,
                stderr=stderr_stream, startupinfo=startup, creationflags=creation_flags,
            )
        except BaseException:
            close(job)
            raise
        # Popen has created the primary thread suspended, but does not expose its
        # handle. OpenThread is mandatory; failure kills the still-suspended root.
        try:
            thread_id = _thread_id_for_process(process.pid)
            open_thread = kernel32.OpenThread
            open_thread.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            open_thread.restype = ctypes.c_void_p
            thread_handle = open_thread(0x0002, False, thread_id)  # THREAD_SUSPEND_RESUME
        except BaseException:
            process.kill()
            process.wait(timeout=2)
            close(job)
            raise
        if not thread_handle:
            process.kill()
            process.wait(timeout=2)
            close(job)
            raise OSError(ctypes.get_last_error(), "OpenThread failed")
        try:
            if not assign(job, int(process._handle)):
                process.kill()
                process.wait(timeout=2)
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
            if _active_process_count(query, job) != 1:
                terminate(job, 3)
                process.wait(timeout=2)
                raise ProtocolError("JOB_OBJECT_MEMBERSHIP_UNCONFIRMED")
            resume_thread = kernel32.ResumeThread
            resume_thread.argtypes = [ctypes.c_void_p]
            resume_thread.restype = ctypes.c_uint32
            if resume_thread(thread_handle) == 0xFFFFFFFF:
                terminate(job, 3)
                process.wait(timeout=2)
                raise OSError(ctypes.get_last_error(), "ResumeThread failed")
        except BaseException:
            close(thread_handle)
            close(job)
            raise
        close(thread_handle)
    return process, job, (query, terminate, close)


def _thread_id_for_process(pid: int) -> int:
    # Toolhelp snapshot avoids guessing that the primary thread id equals PID.
    class _ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32), ("th32ThreadID", ctypes.c_uint32),
            ("th32OwnerProcessID", ctypes.c_uint32), ("tpBasePri", ctypes.c_int32),
            ("tpDeltaPri", ctypes.c_int32), ("dwFlags", ctypes.c_uint32),
        ]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    create_snapshot.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int
    snapshot = create_snapshot(0x00000004, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    entry = _ThreadEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        first = kernel32.Thread32First
        first.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ThreadEntry32)]
        first.restype = ctypes.c_int
        next_item = kernel32.Thread32Next
        next_item.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ThreadEntry32)]
        next_item.restype = ctypes.c_int
        ok = first(snapshot, ctypes.byref(entry))
        while ok:
            if entry.th32OwnerProcessID == pid:
                return int(entry.th32ThreadID)
            ok = next_item(snapshot, ctypes.byref(entry))
    finally:
        close_handle(snapshot)
    raise ProtocolError("PRIMARY_THREAD_NOT_FOUND")


@dataclass
class Job:
    job_id: str
    profile: str
    run_root: str
    state: str
    submitted_monotonic: float
    deadline_monotonic: float
    scenario: str = "suite"
    result: dict[str, object] | None = None
    receipt_sha256: str | None = None
    process: subprocess.Popen[bytes] | None = None
    os_job_handle: Any = None
    job_api: tuple[Any, ...] | None = None
    cancel_requested: bool = False
    thread: threading.Thread | None = None
    scenario_stage: str = "PREPARING"
    scenario_event_sha256: str | None = None
    scenario_child_pid: int | None = None
    scenario_child_creation_time: int | None = None
    worker_pid: int | None = None
    worker_creation_time: int | None = None
    worker_identity_sha256: str | None = None
    worker_job_pids: list[int] | None = None
    worker_membership_verified: bool = False


class HostExecutor:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or _repo_root()).resolve()
        self._jobs: dict[str, Job] = {}
        self._seen_submit_request_ids: set[str] = set()
        self._lock = threading.RLock()

    def handle(self, request: dict[str, Any]) -> dict[str, object]:
        operation = request["op"]
        if operation == "submit":
            with self._lock:
                request_id = request["request_id"]
                if request_id in self._seen_submit_request_ids:
                    return self._reply(request, ok=False, error="REQUEST_ID_REUSED")
                self._seen_submit_request_ids.add(request_id)
                if any(job.state in {"QUEUED", "RUNNING", "CANCELLING"} for job in self._jobs.values()):
                    return self._reply(request, ok=False, error="JOB_ALREADY_ACTIVE")
                job_id = uuid.uuid4().hex
                now = time.monotonic()
                job = Job(
                    job_id, PROFILE_NAME, "", "QUEUED", now, now + HARD_DEADLINE_SECONDS,
                    scenario=request["scenario"],
                )
                self._jobs[job_id] = job
                job.thread = threading.Thread(target=self._run_job, args=(job,), daemon=False)
                job.thread.start()
            return self._reply(request, ok=True, job_id=job_id, state="QUEUED")
        job = self._jobs.get(str(request.get("job_id")))
        if job is None:
            return self._reply(request, ok=False, error="JOB_NOT_FOUND")
        if operation == "status":
            response: dict[str, object] = {
                "ok": True, "job_id": job.job_id, "state": job.state,
            }
            if job.scenario in {"timeout_child", "cancel_child"}:
                with self._lock:
                    self._observe_child_stage(job)
                response.update({
                    "stage": job.scenario_stage,
                    "child_pid": job.scenario_child_pid,
                    "child_creation_time": job.scenario_child_creation_time,
                    "scenario_event_sha256": job.scenario_event_sha256,
                })
            return self._reply(request, **response)
        if operation == "cancel":
            with self._lock:
                if job.scenario == "cancel_child" and job.state in {"QUEUED", "RUNNING"}:
                    self._observe_child_stage(job)
                    if (
                        job.scenario_stage != "CHILD_STARTED"
                        or not job.scenario_event_sha256
                        or job.scenario_child_pid is None
                        or job.scenario_child_creation_time is None
                    ):
                        return self._reply(
                            request, ok=False, error="CANCEL_REQUIRES_OBSERVED_CHILD_STARTED",
                            job_id=job.job_id, state=job.state, stage=job.scenario_stage,
                            child_pid=job.scenario_child_pid,
                            child_creation_time=job.scenario_child_creation_time,
                        )
                if job.state in {"QUEUED", "RUNNING"}:
                    job.cancel_requested = True
                    job.state = "CANCELLING"
            return self._reply(request, ok=True, job_id=job.job_id, state=job.state)
        if operation == "result":
            if job.state not in {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED", "TIMED_OUT"}:
                return self._reply(request, ok=False, error="JOB_NOT_FINAL", job_id=job.job_id, state=job.state)
            if job.result is None:
                return self._reply(request, ok=False, error="FINAL_RESULT_MISSING", job_id=job.job_id)
            receipt_path = Path(job.run_root) / "receipt.json" if job.run_root else None
            try:
                receipts = list(Path(job.run_root).glob("receipt*.json")) if job.run_root else []
                if receipt_path is None or receipts != [receipt_path] or not receipt_path.is_file():
                    return self._reply(request, ok=False, error="FINAL_RECEIPT_MISSING", job_id=job.job_id)
                disk_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return self._reply(request, ok=False, error="FINAL_RECEIPT_INVALID", job_id=job.job_id)
            if (
                type(disk_receipt) is not dict
                or disk_receipt.get("schema") != "s6-v2-mxc-job-receipt-v1"
                or disk_receipt.get("job_id") != job.job_id
                or disk_receipt != job.result
                or job.receipt_sha256 is None
                or _sha256(receipt_path) != job.receipt_sha256
            ):
                return self._reply(request, ok=False, error="FINAL_RECEIPT_IDENTITY_MISMATCH", job_id=job.job_id)
            return self._reply(request, ok=True, job_id=job.job_id, result=job.result)
        return self._reply(request, ok=False, error="OPERATION_UNAVAILABLE")

    def _observe_child_stage(self, job: Job) -> None:
        """Promote only a canonical, hashed child event confirmed inside the OS job."""
        if job.scenario not in {"timeout_child", "cancel_child"}:
            return
        process = job.process
        if process is None:
            job.scenario_stage = "PREPARING"
            return
        job.scenario_stage = "RUNNING"
        event_path = Path(job.run_root) / "artifacts" / "scenario-event.json" if job.run_root else None
        if event_path is None or _is_redirected(event_path):
            return
        try:
            raw = event_path.read_bytes()
            if not raw or len(raw) > 16_384:
                return
            event = json.loads(raw.decode("utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return
        if (
            type(event) is not dict
            or set(event) != {"schema", "job_id", "scenario", "event", "child_pid", "started"}
            or event.get("schema") != "s6-v2-mxc-scenario-event-v1"
            or event.get("job_id") != job.job_id
            or event.get("scenario") != job.scenario
            or event.get("event") != "child_started"
            or event.get("started") is not True
            or type(event.get("child_pid")) is not int
            or event["child_pid"] <= 0
            or event["child_pid"] == process.pid
            or event["child_pid"] == job.worker_pid
            or not job.worker_membership_verified
            or job.worker_pid is None
            or job.worker_creation_time is None
            or process.poll() is not None
            or job.os_job_handle is None
            or job.job_api is None
        ):
            return
        try:
            query, _, _ = job.job_api
            active_count = _active_process_count(query, job.os_job_handle)
            launcher_creation_before = _process_creation_time(process.pid)
            worker_creation_before = _process_creation_time(job.worker_pid)
            child_creation_before = _process_creation_time(event["child_pid"])
            process_ids = _job_process_ids(query, job.os_job_handle)
            launcher_creation_after = _process_creation_time(process.pid)
            worker_creation_after = _process_creation_time(job.worker_pid)
            child_creation_after = _process_creation_time(event["child_pid"])
        except (OSError, ProtocolError):
            return
        if (
            active_count < 3
            or process.pid not in process_ids
            or job.worker_pid not in process_ids
            or event["child_pid"] not in process_ids
            or launcher_creation_before is None or launcher_creation_before <= 0
            or launcher_creation_after != launcher_creation_before
            or worker_creation_before != job.worker_creation_time
            or worker_creation_after != worker_creation_before
            or child_creation_before is None or child_creation_before <= 0
            or child_creation_after != child_creation_before
        ):
            return
        digest = hashlib.sha256(raw).hexdigest()
        if job.scenario_event_sha256 is not None and job.scenario_event_sha256 != digest:
            return
        if job.scenario_child_pid is not None and job.scenario_child_pid != event["child_pid"]:
            return
        job.scenario_event_sha256 = digest
        job.scenario_child_pid = event["child_pid"]
        job.scenario_child_creation_time = child_creation_before
        job.scenario_stage = "CHILD_STARTED"

    def shutdown(self) -> dict[str, object]:
        """Cancel active work at EOF and report whether all workers/receipts closed safely."""
        with self._lock:
            jobs = list(self._jobs.values())
            for job in jobs:
                if job.state in {"QUEUED", "RUNNING", "CANCELLING"}:
                    job.cancel_requested = True
                    job.state = "CANCELLING"
        for job in jobs:
            if job.os_job_handle is not None and job.job_api is not None:
                try:
                    _, terminate, _ = job.job_api
                    terminate(job.os_job_handle, 3)
                except BaseException:
                    pass
        grace_deadline = time.monotonic() + REAP_RESERVE_SECONDS
        for job in jobs:
            thread = job.thread
            if thread is not None:
                thread.join(timeout=max(0.0, grace_deadline - time.monotonic()))
        reports: list[dict[str, object]] = []
        all_closed = True
        for job in jobs:
            thread_alive = bool(job.thread and job.thread.is_alive())
            active_count: int | None = None
            with self._lock:
                handle = job.os_job_handle
                job.os_job_handle = None
            if handle is not None and job.job_api is not None:
                try:
                    query, terminate, close = job.job_api
                    active_count = _active_process_count(query, handle)
                    if active_count != 0:
                        terminate(handle, 3)
                        while active_count != 0 and time.monotonic() < grace_deadline:
                            time.sleep(min(0.025, max(0.0, grace_deadline - time.monotonic())))
                            active_count = _active_process_count(query, handle)
                except BaseException:
                    active_count = None
                finally:
                    try:
                        close(handle)
                    except BaseException:
                        pass
            thread_alive = bool(job.thread and job.thread.is_alive())
            receipt_ok = False
            if job.run_root and job.result is not None:
                try:
                    receipt_path = Path(job.run_root) / "receipt.json"
                    if list(Path(job.run_root).glob("receipt*.json")) != [receipt_path]:
                        raise OSError("RECEIPT_NOT_UNIQUE")
                    disk_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    receipt_ok = (
                        type(disk_receipt) is dict
                        and disk_receipt.get("schema") == "s6-v2-mxc-job-receipt-v1"
                        and disk_receipt.get("job_id") == job.job_id
                        and disk_receipt == job.result
                        and job.receipt_sha256 is not None
                        and _sha256(receipt_path) == job.receipt_sha256
                    )
                    if job.process is not None and type(disk_receipt) is dict:
                        receipt_ok = receipt_ok and (
                            disk_receipt.get("termination_confirmed") is True
                            and disk_receipt.get("tree_boundary_verified") is True
                            and type(disk_receipt.get("active_process_count")) is int
                            and disk_receipt.get("active_process_count") == 0
                        )
                except (OSError, UnicodeError, json.JSONDecodeError):
                    receipt_ok = False
            process_closed = job.process is None or job.process.poll() is not None
            closed = not thread_alive and process_closed and receipt_ok
            all_closed = all_closed and closed
            reports.append({
                "job_id": job.job_id, "state": job.state, "thread_alive": thread_alive,
                "active_process_count": active_count, "receipt_reconciled": receipt_ok,
                "status": "CLOSED" if closed else "BLOCKED",
            })
        return {
            "protocol": PROTOCOL_VERSION, "request_id": "shutdown", "ok": all_closed,
            "status": "CLOSED" if all_closed else "BLOCKED",
            "error": None if all_closed else "SHUTDOWN_WORKER_OR_RECEIPT_UNRECONCILED",
            "jobs": reports,
        }

    @staticmethod
    def _reply(request: dict[str, Any], **payload: object) -> dict[str, object]:
        return {"protocol": PROTOCOL_VERSION, "request_id": request["request_id"], **payload}

    def _run_job(self, job: Job) -> None:
        run_root: Path | None = None
        started = job.submitted_monotonic
        manifest_before: dict[str, str] | None = None
        profile_digest: str | None = None
        canary: LoopbackNetworkCanary | None = None
        network_evidence: dict[str, object] | None = None
        spec: dict[str, object] = {
            "job_id": job.job_id, "profile": job.profile,
            "selection": _scenario_selection(job.scenario), "profile_selection": PROFILE_SELECTION,
            "scenario": job.scenario,
            "scenario_selector": SCENARIO_ALLOWLIST.get(job.scenario, {}).get("pytest_selector"),
            "deadline_seconds": HARD_DEADLINE_SECONDS,
            "diagnostic_seconds": SCENARIO_ALLOWLIST.get(job.scenario, {}).get("diagnostic_seconds", 0),
            "worker_seconds": SCENARIO_ALLOWLIST.get(job.scenario, {}).get("worker_seconds", 0),
            "isolation": "MXC_JOB_OBJECT_AND_NETWORK_DENIAL_UNVERIFIED",
            # The per-run CODEX_HOME does not establish how managed policy is
            # composed by MXC. Keep this unknown until a supported source proves it.
            "policy_effective": "UNKNOWN",
        }
        spec_digest = hashlib.sha256(_json_bytes(spec)).hexdigest()
        try:
            run_root = _allocate_run(self.repo_root, job.job_id)
            job.run_root = str(run_root)
            _atomic_json(run_root / "runspec-before.json", {"runspec": spec, "sha256": spec_digest})
            if job.cancel_requested:
                raise ProtocolError("CANCELLED_BEFORE_START")
            if os.name != "nt":
                raise ProtocolError("MXC_REQUIRES_ACTUAL_WINDOWS_HOST")
            snapshot, manifest_before = _snapshot_inputs(
                self.repo_root, run_root, deadline=job.deadline_monotonic,
                cancelled=lambda: job.cancel_requested,
            )
            _check_preparation_budget(job.deadline_monotonic, lambda: job.cancel_requested)
            manifest_digest = _manifest_digest(manifest_before)
            python = (self.repo_root / ".venv" / "Scripts" / "python.exe").resolve(strict=True)
            runtime_allowlist = _runtime_allowlist(python)
            _check_preparation_budget(job.deadline_monotonic, lambda: job.cancel_requested)
            output_root = run_root / "artifacts"
            output_root.mkdir()
            (output_root / "tmp").mkdir()
            if job.scenario not in SCENARIO_ALLOWLIST:
                raise ProtocolError("SCENARIO_NOT_ALLOWLISTED")
            canary = LoopbackNetworkCanary(output_root, job.job_id, job.scenario)
            canary.start_and_control()
            _check_preparation_budget(job.deadline_monotonic, lambda: job.cancel_requested)
            environment = _clean_environment(run_root, python, canary)
            spec["launch_environment_names"] = sorted(environment)
            spec["launch_environment_sha256"] = hashlib.sha256(_json_bytes(environment)).hexdigest()
            profile_dir = run_root / "codex-home"
            profile_dir.mkdir()
            profile_override = _permission_override(runtime_allowlist, snapshot, output_root, profile_dir)
            profile_digest = hashlib.sha256(profile_override.encode("utf-8")).hexdigest()
            codex = _codex_executable()
            _check_preparation_budget(job.deadline_monotonic, lambda: job.cancel_requested)
            junit_path = output_root / "junit.xml"
            scenario_selection = _scenario_selection(job.scenario)
            selector_args: list[str] = []
            bootstrap = _pytest_bootstrap(
                snapshot, junit_path, selector_args, job_id=job.job_id,
                scenario=job.scenario, selection=scenario_selection,
                diagnostic_seconds=SCENARIO_ALLOWLIST[job.scenario]["diagnostic_seconds"],
            )
            command = [
                str(codex), "-c", "windows.sandbox=mxc", "-c", profile_override,
                "sandbox", "--include-managed-config", "--permission-profile", PROFILE_NAME,
                "--", str(python), "-I", "-S", "-c", bootstrap,
            ]
            spec["snapshot_manifest_sha256"] = manifest_digest
            spec["permission_profile_sha256"] = profile_digest
            spec["runtime_allowlist"] = [str(path) for path in runtime_allowlist]
            spec_digest = hashlib.sha256(_json_bytes(spec)).hexdigest()
            _atomic_json(run_root / "runspec-before.json", {"runspec": spec, "sha256": spec_digest})
            _check_preparation_budget(job.deadline_monotonic, lambda: job.cancel_requested)
            with self._lock:
                job.state = "RUNNING"
            process, job_handle, job_api = _launch_suspended_in_job(
                command, cwd=snapshot, env=environment,
                stdout_path=output_root / "stdout.log", stderr_path=output_root / "stderr.log",
            )
            job.process = process
            job.os_job_handle = job_handle
            query, terminate, close = job_api
            job.job_api = job_api
            _confirm_worker_membership(
                job, output_root=output_root, job_handle=job_handle, query=query,
                start_nonce=canary.worker_start_nonce, deadline=job.deadline_monotonic,
                cancelled=lambda: job.cancel_requested,
            )
            worker_limit = SCENARIO_ALLOWLIST[job.scenario]["worker_seconds"]
            worker_deadline = min(job.deadline_monotonic - REAP_RESERVE_SECONDS, time.monotonic() + worker_limit)
            timed_out = False
            termination_sent = False
            while process.poll() is None:
                if job.cancel_requested:
                    terminate(job_handle, 3)
                    termination_sent = True
                    break
                if job.scenario in {"timeout_child", "cancel_child"}:
                    with self._lock:
                        self._observe_child_stage(job)
                if time.monotonic() >= worker_deadline:
                    timed_out = True
                    terminate(job_handle, 3)
                    termination_sent = True
                    break
                if (output_root / "stdout.log").stat().st_size > MAX_STDIO_BYTES or (output_root / "stderr.log").stat().st_size > MAX_STDIO_BYTES:
                    timed_out = True
                    terminate(job_handle, 4)
                    termination_sent = True
                    break
                time.sleep(min(0.05, max(0.0, worker_deadline - time.monotonic())))
            reap_deadline = min(job.deadline_monotonic, time.monotonic() + REAP_RESERVE_SECONDS)
            while time.monotonic() < reap_deadline:
                process_exit = process.poll()
                try:
                    active_count = _active_process_count(query, job_handle)
                except OSError:
                    active_count = None
                if process_exit is not None and active_count == 0:
                    break
                if process_exit is not None and not termination_sent:
                    terminate(job_handle, 3)
                    termination_sent = True
                time.sleep(0.025)
            process_exit = process.poll()
            try:
                active_count = _active_process_count(query, job_handle)
                active_pids = _job_process_ids(query, job_handle)
            except OSError:
                active_count = None
                active_pids = None
            tree_confirmed = (
                process_exit is not None and active_count == 0 and active_pids == set()
                and job.worker_membership_verified and job.worker_pid is not None
                and job.worker_creation_time is not None
            )
            if not tree_confirmed:
                if not termination_sent:
                    terminate(job_handle, 3)
            close(job_handle)
            job.os_job_handle = None
            if canary is not None:
                network_evidence = canary.finish(output_root / "network-canary-worker.json")
            manifest_after: dict[str, str] = {}
            for name in manifest_before:
                _check_finalization_budget(job.deadline_monotonic)
                manifest_after[name] = _sha256(
                    snapshot / name, deadline=job.deadline_monotonic,
                    cancelled=lambda: False, finalizing=True,
                )
            if manifest_before != manifest_after:
                outcome, reason = "BLOCKED", "SNAPSHOT_DRIFT"
            elif not tree_confirmed:
                outcome, reason = "BLOCKED", "PROCESS_TREE_UNCONFIRMED"
            elif network_evidence is None:
                outcome, reason = "BLOCKED", "NETWORK_CANARY_EVIDENCE_MISSING"
            elif network_evidence.get("result") == "FAIL":
                outcome, reason = "FAIL", str(network_evidence.get("reason"))
            elif network_evidence.get("result") != "PASS":
                outcome, reason = "BLOCKED", str(network_evidence.get("reason"))
            elif job.scenario in {"timeout_child", "cancel_child"}:
                outcome, reason = _reconcile_child_scenario(
                    output_root / "junit.xml", output_root / "scenario-event.json",
                    job_id=job.job_id, scenario=job.scenario, selection=scenario_selection,
                    process_exit=process_exit, active_process_count=active_count,
                    worker_pid=job.worker_pid, timed_out=timed_out,
                    cancel_requested=job.cancel_requested,
                    expected_event_sha256=job.scenario_event_sha256,
                    expected_child_pid=job.scenario_child_pid,
                    expected_child_creation_time=job.scenario_child_creation_time,
                )
            elif timed_out:
                outcome, reason = "BLOCKED", "HARD_DEADLINE_REACHED"
            elif job.cancel_requested:
                outcome, reason = "BLOCKED", "CANCELLED"
            elif job.scenario == "controlled_failure":
                outcome, reason = _reconcile_controlled_failure(
                    output_root / "junit.xml", job_id=job.job_id, scenario=job.scenario,
                    selection=scenario_selection, exit_code=process_exit,
                )
            else:
                outcome, reason = _reconcile_junit(
                    output_root / "junit.xml", output_root / "stdout.log", output_root / "stderr.log",
                    job_id=job.job_id, scenario=job.scenario, selection=scenario_selection,
                    exit_code=process_exit,
                )
            if outcome == "PASS":
                outcome, reason = "BLOCKED", "POLICY_EFFECTIVE_UNKNOWN"
            if time.monotonic() >= job.deadline_monotonic:
                outcome, reason = "BLOCKED", "HARD_DEADLINE_EXCEEDED_BEFORE_RECEIPT"
            receipt: dict[str, object] = {
                "schema": "s6-v2-mxc-job-receipt-v1", "job_id": job.job_id,
                "profile": job.profile, "scenario": job.scenario,
                "selection": scenario_selection, "profile_selection": PROFILE_SELECTION,
                "result": outcome,
                "reason": reason, "exit_code": process_exit, "termination_confirmed": tree_confirmed,
                "policy_effective": "UNKNOWN",
                "active_process_count": active_count, "tree_boundary_verified": tree_confirmed,
                "deadline_configured_seconds": HARD_DEADLINE_SECONDS,
                "deadline_applied_seconds": time.monotonic() - started,
                "worker_limit_seconds": SCENARIO_ALLOWLIST[job.scenario]["worker_seconds"],
                "diagnostic_seconds": SCENARIO_ALLOWLIST[job.scenario]["diagnostic_seconds"],
                "snapshot_sha256_before": manifest_before,
                "snapshot_sha256_after": manifest_after, "snapshot_manifest_sha256": manifest_digest,
                "runspec_sha256_before": spec_digest, "runspec_sha256_after": spec_digest,
                "permission_profile_sha256": profile_digest,
                "runtime_allowlist": [str(path) for path in runtime_allowlist],
                "stdout_path": str(output_root / "stdout.log"), "stderr_path": str(output_root / "stderr.log"),
                "junit_path": str(output_root / "junit.xml"),
                "junit_counts": _junit_counts(output_root / "junit.xml"),
                "network_canary": network_evidence,
                "scenario_stage": job.scenario_stage,
                "scenario_event_sha256": job.scenario_event_sha256,
                "scenario_child_pid": job.scenario_child_pid,
                "scenario_child_creation_time": job.scenario_child_creation_time,
                "worker_pid": job.worker_pid,
                "worker_creation_time": job.worker_creation_time,
                "worker_identity_sha256": job.worker_identity_sha256,
                "worker_membership_verified": job.worker_membership_verified,
                "worker_job_pids_at_start": job.worker_job_pids,
                "job_pids_after_exit": sorted(active_pids) if active_pids is not None else None,
                "network_canary_sha256": _sha256(output_root / "network-canary.json")
                if (output_root / "network-canary.json").is_file() else None,
                "stdout_sha256": _sha256(output_root / "stdout.log"),
                "stderr_sha256": _sha256(output_root / "stderr.log"),
                "junit_sha256": _sha256(output_root / "junit.xml") if (output_root / "junit.xml").is_file() else None,
                "elapsed_seconds": time.monotonic() - started,
            }
            if (run_root / "receipt.json").exists():
                raise ProtocolError("DUPLICATE_FINAL_RECEIPT")
            _atomic_json(run_root / "runspec-after.json", {"runspec": spec, "sha256": spec_digest})
            _atomic_json(run_root / "receipt.json", receipt)
            job.receipt_sha256 = _sha256(run_root / "receipt.json")
            with self._lock:
                job.result = receipt
                if outcome == "PASS":
                    job.state = "COMPLETED"
                elif outcome == "FAIL":
                    job.state = "FAILED"
                elif outcome == "TIMED_OUT":
                    job.state = "TIMED_OUT"
                elif outcome == "CANCELLED":
                    job.state = "CANCELLED"
                else:
                    job.state = "BLOCKED"
        except BaseException as exc:
            reason = exc.args[0] if isinstance(exc, ProtocolError) and exc.args else "EXECUTOR_BLOCKED"
            termination_confirmed = False
            active_count = None
            active_pids: set[int] | None = None
            worker_gone = False
            if job.os_job_handle is not None and job.job_api is not None:
                query, terminate, close = job.job_api
                try:
                    terminate(job.os_job_handle, 3)
                    if job.process is not None:
                        try:
                            job.process.wait(timeout=REAP_RESERVE_SECONDS)
                        except subprocess.TimeoutExpired:
                            pass
                    active_count = _active_process_count(query, job.os_job_handle)
                    active_pids = _job_process_ids(query, job.os_job_handle)
                except BaseException:
                    active_count = None
                    active_pids = None
                finally:
                    try:
                        close(job.os_job_handle)
                    except BaseException:
                        pass
                    job.os_job_handle = None
            if job.worker_pid is not None and job.worker_creation_time is not None:
                current_creation = _process_creation_time(job.worker_pid)
                if current_creation != job.worker_creation_time:
                    worker_gone = True
            termination_confirmed = (
                job.worker_membership_verified and active_count == 0
                and active_pids == set() and worker_gone
            )
            if canary is not None and not canary._closed:
                try:
                    network_evidence = canary.finish(Path(job.run_root) / "artifacts" / "network-canary-worker.json")
                except BaseException:
                    canary.close()
            receipt = {
                "schema": "s6-v2-mxc-job-receipt-v1", "job_id": job.job_id,
                "profile": job.profile, "scenario": job.scenario,
                "selection": _scenario_selection(job.scenario),
                "profile_selection": PROFILE_SELECTION, "result": "BLOCKED",
                "reason": str(reason), "exit_code": job.process.poll() if job.process is not None else None,
                "policy_effective": "UNKNOWN",
                "termination_confirmed": termination_confirmed,
                "active_process_count": active_count, "tree_boundary_verified": termination_confirmed,
                "deadline_configured_seconds": HARD_DEADLINE_SECONDS,
                "deadline_applied_seconds": time.monotonic() - started,
                "worker_limit_seconds": SCENARIO_ALLOWLIST[job.scenario]["worker_seconds"],
                "diagnostic_seconds": SCENARIO_ALLOWLIST[job.scenario]["diagnostic_seconds"],
                "runspec_sha256_before": spec_digest, "runspec_sha256_after": spec_digest,
                "snapshot_sha256_before": manifest_before,
                "snapshot_sha256_after": None,
                "network_canary": network_evidence,
                "scenario_stage": job.scenario_stage,
                "scenario_event_sha256": job.scenario_event_sha256,
                "scenario_child_pid": job.scenario_child_pid,
                "scenario_child_creation_time": job.scenario_child_creation_time,
                "network_canary_sha256": _sha256(Path(job.run_root) / "artifacts" / "network-canary.json")
                if job.run_root and (Path(job.run_root) / "artifacts" / "network-canary.json").is_file() else None,
                "permission_profile_sha256": profile_digest,
                "elapsed_seconds": time.monotonic() - started,
            }
            if run_root is not None and not (run_root / "receipt.json").exists():
                try:
                    _atomic_json(run_root / "runspec-after.json", {"runspec": spec, "sha256": spec_digest})
                    _atomic_json(run_root / "receipt.json", receipt)
                except OSError:
                    pass
            if run_root is not None and (run_root / "receipt.json").is_file():
                try:
                    job.receipt_sha256 = _sha256(run_root / "receipt.json")
                except OSError:
                    job.receipt_sha256 = None
            with self._lock:
                job.result = receipt
                job.state = "BLOCKED"


def _junit_counts(path: Path) -> dict[str, int] | None:
    """Return reconciliable testcase counts without exposing test output."""
    if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    cases = list(root.iter("testcase"))
    failures = sum(1 for case in cases if case.find("failure") is not None)
    errors = sum(1 for case in cases if case.find("error") is not None)
    skipped = sum(1 for case in cases if case.find("skipped") is not None)
    return {
        "tests": len(cases), "passed": len(cases) - failures - errors - skipped,
        "failures": failures, "errors": errors, "skipped": skipped,
    }


def _junit_counts_from_root(root: ET.Element) -> dict[str, int]:
    cases = list(root.iter("testcase"))
    return {
        "tests": len(cases),
        "failures": sum(1 for case in cases if case.find("failure") is not None),
        "errors": sum(1 for case in cases if case.find("error") is not None),
        "skipped": sum(1 for case in cases if case.find("skipped") is not None),
    }


def _junit_declared_counts_match(root: ET.Element) -> bool:
    """Require every declared JUnit aggregate to match its testcase subtree."""
    aggregate_names = ("tests", "failures", "errors", "skipped")
    suites = list(root.iter("testsuite"))
    if root.tag == "testsuite" and root not in suites:
        suites.insert(0, root)
    if not suites:
        return False
    for suite in suites:
        actual = _junit_counts_from_root(suite)
        for name in aggregate_names:
            declared = suite.get(name)
            if declared is None or not declared.isdecimal() or int(declared) != actual[name]:
                return False
    if root.tag == "testsuites":
        actual = _junit_counts_from_root(root)
        for name in aggregate_names:
            declared = root.get(name)
            if declared is None or not declared.isdecimal() or int(declared) != actual[name]:
                return False
    return True


def _reconcile_junit(
    path: Path, stdout: Path, stderr: Path, *, job_id: str, scenario: str,
    selection: str, exit_code: int | None,
) -> tuple[str, str]:
    if exit_code is None:
        return "INCOMPLETE", "PROCESS_EXIT_MISSING"
    if not path.is_file():
        return "INCOMPLETE", "JUNIT_MISSING"
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return "INCOMPLETE", "JUNIT_INVALID"
    cases = list(root.iter("testcase"))
    if not _junit_declared_counts_match(root):
        return "INCOMPLETE", "JUNIT_AGGREGATE_MISMATCH"
    expected_properties = {
        "s6_job_id": job_id, "s6_scenario": scenario, "s6_selection": selection,
    }
    for case in cases:
        property_nodes = case.findall("./properties/property")
        for name, expected in expected_properties.items():
            values = [node.get("value") for node in property_nodes if node.get("name") == name]
            if values != [expected]:
                return "INCOMPLETE", f"JUNIT_{name.upper()}_MISMATCH"
    identities = [prop.get("value") for prop in root.iter("property") if prop.get("name") == "s6_job_id"]
    scenarios = [prop.get("value") for prop in root.iter("property") if prop.get("name") == "s6_scenario"]
    selections = [prop.get("value") for prop in root.iter("property") if prop.get("name") == "s6_selection"]
    if len(identities) != len(cases) or any(identity != job_id for identity in identities):
        return "INCOMPLETE", "JUNIT_IDENTITY_MISMATCH"
    if len(scenarios) != len(cases) or any(value != scenario for value in scenarios):
        return "INCOMPLETE", "JUNIT_SCENARIO_MISMATCH"
    if len(selections) != len(cases) or any(value != selection for value in selections):
        return "INCOMPLETE", "JUNIT_SELECTION_MISMATCH"
    if not cases:
        return "INCOMPLETE", "JUNIT_EMPTY"
    failures = sum(1 for case in cases if case.find("failure") is not None or case.find("error") is not None)
    skipped = sum(1 for case in cases if case.find("skipped") is not None)
    if skipped:
        return "FAIL", "JUNIT_SKIPPED"
    if failures or exit_code != 0:
        return "FAIL", "JUNIT_OR_EXIT_FAILURE"
    if not stdout.is_file() or not stderr.is_file():
        return "INCOMPLETE", "JOB_STREAM_MISSING"
    if stdout.stat().st_size > MAX_STDIO_BYTES or stderr.stat().st_size > MAX_STDIO_BYTES:
        return "INCOMPLETE", "JOB_STREAM_LIMIT_EXCEEDED"
    return "PASS", "WORKER_PASS_WITH_CANARY"


def _reconcile_child_scenario(
    junit_path: Path, event_path: Path, *, job_id: str, scenario: str,
    selection: str, process_exit: int | None, active_process_count: int | None,
    worker_pid: int, timed_out: bool, cancel_requested: bool,
    expected_event_sha256: str | None, expected_child_pid: int | None,
    expected_child_creation_time: int | None,
) -> tuple[str, str]:
    """Reconcile worker-written pre-termination evidence for fixed child scenarios."""
    if scenario not in {"timeout_child", "cancel_child"}:
        return "BLOCKED", "CHILD_SCENARIO_NOT_ALLOWLISTED"
    if not _valid_id(job_id) or selection != _scenario_selection(scenario):
        return "BLOCKED", "CHILD_SCENARIO_IDENTITY_INVALID"
    if process_exit is None or type(active_process_count) is not int or active_process_count != 0:
        return "BLOCKED", "CHILD_PROCESS_TREE_UNCONFIRMED"
    if (
        expected_event_sha256 is None or type(expected_child_pid) is not int
        or expected_child_pid <= 0 or type(expected_child_creation_time) is not int
        or expected_child_creation_time <= 0
    ):
        return "BLOCKED", "CHILD_JOB_MEMBERSHIP_NOT_OBSERVED"
    try:
        if _is_redirected(event_path) or not event_path.is_file() or event_path.stat().st_size > 16_384:
            return "BLOCKED", "CHILD_SCENARIO_EVENT_MISSING"
        event_bytes = event_path.read_bytes()
        event = json.loads(event_bytes.decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "BLOCKED", "CHILD_SCENARIO_EVENT_INVALID"
    event_digest = hashlib.sha256(event_bytes).hexdigest()
    if expected_event_sha256 is not None and event_digest != expected_event_sha256:
        return "BLOCKED", "CHILD_SCENARIO_EVENT_HASH_MISMATCH"
    expected_event_keys = {"schema", "job_id", "scenario", "event", "child_pid", "started"}
    if (
        type(event) is not dict or set(event) != expected_event_keys
        or event.get("schema") != "s6-v2-mxc-scenario-event-v1"
        or event.get("job_id") != job_id or event.get("scenario") != scenario
        or event.get("event") != "child_started" or event.get("started") is not True
        or type(event.get("child_pid")) is not int or event["child_pid"] <= 0
        or type(worker_pid) is not int or worker_pid <= 0 or event["child_pid"] == worker_pid
        or (expected_child_pid is not None and event["child_pid"] != expected_child_pid)
    ):
        return "BLOCKED", "CHILD_SCENARIO_EVENT_IDENTITY_MISMATCH"
    if not junit_path.is_file() or junit_path.stat().st_size > 4 * 1024 * 1024:
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_MISSING"
    try:
        root = ET.parse(junit_path).getroot()
    except (ET.ParseError, OSError):
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_INVALID"
    if root.tag != "testsuite" or not _junit_declared_counts_match(root):
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_AGGREGATE_MISMATCH"
    expected_properties = {
        "s6_job_id": job_id, "s6_scenario": scenario, "s6_selection": selection,
    }
    cases = list(root.iter("testcase"))
    expected_name = selection.rsplit("::", 1)[-1]
    if len(cases) != 1 or cases[0].get("name") != expected_name:
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_TESTCASE_MISMATCH"
    case = cases[0]
    actual_properties: dict[str, str | None] = {}
    for prop in case.findall("./properties/property"):
        name = prop.get("name")
        if name in expected_properties:
            if name in actual_properties:
                return "BLOCKED", "CHILD_SCENARIO_JUNIT_IDENTITY_DUPLICATE"
            actual_properties[name] = prop.get("value")
    if actual_properties != expected_properties:
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_IDENTITY_MISMATCH"
    if any(
        prop.get("name") in expected_properties
        for prop in root.findall("./properties/property")
    ):
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_IDENTITY_SCOPE_MISMATCH"
    if case.find("failure") is not None or case.find("error") is not None or case.find("skipped") is not None:
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_EVENT_NOT_CLEAN"
    expected_marker = (
        f"S6_EXPECTED_EVENT=child_started;job_id={job_id};scenario={scenario};"
        f"child_pid={event['child_pid']}"
    )
    if case.findtext("system-out") != expected_marker:
        return "BLOCKED", "CHILD_SCENARIO_JUNIT_EVENT_MISMATCH"
    if scenario == "timeout_child":
        if not timed_out or cancel_requested:
            return "BLOCKED", "CHILD_SCENARIO_TIMEOUT_NOT_OBSERVED"
        return "TIMED_OUT", "EXPECTED_TIMEOUT_CHILD_REAPED"
    if not cancel_requested or timed_out:
        return "BLOCKED", "CHILD_SCENARIO_CANCEL_NOT_OBSERVED"
    return "CANCELLED", "EXPECTED_CANCEL_CHILD_REAPED"


def _reconcile_controlled_failure(
    path: Path, *, job_id: str, scenario: str, selection: str, exit_code: int | None,
) -> tuple[str, str]:
    """Accept only the fixed expected failure from the controlled-failure node."""
    if scenario != "controlled_failure" or selection != _scenario_selection(scenario):
        return "BLOCKED", "CONTROLLED_FAILURE_SCENARIO_INVALID"
    if exit_code != 1 or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        return "BLOCKED", "CONTROLLED_FAILURE_OUTCOME_UNEXPECTED"
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return "BLOCKED", "CONTROLLED_FAILURE_JUNIT_INVALID"
    if not _junit_declared_counts_match(root):
        return "BLOCKED", "CONTROLLED_FAILURE_JUNIT_AGGREGATE_MISMATCH"
    cases = list(root.iter("testcase"))
    if len(cases) != 1:
        return "BLOCKED", "CONTROLLED_FAILURE_JUNIT_TESTCASE_MISMATCH"
    case = cases[0]
    if case.get("name") != selection.rsplit("::", 1)[-1]:
        return "BLOCKED", "CONTROLLED_FAILURE_JUNIT_TESTCASE_MISMATCH"
    failures = case.findall("failure")
    if len(failures) != 1 or case.find("error") is not None or case.find("skipped") is not None:
        return "BLOCKED", "CONTROLLED_FAILURE_JUNIT_FAILURE_MISMATCH"
    expected_message = f"S6_MXC_EXPECTED_CONTROLLED_FAILURE job_id={job_id}"
    if failures[0].get("message") != expected_message:
        if failures[0].get("message") != f"Failed: {expected_message}":
            return "BLOCKED", "CONTROLLED_FAILURE_JUNIT_FAILURE_MISMATCH"
    for name, expected in (
        ("s6_job_id", job_id), ("s6_scenario", scenario), ("s6_selection", selection),
    ):
        values = [prop.get("value") for prop in case.findall("./properties/property") if prop.get("name") == name]
        if values != [expected]:
            return "BLOCKED", "CONTROLLED_FAILURE_JUNIT_IDENTITY_MISMATCH"
    return "FAIL", "EXPECTED_CONTROLLED_FAILURE"


def serve(input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> int:
    executor = HostExecutor()
    while True:
        raw = input_stream.readline(MAX_REQUEST_BYTES + 2)
        if raw == "":
            break
        if len(raw.encode("utf-8", errors="replace")) > MAX_REQUEST_BYTES:
            while raw and not raw.endswith("\n"):
                raw = input_stream.readline(MAX_REQUEST_BYTES + 2)
            output_stream.write(json.dumps({
                "protocol": PROTOCOL_VERSION, "request_id": "unknown",
                "ok": False, "error": "FRAME_TOO_LARGE",
            }, sort_keys=True, separators=(",", ":")) + "\n")
            output_stream.flush()
            continue
        request_id = "unknown"
        try:
            request = parse_request(raw.rstrip("\r\n"))
            request_id = request["request_id"]
            response = executor.handle(request)
        except ProtocolError as exc:
            response = {"protocol": PROTOCOL_VERSION, "request_id": request_id, "ok": False, "error": str(exc)}
        except BaseException:
            response = {"protocol": PROTOCOL_VERSION, "request_id": request_id, "ok": False, "error": "CONTROL_FAILURE"}
        output_stream.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
        output_stream.flush()
    shutdown = executor.shutdown()
    output_stream.write(json.dumps(shutdown, sort_keys=True, separators=(",", ":")) + "\n")
    output_stream.flush()
    return 0 if shutdown.get("ok") is True else 3


if __name__ == "__main__":
    raise SystemExit(serve())
