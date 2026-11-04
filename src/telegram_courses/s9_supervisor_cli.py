"""Restricted S9 entry points for the existing application CLI.

The smoke path remains offline. The queue path runs only under the external
Windows supervisor and reuses a G1-started durable deadline; it does not
orchestrate or attest the complete G1-G9 sequence.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import math
import os
import secrets
import stat
import sys
import sysconfig
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from telegram_courses.s9_operational_ledger import (
    S9_MEASUREMENT_SOURCE_ENV,
    S9_OPERATIONAL_GATE_ENV,
    LedgerError,
    S9OperationalLedger,
    _create_private_directory,
    _open_private_directory_guard,
    _verify_private_file,
)
from telegram_courses.s9_supervisor import (
    STAGE_TIMEOUTS_SECONDS,
    SupervisorResult,
    WindowsCliSupervisor,
)
from telegram_courses.s9_supervisor_handshake import (
    HANDSHAKE_DIR_ENV,
    HANDSHAKE_NONCE_ENV,
    S9_LEDGER_PATH_ENV,
    S9_PROFILE_ENV,
    S9_SUPERVISED_CHILD_ENV,
    confirmation_callbacks,
)

_CHILD_ENVIRONMENT_KEYS = {
    "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT",
    "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432",
}
_S9_STAGE_ENV = "TELEGRAM_COURSES_S9_STAGE"


class OfflineRunnerError(RuntimeError):
    """Safe, stable failure from the restricted offline integration runner."""


def _trusted_python_command(bootstrap: str) -> list[str]:
    """On Windows, supervise the interpreter itself rather than a venv launcher."""
    if os.name != "nt" or sys.prefix == sys.base_prefix:
        return [sys.executable, "-I", "-c", bootstrap]
    try:
        prefix = Path(sys.prefix).resolve(strict=True)
        site_path = Path(sysconfig.get_path("purelib")).resolve(strict=True)
        base_path = Path(sys._base_executable).resolve(strict=True)
        if (
            site_path != prefix / "Lib" / "site-packages"
            or not site_path.is_dir()
            or not base_path.is_file()
        ):
            raise OfflineRunnerError("TRUSTED_PYTHON_ENVIRONMENT_INVALID")
    except (OSError, TypeError, ValueError, AttributeError):
        raise OfflineRunnerError("TRUSTED_PYTHON_ENVIRONMENT_INVALID") from None
    # -S prevents base global site packages and .pth files from loading; add
    # only the venv's existing site directory, as the normal venv startup does.
    setup = (
        "import sys, site\n"
        f"sys.prefix = sys.exec_prefix = {str(prefix)!r}\n"
        f"site.addsitedir({str(site_path)!r})\n"
    )
    return [str(base_path), "-IS", "-c", setup + bootstrap]


_TRUSTED_CLI_BOOTSTRAP = r"""
import importlib.util
import os
import runpy
import sys

expected = os.path.normcase(os.path.realpath(sys.argv[1]))
arguments = sys.argv[2:]
spec = importlib.util.find_spec("telegram_courses.cli")
actual = None if spec is None else spec.origin
if not actual or os.path.normcase(os.path.realpath(actual)) != expected:
    sys.stderr.write("trusted CLI module origin unavailable\n")
    raise SystemExit(125)
if (
    arguments == ["smoke"]
    and (
        os.environ.get("TELEGRAM_COURSES_S9_SUPERVISED_CHILD") != "1"
        or os.environ.get("TELEGRAM_COURSES_S9_STAGE") == "verification_local"
    )
):
    pass
elif (
    os.environ.get("TELEGRAM_COURSES_S9_SUPERVISED_CHILD") == "1"
    and os.environ.get("TELEGRAM_COURSES_S9_LEDGER_PATH")
    and os.environ.get("TELEGRAM_COURSES_S9_STAGE") == "scan"
    and arguments[:1] == ["scan"]
):
    pass
elif (
    os.environ.get("TELEGRAM_COURSES_S9_SUPERVISED_CHILD") == "1"
    and os.environ.get("TELEGRAM_COURSES_S9_LEDGER_PATH")
    and (
        os.environ.get("TELEGRAM_COURSES_S9_STAGE") == "catalog"
        and arguments[:2] == ["catalog", "build"]
        or os.environ.get("TELEGRAM_COURSES_S9_STAGE") == "inspection"
        and arguments[:2] in (["catalog", "show"], ["catalog", "items"])
    )
    and arguments[:1] == ["catalog"]
):
    pass
elif (
    arguments[:2] == ["download", "queue"]
    and "--confirm" not in arguments
    and not any(item.startswith("--confirm=") for item in arguments)
    and os.environ.get("TELEGRAM_COURSES_S9_SUPERVISED_CHILD") == "1"
    and os.environ.get("TELEGRAM_COURSES_S9_LEDGER_PATH")
    and os.environ.get("TELEGRAM_COURSES_S9_PROFILE") in {"F", "M"}
    and os.environ.get("TELEGRAM_COURSES_S9_MEASUREMENT_SOURCE") in {
        "GATEWAY_RESPONSE", "SYNTHETIC_TEST",
    }
    and os.environ.get("TELEGRAM_COURSES_S9_HANDSHAKE_DIR")
    and os.environ.get("TELEGRAM_COURSES_S9_HANDSHAKE_NONCE")
):
    pass
else:
    sys.stderr.write("offline command rejected\n")
    raise SystemExit(125)
sys.argv = ["telegram-courses", *arguments]
module = runpy.run_module("telegram_courses.cli", run_name="telegram_courses_s9_child")
exit_code = module["main"](arguments)
if os.environ.get("TELEGRAM_COURSES_S9_SUPERVISED_CHILD") == "1":
    try:
        from telegram_courses.operational_logging import finalize_s9_child_exit_code
        exit_code = finalize_s9_child_exit_code(exit_code)
    except Exception:
        exit_code = 125
raise SystemExit(exit_code)
""".strip()


_TRUSTED_G1_BOOTSTRAP = r"""
import importlib.util
import json
import os
import runpy
import sys

def diagnostic(phase, state, failure):
    try:
        sys.stderr.write(json.dumps({"event": "s9.g1.diagnostic", "phase": phase,
                                    "state": state, "failure_class": failure},
                                   separators=(",", ":")) + "\n")
        sys.stderr.flush()
    except Exception:
        pass

diagnostic("bootstrap", "START", "NONE")
try:
    expected = os.path.normcase(os.path.realpath(sys.argv[1]))
except (IndexError, OSError, ValueError):
    diagnostic("bootstrap", "FAILURE", "INVALID_ARGUMENTS")
    raise SystemExit(1) from None
arguments = sys.argv[2:]
try:
    spec = importlib.util.find_spec("telegram_courses.s9_real_gate_producers")
except Exception:
    diagnostic("bootstrap", "FAILURE", "MODULE_LOOKUP_ERROR")
    raise SystemExit(1) from None
actual = None if spec is None else spec.origin
if not actual or os.path.normcase(os.path.realpath(actual)) != expected:
    diagnostic("bootstrap", "BLOCKED", "MODULE_ORIGIN_MISMATCH")
    sys.stderr.write("trusted G1 producer unavailable\n")
    raise SystemExit(125)
if (
    os.environ.get("TELEGRAM_COURSES_S9_SUPERVISED_CHILD") != "1"
    or not os.environ.get("TELEGRAM_COURSES_S9_LEDGER_PATH")
    or os.environ.get("TELEGRAM_COURSES_S9_STAGE") != "discovery"
):
    diagnostic("bootstrap", "BLOCKED", "INVALID_ENVIRONMENT")
    sys.stderr.write("supervised G1 command rejected\n")
    raise SystemExit(125)
try:
    module = runpy.run_module(
        "telegram_courses.s9_real_gate_producers",
        run_name="telegram_courses_s9_g1_child",
    )
except Exception:
    diagnostic("worker_entry", "FAILURE", "MODULE_LOAD_ERROR")
    raise SystemExit(1) from None
exit_code = 4
try:
    exit_code = module["g1_worker_main"](arguments)
except Exception:
    diagnostic("worker_entry", "FAILURE", "UNHANDLED_WORKER_ERROR")
    raise SystemExit(1) from None
finally:
    try:
        from telegram_courses.operational_logging import finalize_s9_child_exit_code
        worker_exit_code = exit_code
        exit_code = finalize_s9_child_exit_code(exit_code)
        if exit_code == 125 and worker_exit_code != 125:
            diagnostic("t24_finalization", "FAILURE", "FINALIZATION_FAILED")
    except Exception:
        diagnostic("t24_finalization", "FAILURE", "FINALIZATION_EXCEPTION")
        exit_code = 125
raise SystemExit(exit_code)
""".strip()


def _trusted_cli_module_origin() -> Path:
    """Pin the child import to the CLI module backing this loaded package."""
    try:
        loaded_file = Path(__file__).resolve(strict=True)
        expected = loaded_file.with_name("cli.py").resolve(strict=True)
        expected_info = expected.lstat()
        package = sys.modules.get("telegram_courses")
        package_paths = getattr(package, "__path__", ())
        search_roots = {Path(item).resolve(strict=True) for item in package_paths}
        spec = importlib.util.find_spec("telegram_courses.cli")
    except (OSError, RuntimeError, ValueError, TypeError, ImportError):
        raise OfflineRunnerError("TRUSTED_CLI_MODULE_UNAVAILABLE") from None
    if (
        not expected.is_file()
        or os.path.normcase(str(expected.parent))
        != os.path.normcase(str(loaded_file.parent))
        or getattr(expected_info, "st_file_attributes", 0) & 0x400
        or expected.parent not in search_roots
        or spec is None
        or not spec.origin
    ):
        raise OfflineRunnerError("TRUSTED_CLI_MODULE_UNAVAILABLE")
    try:
        actual = Path(spec.origin).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        raise OfflineRunnerError("TRUSTED_CLI_MODULE_UNAVAILABLE") from None
    if os.path.normcase(str(actual)) != os.path.normcase(str(expected)):
        raise OfflineRunnerError("TRUSTED_CLI_MODULE_UNAVAILABLE")
    return expected


@dataclass(frozen=True)
class OfflineRunOutcome:
    supervisor: SupervisorResult
    ledger_path: Path
    ledger_status: str
    ledger_result: str


@dataclass(frozen=True)
class S9RunContext:
    run_directory: Path
    ledger_path: Path
    run_id: str
    deadline_ns: int


@dataclass(frozen=True)
class SupervisedQueueOutcome:
    supervisor: SupervisorResult
    ledger_path: Path
    ledger_status: str
    ledger_result: str
    queue_gate_result: str
    deadline_ns: int


@dataclass(frozen=True)
class SupervisedG8Outcome:
    phase: str
    supervisor: SupervisorResult
    ledger_path: Path
    ledger_status: str
    ledger_result: str
    gate_result: str
    deadline_ns: int
    receipt_path: Path | None


@dataclass(frozen=True)
class SupervisedStageOutcome:
    supervisor: SupervisorResult
    ledger_path: Path
    ledger_status: str
    ledger_result: str
    stage: str
    stage_gate: str
    stage_gate_result: str
    deadline_ns: int


def _trusted_module_origin(module_name: str, filename: str) -> Path:
    """Pin a supervised child module to the loaded application package."""
    try:
        loaded_file = Path(__file__).resolve(strict=True)
        expected = loaded_file.with_name(filename).resolve(strict=True)
        expected_info = expected.lstat()
        package = sys.modules.get("telegram_courses")
        package_paths = getattr(package, "__path__", ())
        search_roots = {Path(item).resolve(strict=True) for item in package_paths}
        spec = importlib.util.find_spec(module_name)
        actual = Path(spec.origin).resolve(strict=True) if spec and spec.origin else None
    except (OSError, RuntimeError, ValueError, TypeError, ImportError):
        raise OfflineRunnerError("TRUSTED_CHILD_MODULE_UNAVAILABLE") from None
    if (
        not expected.is_file()
        or expected.parent != loaded_file.parent
        or getattr(expected_info, "st_file_attributes", 0) & 0x400
        or expected.parent not in search_roots
        or actual is None
        or os.path.normcase(str(actual)) != os.path.normcase(str(expected))
    ):
        raise OfflineRunnerError("TRUSTED_CHILD_MODULE_UNAVAILABLE")
    return expected


class _QueueRunLock:
    """Prevent overlapping supervised children for one durable S9 run."""

    _CONTENT = b"S9QUEUE1"

    def __init__(self, ledger_path: Path) -> None:
        self.path = ledger_path.with_name("queue-run.lock")
        self.descriptor: int | None = None
        self._locking_module = None

    def __enter__(self) -> _QueueRunLock:
        if os.path.lexists(self.path):
            info = self.path.lstat()
            if (
                not self.path.is_file()
                or self.path.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise OfflineRunnerError("QUEUE_LOCK_UNSAFE")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            self.descriptor = os.open(self.path, flags, 0o600)
            _verify_private_file(self.path)
            info = os.fstat(self.descriptor)
            if info.st_size == 0:
                os.write(self.descriptor, self._CONTENT)
                os.fsync(self.descriptor)
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            content = os.read(self.descriptor, len(self._CONTENT))
            if content != self._CONTENT or os.fstat(self.descriptor).st_size != len(self._CONTENT):
                raise OfflineRunnerError("QUEUE_LOCK_INVALID")
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                self._locking_module = msvcrt
                msvcrt.locking(self.descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                self._locking_module = fcntl
                fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self
        except OfflineRunnerError:
            self.close()
            raise
        except (ImportError, OSError, LedgerError):
            self.close()
            raise OfflineRunnerError("QUEUE_ALREADY_RUNNING_OR_LOCK_UNAVAILABLE") from None

    def close(self) -> None:
        descriptor = self.descriptor
        if descriptor is None:
            return
        try:
            if self._locking_module is not None:
                if os.name == "nt":
                    self._locking_module.locking(
                        descriptor, self._locking_module.LK_UNLCK, 1,
                    )
                else:
                    self._locking_module.flock(
                        descriptor, self._locking_module.LOCK_UN,
                    )
        except OSError:
            pass
        finally:
            os.close(descriptor)
            self.descriptor = None

    def __exit__(self, *_: object) -> None:
        self.close()


def _ledger_writer_handoff_callbacks(
    ledger: S9OperationalLedger,
) -> tuple[
    Callable[[dict[str, object]], None],
    Callable[[dict[str, object]], None],
    dict[str, object],
]:
    """Build the explicit suspended-child writer release/readmission pair."""
    handoff: dict[str, object] = {}
    state: dict[str, object] = {"parent_readmitted": False}

    def release(identity: dict[str, object]) -> None:
        if handoff:
            raise OfflineRunnerError("LEDGER_HANDOFF_ALREADY_ACTIVE")
        ledger.verify_handoff_ack(identity)
        handoff.update(identity)
        ledger.release_writer_ownership()

    def readmit(identity: dict[str, object]) -> None:
        if not handoff or identity != handoff:
            raise OfflineRunnerError("LEDGER_HANDOFF_IDENTITY_MISMATCH")
        ledger.reacquire_writer_ownership(expected=handoff)
        state["parent_readmitted"] = True

    state["handoff"] = handoff
    return release, readmit, state


def start_supervised_run(
    run_directory: str | Path,
) -> S9RunContext:
    """Create the single durable G1-G9 ledger and deadline before any stage."""
    run_root = _safe_output_directory(run_directory)
    ledger_path = run_root / "operational-ledger.sqlite3"
    ledger = S9OperationalLedger.create(ledger_path)
    deadline_ns = ledger.start_global_deadline()
    ledger.update_execution(
        gate="G1", status="RUNNING", elapsed_ms=0,
        deadline_ns=deadline_ns, process_state="RUNNING", result="UNKNOWN",
    )
    run_id = str(ledger.snapshot()["run"]["run_id"])
    return S9RunContext(run_root, ledger_path, run_id, deadline_ns)


def load_supervised_run_context(run_directory: str | Path) -> S9RunContext:
    """Load, but never recreate, an active run and its original deadline."""
    selected = Path(run_directory)
    if not selected.is_absolute():
        raise OfflineRunnerError("RUN_DIRECTORY_MUST_BE_ABSOLUTE")
    try:
        resolved = selected.resolve(strict=True)
        info = selected.lstat()
        if (
            os.path.normcase(str(selected.absolute())) != os.path.normcase(str(resolved))
            or not selected.is_dir()
            or selected.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
        ):
            raise OfflineRunnerError("RUN_DIRECTORY_UNSAFE")
        guard = _open_private_directory_guard(selected)
    except LedgerError as error:
        raise OfflineRunnerError("RUN_DIRECTORY_PRIVATE_OR_UNAVAILABLE") from error
    except OSError as error:
        raise OfflineRunnerError("RUN_DIRECTORY_UNAVAILABLE") from error
    try:
        guard.verify(resolved)
        ledger_path = resolved / "operational-ledger.sqlite3"
        ledger_info = ledger_path.lstat()
        if (
            not stat.S_ISREG(ledger_info.st_mode)
            or ledger_path.is_symlink()
            or getattr(ledger_info, "st_file_attributes", 0) & 0x400
        ):
            raise OfflineRunnerError("LEDGER_PATH_UNSAFE")
        _verify_private_file(ledger_path)
    except (OSError, LedgerError) as error:
        raise OfflineRunnerError("LEDGER_PATH_PRIVATE_OR_UNAVAILABLE") from error
    finally:
        guard.close()
    ledger = S9OperationalLedger(ledger_path)
    try:
        deadline_ns = ledger.active_global_deadline()
        snapshot = ledger.snapshot()
    except LedgerError as error:
        raise OfflineRunnerError("GLOBAL_RUN_NOT_ACTIVE") from error
    return S9RunContext(
        resolved, ledger_path, str(snapshot["run"]["run_id"]), deadline_ns,
    )


def _safe_output_directory(path: str | Path) -> Path:
    selected = Path(path)
    if not selected.is_absolute():
        raise OfflineRunnerError("OUTPUT_DIRECTORY_MUST_BE_ABSOLUTE")
    parent = selected.parent
    if not parent.is_dir():
        raise OfflineRunnerError("OUTPUT_PARENT_MUST_EXIST")
    for candidate in (parent, *parent.parents):
        try:
            info = candidate.lstat()
        except OSError as error:
            raise OfflineRunnerError("OUTPUT_PARENT_UNAVAILABLE") from error
        if (
            not candidate.is_dir()
            or candidate.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
        ):
            raise OfflineRunnerError("OUTPUT_PARENT_UNSAFE")
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as error:
        raise OfflineRunnerError("OUTPUT_PARENT_UNAVAILABLE") from error
    if os.path.normcase(str(parent.absolute())) != os.path.normcase(str(resolved_parent)):
        raise OfflineRunnerError("OUTPUT_PARENT_UNSAFE")
    try:
        if os.path.lexists(selected):
            guard = _open_private_directory_guard(selected)
        else:
            guard = _create_private_directory(selected)
    except LedgerError as error:
        raise OfflineRunnerError("OUTPUT_DIRECTORY_PRIVATE_OR_CREATE_FAILED") from error
    try:
        resolved = selected.resolve(strict=True)
        if os.path.normcase(str(selected.absolute())) != os.path.normcase(str(resolved)):
            raise OfflineRunnerError("OUTPUT_DIRECTORY_UNSAFE")
        guard.verify(resolved)
        if any(resolved.iterdir()):
            raise OfflineRunnerError("OUTPUT_DIRECTORY_NOT_EMPTY")
        return resolved
    finally:
        guard.close()


def _child_environment() -> dict[str, str]:
    """Pass only runtime essentials; no Telegram/configuration variables."""
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() in _CHILD_ENVIRONMENT_KEYS
    } | {"PYTHONNOUSERSITE": "1"}


def _localappdata_for_child() -> str | None:
    """Allow the existing DPAPI vault path only when it stays outside the repo."""
    value = os.environ.get("LOCALAPPDATA")
    if value is None:
        return None
    selected = Path(value)
    try:
        resolved = selected.resolve(strict=True)
        info = selected.lstat()
        repository = Path(__file__).resolve().parents[2]
    except (OSError, RuntimeError, ValueError):
        raise OfflineRunnerError("LOCALAPPDATA_UNAVAILABLE") from None
    if (
        not selected.is_absolute()
        or not selected.is_dir()
        or selected.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
        or os.path.normcase(str(selected.absolute())) != os.path.normcase(str(resolved))
        or value.startswith(("\\\\", "//"))
        or resolved.drive.casefold() in {"", "\\\\"}
        or resolved == repository
        or repository in resolved.parents
        or (resolved / "telegram_courses").resolve(strict=False) == repository
        or repository in (resolved / "telegram_courses").resolve(strict=False).parents
    ):
        raise OfflineRunnerError("LOCALAPPDATA_UNSAFE")
    return str(resolved)


def _queue_child_environment(
    *, ledger_path: Path, profile: str, handshake_directory: Path, nonce: str,
    measurement_source: str, operational_gate: str = "G5",
) -> dict[str, str]:
    environment = _child_environment()
    localappdata = _localappdata_for_child()
    if localappdata is not None:
        environment["LOCALAPPDATA"] = localappdata
    environment.update({
        HANDSHAKE_DIR_ENV: str(handshake_directory),
        HANDSHAKE_NONCE_ENV: nonce,
        S9_LEDGER_PATH_ENV: str(ledger_path),
        S9_PROFILE_ENV: profile,
        S9_SUPERVISED_CHILD_ENV: "1",
        S9_MEASUREMENT_SOURCE_ENV: measurement_source,
        _S9_STAGE_ENV: "queue_f" if profile == "F" else "queue_m",
    })
    if operational_gate != "G5":
        environment[S9_OPERATIONAL_GATE_ENV] = operational_gate
    return environment


def _validate_supervised_queue_arguments(
    arguments: Sequence[str], profile: str,
) -> list[str]:
    from telegram_courses.cli import _parse_arguments
    from telegram_courses.s9_operational_ledger import F_CAP, M_MAX_CAP

    if type(profile) is not str or profile not in {"F", "M"}:
        raise OfflineRunnerError("QUEUE_PROFILE_INVALID")
    values = list(arguments)
    if (
        len(values) < 2 or values[:2] != ["download", "queue"]
        or any(not isinstance(item, str) or "\x00" in item for item in values)
        or "--confirm" in values
        or any(item.startswith("--confirm=") for item in values)
    ):
        raise OfflineRunnerError("QUEUE_ARGUMENTS_INVALID")
    allowed = {
        "--channel-id", "--database", "--download-dir", "--scope",
        "--workers", "--attempts-per-media", "--max-media-items",
        "--max-transfer-bytes", "--integrity-mode",
    }
    seen: set[str] = set()
    index = 2
    while index < len(values):
        token = values[index]
        if not token.startswith("--"):
            raise OfflineRunnerError("QUEUE_ARGUMENTS_INVALID")
        option = token.split("=", 1)[0]
        if option not in allowed or option in seen:
            raise OfflineRunnerError("QUEUE_ARGUMENTS_INVALID")
        seen.add(option)
        if "=" in token:
            if not token.partition("=")[2]:
                raise OfflineRunnerError("QUEUE_ARGUMENTS_INVALID")
        else:
            index += 1
            if index >= len(values) or values[index].startswith("--"):
                raise OfflineRunnerError("QUEUE_ARGUMENTS_INVALID")
        index += 1
    try:
        parsed = _parse_arguments(values)
    except Exception:
        raise OfflineRunnerError("QUEUE_ARGUMENTS_INVALID") from None
    if (
        parsed.command != "download" or parsed.credentials_action != "queue"
        or parsed.channel_id is None
        or parsed.workers != 1 or parsed.attempts_per_media != 1
        or parsed.max_media_items is None or parsed.max_transfer_bytes is None
        or parsed.integrity_mode != "REMOTE_HASH_REQUIRED"
        or parsed.reference_manifest is not None or parsed.confirm
        or not Path(parsed.database).is_absolute()
        or not Path(parsed.download_dir).is_absolute()
        or not {"--channel-id", "--database", "--download-dir", "--workers",
                "--attempts-per-media", "--max-media-items",
                "--max-transfer-bytes", "--integrity-mode"}.issubset(seen)
    ):
        raise OfflineRunnerError("QUEUE_ARGUMENTS_INVALID")
    if profile == "F" and not 1 <= parsed.max_media_items <= 8:
        raise OfflineRunnerError("QUEUE_LIMIT_INVALID")
    if profile == "F" and parsed.max_transfer_bytes > F_CAP:
        raise OfflineRunnerError("QUEUE_LIMIT_INVALID")
    if profile == "M" and (
        parsed.max_media_items != 1 or parsed.max_transfer_bytes > M_MAX_CAP
    ):
        raise OfflineRunnerError("QUEUE_LIMIT_INVALID")
    return values


def _safe_absolute_database_path(value: object) -> Path:
    if type(value) is not str or not value or "\x00" in value:
        raise OfflineRunnerError("STAGE_DATABASE_PATH_INVALID")
    path = Path(value)
    if not path.is_absolute():
        raise OfflineRunnerError("STAGE_DATABASE_PATH_MUST_BE_ABSOLUTE")
    try:
        resolved = path.resolve(strict=False)
        if os.path.normcase(str(path.absolute())) != os.path.normcase(str(resolved)):
            raise OfflineRunnerError("STAGE_DATABASE_PATH_UNSAFE")
        parent = path.parent
        if not parent.is_dir():
            raise OfflineRunnerError("STAGE_DATABASE_PARENT_UNAVAILABLE")
        for candidate in (parent, *parent.parents):
            info = candidate.lstat()
            if (
                not candidate.is_dir()
                or candidate.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise OfflineRunnerError("STAGE_DATABASE_PATH_UNSAFE")
        if os.path.lexists(path):
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or path.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise OfflineRunnerError("STAGE_DATABASE_PATH_UNSAFE")
    except OfflineRunnerError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise OfflineRunnerError("STAGE_DATABASE_PATH_UNAVAILABLE") from None
    return path


def _validate_queue_storage_paths(
    cli_arguments: Sequence[str], ledger_path: Path,
) -> tuple[Path, Path]:
    """Bind queue state and payloads to private children of the run root."""
    from telegram_courses.cli import _parse_arguments

    try:
        parsed = _parse_arguments(list(cli_arguments))
        run_root = ledger_path.parent.resolve(strict=True)
        database_path = _safe_absolute_database_path(parsed.database)
        download_path = Path(parsed.download_dir)
        if not download_path.is_absolute():
            raise OfflineRunnerError("QUEUE_DOWNLOAD_PATH_MUST_BE_ABSOLUTE")
        download_absolute = download_path.absolute()
        resolved_download = download_path.resolve(strict=False)
        if (
            os.path.normcase(str(download_absolute))
            != os.path.normcase(str(resolved_download))
            or
            os.path.normcase(str(database_path.resolve(strict=False).parent))
            != os.path.normcase(str(run_root))
            or os.path.normcase(str(resolved_download.parent))
            != os.path.normcase(str(run_root))
            or os.path.normcase(str(database_path.resolve(strict=False)))
            == os.path.normcase(str(ledger_path.resolve(strict=True)))
            or os.path.normcase(str(resolved_download))
            in {
                os.path.normcase(str(run_root)),
                os.path.normcase(str(ledger_path.resolve(strict=True))),
                os.path.normcase(str(database_path.resolve(strict=False))),
            }
        ):
            raise OfflineRunnerError("QUEUE_STORAGE_MUST_BE_PRIVATE_RUN_CHILD")
        if os.path.lexists(database_path):
            _verify_private_file(database_path)
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = Path(f"{database_path}{suffix}")
            if os.path.lexists(sidecar):
                _verify_private_file(sidecar)
        if os.path.lexists(resolved_download):
            guard = _open_private_directory_guard(resolved_download)
        else:
            guard = _create_private_directory(resolved_download)
        guard.close()
        return database_path, resolved_download
    except OfflineRunnerError:
        raise
    except (LedgerError, OSError, RuntimeError, TypeError, ValueError):
        raise OfflineRunnerError("QUEUE_STORAGE_PATH_UNSAFE") from None


def _validate_supervised_stage_arguments(
    cli_arguments: Sequence[str],
) -> tuple[str, str, list[str]]:
    """Allow only bounded existing CLI stages; queue stays on its own wrapper."""
    from telegram_courses.cli import _parse_arguments

    values = list(cli_arguments)
    if (
        not values
        or any(not isinstance(item, str) or "\x00" in item for item in values)
        or "--confirm" in values
        or any(item.startswith("--confirm=") for item in values)
    ):
        raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
    command = values[0]
    if command == "scan":
        stage, gate = "scan", "G2"
        allowed = {
            "--channel-id", "--database", "--max-messages",
            "--timeout-seconds", "--incremental", "--reconcile-window",
        }
        required = {
            "--channel-id", "--database", "--max-messages",
            "--timeout-seconds",
        }
    elif command == "catalog" and len(values) >= 2 and values[1] in {"build", "show", "items"}:
        stage = "catalog" if values[1] == "build" else "inspection"
        gate = "G3"
        allowed = {"--channel-id", "--database"}
        if values[1] == "build":
            allowed.add("--parser-key")
        required = {"--channel-id", "--database"}
    else:
        raise OfflineRunnerError("STAGE_COMMAND_NOT_ALLOWLISTED")

    seen: set[str] = set()
    index = 1
    if command == "catalog":
        index = 2
    while index < len(values):
        token = values[index]
        if not token.startswith("--"):
            raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
        option = token.split("=", 1)[0]
        if option not in allowed or option in seen:
            raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
        seen.add(option)
        if option == "--incremental":
            if "=" in token:
                raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
            index += 1
            continue
        if "=" in token:
            if not token.partition("=")[2]:
                raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
        else:
            index += 1
            if index >= len(values) or values[index].startswith("--"):
                raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
        index += 1
    if not required.issubset(seen) or not seen.issubset(allowed):
        raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
    try:
        parsed = _parse_arguments(values)
    except (Exception, SystemExit):
        raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID") from None

    database_path = _safe_absolute_database_path(parsed.database)
    if (
        type(parsed.channel_id) is not int or parsed.channel_id == 0
        or not -(2**63) <= parsed.channel_id <= 2**63 - 1
        or parsed.database != str(database_path)
        or parsed.config is not None or parsed.log_level is not None
    ):
        raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
    if stage == "scan":
        if (
            parsed.command != "scan" or parsed.max_messages is None
            or not 1 <= parsed.max_messages <= 200
            or parsed.timeout_seconds is None
            or not math.isfinite(parsed.timeout_seconds)
            or not 0 < parsed.timeout_seconds <= STAGE_TIMEOUTS_SECONDS["scan"]
        ):
            raise OfflineRunnerError("STAGE_LIMIT_INVALID")
        if parsed.incremental:
            if parsed.reconcile_window != 50:
                raise OfflineRunnerError("STAGE_LIMIT_INVALID")
            gate = "G7"
        elif parsed.reconcile_window is not None:
            raise OfflineRunnerError("STAGE_LIMIT_INVALID")
    elif (
        parsed.command != "catalog"
        or parsed.credentials_action not in {"build", "show", "items"}
        or (
            parsed.parser_key is not None
            and (parsed.credentials_action != "build" or parsed.parser_key != "rasmoo")
        )
    ):
        raise OfflineRunnerError("STAGE_ARGUMENTS_INVALID")
    return stage, gate, values


def _terminal_execution_state(supervisor: SupervisorResult) -> tuple[str, str, str]:
    process_state = (
        "EXITED" if supervisor.exit_code is not None
        and supervisor.process_control_gate == "PASS"
        else "CONTAINED" if supervisor.process_control_gate == "PASS"
        else "UNCONTAINED"
    )
    if supervisor.result == "COMPLETED" and supervisor.exit_code == 0:
        return "COMPLETED", process_state, "NONE"
    if supervisor.result == "FAILED":
        return "FAILED", process_state, "PROCESS"
    if supervisor.result == "TIMED_OUT":
        return "BLOCKED", process_state, "TIMEOUT"
    if supervisor.result == "CANCELLED":
        return "CANCELLED", process_state, "CANCELLED"
    return "BLOCKED", process_state, "PROCESS"


def classify_s9_gate(supervisor: SupervisorResult, limit_check_result: str) -> str:
    """Require both measured supervision and an explicit application limit PASS."""
    if type(limit_check_result) is not str or limit_check_result not in {
        "PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE",
    }:
        return "BLOCKED"
    return "PASS" if (
        supervisor.result == "COMPLETED"
        and supervisor.exit_code == 0
        and supervisor.supervisor_gate == "PASS"
        and supervisor.process_control_gate == "PASS"
        and supervisor.memory_monitoring_gate == "PASS"
        and supervisor.critical_audit_gate == "PASS"
        and supervisor.receipt_persisted
        and supervisor.receipt_attested
        and limit_check_result == "PASS"
    ) else "BLOCKED"


def _sampled_memory(receipt_path: Path) -> tuple[int, int, int] | tuple[None, None, None]:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        memory = receipt["memory"]
        samples = memory["samples"]
        if not samples:
            return None, None, None
        latest = samples[-1]
        working_set = latest["working_set_bytes"]
        private_bytes = latest["private_bytes"]
        peak_working_set = memory["peak_working_set_bytes"]
        if any(type(value) is not int or value < 0 for value in (
            working_set, private_bytes, peak_working_set
        )) or peak_working_set < working_set:
            return None, None, None
        return working_set, peak_working_set, private_bytes
    except (OSError, ValueError, KeyError, TypeError):
        return None, None, None


def _synthetic_test_seam_enabled(
    supervisor_type: type[WindowsCliSupervisor],
) -> bool:
    """Require an explicit fake-supervisor marker for synthetic API tests.

    The command-line entry points always use ``WindowsCliSupervisor``. The
    marker only opens the isolated injection seam used by offline integration
    tests that also inject fake Telegram gateways.
    """
    return (
        supervisor_type is not WindowsCliSupervisor
        and supervisor_type.__dict__.get("_s9_synthetic_test_seam") is True
    )


def _global_deadline_expired(supervisor: SupervisorResult, deadline_ns: int) -> bool:
    return (
        supervisor.reason in {
            "GLOBAL_DEADLINE_EXCEEDED",
            "GLOBAL_DEADLINE_EXCEEDED_BEFORE_LAUNCH",
        }
        or time.time_ns() >= deadline_ns
    )


def _record_f_interruption_after_supervised_stop(
    ledger: S9OperationalLedger,
    *,
    profile: str,
    supervisor: SupervisorResult,
    after_sequence: int,
) -> bool:
    """Record only a contained, explicitly interrupted F attempt for recovery."""
    if (
        profile != "F"
        or supervisor.process_control_gate != "PASS"
        or supervisor.reason not in {
            "STAGE_TIMEOUT",
            "GLOBAL_DEADLINE_EXCEEDED",
            "USER_CANCELLATION_REQUESTED",
        }
    ):
        return False
    snapshot = ledger.snapshot()
    if snapshot["critical_audit"]["quarantined"]:
        raise LedgerError("CRITICAL_AUDIT_QUARANTINED")
    interrupted_aliases: set[str] = set()
    queue_passed = False
    for event in snapshot["critical_audit"]["events"]:
        if event["sequence"] <= after_sequence:
            continue
        if event["event_type"] not in {"ATTEMPT_STARTED", "GATE_STATE_UPDATED"}:
            continue
        try:
            details = json.loads(event["details_json"])
        except (TypeError, ValueError):
            raise LedgerError("INTERRUPTION_AUDIT_INVALID") from None
        if not isinstance(details, dict):
            raise LedgerError("INTERRUPTION_AUDIT_INVALID")
        if (
            event["event_type"] == "GATE_STATE_UPDATED"
            and details.get("gate") == "G5"
            and details.get("result") == "PASS"
        ):
            queue_passed = True
        if event["event_type"] == "ATTEMPT_STARTED":
            alias = details.get("alias")
            if not isinstance(alias, str):
                raise LedgerError("ATTEMPT_AUDIT_INVALID")
            interrupted_aliases.add(alias)
    if queue_passed or len(interrupted_aliases) != 1:
        return False
    ledger.record_interruption(next(iter(interrupted_aliases)))
    return True


def run_offline_smoke(
    output_directory: str | Path,
    *,
    require_tty: bool = True,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> OfflineRunOutcome:
    """Run only the existing CLI's offline ``smoke`` command under supervision."""
    trusted_cli_origin = _trusted_cli_module_origin()
    output = _safe_output_directory(output_directory)
    ledger_path = output / "operational-ledger.sqlite3"
    receipt_path = output / "supervisor-receipt.json"
    ledger = S9OperationalLedger.create(ledger_path)
    run_id = str(ledger.snapshot()["run"]["run_id"])
    started = time.monotonic()
    deadline_ns = ledger.start_global_deadline()
    global_deadline = started + 3600.0
    ledger.update_execution(
        gate="G0", status="RUNNING", elapsed_ms=0, deadline_ns=deadline_ns,
        process_state="RUNNING", result="UNKNOWN",
    )
    supervisor = supervisor_type(
        receipt_path=receipt_path,
        require_tty=require_tty,
        critical_audit_writer=ledger.record_critical_event,
        ledger_run_id=run_id,
    )
    result = supervisor.run(
        [
            sys.executable, "-I", "-c", _TRUSTED_CLI_BOOTSTRAP,
            str(trusted_cli_origin), "smoke",
        ],
        stage="verification_local", timeout_seconds=300,
        global_deadline_monotonic=global_deadline,
        global_started_monotonic=started,
        cwd=output,
        environment=_child_environment(),
    )
    status, process_state, cause = _terminal_execution_state(result)
    working_set, peak_working_set, private_bytes = _sampled_memory(receipt_path)
    ledger.update_execution(
        gate="G0", status=status,
        elapsed_ms=max(0, round((time.monotonic() - started) * 1000)),
        deadline_ns=deadline_ns, process_state=process_state, result="UNKNOWN",
        cause=cause, working_set=working_set,
        peak_working_set=peak_working_set, private_bytes=private_bytes,
    )
    snapshot = ledger.snapshot()["run"]
    return OfflineRunOutcome(
        supervisor=result,
        ledger_path=ledger_path,
        ledger_status=str(snapshot["status"]),
        ledger_result=str(snapshot["result"]),
    )


def _run_supervised_queue_locked(
    output_directory: str | Path,
    ledger_path: str | Path,
    cli_arguments: Sequence[str],
    *,
    profile: str,
    require_tty: bool = True,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> SupervisedQueueOutcome:
    """Run one restricted S5 queue against a G1-started durable S9 run.

    The wrapper reuses the persisted deadline and never creates a queue-local
    substitute. It proves only this queue boundary; it does not orchestrate or
    attest the complete G1-G9 sequence.
    """
    trusted_cli_origin = _trusted_cli_module_origin()
    arguments = _validate_supervised_queue_arguments(cli_arguments, profile)
    selected_ledger = Path(ledger_path)
    if not selected_ledger.is_absolute():
        raise OfflineRunnerError("LEDGER_PATH_MUST_BE_ABSOLUTE")
    ledger = S9OperationalLedger(selected_ledger)
    deadline_ns = ledger.active_global_deadline()
    initial = ledger.snapshot()
    run = initial["run"]
    if run["status"] != "RUNNING" or (
        (run["gate"], run["result"]) not in {
            ("G3", "PASS"), ("G3", "OFFLINE_SYNTHETIC_PASS"),
            ("G5", "PASS"), ("G5", "OFFLINE_SYNTHETIC_PASS"),
        }
    ):
        raise OfflineRunnerError("QUEUE_REQUIRES_G3_PASS")
    try:
        from telegram_courses.s9_real_gate_producers import (
            GateEvidenceError,
            load_approved_manifest,
            read_validated_gate_receipt,
        )

        _manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(
            selected_ledger.parent,
        )
        g0 = read_validated_gate_receipt(
            selected_ledger.parent, initial, "G0",
            run_id=str(run["run_id"]), manifest_sha256=manifest_sha256,
        )
        synthetic_test_seam = _synthetic_test_seam_enabled(supervisor_type)
        expected_g0 = (
            g0.get("status") == "OFFLINE_SYNTHETIC_PASS"
            and g0.get("evidence_origin") == "SYNTHETIC"
            and g0.get("confirmation_source") == "SYNTHETIC_TEST"
        )
        real_g0 = (
            g0.get("status") == "PASS"
            and g0.get("evidence_origin") == "HUMAN_INTERACTIVE"
            and g0.get("confirmation_source") == "INTERACTIVE_TTY"
        )
        if not (real_g0 or synthetic_test_seam and expected_g0):
            raise GateEvidenceError("G0_CONFIRMATION_NOT_HUMAN")
    except (GateEvidenceError, OSError, ValueError, LedgerError):
        raise OfflineRunnerError("G0_CONFIRMATION_REQUIRED") from None
    database_path, download_root = _validate_queue_storage_paths(
        arguments, selected_ledger,
    )
    if any(row["state"] == "RESERVED" for row in initial["reservations"]):
        raise OfflineRunnerError("UNRESOLVED_RESERVATION_REQUIRES_CONTAINMENT")
    initial_sequence = initial["critical_audit"]["head_sequence"]
    remaining_seconds = (deadline_ns - time.time_ns()) / 1_000_000_000
    if not 0 < remaining_seconds <= 3600:
        raise OfflineRunnerError("GLOBAL_DEADLINE_INVALID")
    started = time.monotonic()
    global_deadline = started + remaining_seconds
    global_started = global_deadline - 3600.0
    if global_started > started:
        raise OfflineRunnerError("GLOBAL_DEADLINE_INVALID")

    output = _safe_output_directory(output_directory)
    handshake_guard = _create_private_directory(output / "handshake")
    handshake_directory = handshake_guard.path
    nonce = secrets.token_hex(32)
    baseline_prompt_ready, release_confirmation = confirmation_callbacks(
        handshake_directory, nonce,
    )
    stage = "queue_f" if profile == "F" else "queue_m"
    from telegram_courses.s9_real_gate_producers import (
        g5_queue_receipt_filename,
        g5_supervisor_receipt_filename,
        read_validated_g5_queue_receipt,
    )

    supervisor_receipt_paths = [
        selected_ledger.parent / g5_supervisor_receipt_filename(profile, index)
        for index in (1, 2)
    ]
    queue_receipt_paths = [
        selected_ledger.parent / g5_queue_receipt_filename(profile, index)
        for index in (1, 2)
    ]
    present = [os.path.lexists(path) for path in supervisor_receipt_paths]
    queue_present = [os.path.lexists(path) for path in queue_receipt_paths]
    if present != queue_present:
        raise OfflineRunnerError("G5_QUEUE_RECEIPT_PAIR_INCOMPLETE")
    if present[1] and not present[0] or all(present):
        raise OfflineRunnerError("G5_QUEUE_RECEIPT_SEQUENCE_INVALID")
    pass_index = 2 if present[0] else 1
    if pass_index == 2:
        if run["gate"] != "G5" or run["result"] not in {
            "PASS", "OFFLINE_SYNTHETIC_PASS",
        }:
            raise OfflineRunnerError("SECOND_QUEUE_REQUIRES_G5_PASS")
        try:
            previous_receipt = read_validated_g5_queue_receipt(
                selected_ledger.parent, initial,
                run_id=str(run["run_id"]), manifest_sha256=manifest_sha256,
                profile=profile, pass_index=1,
            )
        except (OfflineRunnerError, OSError, ValueError):
            raise OfflineRunnerError("G5_FIRST_QUEUE_RECEIPT_INVALID") from None
        if (
            previous_receipt.get("supervisor_receipt_file")
            != supervisor_receipt_paths[0].name
            or previous_receipt.get("stage") != stage
        ):
            raise OfflineRunnerError("G5_FIRST_QUEUE_ATTESTATION_MISSING")
    receipt_path = supervisor_receipt_paths[pass_index - 1]
    measurement_source = (
        "GATEWAY_RESPONSE"
        if supervisor_type is WindowsCliSupervisor
        else "SYNTHETIC_TEST"
    )
    supervisor = supervisor_type(
        receipt_path=receipt_path,
        require_tty=require_tty,
        critical_audit_writer=ledger.record_critical_event,
        ledger_run_id=str(initial["run"]["run_id"]),
    )
    handoff_identity: dict[str, object] = {}
    parent_readmitted = False

    def release_parent_writer(identity: dict[str, object]) -> None:
        if handoff_identity:
            raise OfflineRunnerError("LEDGER_HANDOFF_ALREADY_ACTIVE")
        ledger.verify_handoff_ack(identity)
        handoff_identity.update(identity)
        ledger.release_writer_ownership()

    def readmit_parent_writer(identity: dict[str, object]) -> None:
        nonlocal parent_readmitted
        if not handoff_identity or identity != handoff_identity:
            raise OfflineRunnerError("LEDGER_HANDOFF_IDENTITY_MISMATCH")
        ledger.reacquire_writer_ownership(expected=handoff_identity)
        parent_readmitted = True

    try:
        result = supervisor.run(
            [
                *_trusted_python_command(_TRUSTED_CLI_BOOTSTRAP),
                str(trusted_cli_origin), *arguments,
            ],
            stage=stage,
            baseline_prompt_ready=baseline_prompt_ready,
            release_confirmation=release_confirmation,
            global_deadline_monotonic=global_deadline,
            global_started_monotonic=global_started,
            cwd=output,
            release_ledger_writer=release_parent_writer,
            readmit_ledger_writer=readmit_parent_writer,
            environment=_queue_child_environment(
                ledger_path=selected_ledger, profile=profile,
                handshake_directory=handshake_directory, nonce=nonce,
                measurement_source=measurement_source,
            ),
        )
    finally:
        handshake_guard.close()

    if handoff_identity and not parent_readmitted:
        ledger_status = ledger_result = "BLOCKED"
        return SupervisedQueueOutcome(
            supervisor=result, ledger_path=selected_ledger,
            ledger_status=ledger_status, ledger_result=ledger_result,
            queue_gate_result="BLOCKED", deadline_ns=deadline_ns,
        )

    interruption_accounting_pass = True
    if result.process_control_gate == "PASS":
        try:
            ledger._charge_unresolved_reservations_after_containment()
        except LedgerError:
            # A ledger failure remains visible in the gate classification.
            interruption_accounting_pass = False
        try:
            _record_f_interruption_after_supervised_stop(
                ledger,
                profile=profile,
                supervisor=result,
                after_sequence=initial_sequence,
            )
        except LedgerError:
            interruption_accounting_pass = False
    else:
        interruption_accounting_pass = False
        try:
            snapshot = ledger.snapshot()
            if snapshot["run"]["status"] == "RUNNING":
                ledger.update_execution(
                    gate="G5", status="BLOCKED",
                    elapsed_ms=S9OperationalLedger.execution_elapsed_ms(snapshot),
                    deadline_ns=deadline_ns, process_state="UNCONTAINED",
                    result="BLOCKED", cause="PROCESS",
                )
        except LedgerError:
            # The queue result remains blocked if durable quarantine is needed.
            pass

    queue_gate_result = "BLOCKED"
    try:
        snapshot = ledger.snapshot()
        if not snapshot["critical_audit"]["quarantined"]:
            new_queue_events = []
            preconfirmation_pass = False
            for event in snapshot["critical_audit"]["events"]:
                if event["event_type"] != "GATE_STATE_UPDATED":
                    continue
                try:
                    details = json.loads(event["details_json"])
                except (TypeError, ValueError):
                    continue
                if details.get("gate") == "G4" and details.get("result") == "PASS":
                    preconfirmation_pass = True
                if event["sequence"] <= initial_sequence:
                    continue
                if details.get("gate") == "G5":
                    new_queue_events.append(details)
            if not new_queue_events:
                if result.process_control_gate == "PASS":
                    deadline_expired = _global_deadline_expired(result, deadline_ns)
                    current_status = "PARTIAL" if deadline_expired else "RUNNING"
                    current_result = "PARTIAL" if deadline_expired else "BLOCKED"
                    current_cause = "DEADLINE" if deadline_expired else "PROCESS"
                    elapsed_ms = S9OperationalLedger.execution_elapsed_ms(snapshot)
                    ledger.update_execution(
                        gate="G5", status=current_status, elapsed_ms=elapsed_ms,
                        deadline_ns=deadline_ns, process_state=(
                            "EXITED" if result.exit_code is not None
                            else "CONTAINED"
                        ), result=current_result, cause=current_cause,
                    )
                    snapshot = ledger.snapshot()
                    new_queue_events = [{"result": current_result}]
                else:
                    new_queue_events = [{"result": "BLOCKED"}]

            run = snapshot["run"]
            details = new_queue_events[-1]
            memory_values = _sampled_memory(receipt_path)
            if (
                run["gate"] == "G5"
                and result.process_control_gate == "PASS"
                and not snapshot["critical_audit"]["quarantined"]
            ):
                deadline_expired = _global_deadline_expired(result, deadline_ns)
                status = run["status"]
                current_result = run["result"]
                cause = run["cause"]
                if status == "RUNNING" and deadline_expired:
                    status, current_result, cause = "PARTIAL", "PARTIAL", "DEADLINE"
                working_set, peak_working_set, private_bytes = memory_values
                ledger.update_execution(
                    gate="G5", status=status,
                    elapsed_ms=S9OperationalLedger.execution_elapsed_ms(snapshot),
                    deadline_ns=deadline_ns,
                    process_state=(
                        "EXITED" if result.exit_code is not None
                        else "CONTAINED"
                    ),
                    result=current_result, cause=cause,
                    working_set=working_set, peak_working_set=peak_working_set,
                    private_bytes=private_bytes,
                    observed_bytes=details.get("observed_bytes"),
                )
                snapshot = ledger.snapshot()
                if (
                    details.get("result") == "PASS"
                    and snapshot["run"]["gate"] == "G5"
                    and snapshot["run"]["status"] == "RUNNING"
                    and classify_s9_gate(result, result.limit_check_result) == "PASS"
                    and preconfirmation_pass
                    and interruption_accounting_pass
                    and not any(
                        row["state"] == "RESERVED"
                        for row in snapshot["reservations"]
                    )
                ):
                    queue_gate_result = (
                        "PASS" if measurement_source == "GATEWAY_RESPONSE"
                        else "OFFLINE_SYNTHETIC_PASS"
                    )
        run_snapshot = snapshot["run"]
        ledger_status = str(run_snapshot["status"])
        ledger_result = str(run_snapshot["result"])
    except (LedgerError, KeyError, TypeError, ValueError):
        ledger_status = "BLOCKED"
        ledger_result = "BLOCKED"

    if queue_gate_result in {"PASS", "OFFLINE_SYNTHETIC_PASS"}:
        try:
            from telegram_courses.cli import _parse_arguments
            from telegram_courses.s9_real_gate_producers import (
                g5_queue_receipt_filename,
                persist_g5_queue_receipt,
                persist_gate_receipt,
                read_validated_g5_queue_receipt,
                read_validated_gate_receipt,
                reconcile_g6_downloads,
            )

            queue_snapshot = ledger.snapshot()
            supervisor_hash = _read_supervisor_receipt_evidence(
                receipt_path, queue_snapshot,
                run_id=str(initial["run"]["run_id"]), stage=stage,
                expected_exit_code=0,
            )
            stage_finished = [
                event for event in queue_snapshot["critical_audit"]["events"]
                if event["sequence"] > initial_sequence
                and event["event_type"] == "SUPERVISOR_RUN_FINISHED"
                and json.loads(event["details_json"]).get("stage") == stage
                and json.loads(event["details_json"]).get("result") == "COMPLETED"
            ]
            if len(stage_finished) != 1:
                raise OfflineRunnerError("G5_SUPERVISOR_STAGE_ATTESTATION_MISSING")
            gate_updates = [
                (event, json.loads(event["details_json"]))
                for event in queue_snapshot["critical_audit"]["events"]
                if event["sequence"] > stage_finished[0]["sequence"]
                and event["event_type"] == "GATE_STATE_UPDATED"
                and json.loads(event["details_json"]).get("gate") == "G5"
            ]
            if not gate_updates or gate_updates[-1][1].get("result") != "PASS":
                raise OfflineRunnerError("G5_LEDGER_PASS_NOT_ATTESTED")
            observed_bytes = gate_updates[-1][1].get("observed_bytes")
            if type(observed_bytes) is not int or observed_bytes < 0:
                raise OfflineRunnerError("G5_LEDGER_BYTES_NOT_ATTESTED")
            evidence_origin = (
                "REAL_CONTRACTUAL"
                if supervisor_type is WindowsCliSupervisor
                else "SYNTHETIC"
            )
            receipt_status = (
                "PASS" if evidence_origin == "REAL_CONTRACTUAL"
                else "OFFLINE_SYNTHETIC_PASS"
            )
            parsed_queue = _parse_arguments(arguments)
            manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(
                selected_ledger.parent,
            )
            # Persist the S9 classification before the no-overwrite pass receipt.
            if queue_gate_result != receipt_status:
                ledger.update_execution(
                    gate="G5", status="RUNNING",
                    elapsed_ms=S9OperationalLedger.execution_elapsed_ms(queue_snapshot),
                    deadline_ns=deadline_ns, process_state="EXITED",
                    result=receipt_status, cause="NONE",
                    observed_bytes=observed_bytes,
                )
            queue_receipt = {
                "schema": "telegram-courses-s9-g5-queue-receipt-v1",
                "version": 1,
                "gate": "G5",
                "run_id": str(initial["run"]["run_id"]),
                "manifest_sha256": manifest_sha256,
                "channel_id": manifest["channel_id"],
                "database_file": database_path.name,
                "download_root": download_root.name,
                "profile": profile,
                "pass_index": pass_index,
                "stage": stage,
                "status": receipt_status,
                "evidence_origin": evidence_origin,
                "measurement_source": measurement_source,
                "supervisor_receipt_file": receipt_path.name,
                "supervisor_receipt_sha256": supervisor_hash,
                "observed_bytes": observed_bytes,
                "max_media_items": parsed_queue.max_media_items,
                "max_transfer_bytes": parsed_queue.max_transfer_bytes,
                "workers": parsed_queue.workers,
                "attempts_per_media": parsed_queue.attempts_per_media,
                "all_items_already_valid": (
                    pass_index == 2 and observed_bytes == 0
                ),
            }
            persist_g5_queue_receipt(
                selected_ledger.parent, ledger, queue_receipt,
                before_rename_checkpoint=ledger.checkpoint,
            )
            ledger.update_execution(
                gate="G5", status="RUNNING",
                elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
                deadline_ns=deadline_ns, process_state="EXITED",
                result=receipt_status, cause="NONE",
                observed_bytes=observed_bytes,
            )
            queue_gate_result = receipt_status
            queue_snapshot = ledger.snapshot()
            queue_receipts = [
                selected_ledger.parent / g5_queue_receipt_filename(profile, index)
                for profile in ("F", "M") for index in (1, 2)
            ]
            complete_g5_matrix = all(path.is_file() for path in queue_receipts)
            m_receipt_paths = [
                selected_ledger.parent / g5_queue_receipt_filename("M", index)
                for index in (1, 2)
            ]
            no_m_reconciliation_candidate = (
                profile == "F" and pass_index == 2
                and not any(os.path.lexists(path) for path in m_receipt_paths)
                and not any(row.get("profile") == "M" for row in queue_snapshot["media"])
            )
            if (complete_g5_matrix or no_m_reconciliation_candidate) and not (
                selected_ledger.parent / "g6-gate-receipt.json"
            ).exists():
                evidence = reconcile_g6_downloads(
                    selected_ledger.parent, database_path, download_root,
                    run_id=str(initial["run"]["run_id"]), manifest=manifest,
                    manifest_sha256=manifest_sha256, ledger=ledger,
                    ledger_snapshot=queue_snapshot,
                )
                no_m_result = (
                    evidence.get("status") == "PARTIAL"
                    and evidence.get("g5_m_status") == "BLOCKED_DATASET"
                    and evidence.get("g6_aggregate_status") == "PARTIAL"
                    and evidence.get("g7_real_eligible") is False
                    and evidence.get("nfr02_real") == "NOT_TESTED"
                )
                if complete_g5_matrix or no_m_result:
                    persist_gate_receipt(
                        selected_ledger.parent, ledger, evidence,
                        before_rename_checkpoint=ledger.checkpoint,
                    )
                    _update_gate_result(
                        ledger, gate="G6", deadline_ns=deadline_ns,
                        evidence_result=str(evidence.get("status", "BLOCKED")),
                        process_state="EXITED",
                        measurements=_sampled_memory(receipt_path), cause="LEDGER",
                    )
            snapshot = ledger.snapshot()
            ledger_status = str(snapshot["run"]["status"])
            ledger_result = str(snapshot["run"]["result"])
        except (GateEvidenceError, OfflineRunnerError, LedgerError, OSError, ValueError, TypeError):
            queue_gate_result = "BLOCKED"

    return SupervisedQueueOutcome(
        supervisor=result,
        ledger_path=selected_ledger,
        ledger_status=ledger_status,
        ledger_result=ledger_result,
        queue_gate_result=queue_gate_result,
        deadline_ns=deadline_ns,
    )


def run_supervised_queue(
    output_directory: str | Path,
    ledger_path: str | Path,
    cli_arguments: Sequence[str],
    *,
    profile: str,
    require_tty: bool = True,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> SupervisedQueueOutcome:
    """Serialize and supervise one queue stage against an existing run."""
    selected_ledger = Path(ledger_path)
    if not selected_ledger.is_absolute():
        raise OfflineRunnerError("LEDGER_PATH_MUST_BE_ABSOLUTE")
    try:
        info = selected_ledger.lstat()
    except OSError as error:
        raise OfflineRunnerError("LEDGER_PATH_UNAVAILABLE") from error
    if (
        not selected_ledger.is_file()
        or selected_ledger.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
    ):
        raise OfflineRunnerError("LEDGER_PATH_UNSAFE")
    try:
        run_guard = _open_private_directory_guard(selected_ledger.parent)
        run_guard.verify(selected_ledger.parent)
    except LedgerError as error:
        raise OfflineRunnerError("RUN_DIRECTORY_PRIVATE_OR_UNAVAILABLE") from error
    try:
        with _QueueRunLock(selected_ledger):
            return _run_supervised_queue_locked(
                output_directory, selected_ledger, cli_arguments,
                profile=profile, require_tty=require_tty,
                supervisor_type=supervisor_type,
            )
    finally:
        run_guard.close()


def _g8_interrupted_checkpoint(
    ledger: S9OperationalLedger,
    database_path: Path,
    download_root: Path,
    alias: str,
) -> tuple[tuple[int, int, int], int, int]:
    """Reopen SQLite and the owned .part file after confirmed containment."""
    import sqlite3

    if not database_path.is_file() or database_path.is_symlink():
        raise OfflineRunnerError("G8_DATABASE_UNAVAILABLE")
    try:
        uri = database_path.resolve(strict=True).as_uri() + "?mode=ro"
        db = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise OfflineRunnerError("G8_DATABASE_INTEGRITY_FAILED")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise OfflineRunnerError("G8_DATABASE_FOREIGN_KEY_FAILED")
            matches = []
            for row in db.execute(
                "SELECT id,channel_id,telegram_message_id,media_ordinal,kind,file_size_bytes "
                "FROM media_items"
            ):
                identity = (
                    int(row["channel_id"]), int(row["telegram_message_id"]),
                    int(row["media_ordinal"]),
                )
                if ledger.pseudonym(
                    f"{identity[0]}:{identity[1]}:{identity[2]}"
                ) == alias:
                    matches.append((row, identity))
            if len(matches) != 1:
                raise OfflineRunnerError("G8_MEDIA_IDENTITY_INVALID")
            media, identity = matches[0]
            if media["kind"] != "DOCUMENT" or type(media["file_size_bytes"]) is not int:
                raise OfflineRunnerError("G8_MEDIA_IDENTITY_INVALID")
            rows = db.execute(
                "SELECT state,final_path,partial_path,expected_bytes,downloaded_bytes "
                "FROM downloads WHERE media_item_id=?",
                (media["id"],),
            ).fetchall()
            if len(rows) != 1:
                raise OfflineRunnerError("G8_DOWNLOAD_CHECKPOINT_MISSING")
            download = rows[0]
            if (
                download["state"] != "FAILED_RETRYABLE"
                or download["expected_bytes"] != media["file_size_bytes"]
                or type(download["downloaded_bytes"]) is not int
                or download["downloaded_bytes"] <= 0
                or download["downloaded_bytes"] >= download["expected_bytes"]
                or not isinstance(download["partial_path"], str)
                or not isinstance(download["final_path"], str)
            ):
                raise OfflineRunnerError("G8_DOWNLOAD_CHECKPOINT_INVALID")
            partial = Path(download["partial_path"])
            final = Path(download["final_path"])
            if not partial.is_absolute() or not final.is_absolute():
                raise OfflineRunnerError("G8_DOWNLOAD_PATH_INVALID")
            root = download_root.resolve(strict=True)
            partial_resolved = partial.resolve(strict=True)
            final_resolved = final.resolve(strict=False)
            if (
                partial.is_symlink()
                or not partial.name.endswith(".part")
                or getattr(partial.lstat(), "st_file_attributes", 0) & 0x400
                or root not in partial_resolved.parents
                or os.path.lexists(final)
                or root not in final_resolved.parents
            ):
                raise OfflineRunnerError("G8_DOWNLOAD_PATH_INVALID")
            part_info = partial_resolved.stat()
            if (
                not stat.S_ISREG(part_info.st_mode)
                or part_info.st_size != download["downloaded_bytes"]
            ):
                raise OfflineRunnerError("G8_PARTIAL_CHECKPOINT_MISMATCH")
            return identity, int(download["downloaded_bytes"]), int(download["expected_bytes"])
        finally:
            db.close()
    except OfflineRunnerError:
        raise
    except (sqlite3.Error, OSError, TypeError, ValueError, KeyError):
        raise OfflineRunnerError("G8_CHECKPOINT_RECONCILIATION_FAILED") from None


def run_supervised_g8(
    run_context: S9RunContext,
    output_directory: str | Path,
    cli_arguments: Sequence[str],
    *,
    phase: str,
    require_tty: bool = True,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> SupervisedG8Outcome:
    """Run one G8 F interruption or recovery stage under the G1 deadline."""
    selected_ledger = Path(run_context.ledger_path)
    if not selected_ledger.is_absolute():
        raise OfflineRunnerError("LEDGER_PATH_MUST_BE_ABSOLUTE")
    try:
        info = selected_ledger.lstat()
    except OSError as error:
        raise OfflineRunnerError("LEDGER_PATH_UNAVAILABLE") from error
    if (
        not selected_ledger.is_file() or selected_ledger.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
    ):
        raise OfflineRunnerError("LEDGER_PATH_UNSAFE")
    if phase not in {"interrupt", "recover"}:
        raise OfflineRunnerError("G8_PHASE_INVALID")
    try:
        guard = _open_private_directory_guard(run_context.run_directory)
        guard.verify(run_context.run_directory)
    except LedgerError as error:
        raise OfflineRunnerError("RUN_DIRECTORY_PRIVATE_OR_UNAVAILABLE") from error
    try:
        with _QueueRunLock(selected_ledger):
            return _run_supervised_g8_locked(
                run_context,
                output_directory,
                cli_arguments,
                phase=phase,
                require_tty=require_tty,
                supervisor_type=supervisor_type,
            )
    finally:
        guard.close()


def _run_supervised_g8_locked(
    run_context: S9RunContext,
    output_directory: str | Path,
    cli_arguments: Sequence[str],
    *,
    phase: str,
    require_tty: bool,
    supervisor_type: type[WindowsCliSupervisor],
) -> SupervisedG8Outcome:
    from telegram_courses.s9_operational_reconciliation import (
        G8_INTERRUPTION_SUPERVISOR_FILE,
        G8_OPERATIONAL_RECEIPT_FILE,
        G8_PREFIX_PROOF_FILE,
        G8_RECOVERY_SUPERVISOR_FILE,
        OperationalReconciliationError,
        _g8_source_evidence,
        _validated_supervisor_receipt,
        read_g8_database_baseline,
        reconcile_g8_operational,
        record_g8_database_baseline,
    )

    selected_ledger = Path(run_context.ledger_path)
    ledger = S9OperationalLedger(selected_ledger)
    initial = ledger.snapshot()
    run = initial["run"]
    if (
        run_context.run_id != run.get("run_id")
        or run_context.run_directory.resolve(strict=True)
        != selected_ledger.parent.resolve(strict=True)
        or run_context.deadline_ns != run.get("deadline_ns")
        or run.get("status") != "RUNNING"
        or initial["critical_audit"].get("quarantined") is not False
        or any(row["state"] == "RESERVED" for row in initial["reservations"])
    ):
        raise OfflineRunnerError("G8_RUN_PRECONDITION_FAILED")
    arguments = _validate_supervised_queue_arguments(cli_arguments, "F")
    database_path, download_root = _validate_queue_storage_paths(
        arguments, selected_ledger,
    )
    manifest_sha256: str
    if phase == "interrupt":
        if (
            run.get("gate") != "G7"
            or os.path.lexists(selected_ledger.parent / G8_INTERRUPTION_SUPERVISOR_FILE)
            or os.path.lexists(selected_ledger.parent / G8_RECOVERY_SUPERVISOR_FILE)
            or os.path.lexists(selected_ledger.parent / G8_OPERATIONAL_RECEIPT_FILE)
            or os.path.lexists(selected_ledger.parent / G8_PREFIX_PROOF_FILE)
            or run.get("result") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        ):
            raise OfflineRunnerError("G8_INTERRUPTION_ORDER_INVALID")
        try:
            _manifest, manifest_sha256, predecessors, origin = _g8_source_evidence(
                selected_ledger.parent, database_path, download_root, ledger,
            )
            from telegram_courses.s9_real_gate_producers import _database_sha256

            # Match G7's DB+WAL+SHM digest when binding the pre-G8 baseline.
            database_sha256_before = _database_sha256(database_path)
            record_g8_database_baseline(
                selected_ledger.parent,
                ledger,
                database_sha256_before=database_sha256_before,
                database_file=database_path.name,
                download_root=download_root.name,
                manifest_sha256=manifest_sha256,
                evidence_origin=origin,
                predecessors=predecessors,
            )
        except (OperationalReconciliationError, OSError, ValueError, TypeError, LedgerError):
            raise OfflineRunnerError("G8_PREDECESSOR_EVIDENCE_INVALID") from None
    else:
        if (
            run.get("gate") != "G8" or run.get("result") != "PARTIAL"
            or not os.path.isfile(selected_ledger.parent / G8_INTERRUPTION_SUPERVISOR_FILE)
            or os.path.lexists(selected_ledger.parent / G8_RECOVERY_SUPERVISOR_FILE)
            or os.path.lexists(selected_ledger.parent / G8_OPERATIONAL_RECEIPT_FILE)
            or os.path.lexists(selected_ledger.parent / G8_PREFIX_PROOF_FILE)
            or run.get("interruptions") != 1 or run.get("recoveries") != 0
        ):
            raise OfflineRunnerError("G8_RECOVERY_ORDER_INVALID")
        try:
            from telegram_courses.s9_real_gate_producers import load_approved_manifest

            _manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(
                selected_ledger.parent,
            )
            baseline = read_g8_database_baseline(
                selected_ledger.parent,
                initial,
                run_id=run_context.run_id,
                manifest_sha256=manifest_sha256,
            )
            origin = str(baseline["evidence_origin"])
            if baseline.get("database_file") != database_path.name:
                raise OperationalReconciliationError("G8_DATABASE_FILE_BINDING_INVALID")
        except (OperationalReconciliationError, OSError, ValueError, TypeError, LedgerError):
            raise OfflineRunnerError("G8_PREDECESSOR_EVIDENCE_INVALID") from None
    synthetic_test_seam = _synthetic_test_seam_enabled(supervisor_type)
    measurement_source = (
        "GATEWAY_RESPONSE"
        if supervisor_type is WindowsCliSupervisor
        else "SYNTHETIC_TEST"
    )
    if (
        (measurement_source == "GATEWAY_RESPONSE" and origin != "REAL_CONTRACTUAL")
        or (measurement_source == "SYNTHETIC_TEST" and (
            origin != "SYNTHETIC" or not synthetic_test_seam
        ))
    ):
        raise OfflineRunnerError("G8_MEASUREMENT_ORIGIN_MISMATCH")

    interruption_receipt = selected_ledger.parent / G8_INTERRUPTION_SUPERVISOR_FILE
    recovery_receipt = selected_ledger.parent / G8_RECOVERY_SUPERVISOR_FILE
    operational_receipt = selected_ledger.parent / G8_OPERATIONAL_RECEIPT_FILE
    prefix_proof = selected_ledger.parent / G8_PREFIX_PROOF_FILE
    if phase == "interrupt":
        if (
            run.get("gate") != "G7"
            or os.path.lexists(interruption_receipt)
            or os.path.lexists(recovery_receipt)
            or os.path.lexists(operational_receipt)
            or os.path.lexists(prefix_proof)
            or initial["run"].get("result") not in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        ):
            raise OfflineRunnerError("G8_INTERRUPTION_ORDER_INVALID")
        ledger.update_execution(
            gate="G8", status="RUNNING", elapsed_ms=S9OperationalLedger.execution_elapsed_ms(initial),
            deadline_ns=run_context.deadline_ns, process_state="RUNNING",
            result="UNKNOWN", cause="NONE",
        )
        receipt_path = interruption_receipt
    else:
        if (
            run.get("gate") != "G8" or run.get("result") != "PARTIAL"
            or not os.path.isfile(interruption_receipt)
            or os.path.lexists(recovery_receipt)
            or os.path.lexists(operational_receipt)
            or os.path.lexists(prefix_proof)
            or run.get("interruptions") != 1
            or run.get("recoveries") != 0
        ):
            raise OfflineRunnerError("G8_RECOVERY_ORDER_INVALID")
        try:
            _validated_supervisor_receipt(
                selected_ledger.parent,
                initial,
                filename=G8_INTERRUPTION_SUPERVISOR_FILE,
                run_id=run_context.run_id,
                expected_stage="queue_f",
                expected_exit_code=None,
                expected_result=(
                    "INTERRUPTED"
                    if origin == "REAL_CONTRACTUAL"
                    else "INTERRUPTED_SYNTHETIC"
                ),
            )
        except OperationalReconciliationError:
            raise OfflineRunnerError("G8_INTERRUPTION_RECEIPT_INVALID") from None
        receipt_path = recovery_receipt

    try:
        _open_private_directory_guard(download_root).close()
    except LedgerError as error:
        raise OfflineRunnerError("G8_DOWNLOAD_ROOT_UNSAFE") from error
    deadline_ns = ledger.active_global_deadline()
    remaining = (deadline_ns - time.time_ns()) / 1_000_000_000
    if not 0 < remaining <= 3600:
        raise OfflineRunnerError("GLOBAL_DEADLINE_INVALID")
    started = time.monotonic()
    global_deadline = started + remaining
    global_started = global_deadline - 3600.0
    output = _safe_output_directory(output_directory)
    handshake_guard = _create_private_directory(output / f"g8-{phase}-handshake")
    nonce = secrets.token_hex(32)
    baseline_prompt_ready, release_confirmation = confirmation_callbacks(
        handshake_guard.path, nonce,
    )
    supervisor = supervisor_type(
        receipt_path=receipt_path,
        require_tty=require_tty,
        critical_audit_writer=ledger.record_critical_event,
        ledger_run_id=run_context.run_id,
    )
    initial_sequence = initial["critical_audit"]["head_sequence"]
    release_writer, readmit_writer, handoff_state = _ledger_writer_handoff_callbacks(ledger)
    try:
        result = supervisor.run(
            [
                *_trusted_python_command(_TRUSTED_CLI_BOOTSTRAP),
                str(_trusted_cli_module_origin()), *arguments,
            ],
            stage="queue_f",
            timeout_seconds=STAGE_TIMEOUTS_SECONDS["queue_f"],
            baseline_prompt_ready=baseline_prompt_ready,
            release_confirmation=release_confirmation,
            global_deadline_monotonic=global_deadline,
            global_started_monotonic=global_started,
            cwd=output,
            release_ledger_writer=release_writer,
            readmit_ledger_writer=readmit_writer,
            environment=_queue_child_environment(
                ledger_path=selected_ledger,
                profile="F",
                handshake_directory=handshake_guard.path,
                nonce=nonce,
                measurement_source=measurement_source,
                operational_gate="G8",
            ),
        )
    except Exception:
        result = SupervisorResult(
            run_id=run_context.run_id, result="BLOCKED",
            reason="SUPERVISOR_EXCEPTION", exit_code=None,
            receipt_path=receipt_path, receipt_persisted=False,
            supervisor_gate="BLOCKED", process_control_gate="UNCONTAINED",
            memory_monitoring_gate="BLOCKED", critical_audit_gate="BLOCKED",
        )
    finally:
        handshake_guard.close()

    if handoff_state["handoff"] and not handoff_state["parent_readmitted"]:
        return SupervisedG8Outcome(
            phase=phase, supervisor=result, ledger_path=selected_ledger,
            ledger_status="BLOCKED", ledger_result="BLOCKED",
            gate_result="BLOCKED", deadline_ns=deadline_ns,
            receipt_path=receipt_path,
        )

    if phase == "interrupt":
        gate_result = "BLOCKED"
        try:
            if result.process_control_gate != "PASS":
                raise OfflineRunnerError("G8_PROCESS_CONTAINMENT_UNPROVEN")
            if not result.receipt_persisted or not result.receipt_attested:
                raise OfflineRunnerError("G8_SUPERVISOR_RECEIPT_NOT_ATTESTED")
            _validated_supervisor_receipt(
                selected_ledger.parent,
                ledger.snapshot(),
                filename=G8_INTERRUPTION_SUPERVISOR_FILE,
                run_id=run_context.run_id,
                expected_stage="queue_f",
                expected_exit_code=None,
                expected_result=(
                    "INTERRUPTED"
                    if origin == "REAL_CONTRACTUAL"
                    else "INTERRUPTED_SYNTHETIC"
                ),
            )
            attempts = []
            for event in ledger.snapshot()["critical_audit"]["events"]:
                if event["sequence"] <= initial_sequence or event["event_type"] != "ATTEMPT_STARTED":
                    continue
                details = json.loads(event["details_json"])
                if type(details) is dict:
                    attempts.append(details)
            if len(attempts) != 1 or attempts[0].get("recovery") is not False:
                raise OfflineRunnerError("G8_INTERRUPTED_ATTEMPT_NOT_ATTESTED")
            alias = attempts[0].get("alias")
            if type(alias) is not str:
                raise OfflineRunnerError("G8_INTERRUPTED_ALIAS_INVALID")
            ledger._charge_unresolved_reservations_after_containment()
            identity, part_bytes, expected_bytes = _g8_interrupted_checkpoint(
                ledger, database_path, download_root, alias,
            )
            ledger.record_interruption(
                alias, part_bytes=part_bytes, expected_bytes=expected_bytes,
            )
            after_checkpoint = ledger.snapshot()
            ledger.update_execution(
                gate="G8", status="RUNNING",
                elapsed_ms=S9OperationalLedger.execution_elapsed_ms(after_checkpoint),
                deadline_ns=deadline_ns, process_state="CONTAINED",
                result="PARTIAL", cause="OTHER",
            )
            gate_result = "INTERRUPTED"
        except (OfflineRunnerError, LedgerError, OperationalReconciliationError, OSError, ValueError, TypeError):
            snapshot = ledger.snapshot()
            if snapshot["run"].get("status") == "RUNNING":
                ledger.update_execution(
                    gate="G8", status="RUNNING",
                    elapsed_ms=S9OperationalLedger.execution_elapsed_ms(snapshot),
                    deadline_ns=deadline_ns, process_state=(
                        "CONTAINED" if result.process_control_gate == "PASS" else "UNCONTAINED"
                    ),
                    result="BLOCKED", cause="OTHER" if result.process_control_gate == "PASS" else "PROCESS",
                )
    else:
        gate_result = "BLOCKED"
        try:
            if (
                result.result != "COMPLETED" or result.exit_code != 0
                or result.supervisor_gate != "PASS"
                or result.process_control_gate != "PASS"
                or result.memory_monitoring_gate != "PASS"
                or result.critical_audit_gate != "PASS"
                or not result.receipt_persisted or not result.receipt_attested
            ):
                raise OfflineRunnerError("G8_RECOVERY_SUPERVISOR_NOT_PASSED")
            _read_supervisor_receipt_evidence(
                receipt_path,
                ledger.snapshot(),
                run_id=run_context.run_id,
                stage="queue_f",
                expected_exit_code=0,
            )
            current = ledger.snapshot()["run"]
            if current.get("status") != "RUNNING" or current.get("gate") != "G8":
                raise OfflineRunnerError("G8_RECOVERY_LEDGER_STATE_INVALID")
            expected_result = "PASS" if origin == "REAL_CONTRACTUAL" else "OFFLINE_SYNTHETIC_PASS"
            if current.get("result") != expected_result:
                ledger.update_execution(
                    gate="G8", status="RUNNING",
                    elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
                    deadline_ns=deadline_ns, process_state="EXITED",
                    result=expected_result, cause="NONE",
                )
            reconciled = reconcile_g8_operational(
                selected_ledger.parent, database_path, download_root,
            )
            gate_result = reconciled.status
        except (OfflineRunnerError, OperationalReconciliationError, LedgerError, OSError, ValueError, TypeError):
            try:
                reconciled = reconcile_g8_operational(
                    selected_ledger.parent, database_path, download_root,
                )
                gate_result = reconciled.status
            except (OperationalReconciliationError, LedgerError, OSError, ValueError, TypeError):
                gate_result = "BLOCKED"

    final_snapshot = ledger.snapshot()["run"]
    return SupervisedG8Outcome(
        phase, result, selected_ledger, str(final_snapshot["status"]),
        str(final_snapshot["result"]), gate_result, deadline_ns,
        receipt_path if os.path.lexists(receipt_path) else None,
    )


def _stage_child_environment(*, stage: str, ledger_path: Path) -> dict[str, str]:
    environment = _child_environment()
    localappdata = _localappdata_for_child()
    if localappdata is not None:
        environment["LOCALAPPDATA"] = localappdata
    return environment | {
        S9_LEDGER_PATH_ENV: str(ledger_path),
        S9_SUPERVISED_CHILD_ENV: "1",
        _S9_STAGE_ENV: stage,
    }


def _stage_precondition(
    stage: str,
    gate: str,
    run: dict[str, object],
    *,
    allow_synthetic: bool = False,
) -> None:
    if run.get("status") != "RUNNING":
        raise OfflineRunnerError("GLOBAL_RUN_NOT_ACTIVE")
    result = run.get("result")
    current_gate = run.get("gate")
    allowed = {
        ("scan", "G2"): ("G1", "PASS"),
        ("scan", "G7"): ("G6", "PASS"),
        ("catalog", "G3"): ("G2", "PASS"),
        ("inspection", "G3"): ("G3", "PASS"),
    }
    required = allowed.get((stage, gate))
    if allow_synthetic:
        allowed_test = {
            ("scan", "G2"): ("G1", "OFFLINE_SYNTHETIC_PASS"),
            ("scan", "G7"): ("G6", "OFFLINE_SYNTHETIC_PASS"),
            ("catalog", "G3"): ("G2", "OFFLINE_SYNTHETIC_PASS"),
        }
        required = allowed_test.get((stage, gate), required)
    repeated_g7 = (
        (stage, gate) == ("scan", "G7")
        and current_gate == "G7"
        and result in ({"PASS", "OFFLINE_SYNTHETIC_PASS"} if allow_synthetic else {"PASS"})
    )
    if required is None or (current_gate != required[0] and not repeated_g7):
        raise OfflineRunnerError("STAGE_ORDER_INVALID")
    if not repeated_g7 and result != required[1]:
        raise OfflineRunnerError("STAGE_PREVIOUS_GATE_NOT_PASSED")


def _read_supervisor_receipt_evidence(
    receipt_path: Path,
    ledger_snapshot: dict[str, object],
    *,
    run_id: str,
    stage: str,
    expected_exit_code: int | None = None,
) -> str:
    """Require the child receipt and its critical-audit acknowledgements."""
    from telegram_courses.s9_real_gate_producers import sha256_bytes

    try:
        _verify_private_file(receipt_path)
        raw = receipt_path.read_bytes()
        receipt = json.loads(raw.decode("utf-8"))
    except (LedgerError, OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise OfflineRunnerError("SUPERVISOR_RECEIPT_UNAVAILABLE") from None
    if (
        type(receipt) is not dict
        or receipt.get("schema") != "telegram-courses-s9-supervisor-receipt-v1"
        or receipt.get("run_id") != run_id
        or receipt.get("ledger_run_id") != run_id
        or receipt.get("stage") != stage
        or receipt.get("result") != "COMPLETED"
        or expected_exit_code is not None
        and (
            type(expected_exit_code) is not int
            or receipt.get("external_exit_code") != expected_exit_code
        )
        or not (
            receipt.get("external_exit_code") == 0
            or (
                stage == "scan"
                and receipt.get("external_exit_code") == 4
                and receipt.get("message_limit_exit_allowed") is True
                and receipt.get("reason") == "EXPECTED_MESSAGE_LIMIT_EXIT"
            )
        )
        or receipt.get("process_tree_termination_confirmed") is not True
        or receipt.get("critical_audit_gate") != "PASS"
        or receipt.get("supervisor_offline_gate") != "PASS"
        or receipt.get("process_control_offline_gate") != "PASS"
        or receipt.get("memory_monitoring_offline_gate") != "PASS"
        or receipt.get("receipt_attestation_event_id") is None
    ):
        raise OfflineRunnerError("SUPERVISOR_RECEIPT_INVALID")
    audit = ledger_snapshot.get("critical_audit")
    events = audit.get("events") if type(audit) is dict else None
    if type(events) is not list or audit.get("quarantined") is not False:
        raise OfflineRunnerError("SUPERVISOR_AUDIT_UNAVAILABLE")
    event_by_id = {
        item.get("event_id"): item for item in events if type(item) is dict
    }
    acknowledgements = receipt.get("critical_audit_acknowledgements")
    if type(acknowledgements) is not list or not acknowledgements:
        raise OfflineRunnerError("SUPERVISOR_AUDIT_ACK_MISSING")
    acknowledged_ids: set[str] = set()
    previous_sequence = 0
    for ack in acknowledgements:
        if type(ack) is not dict:
            raise OfflineRunnerError("SUPERVISOR_AUDIT_ACK_INVALID")
        event = event_by_id.get(ack.get("event_id"))
        if (
            ack.get("run_id") != run_id
            or event is None
            or event.get("event_hash") != ack.get("event_hash")
            or event.get("sequence") != ack.get("sequence")
            or type(ack.get("sequence")) is not int
            or ack.get("sequence", 0) <= previous_sequence
            or ack.get("event_id") in acknowledged_ids
        ):
            raise OfflineRunnerError("SUPERVISOR_AUDIT_ACK_INVALID")
        acknowledged_ids.add(str(ack["event_id"]))
        previous_sequence = ack["sequence"]
    stage_events: dict[str, list[dict[str, object]]] = {}
    for event in events:
        if type(event) is not dict or event.get("event_id") not in acknowledged_ids:
            continue
        try:
            details = json.loads(str(event.get("details_json")))
        except (TypeError, ValueError):
            continue
        if type(details) is dict and details.get("stage") == stage:
            stage_events.setdefault(str(event.get("event_type")), []).append(details)
    if any(len(stage_events.get(event_type, [])) != 1 for event_type in (
        "RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "GATE_STARTED",
        "CHILD_PROCESS_CONFIRMED", "SUPERVISOR_RUN_FINISHED",
    )):
        raise OfflineRunnerError("SUPERVISOR_STAGE_AUDIT_INCOMPLETE")
    for event_type in (
        "RUN_INITIALIZED", "PREFLIGHT_CONFIRMED", "GATE_STARTED",
        "CHILD_PROCESS_CONFIRMED", "SUPERVISOR_RUN_FINISHED",
    ):
        if not any(
            item.get("event_type") == event_type
            and item.get("event_id") in acknowledged_ids
            for item in events if type(item) is dict
        ):
            raise OfflineRunnerError("SUPERVISOR_STAGE_AUDIT_ACK_MISSING")
    finished = stage_events["SUPERVISOR_RUN_FINISHED"][0]
    message_limit_exit_attested = (
        stage == "scan"
        and finished.get("exit_code") == 4
        and receipt.get("external_exit_code") == 4
        and receipt.get("message_limit_exit_allowed") is True
        and receipt.get("reason") == "EXPECTED_MESSAGE_LIMIT_EXIT"
    )
    if (
        finished.get("result") != "COMPLETED"
        or not (finished.get("exit_code") == 0 or message_limit_exit_attested)
        or finished.get("tree_confirmed") is not True
    ):
        raise OfflineRunnerError("SUPERVISOR_STAGE_AUDIT_INVALID")
    receipt_hash = sha256_bytes(raw)
    for event_type, expected_id in (
        ("RECEIPT_PREPARED", receipt.get("receipt_prepared_event_id")),
        ("RECEIPT_PERSISTED", receipt.get("receipt_attestation_event_id")),
    ):
        event = event_by_id.get(expected_id)
        if event is None or event.get("event_type") != event_type:
            raise OfflineRunnerError("SUPERVISOR_RECEIPT_AUDIT_INVALID")
        try:
            details = json.loads(str(event.get("details_json")))
        except (TypeError, ValueError):
            raise OfflineRunnerError("SUPERVISOR_RECEIPT_AUDIT_INVALID") from None
        if type(details) is not dict or details.get("receipt_sha256") != receipt_hash:
            raise OfflineRunnerError("SUPERVISOR_RECEIPT_AUDIT_INVALID")
    return receipt_hash


def _trusted_g1_module_origin() -> Path:
    return _trusted_module_origin(
        "telegram_courses.s9_real_gate_producers", "s9_real_gate_producers.py",
    )


def _update_gate_result(
    ledger: S9OperationalLedger,
    *,
    gate: str,
    deadline_ns: int,
    evidence_result: str,
    process_state: str,
    measurements: tuple[int, int, int] | tuple[None, None, None],
    cause: str,
) -> tuple[str, str]:
    status = (
        "RUNNING" if evidence_result in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        else "PARTIAL" if evidence_result == "PARTIAL"
        else "BLOCKED"
    )
    result = evidence_result if status in {"RUNNING", "PARTIAL"} else "BLOCKED"
    try:
        working_set, peak_working_set, private_bytes = measurements
        ledger.update_execution(
            gate=gate,
            status=status,
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
            deadline_ns=deadline_ns,
            process_state=process_state,
            result=result,
            cause=(
                "NONE" if status == "RUNNING"
                else "PROCESS" if status == "PARTIAL"
                else cause
            ),
            working_set=working_set,
            peak_working_set=peak_working_set,
            private_bytes=private_bytes,
        )
        run = ledger.snapshot()["run"]
        if run.get("gate") != gate or run.get("result") != result:
            raise LedgerError("GATE_RESULT_NOT_RECORDED")
        return str(run["status"]), str(run["result"])
    except (LedgerError, KeyError, TypeError, ValueError):
        return "BLOCKED", "BLOCKED"


def _persist_and_update_evidence_gate(
    ledger: S9OperationalLedger,
    run_context: S9RunContext,
    evidence: dict[str, object],
    *,
    deadline_ns: int,
    process_state: str,
    measurements: tuple[int, int, int] | tuple[None, None, None],
) -> tuple[str, str]:
    from telegram_courses.s9_real_gate_producers import persist_gate_receipt

    evidence_result = str(evidence.get("status", "BLOCKED"))
    try:
        if (
            str(evidence.get("gate", "G1")) == "G7"
            and evidence_result in {"PASS", "OFFLINE_SYNTHETIC_PASS"}
        ):
            persist_gate_receipt(
                run_context.run_directory, ledger, evidence,
                before_rename_checkpoint=ledger.checkpoint,
            )
        else:
            persist_gate_receipt(run_context.run_directory, ledger, evidence)
    except Exception:
        evidence_result = "BLOCKED"
    return _update_gate_result(
        ledger,
        gate=str(evidence.get("gate", "G1")),
        deadline_ns=deadline_ns,
        evidence_result=evidence_result,
        process_state=process_state,
        measurements=measurements,
        cause="LEDGER",
    )


def _run_supervised_g1_locked(
    run_context: S9RunContext,
    output_directory: str | Path,
    *,
    require_tty: bool = False,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> SupervisedStageOutcome:
    from telegram_courses.s9_real_gate_producers import (
        G1_WORKER_RECEIPT,
        GateEvidenceError,
        collect_g1_evidence,
        load_approved_manifest,
        read_validated_gate_receipt,
        sha256_bytes,
        validate_g1_evidence,
    )

    ledger = S9OperationalLedger(run_context.ledger_path)
    initial = ledger.snapshot()
    run = initial["run"]
    if (
        run_context.run_id != run.get("run_id")
        or run_context.run_directory.resolve(strict=True)
        != Path(run_context.ledger_path).parent.resolve(strict=True)
        or run.get("gate") != "G1" or run.get("status") != "RUNNING"
        or run.get("result") != "UNKNOWN"
        or run_context.deadline_ns != run.get("deadline_ns")
        or initial["critical_audit"].get("quarantined") is not False
        or any(row["state"] == "RESERVED" for row in initial["reservations"])
    ):
        raise OfflineRunnerError("G1_RUN_PRECONDITION_FAILED")
    try:
        manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(
            run_context.run_directory,
        )
    except GateEvidenceError as error:
        raise OfflineRunnerError("G1_APPROVED_MANIFEST_REQUIRED") from error
    if (run_context.run_directory / G1_WORKER_RECEIPT).exists():
        raise OfflineRunnerError("G1_WORKER_EVIDENCE_ALREADY_EXISTS")
    if (run_context.run_directory / "g1-gate-receipt.json").exists():
        raise OfflineRunnerError("G1_GATE_RECEIPT_ALREADY_EXISTS")
    producer_origin = _trusted_g1_module_origin()
    deadline_ns = ledger.active_global_deadline()
    remaining = (deadline_ns - time.time_ns()) / 1_000_000_000
    if not 0 < remaining <= 3600:
        raise OfflineRunnerError("GLOBAL_DEADLINE_INVALID")
    started = time.monotonic()
    global_deadline = started + remaining
    global_started = global_deadline - 3600.0
    output = _safe_output_directory(output_directory)
    receipt_path = run_context.run_directory / "g1-discovery-supervisor-receipt.json"
    supervisor = supervisor_type(
        receipt_path=receipt_path,
        require_tty=require_tty,
        critical_audit_writer=ledger.record_critical_event,
        ledger_run_id=run_context.run_id,
    )
    release_writer, readmit_writer, handoff_state = _ledger_writer_handoff_callbacks(ledger)
    synthetic_test_seam = _synthetic_test_seam_enabled(supervisor_type)
    from telegram_courses.s9_g0_confirmation import (
        G0ConfirmationError,
        request_g0_confirmation,
    )

    try:
        confirmation = request_g0_confirmation(
            run_context.run_directory,
            ledger,
            run_id=run_context.run_id,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            scope_sha256=_scope_sha256,
            test_mode=synthetic_test_seam,
        )
        if (
            confirmation.get("status") != (
                "OFFLINE_SYNTHETIC_PASS" if synthetic_test_seam else "PASS"
            )
            or confirmation.get("evidence_origin") != (
                "SYNTHETIC" if synthetic_test_seam else "HUMAN_INTERACTIVE"
            )
        ):
            raise GateEvidenceError("G0_HUMAN_CONFIRMATION_REQUIRED")
        _update_gate_result(
            ledger,
            gate="G0",
            deadline_ns=deadline_ns,
            evidence_result=str(confirmation.get("status", "BLOCKED")),
            process_state="UNKNOWN",
            measurements=(None, None, None),
            cause="LEDGER",
        )
        attested_confirmation = read_validated_gate_receipt(
            run_context.run_directory,
            ledger.snapshot(),
            "G0",
            run_id=run_context.run_id,
            manifest_sha256=manifest_sha256,
        )
        if (
            attested_confirmation.get("status") != confirmation.get("status")
            or attested_confirmation.get("evidence_origin") != confirmation.get("evidence_origin")
        ):
            raise GateEvidenceError("G0_CONFIRMATION_NOT_ATTESTED")
        ledger.update_execution(
            gate="G1",
            status="RUNNING",
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
            deadline_ns=deadline_ns,
            process_state="UNKNOWN",
            result="UNKNOWN",
            cause="NONE",
        )
        resumed = ledger.snapshot()["run"]
        if resumed.get("gate") != "G1" or resumed.get("status") != "RUNNING":
            raise LedgerError("G1_NOT_RESUMED_AFTER_G0")
    except (G0ConfirmationError, GateEvidenceError, LedgerError, OSError, ValueError):
        try:
            current = ledger.snapshot()["run"]
            if current.get("status") == "RUNNING":
                ledger.update_execution(
                    gate="G0",
                    status="BLOCKED",
                    elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
                    deadline_ns=deadline_ns,
                    process_state="UNKNOWN",
                    result="BLOCKED",
                    cause="PROCESS",
                )
        except (LedgerError, KeyError, TypeError, ValueError):
            pass
        raise OfflineRunnerError("G0_CONFIRMATION_REQUIRED") from None
    if synthetic_test_seam:
        # Synthetic G1 evidence is available only to a marked injected test
        # supervisor and its explicitly injected gateway/credential providers.
        # The production worker remains bound to human G0 and cannot inherit
        # this seam from CLI arguments or environment variables.
        gateway_factory = supervisor_type.__dict__.get(
            "_s9_g1_gateway_factory",
        )
        credentials_loader = supervisor_type.__dict__.get(
            "_s9_g1_credentials_loader",
        )
        if not callable(gateway_factory) or not callable(credentials_loader):
            raise OfflineRunnerError("G1_SYNTHETIC_TEST_DEPENDENCIES_REQUIRED")
        try:
            worker_evidence = asyncio.run(collect_g1_evidence(
                run_id=run_context.run_id,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                gateway_factory=gateway_factory,
                credentials_loader=credentials_loader,
            ))
            synthetic_status, _synthetic_reason = validate_g1_evidence(
                worker_evidence,
                run_id=run_context.run_id,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
            )
            if (
                synthetic_status != "OFFLINE_SYNTHETIC_PASS"
                or worker_evidence.get("evidence_origin") != "SYNTHETIC"
            ):
                raise GateEvidenceError("G1_SYNTHETIC_TEST_EVIDENCE_INVALID")
            from telegram_courses.s9_supervisor import _write_no_overwrite_json

            _write_no_overwrite_json(
                run_context.run_directory / G1_WORKER_RECEIPT,
                worker_evidence,
                before_rename=lambda _raw: None,
                after_rename=lambda _raw: None,
            )
        except (GateEvidenceError, OSError, TypeError, ValueError):
            raise OfflineRunnerError("G1_SYNTHETIC_TEST_EVIDENCE_INVALID") from None
    try:
        result = supervisor.run(
            [
                *_trusted_python_command(_TRUSTED_G1_BOOTSTRAP),
                str(producer_origin), str(run_context.run_directory),
                run_context.run_id, manifest_sha256,
            ],
            stage="discovery",
            timeout_seconds=STAGE_TIMEOUTS_SECONDS["discovery"],
            global_deadline_monotonic=global_deadline,
            global_started_monotonic=global_started,
            cwd=output,
            release_ledger_writer=release_writer,
            readmit_ledger_writer=readmit_writer,
            environment=_stage_child_environment(
                stage="discovery", ledger_path=run_context.ledger_path,
            ),
        )
    except Exception:
        result = SupervisorResult(
            run_id=run_context.run_id, result="BLOCKED",
            reason="SUPERVISOR_EXCEPTION", exit_code=None,
            receipt_path=receipt_path, receipt_persisted=False,
            supervisor_gate="BLOCKED", process_control_gate="UNCONTAINED",
            memory_monitoring_gate="BLOCKED", critical_audit_gate="BLOCKED",
        )
    if handoff_state["handoff"] and not handoff_state["parent_readmitted"]:
        return SupervisedStageOutcome(
            supervisor=result, ledger_path=run_context.ledger_path,
            ledger_status="BLOCKED", ledger_result="BLOCKED",
            stage="discovery", stage_gate="G1", stage_gate_result="BLOCKED",
            deadline_ns=deadline_ns,
        )
    measurements = _sampled_memory(receipt_path)
    passed = (
        result.result == "COMPLETED" and result.exit_code == 0
        and result.run_id == run_context.run_id
        and result.supervisor_gate == "PASS"
        and result.process_control_gate == "PASS"
        and result.memory_monitoring_gate == "PASS"
        and result.critical_audit_gate == "PASS"
        and result.receipt_persisted and result.receipt_attested
        and None not in measurements
    )
    evidence: dict[str, object] = {
        "schema_version": 1,
        "gate": "G1",
        "status": "BLOCKED",
        "reason": "SUPERVISED_DISCOVERY_NOT_PASSED",
        "run_id": run_context.run_id,
        "manifest_sha256": manifest_sha256,
        "channel_id": manifest["channel_id"],
        "channel_alias": manifest["channel_alias"],
        "supervisor_stage": "discovery",
        "supervisor_receipt_file": "g1-discovery-supervisor-receipt.json",
    }
    if passed:
        try:
            supervisor_hash = _read_supervisor_receipt_evidence(
                receipt_path, ledger.snapshot(), run_id=run_context.run_id,
                stage="discovery",
            )
            worker_path = run_context.run_directory / G1_WORKER_RECEIPT
            _verify_private_file(worker_path)
            raw_worker = worker_path.read_bytes()
            worker_evidence = json.loads(raw_worker.decode("utf-8"))
            if type(worker_evidence) is not dict:
                raise GateEvidenceError("G1_WORKER_EVIDENCE_INVALID")
            gate_status, reason = validate_g1_evidence(
                worker_evidence, run_id=run_context.run_id,
                manifest=manifest, manifest_sha256=manifest_sha256,
            )
            worker_receipt = dict(worker_evidence) | {
                "supervisor_stage": "discovery",
                "supervisor_receipt_file": receipt_path.name,
                "supervisor_receipt_sha256": supervisor_hash,
                "worker_evidence_sha256": sha256_bytes(raw_worker),
            }
            if gate_status == "PASS" or (
                synthetic_test_seam and gate_status == "OFFLINE_SYNTHETIC_PASS"
            ):
                evidence = worker_receipt
            else:
                evidence = worker_receipt | {
                    "status": "BLOCKED",
                    "reason": reason,
                }
        except (GateEvidenceError, LedgerError, OSError, ValueError):
            evidence.update({"status": "BLOCKED", "reason": "G1_EVIDENCE_OR_AUDIT_INVALID"})
    ledger_status, ledger_result = _persist_and_update_evidence_gate(
        ledger,
        run_context,
        evidence,
        deadline_ns=deadline_ns,
        process_state=(
            "EXITED" if result.process_control_gate == "PASS" and result.exit_code is not None
            else "CONTAINED" if result.process_control_gate == "PASS"
            else "UNCONTAINED"
        ),
        measurements=measurements,
    )
    stage_gate_result = (
        ledger_result
        if ledger_status == "RUNNING" and ledger_result in {
            "PASS", "OFFLINE_SYNTHETIC_PASS",
        }
        else "BLOCKED"
    )
    return SupervisedStageOutcome(
        supervisor=result, ledger_path=run_context.ledger_path,
        ledger_status=ledger_status, ledger_result=ledger_result,
        stage="discovery", stage_gate="G1", stage_gate_result=stage_gate_result,
        deadline_ns=deadline_ns,
    )


def run_supervised_g1(
    run_context: S9RunContext,
    output_directory: str | Path,
    *,
    require_tty: bool = False,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> SupervisedStageOutcome:
    """Collect authenticated G1 evidence under the existing S9 supervisor."""
    selected_ledger = Path(run_context.ledger_path)
    if not selected_ledger.is_absolute():
        raise OfflineRunnerError("LEDGER_PATH_MUST_BE_ABSOLUTE")
    try:
        info = selected_ledger.lstat()
    except OSError as error:
        raise OfflineRunnerError("LEDGER_PATH_UNAVAILABLE") from error
    if not selected_ledger.is_file() or selected_ledger.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
        raise OfflineRunnerError("LEDGER_PATH_UNSAFE")
    try:
        run_guard = _open_private_directory_guard(run_context.run_directory)
        run_guard.verify(run_context.run_directory)
    except LedgerError as error:
        raise OfflineRunnerError("RUN_DIRECTORY_PRIVATE_OR_UNAVAILABLE") from error
    try:
        with _QueueRunLock(selected_ledger):
            return _run_supervised_g1_locked(
                run_context, output_directory, require_tty=require_tty,
                supervisor_type=supervisor_type,
            )
    finally:
        run_guard.close()


def _run_supervised_cli_stage_locked(
    run_context: S9RunContext,
    output_directory: str | Path,
    cli_arguments: Sequence[str],
    *,
    require_tty: bool = True,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> SupervisedStageOutcome:
    trusted_cli_origin = _trusted_cli_module_origin()
    stage, gate, arguments = _validate_supervised_stage_arguments(cli_arguments)
    selected_ledger = Path(run_context.ledger_path)
    if not selected_ledger.is_absolute():
        raise OfflineRunnerError("LEDGER_PATH_MUST_BE_ABSOLUTE")
    ledger = S9OperationalLedger(selected_ledger)
    try:
        deadline_ns = ledger.active_global_deadline()
        initial = ledger.snapshot()
    except LedgerError as error:
        raise OfflineRunnerError("GLOBAL_RUN_NOT_ACTIVE") from error
    if (
        run_context.deadline_ns != deadline_ns
        or run_context.run_id != initial["run"]["run_id"]
        or run_context.run_directory.resolve(strict=True)
        != selected_ledger.parent.resolve(strict=True)
    ):
        raise OfflineRunnerError("RUN_CONTEXT_MISMATCH")
    if any(row["state"] == "RESERVED" for row in initial["reservations"]):
        raise OfflineRunnerError("UNRESOLVED_RESERVATION_REQUIRES_CONTAINMENT")
    synthetic_test_seam = _synthetic_test_seam_enabled(supervisor_type)
    _stage_precondition(
        stage, gate, initial["run"], allow_synthetic=synthetic_test_seam,
    )
    parsed = None
    database_path: Path | None = None
    if stage != "verification_local":
        from telegram_courses.cli import _parse_arguments

        parsed = _parse_arguments(arguments)
        database_path = _safe_absolute_database_path(parsed.database)
        try:
            run_root = run_context.run_directory.resolve(strict=True)
            if database_path.resolve(strict=False).parent != run_root:
                raise OfflineRunnerError("STAGE_DATABASE_MUST_BE_IN_PRIVATE_RUN")
            if database_path.resolve(strict=False) == selected_ledger.resolve(strict=True):
                raise OfflineRunnerError("STAGE_DATABASE_MUST_NOT_BE_LEDGER")
            if os.path.exists(database_path) and os.path.samefile(database_path, selected_ledger):
                raise OfflineRunnerError("STAGE_DATABASE_MUST_NOT_BE_LEDGER")
            if os.path.exists(database_path):
                _verify_private_file(database_path)
        except OSError as error:
            raise OfflineRunnerError("STAGE_DATABASE_PATH_UNAVAILABLE") from error
        except LedgerError as error:
            raise OfflineRunnerError("STAGE_DATABASE_NOT_PRIVATE") from error

    manifest: dict[str, object] | None = None
    manifest_sha256: str | None = None
    g1_evidence: dict[str, object] | None = None
    g2_receipt: dict[str, object] | None = None
    g6_receipt: dict[str, object] | None = None
    database_scan_ids_before: set[str] | None = None
    database_catalog_ids_before: set[str] | None = None
    g7_baseline_scan_run_id: str | None = None
    g7_database_sha256_before: str | None = None
    g7_sync_index: int | None = None
    g7_previous_receipt: dict[str, object] | None = None
    ledger_before = initial
    if (
        stage == "scan" and gate in {"G2", "G7"}
        or stage == "catalog" and gate == "G3"
    ):
        from telegram_courses.s9_real_gate_producers import (
            MAX_G7_SYNCS,
            GateEvidenceError,
            _database_sha256,
            _g7_receipt_filename,
            _g7_supervisor_receipt_filename,
            _ledger_scan_rows,
            load_approved_manifest,
            read_g7_baseline,
            read_sqlite_ids,
            read_validated_gate_receipt,
        )

        try:
            manifest, manifest_sha256, _scope_sha256 = load_approved_manifest(
                run_context.run_directory,
            )
            if parsed is None or parsed.channel_id != manifest.get("channel_id"):
                raise GateEvidenceError("STAGE_CHANNEL_MANIFEST_MISMATCH")
            g0 = read_validated_gate_receipt(
                run_context.run_directory, initial, "G0",
                run_id=run_context.run_id, manifest_sha256=manifest_sha256,
            )
            real_g0 = (
                g0.get("status") == "PASS"
                and g0.get("evidence_origin") == "HUMAN_INTERACTIVE"
                and g0.get("confirmation_source") == "INTERACTIVE_TTY"
            )
            synthetic_g0 = (
                g0.get("status") == "OFFLINE_SYNTHETIC_PASS"
                and g0.get("evidence_origin") == "SYNTHETIC"
                and g0.get("confirmation_source") == "SYNTHETIC_TEST"
            )
            if not (real_g0 or synthetic_test_seam and synthetic_g0):
                raise GateEvidenceError("G0_CONFIRMATION_NOT_HUMAN")
            g1_evidence = read_validated_gate_receipt(
                run_context.run_directory, initial, "G1",
                run_id=run_context.run_id, manifest_sha256=manifest_sha256,
            )
            real_g1 = (
                g1_evidence.get("status") == "PASS"
                and g1_evidence.get("evidence_origin") == "REAL_CONTRACTUAL"
            )
            synthetic_g1 = (
                g1_evidence.get("status") == "OFFLINE_SYNTHETIC_PASS"
                and g1_evidence.get("evidence_origin") == "SYNTHETIC"
            )
            if not (real_g1 or synthetic_test_seam and synthetic_g1):
                raise GateEvidenceError("G1_NOT_REAL_PASS")
            if gate == "G2":
                if parsed.incremental:
                    raise GateEvidenceError("G2_REQUIRES_FULL_SCAN")
                database_scan_ids_before = read_sqlite_ids(
                    run_context.run_directory, database_path, "scan_runs",
                )
            elif gate == "G7":
                if not parsed.incremental or parsed.reconcile_window != 50:
                    raise GateEvidenceError("G7_REQUIRES_BOUNDED_INCREMENTAL_SCAN")
                g2_receipt = read_validated_gate_receipt(
                    run_context.run_directory, initial, "G2",
                    run_id=run_context.run_id, manifest_sha256=manifest_sha256,
                )
                g6_receipt = read_validated_gate_receipt(
                    run_context.run_directory, initial, "G6",
                    run_id=run_context.run_id, manifest_sha256=manifest_sha256,
                )
                expected_predecessor_origin = (
                    "SYNTHETIC" if synthetic_test_seam else "REAL_CONTRACTUAL"
                )
                expected_predecessor_status = (
                    "OFFLINE_SYNTHETIC_PASS"
                    if synthetic_test_seam else "PASS"
                )
                if (
                    g2_receipt.get("status") != expected_predecessor_status
                    or g2_receipt.get("evidence_origin") != expected_predecessor_origin
                    or g2_receipt.get("scan_status") != "COMPLETE"
                    or g2_receipt.get("stop_reason") is not None
                    or g6_receipt.get("status") != expected_predecessor_status
                    or g6_receipt.get("evidence_origin") != expected_predecessor_origin
                    or g6_receipt.get("channel_id") != manifest.get("channel_id")
                    or g6_receipt.get("database_file") != database_path.name
                    or g2_receipt.get("database_file") != database_path.name
                ):
                    raise GateEvidenceError("G7_REAL_PREDECESSOR_REQUIRED")
                g7_baseline_scan_run_id, _high_water = read_g7_baseline(
                    run_context.run_directory, database_path,
                    channel_id=manifest["channel_id"],
                )
                g7_database_sha256_before = _database_sha256(database_path)
                previous_scans = _ledger_scan_rows(initial)
                g7_sync_index = sum(
                    row.get("incremental") == 1 for row in previous_scans
                ) + 1
                if g7_sync_index > MAX_G7_SYNCS:
                    raise GateEvidenceError("G7_SYNC_BUDGET_EXCEEDED")
                if g7_sync_index == 1:
                    if g6_receipt.get("database_sha256") != g7_database_sha256_before:
                        raise GateEvidenceError("G7_G6_DATABASE_SNAPSHOT_MISMATCH")
                else:
                    g7_previous_receipt = read_validated_gate_receipt(
                        run_context.run_directory, initial, "G7",
                        run_id=run_context.run_id,
                        manifest_sha256=manifest_sha256,
                        receipt_index=1,
                    )
                    if (
                        g7_previous_receipt.get("sync_index") != 1
                        or g7_previous_receipt.get("status") != expected_predecessor_status
                        or g7_previous_receipt.get("evidence_origin") != expected_predecessor_origin
                        or g7_previous_receipt.get("scan_status") != "COMPLETE"
                        or g7_previous_receipt.get("incremental_scan_run_id")
                        != g7_baseline_scan_run_id
                        or g7_previous_receipt.get("database_sha256_after")
                        != g7_database_sha256_before
                    ):
                        raise GateEvidenceError("G7_PREVIOUS_SYNC_REQUIRED")
                database_scan_ids_before = read_sqlite_ids(
                    run_context.run_directory, database_path, "scan_runs",
                )
                if g7_sync_index is None:
                    raise GateEvidenceError("G7_SYNC_INDEX_UNAVAILABLE")
                if (
                    run_context.run_directory
                    / _g7_receipt_filename(g7_sync_index)
                ).exists():
                    raise GateEvidenceError("G7_RECEIPT_ALREADY_EXISTS")
                if (
                    run_context.run_directory
                    / _g7_supervisor_receipt_filename(g7_sync_index)
                ).exists():
                    raise GateEvidenceError("G7_SUPERVISOR_RECEIPT_ALREADY_EXISTS")
                if (
                    run_context.run_directory / "g7-gate-receipt.json"
                ).exists() or (
                    run_context.run_directory / "g7-scan-supervisor-receipt.json"
                ).exists():
                    raise GateEvidenceError("G7_LEGACY_RECEIPT_PRESENT")
            else:
                g2_receipt = read_validated_gate_receipt(
                    run_context.run_directory, initial, "G2",
                    run_id=run_context.run_id, manifest_sha256=manifest_sha256,
                )
                if (
                    g2_receipt.get("status") != (
                        "OFFLINE_SYNTHETIC_PASS" if synthetic_test_seam else "PASS"
                    )
                    or g2_receipt.get("evidence_origin") != (
                        "SYNTHETIC" if synthetic_test_seam else "REAL_CONTRACTUAL"
                    )
                    or g2_receipt.get("channel_id") != manifest.get("channel_id")
                ):
                    raise GateEvidenceError("G2_NOT_REAL_PASS")
                database_catalog_ids_before = read_sqlite_ids(
                    run_context.run_directory, database_path, "catalog_runs",
                )
        except GateEvidenceError as error:
            raise OfflineRunnerError("REAL_GATE_PREDECESSOR_OR_MANIFEST_INVALID") from error

    deadline_remaining = (deadline_ns - time.time_ns()) / 1_000_000_000
    if not 0 < deadline_remaining <= 3600:
        raise OfflineRunnerError("GLOBAL_DEADLINE_INVALID")
    started = time.monotonic()
    global_deadline = started + deadline_remaining
    global_started = global_deadline - 3600.0
    if global_started > started:
        raise OfflineRunnerError("GLOBAL_DEADLINE_INVALID")

    output = _safe_output_directory(output_directory)
    receipt_name = (
        _g7_supervisor_receipt_filename(g7_sync_index)
        if gate == "G7" and g7_sync_index is not None
        else f"{gate.lower()}-{stage}-supervisor-receipt.json"
    )
    receipt_path = run_context.run_directory / receipt_name
    supervisor = supervisor_type(
        receipt_path=receipt_path,
        require_tty=require_tty,
        critical_audit_writer=ledger.record_critical_event,
        ledger_run_id=run_context.run_id,
    )
    handoff_state: dict[str, object] | None = None
    release_writer = None
    readmit_writer = None
    if stage == "scan":
        release_writer, readmit_writer, handoff_state = _ledger_writer_handoff_callbacks(ledger)
    stage_started_ns = time.time_ns()
    try:
        result = supervisor.run(
            [
                *_trusted_python_command(_TRUSTED_CLI_BOOTSTRAP),
                str(trusted_cli_origin), *arguments,
            ],
            stage=stage,
            timeout_seconds=STAGE_TIMEOUTS_SECONDS[stage],
            allow_message_limit_exit=(stage == "scan" and gate in {"G2", "G7"}),
            global_deadline_monotonic=global_deadline,
            global_started_monotonic=global_started,
            cwd=output,
            release_ledger_writer=release_writer,
            readmit_ledger_writer=readmit_writer,
            environment=_stage_child_environment(
                stage=stage, ledger_path=selected_ledger,
            ),
        )
    except Exception:
        result = SupervisorResult(
            run_id=run_context.run_id,
            result="BLOCKED",
            reason="SUPERVISOR_EXCEPTION",
            exit_code=None,
            receipt_path=receipt_path,
            receipt_persisted=False,
            supervisor_gate="BLOCKED",
            process_control_gate="UNCONTAINED",
            memory_monitoring_gate="BLOCKED",
            critical_audit_gate="BLOCKED",
        )
    if (
        handoff_state is not None and handoff_state["handoff"]
        and not handoff_state["parent_readmitted"]
    ):
        return SupervisedStageOutcome(
            supervisor=result, ledger_path=selected_ledger,
            ledger_status="BLOCKED", ledger_result="BLOCKED",
            stage=stage, stage_gate=gate, stage_gate_result="BLOCKED",
            deadline_ns=deadline_ns,
        )
    stage_finished_ns = time.time_ns()

    process_state = (
        "EXITED" if result.process_control_gate == "PASS" and result.exit_code is not None
        else "CONTAINED" if result.process_control_gate == "PASS"
        else "UNCONTAINED"
    )
    working_set, peak_working_set, private_bytes = _sampled_memory(receipt_path)
    globally_expired = _global_deadline_expired(result, deadline_ns)
    application_exit_acceptable = result.exit_code == 0 or (
        stage == "scan" and gate in {"G2", "G7"} and result.exit_code == 4
        and result.reason == "EXPECTED_MESSAGE_LIMIT_EXIT"
    )
    supervisor_passed = (
        result.result == "COMPLETED"
        and application_exit_acceptable
        and result.supervisor_gate == "PASS"
        and result.process_control_gate == "PASS"
        and result.memory_monitoring_gate == "PASS"
        and result.critical_audit_gate == "PASS"
        and result.receipt_persisted
        and result.receipt_attested
        and working_set is not None
        and peak_working_set is not None
        and private_bytes is not None
    )
    stage_gate_result = "BLOCKED"
    if globally_expired:
        status, stage_result, cause = "PARTIAL", "PARTIAL", "DEADLINE"
    elif supervisor_passed:
        # Process success is evidence for this wrapper only. G2/G3 need their
        # own persistence and manifest reconciliation before they can pass.
        status, stage_result, cause = "RUNNING", "UNKNOWN", "NONE"
        stage_gate_result = "NOT_ASSESSED"
    else:
        status, stage_result = "BLOCKED", "BLOCKED"
        if result.process_control_gate != "PASS" or result.exit_code not in {None, 0}:
            cause = "PROCESS"
        elif result.memory_monitoring_gate != "PASS" or working_set is None:
            cause = "MEMORY"
        elif (
            result.critical_audit_gate != "PASS"
            or not result.receipt_persisted or not result.receipt_attested
        ):
            cause = "LEDGER"
        elif result.reason in {"STAGE_TIMEOUT_EXCEEDED", "PROCESS_TIMEOUT"} or result.result == "TIMED_OUT":
            cause = "TIMEOUT"
        else:
            cause = "PROCESS"
    try:
        ledger.update_execution(
            gate=gate,
            status=status,
            elapsed_ms=S9OperationalLedger.execution_elapsed_ms(ledger.snapshot()),
            deadline_ns=deadline_ns,
            process_state=process_state,
            result=stage_result,
            cause=cause,
            working_set=working_set,
            peak_working_set=peak_working_set,
            private_bytes=private_bytes,
        )
        ledger_snapshot = ledger.snapshot()["run"]
        ledger_status = str(ledger_snapshot["status"])
        ledger_result = str(ledger_snapshot["result"])
        if ledger_snapshot["gate"] != gate:
            raise LedgerError("STAGE_GATE_NOT_RECORDED")
    except (LedgerError, KeyError, TypeError, ValueError):
        ledger_status, ledger_result = "BLOCKED", "BLOCKED"
        stage_gate_result = "BLOCKED"

    if supervisor_passed and stage == "scan" and gate == "G2":
        from telegram_courses.s9_real_gate_producers import (
            reconcile_g2_scan,
        )

        try:
            ledger_after = ledger.snapshot()
            supervisor_hash = _read_supervisor_receipt_evidence(
                receipt_path, ledger_after, run_id=run_context.run_id,
                stage="scan", expected_exit_code=result.exit_code,
            )
            evidence = reconcile_g2_scan(
                run_context.run_directory,
                database_path,
                run_id=run_context.run_id,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                g1_evidence=g1_evidence,
                ledger_after=ledger_after,
                database_scan_ids_before=database_scan_ids_before,
                ledger_before=ledger_before,
                requested_max_messages=parsed.max_messages,
                application_exit_code=result.exit_code,
                external_exit_code=result.exit_code,
                stage_started_ns=stage_started_ns,
                stage_finished_ns=stage_finished_ns,
            )
            evidence.update({
                "supervisor_stage": "scan",
                "supervisor_receipt_file": receipt_path.name,
                "supervisor_receipt_sha256": supervisor_hash,
            })
            ledger_status, ledger_result = _persist_and_update_evidence_gate(
                ledger, run_context, evidence,
                deadline_ns=deadline_ns,
                process_state=process_state,
                measurements=(working_set, peak_working_set, private_bytes),
            )
            stage_gate_result = (
                "PASS" if ledger_status == "RUNNING" and ledger_result == "PASS"
                else "OFFLINE_SYNTHETIC_PASS"
                if ledger_status == "RUNNING" and ledger_result == "OFFLINE_SYNTHETIC_PASS"
                else "BLOCKED"
            )
        except (GateEvidenceError, OfflineRunnerError, LedgerError, OSError, ValueError):
            ledger_status, ledger_result = _update_gate_result(
                ledger, gate="G2", deadline_ns=deadline_ns,
                evidence_result="BLOCKED", process_state=process_state,
                measurements=(working_set, peak_working_set, private_bytes),
                cause="LEDGER",
            )
            stage_gate_result = "BLOCKED"
    elif supervisor_passed and stage == "scan" and gate == "G7":
        from telegram_courses.s9_real_gate_producers import (
            GateEvidenceError,
            reconcile_g7_scan,
        )

        try:
            if (
                manifest is None or manifest_sha256 is None
                or g1_evidence is None or g2_receipt is None or g6_receipt is None
                or database_scan_ids_before is None
                or g7_baseline_scan_run_id is None
                or g7_database_sha256_before is None or parsed is None
                or g7_sync_index is None
            ):
                raise GateEvidenceError("G7_STAGE_CONTEXT_INCOMPLETE")
            ledger_after = ledger.snapshot()
            supervisor_hash = _read_supervisor_receipt_evidence(
                receipt_path, ledger_after, run_id=run_context.run_id,
                stage="scan", expected_exit_code=result.exit_code,
            )
            evidence = reconcile_g7_scan(
                run_context.run_directory,
                database_path,
                run_id=run_context.run_id,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                g1_evidence=g1_evidence,
                g2_evidence=g2_receipt,
                g6_evidence=g6_receipt,
                baseline_scan_run_id=g7_baseline_scan_run_id,
                database_scan_ids_before=database_scan_ids_before,
                database_sha256_before=g7_database_sha256_before,
                ledger_before=ledger_before,
                ledger_after=ledger_after,
                requested_max_messages=parsed.max_messages,
                application_exit_code=result.exit_code,
                external_exit_code=result.exit_code,
                stage_started_ns=stage_started_ns,
                stage_finished_ns=stage_finished_ns,
                sync_index=g7_sync_index,
                previous_g7_evidence=g7_previous_receipt,
            )
            evidence.update({
                "supervisor_stage": "scan",
                "supervisor_receipt_file": receipt_path.name,
                "supervisor_receipt_sha256": supervisor_hash,
            })
            ledger_status, ledger_result = _persist_and_update_evidence_gate(
                ledger, run_context, evidence,
                deadline_ns=deadline_ns,
                process_state=process_state,
                measurements=(working_set, peak_working_set, private_bytes),
            )
            if ledger_status == "RUNNING" and ledger_result == "PASS":
                stage_gate_result = "PASS"
            elif (
                ledger_status == "RUNNING"
                and ledger_result == "OFFLINE_SYNTHETIC_PASS"
            ):
                stage_gate_result = "OFFLINE_SYNTHETIC_PASS"
            elif ledger_status == "PARTIAL" and ledger_result == "PARTIAL":
                stage_gate_result = "PARTIAL"
            else:
                stage_gate_result = "BLOCKED"
        except (GateEvidenceError, OfflineRunnerError, LedgerError, OSError, ValueError):
            ledger_status, ledger_result = _update_gate_result(
                ledger, gate="G7", deadline_ns=deadline_ns,
                evidence_result="BLOCKED", process_state=process_state,
                measurements=(working_set, peak_working_set, private_bytes),
                cause="LEDGER",
            )
            stage_gate_result = "BLOCKED"
    elif supervisor_passed and stage == "catalog" and gate == "G3":
        from telegram_courses.s9_real_gate_producers import (
            reconcile_g3_catalog,
        )

        try:
            ledger_after = ledger.snapshot()
            supervisor_hash = _read_supervisor_receipt_evidence(
                receipt_path, ledger_after, run_id=run_context.run_id, stage="catalog",
            )
            evidence = reconcile_g3_catalog(
                run_context.run_directory,
                database_path,
                run_id=run_context.run_id,
                manifest=manifest,
                manifest_sha256=manifest_sha256,
                g2_receipt=g2_receipt,
                ledger_snapshot=ledger_after,
                database_catalog_ids_before=database_catalog_ids_before,
            )
            evidence.update({
                "supervisor_stage": "catalog",
                "supervisor_receipt_file": receipt_path.name,
                "supervisor_receipt_sha256": supervisor_hash,
            })
            ledger_status, ledger_result = _persist_and_update_evidence_gate(
                ledger, run_context, evidence,
                deadline_ns=deadline_ns,
                process_state=process_state,
                measurements=(working_set, peak_working_set, private_bytes),
            )
            stage_gate_result = (
                "PASS" if ledger_status == "RUNNING" and ledger_result == "PASS"
                else "OFFLINE_SYNTHETIC_PASS"
                if ledger_status == "RUNNING" and ledger_result == "OFFLINE_SYNTHETIC_PASS"
                else "BLOCKED"
            )
        except (GateEvidenceError, OfflineRunnerError, LedgerError, OSError, ValueError):
            ledger_status, ledger_result = _update_gate_result(
                ledger, gate="G3", deadline_ns=deadline_ns,
                evidence_result="BLOCKED", process_state=process_state,
                measurements=(working_set, peak_working_set, private_bytes),
                cause="LEDGER",
            )
            stage_gate_result = "BLOCKED"
    return SupervisedStageOutcome(
        supervisor=result,
        ledger_path=selected_ledger,
        ledger_status=ledger_status,
        ledger_result=ledger_result,
        stage=stage,
        stage_gate=gate,
        stage_gate_result=stage_gate_result,
        deadline_ns=deadline_ns,
    )


def run_supervised_cli_stage(
    run_context: S9RunContext,
    output_directory: str | Path,
    cli_arguments: Sequence[str],
    *,
    require_tty: bool = True,
    supervisor_type: type[WindowsCliSupervisor] = WindowsCliSupervisor,
) -> SupervisedStageOutcome:
    """Run one allowlisted CLI stage against the run's original G1 deadline."""
    selected_ledger = Path(run_context.ledger_path)
    if not selected_ledger.is_absolute():
        raise OfflineRunnerError("LEDGER_PATH_MUST_BE_ABSOLUTE")
    try:
        info = selected_ledger.lstat()
    except OSError as error:
        raise OfflineRunnerError("LEDGER_PATH_UNAVAILABLE") from error
    if (
        not selected_ledger.is_file()
        or selected_ledger.is_symlink()
        or getattr(info, "st_file_attributes", 0) & 0x400
    ):
        raise OfflineRunnerError("LEDGER_PATH_UNSAFE")
    try:
        run_guard = _open_private_directory_guard(run_context.run_directory)
        run_guard.verify(run_context.run_directory)
    except LedgerError as error:
        raise OfflineRunnerError("RUN_DIRECTORY_PRIVATE_OR_UNAVAILABLE") from error
    try:
        with _QueueRunLock(selected_ledger):
            return _run_supervised_cli_stage_locked(
                run_context, output_directory, cli_arguments,
                require_tty=require_tty, supervisor_type=supervisor_type,
            )
    finally:
        run_guard.close()


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    values = list(argv) if argv is not None else sys.argv[1:]
    if values and values[0] in {
        "start-run", "g1", "queue", "stage", "g8", "g9-reconcile",
        "reconcile-offline",
    }:
        parser = argparse.ArgumentParser(
            prog="python -m telegram_courses.s9_supervisor_cli",
            description="Start a durable S9 run, supervise one bounded stage, or reconcile synthetic offline evidence.",
        )
        operations = parser.add_subparsers(dest="operation", required=True)
        start = operations.add_parser("start-run")
        start.add_argument("--run-directory", required=True)
        g1 = operations.add_parser(
            "g1", help="run supervised authentication and channel discovery from an approved private manifest",
        )
        g1.add_argument("--run-directory", required=True)
        g1.add_argument("--output-directory", required=True)
        queue = operations.add_parser("queue")
        queue.add_argument("--run-directory", required=True)
        queue.add_argument("--output-directory", required=True)
        queue.add_argument("--profile", choices=("F", "M"), required=True)
        queue.add_argument("cli_arguments", nargs=argparse.REMAINDER)
        stage = operations.add_parser("stage")
        stage.add_argument("--run-directory", required=True)
        stage.add_argument("--output-directory", required=True)
        stage.add_argument("cli_arguments", nargs=argparse.REMAINDER)
        g8 = operations.add_parser(
            "g8", help="supervise the separate F interruption or S6 V1 recovery stage",
        )
        g8.add_argument("--run-directory", required=True)
        g8.add_argument("--output-directory", required=True)
        g8.add_argument("--phase", choices=("interrupt", "recover"), required=True)
        g8.add_argument("cli_arguments", nargs=argparse.REMAINDER)
        g9 = operations.add_parser(
            "g9-reconcile", help="reopen operational S9 evidence and persist a sanitized G9 report",
        )
        g9.add_argument("--run-directory", required=True)
        g9.add_argument("--database", required=True)
        g9.add_argument("--download-root", required=True)
        reconcile = operations.add_parser(
            "reconcile-offline",
            help="validate a synthetic G1-G8 evidence bundle and persist a G9 receipt; never contacts Telegram",
        )
        reconcile.add_argument("--run-directory", required=True)
        reconcile.add_argument("--evidence-file", required=True)
        return parser.parse_args(values)

    parser = argparse.ArgumentParser(
        prog="python -m telegram_courses.s9_supervisor_cli",
        description="Execute the restricted offline smoke command under Windows supervision.",
    )
    parser.add_argument("--output-directory", required=True)
    args = parser.parse_args(values)
    args.operation = "smoke"
    return args


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _arguments(argv)
        if args.operation == "start-run":
            context = start_supervised_run(args.run_directory)
            print(
                f"s9 run started run_id={context.run_id} "
                f"deadline_ns={context.deadline_ns} ledger={context.ledger_path}"
            )
            return 0
        if args.operation == "g1":
            run_context = load_supervised_run_context(args.run_directory)
            outcome = run_supervised_g1(
                run_context, args.output_directory,
            )
            print(
                f"s9 stage=discovery gate=G1 stage_result={outcome.stage_gate_result} "
                f"supervisor_result={outcome.supervisor.result} "
                f"supervisor_gate={outcome.supervisor.supervisor_gate} "
                f"process_gate={outcome.supervisor.process_control_gate} "
                f"memory_gate={outcome.supervisor.memory_monitoring_gate} "
                f"audit_gate={outcome.supervisor.critical_audit_gate} "
                f"receipt_persisted={outcome.supervisor.receipt_persisted} "
                f"deadline_ns={outcome.deadline_ns} ledger={outcome.ledger_status}"
            )
            return 0 if outcome.stage_gate_result in {
                "PASS", "OFFLINE_SYNTHETIC_PASS",
            } else 4
        if args.operation == "queue":
            cli_arguments = list(args.cli_arguments)
            if cli_arguments and cli_arguments[0] == "--":
                cli_arguments = cli_arguments[1:]
            outcome = run_supervised_queue(
                args.output_directory,
                Path(args.run_directory) / "operational-ledger.sqlite3",
                cli_arguments,
                profile=args.profile,
            )
            print(
                f"s9 queue profile={args.profile} "
                f"result={outcome.supervisor.result} "
                f"queue_gate={outcome.queue_gate_result} "
                f"supervisor_gate={outcome.supervisor.supervisor_gate} "
                f"process_gate={outcome.supervisor.process_control_gate} "
                f"memory_gate={outcome.supervisor.memory_monitoring_gate} "
                f"limit_check={outcome.supervisor.limit_check_result} "
                f"ledger={outcome.ledger_status}"
            )
            return 0 if outcome.queue_gate_result in {
                "PASS", "OFFLINE_SYNTHETIC_PASS",
            } else 4
        if args.operation == "stage":
            cli_arguments = list(args.cli_arguments)
            if cli_arguments and cli_arguments[0] == "--":
                cli_arguments = cli_arguments[1:]
            run_context = load_supervised_run_context(args.run_directory)
            outcome = run_supervised_cli_stage(
                run_context, args.output_directory, cli_arguments,
            )
            print(
                f"s9 stage={outcome.stage} gate={outcome.stage_gate} "
                f"stage_result={outcome.stage_gate_result} "
                f"supervisor_result={outcome.supervisor.result} "
                f"supervisor_gate={outcome.supervisor.supervisor_gate} "
                f"process_gate={outcome.supervisor.process_control_gate} "
                f"memory_gate={outcome.supervisor.memory_monitoring_gate} "
                f"audit_gate={outcome.supervisor.critical_audit_gate} "
                f"receipt_persisted={outcome.supervisor.receipt_persisted} "
                f"deadline_ns={outcome.deadline_ns} ledger={outcome.ledger_status}"
            )
            return 0 if outcome.stage_gate_result in {
                "PASS", "OFFLINE_SYNTHETIC_PASS",
            } else 4
        if args.operation == "g8":
            cli_arguments = list(args.cli_arguments)
            if cli_arguments and cli_arguments[0] == "--":
                cli_arguments = cli_arguments[1:]
            run_context = load_supervised_run_context(args.run_directory)
            outcome = run_supervised_g8(
                run_context,
                args.output_directory,
                cli_arguments,
                phase=args.phase,
            )
            print(
                f"s9 g8 phase={outcome.phase} result={outcome.gate_result} "
                f"supervisor_result={outcome.supervisor.result} "
                f"process_gate={outcome.supervisor.process_control_gate} "
                f"receipt_persisted={outcome.supervisor.receipt_persisted} "
                f"deadline_ns={outcome.deadline_ns} ledger={outcome.ledger_status}"
            )
            return 0 if outcome.gate_result in {
                "INTERRUPTED", "PASS", "OFFLINE_SYNTHETIC_PASS",
            } else 4
        if args.operation == "g9-reconcile":
            from telegram_courses.s9_operational_reconciliation import (
                reconcile_g9_operational,
            )

            outcome = reconcile_g9_operational(
                args.run_directory, args.database, args.download_root,
            )
            print(
                f"s9 g9 result={outcome.result} origin={outcome.evidence_origin} "
                f"real_evidence={outcome.real_evidence_status} "
                f"gates={len(outcome.gates)} receipt={outcome.receipt_path} "
                f"report={outcome.report_path}"
            )
            return 0 if outcome.result in {
                "PASS", "OFFLINE_SYNTHETIC_PASS", "PARTIAL",
            } else 4
        if args.operation == "reconcile-offline":
            from telegram_courses.s9_gate_reconciliation import (
                reconcile_offline_evidence,
            )

            outcome = reconcile_offline_evidence(
                args.run_directory, args.evidence_file,
            )
            print(
                f"s9 offline reconciliation result={outcome.result} "
                f"gates={len(outcome.gates)} real_evidence={outcome.real_evidence_status} "
                f"receipt={outcome.receipt_path}"
            )
            return 0 if outcome.result == "OFFLINE_SYNTHETIC_PASS" else 4
        outcome = run_offline_smoke(args.output_directory)
    except (OfflineRunnerError, OSError, ValueError, RuntimeError):
        sys.stderr.write("offline supervisor blocked\n")
        return 2
    print(
        "offline smoke "
        f"result={outcome.supervisor.result} "
        f"supervisor_gate={outcome.supervisor.supervisor_gate} "
        f"process_gate={outcome.supervisor.process_control_gate} "
        f"memory_gate={outcome.supervisor.memory_monitoring_gate} "
        f"limit_check=UNKNOWN ledger={outcome.ledger_status}"
    )
    return 0 if (
        outcome.supervisor.result == "COMPLETED"
        and outcome.supervisor.exit_code == 0
        and outcome.supervisor.supervisor_gate == "PASS"
        and outcome.supervisor.critical_audit_gate == "PASS"
        and outcome.supervisor.receipt_persisted
        and outcome.supervisor.receipt_attested
        and outcome.ledger_status == "COMPLETED"
    ) else 4


if __name__ == "__main__":
    raise SystemExit(main())
