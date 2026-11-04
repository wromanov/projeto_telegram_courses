"""Isolated, explicitly authorized S6 V2 real-proof harness.

DryRun and all tests use synthetic gateways. Execute mode is intentionally
gated by the native PowerShell launcher and runs each stage in a fresh child
process with a new proof root, SQLite database, and durable budget ledger.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import uuid
import warnings
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CHUNK_BYTES = 256 * 1024
MAX_ATTEMPTS = 3
FLOODWAIT_MAX_SECONDS = 120
MAX_WORKERS = 1
MEDIA_ORDINAL = 0
MEDIA_KIND = "DOCUMENT"
PHASE1_TRANSFER_ATTEMPT_CAP = 1
PHASE2_TRANSFER_ATTEMPT_CAP = MAX_ATTEMPTS - PHASE1_TRANSFER_ATTEMPT_CAP
V2_CONTRACT_SHA256 = "C9C8A59B5F370B67A86D04CE7407517965711AE5E9780A17DED1C56A747BDF52"
COMMON_TARGET = {
    "channel_id": -1002758699600,
    "message_id": 598,
    "media_ordinal": 0,
    "media_kind": MEDIA_KIND,
    "media_id": "5175124468544046445",
    "expected_bytes": 11_649_955,
    "preferred_minimum_bytes": 1024**3,
}
CONTROLLED_TARGET = {
    "channel_id": -1002368271467,
    "message_id": 7603,
    "media_ordinal": 0,
    "media_kind": MEDIA_KIND,
    "media_id": "5089068167339181674",
    "expected_bytes": 1_119_129_690,
}
COMMON_PREFIX_ALIGNED = 1024 * 1024
CONTROLLED_PREFIX_OPTIONS = {"8MiB": 8 * 1024 * 1024, "128MiB": 128 * 1024 * 1024}
CONTROLLED_PREFIX_ALIGNED = CONTROLLED_PREFIX_OPTIONS["8MiB"]
MAX_NATIVE_PATH_CHARS = 240
CANONICAL_TRUSTED_REFERENCE_PATH = Path(r"C:\Users\walac\Downloads\64Gram Desktop\Teste Telegram.rar")
CANONICAL_TRUSTED_REFERENCE_SHA256 = "3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONFIRMATION_PREFIX = "EXECUTE S6 V2 PROOF"
PROOF_STARTUP_TIMEOUT_SECONDS = 30
PROOF_SEMANTIC_IDLE_TIMEOUT_SECONDS = 180
PROOF_OPERATIONAL_PROCESS_TIMEOUT_SECONDS = 3600
PROOF_OPERATIONAL_AGGREGATE_DEADLINE_SECONDS = 900
PROOF_TRUSTED_REFERENCE_PROCESS_TIMEOUT_SECONDS = 4500
PROOF_TRUSTED_REFERENCE_AGGREGATE_DEADLINE_SECONDS = 4800
# Kept as a compatibility alias for existing offline callers/tests. Runtime
# policy is selected by scenario with _deadline_policy().
PROOF_AGGREGATE_DEADLINE_SECONDS = PROOF_OPERATIONAL_AGGREGATE_DEADLINE_SECONDS
PROOF_CANCEL_GRACE_SECONDS = 30
PROOF_PROGRESS_HEARTBEAT_SECONDS = 15
APPROVED_LIMITS = {
    "getfile_calls": 139, "getfilehashes_calls": 138,
    "reserved_bytes": 36_438_016,
}
EFFECTIVE_LIMITS = {
    "getfile_calls": 94, "getfilehashes_calls": 92,
    "reserved_bytes": 24_641_536,
}
UNALIGNED_EFFECTIVE_LIMITS = {
    "getfile_calls": 95, "getfilehashes_calls": 92,
    "reserved_bytes": 24_903_680,
}
TRUSTED_REFERENCE_APPROVED_MAXIMA = {
    "getfile_calls": 8_508,
    "getfilehashes_calls": 8_542,
    "reserved_bytes": 2_230_321_152,
}
_PROGRESS_STAGES = {
    "supervisor.initialized", "supervisor.child_spawned", "child.ready",
    "child.event_loop_initialized", "child.sqlite_created", "child.ledger_created",
    "child.gateway_constructed", "child.session_restored", "child.remote_identity_validated",
    "child.phase1_checkpoint", "child.planned_interruption", "child.phase_report_written",
    "supervisor.phase1_exit", "child.phase2_checkpoint_validated",
    "child.full_prefix_reread", "child.prefix_hash_reconciled", "child.local_prefix_reference_validated",
    "child.continuation_started",
    "child.transfer_progress", "child.finalized", "supervisor.sqlite_ledger_reconciled", "supervisor.child_ready_timeout",
    "supervisor.semantic_idle_timeout", "supervisor.aggregate_timeout", "supervisor.child_exit",
    "child.remote_hash_progress",
}
_PROGRESS_OUTCOMES = {"started", "ready", "created", "restored", "validated", "matched",
    "mismatch", "short", "started_transfer", "completed", "failed",
                      "timeout", "exit_confirmed", "exit_unconfirmed", "interrupted"}
_PROGRESS_COUNTS = {"verified_bytes", "getfile_calls", "getfilehashes_calls", "reserved_bytes"}
_PROGRESS_COUNTS.update({
    "stream_confirmed_bytes", "persisted_bytes", "received_bytes", "stage_count",
    "event_count", "throughput_bytes_per_second",
})
_PROGRESS_SEQUENCE = 0
_PROGRESS_FILE_LOCK = threading.Lock()
_OPERATIONAL_STACK_STREAM = None
_OPERATIONAL_STACK_STOP = threading.Event()
_OPERATIONAL_STACK_THREAD = None

_PROBE_FAULTHANDLER_STREAM = None

# Stable, non-sensitive DownloadError categories that may cross the child
# process boundary. Never forward arbitrary exception attributes or text.
_SAFE_DOWNLOAD_ERROR_CODES = frozenset({
    "ALREADY_COMPLETED_V2", "ALREADY_DOWNLOADED", "ATOMIC_FINALIZATION_FAILED",
    "BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE", "BUDGET_BLOCK", "CANCELLED",
    "CHECKPOINT_INCONSISTENT", "COMPLETED_V2_FILE_MISMATCH", "DESTINATION_EXISTS",
    "DOWNLOAD_ROOT_CHANGED", "DOWNLOADED_FILE_MISMATCH", "FINAL_FILE_MISMATCH",
    "FINAL_FILE_MISSING", "FINALIZATION_FILE_MISMATCH",
    "FINALIZATION_RECOVERY_REQUIRES_EVIDENCE", "GATEWAY_FAILURE",
    "IDENTITY_REVALIDATION_UNAVAILABLE", "INSUFFICIENT_DISK_SPACE", "INVALID_CHUNK",
    "INVALID_HASH_RESPONSE", "INVALID_INTEGRITY_MODE", "MEDIA_NOT_ELIGIBLE",
    "MODE_SELECTION_MISMATCH", "OVERLAP_INCOMPLETE", "OVERLAP_MISMATCH",
    "PARTIAL_CHANGED", "PARTIAL_INTEGRITY_MISMATCH", "PARTIAL_SIZE_EXCEEDED",
    "PATH_ACCESS_FAILED", "PATH_COLLISION", "PATH_CREATE_FAILED", "PATH_TOO_LONG",
    "PREFIX_CONFLICT", "RATE_LIMITED", "REMOTE_HASH_ABSENT", "REMOTE_HASH_COVERAGE_GAP",
    "REMOTE_HASH_DIVERGENT", "REMOTE_HASH_INVALID_RESPONSE", "REMOTE_HASH_RANGE_INVALID",
    "REMOTE_HASH_RESPONSE_INVALID", "REMOTE_HASH_UNAVAILABLE", "REMOTE_HASH_UNVERIFIABLE_EOF",
    "REMOTE_HASHES_INCOMPLETE", "REMOTE_HASHES_UNAVAILABLE", "REMOTE_IDENTITY_CONFLICT",
    "REMOTE_PREFIX_INCOMPLETE", "REFERENCE_ABSENT", "REFERENCE_INVALID",
    "REFERENCE_MISMATCH", "RESUME_IDENTITY_MISMATCH", "SIZE_EXCEEDED", "SIZE_MISMATCH",
    "STATE_COMMIT_PENDING", "TRANSFER_BUDGET_EXCEEDED", "TRANSFER_BUDGET_EXHAUSTED",
    "TRANSFER_BUDGET_STATE_INVALID", "TRANSFER_FAILED", "TRANSFER_IN_PROGRESS",
    "UNKNOWN_LEGACY", "UNOWNED_PARTIAL_EXISTS", "UNSAFE_PATH", "V2_INACTIVE",
    "BUDGET_ENFORCEMENT_UNAVAILABLE", "CHANNEL_MISMATCH", "CONFIGURATION",
    "DIRECT_ITERATOR_INCOMPATIBLE", "INVALID_MEDIA_IDENTITY_REQUEST", "INVALID_OFFSET",
    "INVALID_HASH_REQUEST", "MEDIA_MISMATCH", "MESSAGE_NOT_FOUND", "NETWORK",
    "SESSION_INVALID", "CONTINUATION_INTEGRITY_MISMATCH", "CATALOG_NOT_FOUND",
    "CATALOG_NOT_READY", "CHANNEL_NOT_FOUND", "INVALID_SELECTION", "MEDIA_LIMIT_EXCEEDED",
    "UNKNOWN_SIZE", "RATE_LIMITED", "REMOTE_HASH_RANGE_INVALID",
})
_SAFE_DOWNLOAD_ERROR_STAGES = frozenset({"REMOTE_HASH"})
_SAFE_EXCEPTION_LABELS = frozenset({
    "KeyboardInterrupt", "CancelledError", "TimeoutExpired", "SQLiteError",
    "TimeoutError", "OSError", "ValueError", "TypeError", "AssertionError",
    "RuntimeError", "Exception", "OTHER",
})


def _progress_event(stage: str, *, phase: int, execution_id: str | None = None,
                    outcome: str = "completed", counts: dict[str, int] | None = None,
                    progress_path: Path | None = None, progress_root: Path | None = None) -> None:
    """Append only allowlisted, secret-free operational progress evidence."""
    global _PROGRESS_SEQUENCE
    if stage not in _PROGRESS_STAGES or outcome not in _PROGRESS_OUTCOMES:
        return
    safe_counts = {}
    for key, value in (counts or {}).items():
        if key in _PROGRESS_COUNTS and type(value) is int and value >= 0:
            safe_counts[key] = value
    path_text = str(progress_path) if progress_path is not None else os.environ.get("S6_V2_PROGRESS_JSONL")
    root_text = str(progress_root) if progress_root is not None else os.environ.get("S6_V2_PROGRESS_ROOT")
    if not path_text or not root_text:
        return
    try:
        root = Path(root_text).resolve(strict=True)
        path = Path(path_text)
        if not path.resolve(strict=False).is_relative_to(root):
            return
        with _PROGRESS_FILE_LOCK:
            _PROGRESS_SEQUENCE += 1
            record = {
                "execution_id": execution_id or os.environ.get("S6_V2_PROGRESS_EXECUTION_ID", "unknown"),
                "phase": phase,
                "process_id": os.getpid(), "stage": stage, "sequence": _PROGRESS_SEQUENCE,
                "monotonic_ns": time.monotonic_ns(), "outcome": outcome, "counts": safe_counts,
            }
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        # A missing event is rejected by the supervisor's fail-closed gates.
        return


def _progress_is_semantic(
    event: dict[str, Any], seen_stages: set[str], max_counts: dict[str, int],
) -> bool:
    """Only successful first-stage completion or an increasing safe count advances liveness."""
    if event.get("stage") not in _PROGRESS_STAGES:
        return False
    if event.get("outcome") in {"mismatch", "short", "failed", "timeout"}:
        return False
    completed = {"ready", "created", "restored", "validated", "matched", "completed", "interrupted", "exit_confirmed", "started_transfer"}
    semantic = False
    stage = event.get("stage")
    if stage not in seen_stages and event.get("outcome") in completed:
        seen_stages.add(stage)
        semantic = True
    counts = event.get("counts")
    if isinstance(counts, dict):
        for key, value in counts.items():
            if key in _PROGRESS_COUNTS and type(value) is int and value >= 0 and value > max_counts.get(key, -1):
                max_counts[key] = value
                semantic = True
    return semantic


def _supervisor_timeout_reason(
    *, now: float, spawned: float, last_semantic: float, ready: bool,
    aggregate_started: float, phase_timeout: float, aggregate_deadline: float | None = None,
) -> str | None:
    deadline = PROOF_AGGREGATE_DEADLINE_SECONDS if aggregate_deadline is None else aggregate_deadline
    if now - aggregate_started >= deadline:
        return "AGGREGATE_DEADLINE"
    if not ready and now - spawned >= PROOF_STARTUP_TIMEOUT_SECONDS:
        return "CHILD_READINESS_TIMEOUT"
    if now - last_semantic >= PROOF_SEMANTIC_IDLE_TIMEOUT_SECONDS:
        return "SEMANTIC_INACTIVITY_TIMEOUT"
    if now - spawned >= phase_timeout:
        return "PHASE_PROCESS_TIMEOUT"
    return None


def _deadline_policy(mode: str) -> tuple[int, int]:
    if mode == "TRUSTED_REFERENCE":
        return PROOF_TRUSTED_REFERENCE_PROCESS_TIMEOUT_SECONDS, PROOF_TRUSTED_REFERENCE_AGGREGATE_DEADLINE_SECONDS
    return PROOF_OPERATIONAL_PROCESS_TIMEOUT_SECONDS, PROOF_AGGREGATE_DEADLINE_SECONDS


def _effective_timeout_policy(target: str, mode: str) -> dict[str, object]:
    """Return the timeout values selected by the same config used by execute()."""
    allowed_scenarios = {("common", "OPERATIONAL_ONLY"), ("controlled", "TRUSTED_REFERENCE")}
    if (target, mode) not in allowed_scenarios:
        raise RuntimeError("TIMEOUT_POLICY_SCENARIO_NOT_AUTHORIZED")
    process_timeout, aggregate_deadline = _deadline_policy(mode)
    values: dict[str, object] = {
        "target": target,
        "mode": mode,
        "process_timeout_effective_seconds": process_timeout,
        "aggregate_deadline_effective_seconds": aggregate_deadline,
        "semantic_inactivity_timeout_seconds": PROOF_SEMANTIC_IDLE_TIMEOUT_SECONDS,
        "progress_heartbeat_seconds": PROOF_PROGRESS_HEARTBEAT_SECONDS,
        "cancellation_grace_max_seconds": PROOF_CANCEL_GRACE_SECONDS,
        "grace_inside_hard_deadline": True,
    }
    contract_values = {
        ("common", "OPERATIONAL_ONLY"): (3600, 900, 180, 15, 30),
        ("controlled", "TRUSTED_REFERENCE"): (4500, 4800, 180, 15, 30),
    }[(target, mode)]
    values["contract_match"] = (
        process_timeout, aggregate_deadline, PROOF_SEMANTIC_IDLE_TIMEOUT_SECONDS,
        PROOF_PROGRESS_HEARTBEAT_SECONDS, PROOF_CANCEL_GRACE_SECONDS,
    ) == contract_values
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    values["policy_sha256"] = hashlib.sha256(canonical).hexdigest()
    return values


def _split_progress_buffer(pending: bytes, new_data: bytes) -> tuple[list[bytes], bytes]:
    pieces = (pending + new_data).split(b"\n")
    return pieces[:-1], pieces[-1]


def _child_cancel_requested() -> bool:
    marker_text = os.environ.get("S6_V2_CANCEL_MARKER")
    root_text = os.environ.get("S6_V2_PROGRESS_ROOT")
    if not marker_text or not root_text:
        return False
    try:
        root = Path(root_text).resolve(strict=True)
        raw_marker = Path(marker_text)
        marker = raw_marker.resolve(strict=False)
        return (not raw_marker.is_symlink() and marker.is_relative_to(root)
                and marker.is_file())
    except OSError:
        return False


def _status_only_secure_preflight() -> dict[str, str]:
    """Decrypt existing local artifacts in memory only; never connects or writes."""
    result = {"credential_vault": "NO", "protected_session": "NO", "provider": "WINDOWS_PROTECTED_VAULT"}
    credentials = session_value = None
    try:
        from telegram_courses.config import load_telegram_credentials
        credentials = load_telegram_credentials(environ={})
        result["credential_vault"] = "YES"
    except Exception:
        result["credential_vault"] = "NO"
    try:
        from telegram_courses.telethon_session import _ProtectedSessionVault
        session_value = _ProtectedSessionVault()._load()
        result["protected_session"] = "YES" if session_value else "NO"
    except Exception:
        result["protected_session"] = "NO"
    finally:
        del credentials, session_value
    return result


def _start_operational_stack_capture() -> None:
    """Capture at most one Python stack without locals after a long stall."""
    global _OPERATIONAL_STACK_STREAM, _OPERATIONAL_STACK_THREAD
    stack_path = os.environ.get("S6_V2_STACK_PATH")
    root_text = os.environ.get("S6_V2_PROGRESS_ROOT")
    if not stack_path or not root_text:
        return
    try:
        path = Path(stack_path)
        root = Path(root_text).resolve(strict=True)
        if not path.resolve(strict=False).is_relative_to(root):
            return
        _OPERATIONAL_STACK_STREAM = path.open("a", encoding="utf-8")
        _OPERATIONAL_STACK_STOP.clear()

        def capture_bounded_stacks():
            import faulthandler
            for _ in range(3):
                if _OPERATIONAL_STACK_STOP.wait(10):
                    return
                faulthandler.dump_traceback(file=_OPERATIONAL_STACK_STREAM, all_threads=True)
                _OPERATIONAL_STACK_STREAM.flush()

        _OPERATIONAL_STACK_THREAD = threading.Thread(
            target=capture_bounded_stacks, name="s6-stack-capture", daemon=True,
        )
        _OPERATIONAL_STACK_THREAD.start()
    except Exception:
        _OPERATIONAL_STACK_STREAM = None


def _stop_operational_stack_capture() -> None:
    global _OPERATIONAL_STACK_STREAM, _OPERATIONAL_STACK_THREAD
    if _OPERATIONAL_STACK_STREAM is not None:
        _OPERATIONAL_STACK_STOP.set()
        if _OPERATIONAL_STACK_THREAD is not None:
            _OPERATIONAL_STACK_THREAD.join(timeout=1)
        _OPERATIONAL_STACK_THREAD = None
        _OPERATIONAL_STACK_STREAM.close()
        _OPERATIONAL_STACK_STREAM = None


def _probe_enabled() -> bool:
    return os.environ.get("S6_V2_TEST_PROBE") == "1"


def _probe_mark(stage: str, boundary: str, *, outcome: str | None = None,
                error: BaseException | None = None, execution_id: str | None = None) -> None:
    if not _probe_enabled():
        return
    path_text = os.environ.get("S6_V2_TEST_PROBE_JSONL")
    execution_id = execution_id or os.environ.get("S6_V2_TEST_PROBE_EXECUTION_ID")
    if not path_text or not execution_id:
        return
    try:
        allowed_text = os.environ.get("S6_V2_TEST_ALLOWED_ROOT")
        if not allowed_text:
            return
        event_path = Path(path_text)
        allowed_root = Path(allowed_text).resolve(strict=True)
        if not event_path.resolve(strict=False).is_relative_to(allowed_root):
            return
        try:
            loop = asyncio.get_running_loop()
            loop_name = type(loop).__name__
        except RuntimeError:
            loop_name = None
        thread = threading.current_thread()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            policy_name = type(asyncio.get_event_loop_policy()).__name__
        record = {
            "execution_id": execution_id,
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "monotonic_ns": time.monotonic_ns(),
            "stage": stage,
            "boundary": boundary,
            "outcome": outcome,
            "exception_class": _safe_exception_class(error),
            "thread_id": threading.get_ident(),
            "thread_name": thread.name,
            "loop_type": loop_name,
            "policy_type": policy_name,
        }
        payload = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
        descriptor = os.open(path_text, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)
    except Exception:
        # Diagnostic telemetry must never alter the proof path.
        return


@contextmanager
def _probe_stage(stage: str):
    _probe_mark(stage, "start")
    try:
        yield
    except BaseException as error:
        _probe_mark(stage, "end", outcome="exception", error=error)
        raise
    else:
        _probe_mark(stage, "end", outcome="ok")


def _probe_start_faulthandler() -> None:
    global _PROBE_FAULTHANDLER_STREAM
    if not _probe_enabled() or _PROBE_FAULTHANDLER_STREAM is not None:
        return
    path_text = os.environ.get("S6_V2_TEST_PROBE_STACK_PATH")
    allowed_text = os.environ.get("S6_V2_TEST_ALLOWED_ROOT")
    if not path_text or not allowed_text:
        return
    import faulthandler

    stack_path = Path(path_text)
    if not stack_path.resolve(strict=False).is_relative_to(Path(allowed_text).resolve(strict=True)):
        return
    _PROBE_FAULTHANDLER_STREAM = stack_path.open("a", encoding="utf-8")
    timeout = max(1, min(int(os.environ.get("S6_V2_TEST_PROBE_STACK_SECONDS", "5")), 30))
    faulthandler.dump_traceback_later(timeout, repeat=True, file=_PROBE_FAULTHANDLER_STREAM)


def _probe_stop_faulthandler() -> None:
    global _PROBE_FAULTHANDLER_STREAM
    if _PROBE_FAULTHANDLER_STREAM is None:
        return
    import faulthandler

    faulthandler.cancel_dump_traceback_later()
    _PROBE_FAULTHANDLER_STREAM.close()
    _PROBE_FAULTHANDLER_STREAM = None


_probe_mark("B01_script_entry", "end", outcome="entered")


def _ceil_chunks(count: int) -> int:
    if type(count) is not int or count < 0:
        raise ValueError("INVALID_BYTE_COUNT")
    return (count + CHUNK_BYTES - 1) // CHUNK_BYTES


def proof_budget(expected_bytes: int, prefix_bytes: int, mode: str) -> dict[str, int | str]:
    """Calculate request-quantized bounds for the implemented S6 V2 paths."""
    if mode not in {"OPERATIONAL_ONLY", "TRUSTED_REFERENCE"}:
        raise ValueError("EXPLICIT_V2_MODE_REQUIRED")
    if type(expected_bytes) is not int or expected_bytes <= 0:
        raise ValueError("INVALID_EXPECTED_BYTES")
    if type(prefix_bytes) is not int or not 0 < prefix_bytes < expected_bytes:
        raise ValueError("INVALID_PREFIX_BYTES")

    wire_offset = (prefix_bytes // CHUNK_BYTES) * CHUNK_BYTES
    overlap = prefix_bytes - wire_offset
    reuse_boundary = mode == "OPERATIONAL_ONLY" and overlap > 0
    transfer_offset = wire_offset + CHUNK_BYTES if reuse_boundary else wire_offset
    prefix_reserve = _ceil_chunks(prefix_bytes) * CHUNK_BYTES if mode == "OPERATIONAL_ONLY" else 0
    transfer_reserve = _ceil_chunks(expected_bytes - transfer_offset) * CHUNK_BYTES
    phase1_reserve = _ceil_chunks(prefix_bytes) * CHUNK_BYTES
    one_resume_reserve = prefix_reserve + transfer_reserve
    hash_calls_per_attempt = _ceil_chunks(expected_bytes) + 1
    phase1_getfile_calls = _ceil_chunks(prefix_bytes)
    resume_getfile_calls_per_attempt = (
        (_ceil_chunks(prefix_bytes) if mode == "OPERATIONAL_ONLY" and prefix_bytes else 0)
        + _ceil_chunks(expected_bytes - transfer_offset)
    )
    aggregate_payload_cap = phase1_reserve + PHASE2_TRANSFER_ATTEMPT_CAP * one_resume_reserve
    aggregate_getfile_cap = phase1_getfile_calls + PHASE2_TRANSFER_ATTEMPT_CAP * resume_getfile_calls_per_attempt
    aggregate_hash_cap = PHASE2_TRANSFER_ATTEMPT_CAP * hash_calls_per_attempt
    phase1_identity_cap = 1
    phase2_identity_cap = 2 * PHASE2_TRANSFER_ATTEMPT_CAP
    aggregate_identity_cap = phase1_identity_cap + phase2_identity_cap
    from telegram_courses.s5_downloads import GIB

    phase1_margin = max(GIB, int(expected_bytes * 0.10))
    resume_bytes = expected_bytes - prefix_bytes
    resume_margin = max(GIB, int(resume_bytes * 0.10))
    return {
        "mode": mode,
        "expected_bytes": expected_bytes,
        "prefix_bytes": prefix_bytes,
        "wire_offset": wire_offset,
        "overlap_bytes": overlap,
        "transfer_offset": transfer_offset,
        "phase1_getfile_cap": phase1_getfile_calls,
        "resume_getfile_cap_per_attempt": resume_getfile_calls_per_attempt,
        "phase2_getfile_cap_per_attempt": resume_getfile_calls_per_attempt,
        "aggregate_getfile_cap": aggregate_getfile_cap,
        "getfilehashes_cap_per_attempt": hash_calls_per_attempt,
        "phase1_getfilehashes_cap": 0,
        "phase2_getfilehashes_cap_per_attempt": hash_calls_per_attempt,
        "phase1_identity_getmessages_cap": phase1_identity_cap,
        "phase2_identity_getmessages_cap": phase2_identity_cap,
        "aggregate_identity_getmessages_cap": aggregate_identity_cap,
        "aggregate_getfilehashes_cap": aggregate_hash_cap,
        "phase2_getfile_cap_per_process": PHASE2_TRANSFER_ATTEMPT_CAP * resume_getfile_calls_per_attempt,
        "phase2_getfilehashes_cap_per_process": aggregate_hash_cap,
        "aggregate_getmessages_for_hashes_cap": aggregate_hash_cap,
        "session_restore_getme_cap": 2,
        "aggregate_counted_getmessages_lower_bound_cap": aggregate_hash_cap + aggregate_identity_cap,
        "aggregate_getmessages_total_cap": None,
        "aggregate_getmessages_total_cap_reason": (
            "Unknown; excludes stream metadata refetch calls"
        ),
        "aggregate_selected_media_rpc_lower_bound": (
            aggregate_getfile_cap + aggregate_hash_cap * 2 + aggregate_identity_cap + 2
        ),
        "aggregate_selected_media_rpc_total": None,
        "aggregate_selected_media_rpc_total_reason": (
            "Unknown; lower bound omits per-stream metadata refetch calls and Telethon connect RPCs"
        ),
        "phase1_payload_reservation_cap": phase1_reserve,
        "resume_payload_reservation_cap_per_attempt": one_resume_reserve,
        "phase2_payload_reservation_cap_per_attempt": one_resume_reserve,
        "aggregate_payload_reservation_cap": aggregate_payload_cap,
        "phase2_payload_reservation_cap_per_process": PHASE2_TRANSFER_ATTEMPT_CAP * one_resume_reserve,
        "disk_required_phase1_bytes": expected_bytes + phase1_margin,
        "disk_required_resume_bytes": resume_bytes + resume_margin,
        "phase1_transfer_attempt_cap": PHASE1_TRANSFER_ATTEMPT_CAP,
        "phase2_transfer_attempt_cap": PHASE2_TRANSFER_ATTEMPT_CAP,
        "phase1_s5_attempt_cap": PHASE1_TRANSFER_ATTEMPT_CAP,
        "phase2_s5_attempt_cap": PHASE2_TRANSFER_ATTEMPT_CAP,
        "aggregate_s5_attempt_cap": MAX_ATTEMPTS,
        "s5_attempts_per_media_across_phases": MAX_ATTEMPTS,
        "s5_attempts_per_resume_process": PHASE2_TRANSFER_ATTEMPT_CAP,
        "floodwait_seconds_per_resume_process": FLOODWAIT_MAX_SECONDS,
    }


def target_for(name: str) -> dict[str, Any]:
    if name == "common":
        return dict(COMMON_TARGET)
    if name == "controlled":
        return dict(CONTROLLED_TARGET)
    raise ValueError("UNKNOWN_TARGET")


def _verify_ratified_contract() -> None:
    contract = REPOSITORY_ROOT / "docs/contracts/S6_INTEGRITY_CONTRACT_V2_PROPOSAL_DRAFT.md"
    if not contract.is_file():
        raise RuntimeError("RATIFIED_V2_CONTRACT_MISSING")
    digest = hashlib.sha256(contract.read_bytes()).hexdigest().upper()
    if digest != V2_CONTRACT_SHA256:
        raise RuntimeError("RATIFIED_V2_CONTRACT_HASH_MISMATCH")


def _scoped_v2_switch(mode: str, target: dict[str, Any], authorized: bool):
    """Temporarily open only this child process's single-item V2 app call."""
    if mode not in {"OPERATIONAL_ONLY", "TRUSTED_REFERENCE"}:
        raise RuntimeError("EXPLICIT_V2_MODE_REQUIRED")
    if target not in (COMMON_TARGET, CONTROLLED_TARGET) or not authorized:
        raise RuntimeError("HOMOLOGATION_SCOPE_NOT_AUTHORIZED")
    import telegram_courses.downloads as downloads_module

    if downloads_module.V2_EFFECTIVE is not False:
        raise RuntimeError("UNEXPECTED_V2_STATE")

    @contextmanager
    def scope():
        downloads_module.V2_EFFECTIVE = True
        try:
            yield
        finally:
            downloads_module.V2_EFFECTIVE = False

    return scope()


def _trusted_reference_preflight(evidence_parent: Path | None = None) -> dict[str, Any]:
    """Verify the fixed target and reference using local, read-only checks only."""
    source_manifest = (
        REPOSITORY_ROOT / "docs/reports/S6_CONTROLLED_REFERENCE_PREPARATION_2026-10-17/reference_manifest.json"
    )
    upload_result = (
        REPOSITORY_ROOT / "docs/reports/S6_CONTROLLED_UPLOAD_AND_EOF_GATE_2026-10-17/controlled_upload_result.json"
    )
    try:
        source = json.loads(source_manifest.read_text(encoding="utf-8"))
        uploaded = json.loads(upload_result.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise RuntimeError("TRUSTED_REFERENCE_CANONICAL_MANIFEST_UNAVAILABLE") from error
    remote = uploaded.get("refetched_message")
    source_digest = source.get("source_file_sha256")
    if (
        source.get("reference_gate") != "PASS"
        or source.get("source_file_size_bytes") != CONTROLLED_TARGET["expected_bytes"]
        or not isinstance(source_digest, str)
        or source_digest.casefold() != CANONICAL_TRUSTED_REFERENCE_SHA256
        or not isinstance(remote, dict)
        or remote.get("channel_id") != CONTROLLED_TARGET["channel_id"]
        or remote.get("message_id") != CONTROLLED_TARGET["message_id"]
        or str(remote.get("media_id")) != CONTROLLED_TARGET["media_id"]
        or remote.get("ordinal") != 0
        or remote.get("kind") != "DOCUMENT"
        or remote.get("document_size_bytes") != CONTROLLED_TARGET["expected_bytes"]
        or uploaded.get("reference_gate") != "PASS"
    ):
        raise RuntimeError("CONTROLLED_REFERENCE_MANIFEST_GATE_FAILED")
    reference_path = Path(source["source_file_path"]).expanduser().absolute()
    if not reference_path.is_file() or _path_is_reparse_or_linked(reference_path):
        raise RuntimeError("CONTROLLED_REFERENCE_MISSING_OR_UNSAFE")
    if reference_path != CANONICAL_TRUSTED_REFERENCE_PATH:
        raise RuntimeError("CONTROLLED_REFERENCE_PATH_MISMATCH")
    if evidence_parent is not None:
        parent = Path(evidence_parent).absolute()
        if not _directory_path_is_safe(parent):
            raise RuntimeError("EVIDENCE_PARENT_UNSAFE")
        resolved_parent = parent.resolve(strict=True)
        resolved_reference = reference_path.resolve(strict=True)
        if (resolved_reference == resolved_parent
                or resolved_reference.is_relative_to(resolved_parent)
                or resolved_parent.is_relative_to(resolved_reference)):
            raise RuntimeError("REFERENCE_ALIASES_EVIDENCE_ROOT")
        production_database = REPOSITORY_ROOT / "data/telegram_courses.sqlite3"
        resolved_database = production_database.resolve(strict=False)
        if (resolved_database.is_relative_to(resolved_parent)
                or resolved_parent.is_relative_to(resolved_database.parent)):
            raise RuntimeError("OPERATIONAL_SQLITE_PATH_REUSED")
        _guard_native_paths((resolved_parent, resolved_reference))
    try:
        identity_before = _file_identity(reference_path)
        size, digest = _hash_file(reference_path)
        identity_after = _file_identity(reference_path)
    except OSError as error:
        raise RuntimeError("TRUSTED_REFERENCE_UNAVAILABLE") from error
    if (size != CONTROLLED_TARGET["expected_bytes"]
            or size != source["source_file_size_bytes"]
            or digest != CANONICAL_TRUSTED_REFERENCE_SHA256):
        raise RuntimeError("CONTROLLED_REFERENCE_INTEGRITY_MISMATCH")
    if identity_before != identity_after:
        raise RuntimeError("CONTROLLED_REFERENCE_CHANGED_DURING_HASH")
    return {
        "schema_version": 1,
        "channel_id": CONTROLLED_TARGET["channel_id"],
        "telegram_message_id": CONTROLLED_TARGET["message_id"],
        "media_ordinal": 0,
        "telegram_media_id": CONTROLLED_TARGET["media_id"],
        "expected_bytes": CONTROLLED_TARGET["expected_bytes"],
        "provenance": source["provenance_informed"],
        "reference_path": str(reference_path),
        "reference_size": size,
        "sha256": digest,
        "file_identity": identity_after,
    }


def _write_reference_manifest(target_root: Path) -> Path:
    """Persist a proof-local manifest after read-only source verification."""
    manifest = _trusted_reference_preflight(target_root)
    path = target_root / "reference-manifest.v1.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open(mode="rb") as stream:
        while block := stream.read(1024 * 1024):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _path_is_reparse_or_linked(path: Path) -> bool:
    """Reject links/reparse points for proof inputs and outputs."""
    try:
        info = path.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return path.is_symlink() or bool(attributes & reparse_flag) or info.st_nlink != 1
    except OSError:
        return True


def _file_identity(path: Path) -> dict[str, int]:
    info = path.stat(follow_symlinks=False)
    if _path_is_reparse_or_linked(path) or not stat.S_ISREG(info.st_mode):
        raise RuntimeError("REFERENCE_PATH_IDENTITY_UNSAFE")
    return {"device": int(info.st_dev), "file_id": int(info.st_ino), "size": int(info.st_size),
            "mtime_ns": int(info.st_mtime_ns), "ctime_ns": int(info.st_ctime_ns)}


def _directory_path_is_safe(path: Path) -> bool:
    """Reject missing, non-directory, symlink, or reparse components."""
    try:
        absolute = Path(os.path.abspath(path))
        if not absolute.is_dir() or absolute.resolve(strict=True) != absolute:
            return False
        current = absolute
        while True:
            info = current.lstat()
            attributes = getattr(info, "st_file_attributes", 0)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if current.is_symlink() or attributes & reparse_flag or not stat.S_ISDIR(info.st_mode):
                return False
            if current.parent == current:
                return True
            current = current.parent
    except (OSError, RuntimeError, ValueError):
        return False


def _verify_reference_manifest(case_root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = case_root / "reference-manifest.v1.json"
    manifest = _read_json_object(manifest_path)
    try:
        preflight = _trusted_reference_preflight(case_root)
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError("TRUSTED_REFERENCE_CANONICAL_MANIFEST_UNAVAILABLE") from error
    if (
        not isinstance(manifest.get("sha256"), str)
        or Path(manifest.get("reference_path", "")) != CANONICAL_TRUSTED_REFERENCE_PATH
        or manifest.get("channel_id") != preflight["channel_id"]
        or manifest.get("telegram_message_id") != preflight["telegram_message_id"]
        or str(manifest.get("telegram_media_id")) != preflight["telegram_media_id"]
        or manifest.get("media_ordinal") != preflight["media_ordinal"]
        or manifest.get("expected_bytes") != preflight["expected_bytes"]
        or manifest.get("reference_size") != preflight["reference_size"]
        or manifest.get("sha256", "").casefold() != preflight["sha256"]
        or manifest.get("file_identity") != preflight["file_identity"]
    ):
        raise RuntimeError("TRUSTED_REFERENCE_CANONICAL_BINDING_FAILED")
    return manifest, Path(preflight["reference_path"])


def _post_verify_reference_integrity(case_root: Path) -> dict[str, Any]:
    """Verify the trusted source after every controlled run, including failures."""
    manifest_path = case_root / "reference-manifest.v1.json"
    try:
        if not manifest_path.is_file() or _path_is_reparse_or_linked(manifest_path):
            return {"status": "INCOMPLETE", "reason": "POST_PROOF_REFERENCE_MANIFEST_MISSING"}
        manifest, reference = _verify_reference_manifest(case_root)
        return {
            "status": "PASS",
            "reference_bytes": manifest["reference_size"],
            "reference_sha256": manifest["sha256"],
            "reference_file_identity": manifest["file_identity"],
            "reference_path": str(reference),
            "access_mode": "READ_ONLY_BINARY",
        }
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        reason = error.args[0] if isinstance(error, RuntimeError) and error.args else "REFERENCE_CHECK_FAILED"
        status = (
            "BLOCKED" if reason in {
                "TRUSTED_REFERENCE_INTEGRITY_MISMATCH",
                "CONTROLLED_REFERENCE_INTEGRITY_MISMATCH",
                "CONTROLLED_REFERENCE_CHANGED_DURING_HASH",
                "REFERENCE_PATH_IDENTITY_UNSAFE",
                "REFERENCE_ALIASES_EVIDENCE_ROOT",
            } else "INCOMPLETE"
        )
        return {"status": status, "reason": reason}


def _trusted_reference_match_allowed(
    child_match: bool, supervisor_result: dict[str, Any] | None,
    post_verification: dict[str, Any],
) -> bool:
    return bool(
        child_match
        and supervisor_result is not None
        and supervisor_result.get("status") == "TRUSTED_REFERENCE_MATCH"
        and post_verification.get("status") == "PASS"
    )


def _preconfirmation_status(
    target_name: str, mode: str, prefix_profile: str | None,
    evidence_parent: Path | None,
) -> dict[str, Any]:
    """Check the declared fixed target and local reference without any RPC."""
    if (target_name, mode) != ("controlled", "TRUSTED_REFERENCE"):
        raise RuntimeError("PRECONFIRMATION_PROFILE_NOT_AUTHORIZED")
    _verify_ratified_contract()
    target, _cases = _validate_target_profile(target_name, mode, prefix_profile)
    budget = _case_budget(target, mode, "aligned", prefix_profile)
    reference = _trusted_reference_preflight(evidence_parent)
    return {
        "status": "PASS",
        "rpc_calls": 0,
        "target": target,
        "prefix_profile": budget["prefix_profile"],
        "prefix_bytes": budget["prefix_bytes"],
        "effective_caps": _case_effective_limits("aligned", mode, target_name, budget),
        "reference": {
            "path": reference["reference_path"],
            "bytes": reference["reference_size"],
            "sha256": reference["sha256"],
            "access_mode": "READ_ONLY_BINARY",
        },
        "v1_active": True,
        "v2_global_effective": False,
    }


def _verify_reference_prefix(case_root: Path, partial: Path, prefix_bytes: int,
                              checkpoint_bytes: int, checkpoint_sha256: str) -> dict[str, Any]:
    manifest, reference = _verify_reference_manifest(case_root)
    downloads_root = case_root / "downloads"
    resolved_downloads = downloads_root.resolve(strict=True)
    resolved_partial = partial.resolve(strict=True)
    if (
        downloads_root.is_symlink() or resolved_downloads != case_root.resolve(strict=True) / "downloads"
        or not resolved_partial.is_relative_to(resolved_downloads)
        or _path_is_reparse_or_linked(partial)
        or os.path.samefile(partial, reference)
    ):
        raise RuntimeError("TRUSTED_REFERENCE_PARTIAL_PATH_UNSAFE")
    _guard_native_paths((downloads_root, partial, reference))
    if prefix_bytes != checkpoint_bytes or partial.stat().st_size != prefix_bytes:
        raise RuntimeError("TRUSTED_REFERENCE_PREFIX_SIZE_MISMATCH")
    size, digest = _hash_file(partial)
    if size != prefix_bytes or digest != checkpoint_sha256:
        raise RuntimeError("TRUSTED_REFERENCE_PREFIX_CHECKPOINT_MISMATCH")
    prefix_digest = hashlib.sha256()
    compared = 0
    with partial.open("rb") as actual, reference.open("rb") as original:
        while compared < prefix_bytes:
            amount = min(1024 * 1024, prefix_bytes - compared)
            actual_block = actual.read(amount)
            reference_block = original.read(amount)
            if len(actual_block) != amount or actual_block != reference_block:
                raise RuntimeError("TRUSTED_REFERENCE_PREFIX_MISMATCH")
            prefix_digest.update(reference_block)
            compared += amount
    if prefix_digest.hexdigest() != checkpoint_sha256:
        raise RuntimeError("TRUSTED_REFERENCE_PREFIX_HASH_MISMATCH")
    _verify_reference_manifest(case_root)
    return {
        "status": "LOCAL_PREFIX_REFERENCE_MATCH", "bytes": compared,
        "sha256": checkpoint_sha256, "reference_sha256": manifest["sha256"],
        "source": "LOCAL_IMMUTABLE_REFERENCE", "remote_reread": False,
    }


def _supervisor_compare_reference(case_root: Path, final_path: str) -> dict[str, Any]:
    """Independently compare the completed file to the canonical original in the parent."""
    try:
        manifest, reference = _verify_reference_manifest(case_root)
        final = _resolve_completed_final_path(
            case_root, state="COMPLETED_V2", final_path=final_path,
        )
        if os.path.samefile(reference, final):
            raise RuntimeError("OUTPUT_ALIASES_TRUSTED_REFERENCE")
        reference_identity = _file_identity(reference)
        final_identity = _file_identity(final)
        final_size, final_digest = _hash_file(final)
        reference_size, reference_digest = _hash_file(reference)
        bytewise_match = final_size == reference_size
        if bytewise_match:
            with final.open("rb") as actual, reference.open("rb") as original:
                while True:
                    actual_block = actual.read(1024 * 1024)
                    reference_block = original.read(1024 * 1024)
                    if actual_block != reference_block:
                        bytewise_match = False
                        break
                    if not actual_block:
                        break
        if _file_identity(reference) != reference_identity or _file_identity(final) != final_identity:
            raise RuntimeError("SUPERVISOR_FILE_IDENTITY_CHANGED")
        match = (
            bytewise_match and final_size == manifest["expected_bytes"]
            and reference_size == manifest["expected_bytes"]
            and final_digest == reference_digest == manifest["sha256"]
        )
        return {
            "status": "TRUSTED_REFERENCE_MATCH" if match else "TRUSTED_REFERENCE_MISMATCH",
            "final_bytes": final_size, "reference_bytes": reference_size,
            "final_sha256": final_digest, "reference_sha256": reference_digest,
            "bytewise_match": bytewise_match, "comparison_method": "BYTEWISE_AND_SHA256",
            "final_file_identity": final_identity, "reference_file_identity": reference_identity,
        }
    except (OSError, RuntimeError, ValueError) as error:
        safe_reason = (
            error.args[0]
            if isinstance(error, RuntimeError) and error.args
            and error.args[0] in {
                "TRUSTED_REFERENCE_UNAVAILABLE",
                "OUTPUT_ALIASES_TRUSTED_REFERENCE",
                "SUPERVISOR_FILE_IDENTITY_CHANGED",
            }
            else _safe_stop_condition(error)
        )
        return {
            "status": "BLOCKED", "reason": safe_reason,
        }


def _atomic_write_json(path: Path, document: dict[str, Any], *, replace: bool = True) -> None:
    """Publish strict JSON atomically in the destination directory."""
    if type(document) is not dict:
        raise TypeError("JSON_DOCUMENT_MUST_BE_OBJECT")

    def normalize(value: Any) -> Any:
        if value is None or type(value) in (str, bool, int, float):
            return value
        if type(value) in (list, tuple):
            return [normalize(item) for item in value]
        if type(value) is dict:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise TypeError("JSON_OBJECT_KEYS_MUST_BE_STRINGS")
                normalized[key] = normalize(item)
            return normalized
        raise TypeError(f"UNSUPPORTED_JSON_VALUE:{type(value).__name__}")

    normalized = normalize(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (not replace and path.exists()):
        raise RuntimeError("JSON_DESTINATION_EXISTS_OR_UNSAFE")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(normalized, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or (not replace and path.exists()):
            raise RuntimeError("JSON_DESTINATION_EXISTS_OR_UNSAFE")
        os.replace(temporary, path)
        published = json.loads(path.read_text(encoding="utf-8"))
        if json.dumps(published, allow_nan=False, separators=(",", ":")) != json.dumps(
            normalized, allow_nan=False, separators=(",", ":")
        ):
            raise RuntimeError("JSON_PUBLISHED_CONTENT_MISMATCH")
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_json_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("JSON_REPORT_MISSING_OR_UNSAFE")
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise RuntimeError("JSON_REPORT_NOT_OBJECT")
    return value


def _acquire_execution_lock(root: Path, execution_id: str) -> Path:
    lock = root / ".execution.lock"
    if lock.is_symlink():
        raise RuntimeError("PROOF_ROOT_LOCK_UNSAFE")
    try:
        with lock.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"execution_id": execution_id, "pid": os.getpid()}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise RuntimeError("PROOF_ROOT_ALREADY_ACTIVE_OR_UNRECONCILED") from error
    return lock


def _release_execution_lock(lock: Path, execution_id: str) -> None:
    if lock.is_symlink() or not lock.is_file():
        raise RuntimeError("PROOF_ROOT_LOCK_MISSING_OR_UNSAFE")
    owner = _read_json_object(lock)
    if owner.get("execution_id") != execution_id or owner.get("pid") != os.getpid():
        raise RuntimeError("PROOF_ROOT_LOCK_OWNER_MISMATCH")
    lock.unlink()


def _read_budget_snapshot(path: Path) -> dict[str, int] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
        try:
            ProofLedger._validate_schema(db)
            if db.execute("SELECT COUNT(*) FROM proof_budget").fetchone() != (1,):
                return None
            row = db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone()
            snapshot = ProofLedger._snapshot_from_row(row)
            ProofLedger._reservation_counts(db, snapshot)
        finally:
            db.close()
    except (sqlite3.Error, RuntimeError):
        return None
    return snapshot


def _phase1_root_is_new_and_empty(case_root: Path, ledger_path: Path) -> bool:
    database = case_root / "proof.sqlite3"
    downloads = case_root / "downloads"
    if (
        not case_root.is_dir() or case_root.is_symlink()
        or database.exists() or database.is_symlink()
        or ledger_path.exists() or ledger_path.is_symlink()
        or not downloads.is_dir() or downloads.is_symlink()
    ):
        return False
    try:
        return not any(downloads.iterdir()) and {path.name for path in case_root.iterdir()} == {"downloads"}
    except OSError:
        return False


def _progress_log_stat(path: Path, evidence_root: Path) -> os.stat_result:
    """Require the progress log to be a regular, non-symlink file inside its proof root."""
    root = evidence_root.resolve(strict=True)
    if not root.is_dir() or evidence_root.is_symlink():
        raise RuntimeError("PROGRESS_ROOT_UNSAFE")
    if path.is_symlink():
        raise RuntimeError("PROGRESS_LOG_UNSAFE")
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise RuntimeError("PROGRESS_LOG_UNAVAILABLE") from error
    expected = root / "execution-progress.jsonl"
    if (
        not stat.S_ISREG(info.st_mode)
        or resolved != expected
        or not resolved.is_relative_to(root)
    ):
        raise RuntimeError("PROGRESS_LOG_UNSAFE")
    return info


def _prepare_progress_log(
    *, path: Path, evidence_root: Path, phase: int, case_root: Path,
) -> tuple[int, tuple[int, int]]:
    """Create a fresh phase-1 log or validate and append to its accepted phase-1 log."""
    if phase == 1:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise RuntimeError("PROGRESS_LOG_ALREADY_EXISTS") from error
        else:
            os.close(descriptor)
        info = _progress_log_stat(path, evidence_root)
        return info.st_size, (info.st_dev, info.st_ino)

    if phase != 2:
        raise RuntimeError("PROGRESS_PHASE_INVALID")
    phase1_receipt_path = case_root / "phase-1.json"
    if phase1_receipt_path.is_symlink():
        raise RuntimeError("PHASE1_RECEIPT_UNSAFE")
    try:
        phase1_info = phase1_receipt_path.lstat()
        phase1_resolved = phase1_receipt_path.resolve(strict=True)
        phase1_receipt = _read_json_object(phase1_receipt_path)
    except (OSError, RuntimeError, json.JSONDecodeError, UnicodeError) as error:
        raise RuntimeError("PHASE1_RECEIPT_UNAVAILABLE") from error
    if (
        not stat.S_ISREG(phase1_info.st_mode)
        or phase1_resolved != phase1_receipt_path
        or phase1_receipt.get("phase") != 1
        or phase1_receipt.get("progress_evidence_valid") is not True
    ):
        raise RuntimeError("PHASE1_RECEIPT_INVALID")
    prior_execution_id = phase1_receipt.get("execution_id")
    prior_identity = phase1_receipt.get("progress_log_identity")
    if (
        not isinstance(prior_execution_id, str) or not prior_execution_id
        or not isinstance(prior_identity, dict)
    ):
        raise RuntimeError("PHASE1_PROGRESS_IDENTITY_MISSING")
    info = _progress_log_stat(path, evidence_root)
    identity = (info.st_dev, info.st_ino)
    if identity != (prior_identity.get("device"), prior_identity.get("inode")):
        raise RuntimeError("PROGRESS_LOG_REPLACED")
    try:
        rows = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("PHASE1_PROGRESS_LOG_INVALID") from error
    if not any(
        row.get("execution_id") == prior_execution_id and row.get("phase") == 1
        and row.get("stage") == "supervisor.sqlite_ledger_reconciled"
        and row.get("outcome") == "completed"
        for row in rows if isinstance(row, dict)
    ):
        raise RuntimeError("PHASE1_PROGRESS_LOG_UNRECONCILED")
    return info.st_size, identity


def _phase2_ledger_before_matches(
    *, phase: int, ledger_before: dict[str, int] | None,
    phase1_ledger_after: dict[str, int] | None,
) -> bool:
    return (
        phase == 2 and isinstance(ledger_before, dict)
        and isinstance(phase1_ledger_after, dict)
        and ledger_before == phase1_ledger_after
    )


def _normalize_attempt_rows(rows: object) -> list[dict[str, Any]] | None:
    if not isinstance(rows, list):
        return None
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            return None
        raw_id = item.get("id")
        canonical_id = item.get("attempt_id")
        if raw_id is not None and canonical_id is not None and raw_id != canonical_id:
            return None
        identity = canonical_id if canonical_id is not None else raw_id
        if not isinstance(identity, str) or not identity or identity in seen:
            return None
        normalized.append({**item, "attempt_id": identity})
        seen.add(identity)
    return normalized


def _read_attempt_rows(database: Path) -> list[dict[str, Any]] | None:
    if database.is_symlink() or not database.is_file():
        return None
    db = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    try:
        columns = {row[1] for row in db.execute("PRAGMA table_info(s6_v2_attempts)").fetchall()}
        identity_column = "id" if "id" in columns else "attempt_id" if "attempt_id" in columns else None
        if identity_column is None:
            return None
        names = (
            "attempt_id", "channel_id", "telegram_message_id", "media_ordinal", "telegram_media_id",
            "expected_bytes", "selected_mode", "schema_version", "contract_version",
            "evidence_version", "status", "remote_hash_class", "evidence_class", "requests",
            "bytes_reserved", "bytes_received", "details_json", "plan_id", "invocation_id",
        )
        rows = db.execute(
            "SELECT " + identity_column + " AS attempt_id," + ",".join(names[1:])
            + " FROM s6_v2_attempts ORDER BY rowid"
        ).fetchall()
    finally:
        db.close()
    result = []
    for raw in rows:
        row = dict(zip(names, raw, strict=True))
        try:
            details = json.loads(row.pop("details_json"))
            row["details"] = details if isinstance(details, dict) else None
        except (TypeError, ValueError):
            row["details"] = None
        result.append(row)
    return _normalize_attempt_rows(result)


def _safe_exception_class(error: BaseException | None) -> str | None:
    if error is None:
        return None
    # These domain exceptions may have specialized subclasses.  Report only a
    # fixed label; never inspect their message, category, or other attributes.
    try:
        from telegram_courses.downloads import DownloadError, DownloadGatewayError
    except Exception:
        DownloadError = DownloadGatewayError = ()  # type: ignore[assignment]
    if DownloadError and isinstance(error, DownloadError):
        code = error.__dict__.get("category")
        return code if type(code) is str and code in _SAFE_DOWNLOAD_ERROR_CODES else "OTHER"
    if DownloadGatewayError and isinstance(error, DownloadGatewayError):
        code = error.__dict__.get("category")
        return code if type(code) is str and code in _SAFE_DOWNLOAD_ERROR_CODES else "OTHER"
    for exception_type, label in (
        (KeyboardInterrupt, "KeyboardInterrupt"),
        (asyncio.CancelledError, "CancelledError"),
        (subprocess.TimeoutExpired, "TimeoutExpired"),
        (sqlite3.Error, "SQLiteError"),
        (TimeoutError, "TimeoutError"),
        (OSError, "OSError"),
        (ValueError, "ValueError"),
        (TypeError, "TypeError"),
        (AssertionError, "AssertionError"),
        (RuntimeError, "RuntimeError"),
        (Exception, "Exception"),
    ):
        if (type(error) is exception_type if exception_type is Exception
                else isinstance(error, exception_type)):
            return label
    return "OTHER"


def _safe_exception_stage(error: BaseException | None) -> str | None:
    """Return only a known domain stage; never inspect exception text or repr."""
    if error is None:
        return None
    try:
        from telegram_courses.downloads import DownloadError
    except Exception:
        return None
    if not isinstance(error, DownloadError):
        return None
    stage = error.__dict__.get("failure_phase")
    return stage if type(stage) is str and stage in _SAFE_DOWNLOAD_ERROR_STAGES else None


def _safe_stop_condition(error: BaseException) -> str:
    # Exception text may contain credentials, paths, or attacker-controlled input.
    # Keep only a stable class label in evidence and console output.
    return _safe_exception_class(error) or "OTHER"


def _expected_common_final_path(case_root: Path, media_item_id: int, target: dict[str, Any]) -> str:
    from telegram_courses.download_repository import DownloadCandidate
    from telegram_courses.downloads import destination_paths

    candidate = DownloadCandidate(
        media_item_id=media_item_id,
        channel_id=target["channel_id"],
        telegram_message_id=target["message_id"],
        media_ordinal=target["media_ordinal"],
        telegram_media_id=target["media_id"],
        expected_bytes=target["expected_bytes"],
        original_filename="proof-document.bin",
        lineage=(("lesson", "S6 V2 proof item"),),
    )
    return str(destination_paths(case_root / "downloads", candidate)[0])


def _observe_isolated_media_state(case_root: Path) -> dict[str, Any]:
    """Observe proof DB and files read-only; never follows paths outside proof root."""
    database = case_root / "proof.sqlite3"
    downloads_path = case_root / "downloads"
    if not downloads_path.is_dir() or downloads_path.is_symlink():
        return {"available": False, "reason": "PROOF_DOWNLOADS_DIRECTORY_MISSING_OR_UNSAFE"}
    downloads_root = downloads_path.resolve(strict=True)
    if database.is_symlink() or not database.is_file():
        return {"available": False, "reason": "PROOF_DATABASE_MISSING"}
    try:
        db = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
        try:
            rows = db.execute(
                "SELECT d.media_item_id,d.state,d.partial_path,d.final_path,d.expected_bytes,"
                "d.downloaded_bytes,d.sha256,d.failure_category,d.contract_version,d.evidence_version,d.owner_pid,"
                "m.channel_id,m.telegram_message_id,m.media_ordinal,m.telegram_media_id,m.kind,m.file_size_bytes "
                "FROM downloads d JOIN media_items m ON m.id=d.media_item_id"
            ).fetchall()
            attempts = db.execute(
                "SELECT id,channel_id,telegram_message_id,media_ordinal,telegram_media_id,expected_bytes,"
                "selected_mode,schema_version,contract_version,evidence_version,status,remote_hash_class,"
                "evidence_class,requests,bytes_reserved,bytes_received,details_json,plan_id,invocation_id "
                "FROM s6_v2_attempts ORDER BY rowid"
            ).fetchall()
            evidence_rows = db.execute(
                "SELECT media_item_id,attempt_id,channel_id,telegram_message_id,media_ordinal,"
                "telegram_media_id,expected_bytes,final_path,final_sha256,selected_mode,schema_version,"
                "evidence_class,remote_hash_class,contract_version,evidence_version,plan_id,invocation_id "
                "FROM s6_v2_evidence"
            ).fetchall()
        finally:
            db.close()
    except sqlite3.Error as error:
        return {"available": False, "reason": f"PROOF_DATABASE_READ_ERROR:{_safe_exception_class(error)}"}
    if len(rows) != 1:
        return {"available": False, "reason": "PROOF_DOWNLOAD_RECORD_COUNT_MISMATCH"}
    (
        media_item_id,state,partial_text,final_text,expected,downloaded,digest,
        failure_category,contract_version,evidence_version,owner_pid,channel_id,message_id,media_ordinal,
        telegram_media_id,media_kind,catalog_expected_bytes,
    ) = rows[0]
    observed: dict[str, Any] = {
        "available": True, "media_item_id": media_item_id,
        "sqlite_state": state, "sqlite_checkpoint_bytes": downloaded,
        "expected_bytes": expected, "sqlite_sha256": digest,
        "failure_category": failure_category,
        "owner_pid": owner_pid,
        "contract_version": contract_version, "evidence_version": evidence_version,
        "identity": {
            "channel_id": channel_id, "message_id": message_id,
            "media_ordinal": media_ordinal, "media_id": telegram_media_id,
            "media_kind": media_kind, "expected_bytes": expected,
            "catalog_expected_bytes": catalog_expected_bytes,
        },
        "attempt_rows": len(attempts),
        "evidence_rows": len(evidence_rows),
        "expected_planned_final_path": (
            _expected_common_final_path(
                case_root, media_item_id,
                CONTROLLED_TARGET if channel_id == CONTROLLED_TARGET["channel_id"] else COMMON_TARGET,
            )
            if (
                channel_id, message_id, media_ordinal, telegram_media_id
            ) in {
                (COMMON_TARGET["channel_id"], COMMON_TARGET["message_id"],
                 COMMON_TARGET["media_ordinal"], COMMON_TARGET["media_id"]),
                (CONTROLLED_TARGET["channel_id"], CONTROLLED_TARGET["message_id"],
                 CONTROLLED_TARGET["media_ordinal"], CONTROLLED_TARGET["media_id"]),
            }
            else None
        ),
    }
    attempt_keys = (
        "attempt_id","channel_id","message_id","media_ordinal","media_id","expected_bytes",
        "selected_mode","schema_version","contract_version","evidence_version","status",
        "remote_hash_class","evidence_class","requests","bytes_reserved","bytes_received",
        "details_json","plan_id","invocation_id",
    )
    observed["attempts"] = []
    for row in attempts:
        attempt = dict(zip(attempt_keys, row, strict=True))
        try:
            details = json.loads(attempt.pop("details_json"))
            attempt["details"] = details if isinstance(details, dict) else None
        except (TypeError, ValueError):
            attempt["details"] = None
        observed["attempts"].append(attempt)
    evidence_keys = (
        "media_item_id","attempt_id","channel_id","message_id","media_ordinal","media_id",
        "expected_bytes","final_path","final_sha256","selected_mode","schema_version",
        "evidence_class","remote_hash_class","contract_version","evidence_version",
        "plan_id","invocation_id",
    )
    observed["evidence"] = (
        dict(zip(evidence_keys, evidence_rows[0], strict=True)) if len(evidence_rows) == 1 else None
    )
    for key, value in (("partial", partial_text), ("final", final_text)):
        observed[f"{key}_path"] = value
        if key == "final":
            observed["final_exists"] = False
        if value is None:
            observed[f"{key}_bytes"] = None
            continue
        candidate = Path(value)
        try:
            relative = candidate.relative_to(downloads_path)
        except ValueError:
            observed[f"{key}_bytes"] = None
            observed[f"{key}_path_status"] = "OUTSIDE_OR_UNSAFE"
            continue
        if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            observed[f"{key}_bytes"] = None
            observed[f"{key}_path_status"] = "OUTSIDE_OR_UNSAFE"
            continue
        cursor = downloads_path
        unsafe_component = False
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                unsafe_component = True
                break
        if unsafe_component:
            observed[f"{key}_bytes"] = None
            observed[f"{key}_path_status"] = "OUTSIDE_OR_UNSAFE"
            continue
        try:
            resolved_planned = candidate.resolve(strict=False)
        except OSError:
            observed[f"{key}_bytes"] = None
            observed[f"{key}_path_status"] = "OUTSIDE_OR_UNSAFE"
            continue
        if not resolved_planned.is_relative_to(downloads_root):
            observed[f"{key}_bytes"] = None
            observed[f"{key}_path_status"] = "OUTSIDE_OR_UNSAFE"
            continue
        exists = candidate.exists()
        if key == "final":
            observed["final_exists"] = exists
        if not exists and key == "final":
            observed[f"{key}_bytes"] = None
            observed[f"{key}_path_status"] = "PLANNED_ABSENT"
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            observed[f"{key}_bytes"] = None
            continue
        if candidate.is_symlink() or not resolved.is_relative_to(downloads_root) or not resolved.is_file():
            observed[f"{key}_bytes"] = None
            observed[f"{key}_path_status"] = "OUTSIDE_OR_UNSAFE"
            continue
        observed[f"{key}_bytes"] = resolved.stat().st_size
        observed[f"{key}_sha256"] = _hash_file(resolved)[1]
        observed[f"{key}_path_status"] = "SAFE"
        if key == "final":
            observed["physical_sha256"] = observed["final_sha256"]
    return observed


def _reconcile_supervisor_timeout(
    *, case_root: Path, target: dict[str, Any], mode: str, phase_id: str,
    media_state: dict[str, Any], attempts_before: list[dict[str, Any]] | None,
    process_pid: int, child_report_pid: int | None = None,
) -> dict[str, Any]:
    """Normalize only consistent proof-root state after the child is confirmed exited."""
    database = case_root / "proof.sqlite3"
    expected = {
        "channel_id": target["channel_id"], "message_id": target["message_id"],
        "media_ordinal": target["media_ordinal"], "media_id": target["media_id"],
        "media_kind": target["media_kind"], "expected_bytes": target["expected_bytes"],
        "catalog_expected_bytes": target["expected_bytes"],
    }
    result = {"status": "BLOCKED", "reason": "INCONSISTENT_TIMEOUT_OBSERVATION"}
    if database.is_file() and not database.is_symlink():
        try:
            with sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True) as prior_db:
                table = prior_db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='s6_v2_supervisor_reconciliations'"
                ).fetchone()
                prior = (
                    prior_db.execute(
                        "SELECT status,details_json FROM s6_v2_supervisor_reconciliations "
                        "WHERE phase_id=?", (phase_id,),
                    ).fetchone()
                    if table else None
                )
                if prior:
                    details = json.loads(prior[1])
                    attempt_id = details.get("attempt_id") if isinstance(details, dict) else None
                    row = prior_db.execute(
                        "SELECT state,failure_category,partial_path,expected_bytes,downloaded_bytes,owner_pid "
                        "FROM downloads WHERE media_item_id=?", (media_state.get("media_item_id"),),
                    ).fetchone()
                    attempt = prior_db.execute(
                        "SELECT status,details_json FROM s6_v2_attempts WHERE id=?", (attempt_id,),
                    ).fetchone() if isinstance(attempt_id, str) else None
                    valid_replay = bool(
                        prior[0] == "RECONCILED" and isinstance(details, dict)
                        and details.get("reason") == "SUPERVISOR_TIMEOUT"
                        and details.get("confirmed_exited_process_pid") == process_pid
                        and details.get("media_item_id") == media_state.get("media_item_id")
                        and details.get("partial_path") == media_state.get("partial_path")
                        and details.get("checkpoint_bytes") == media_state.get("sqlite_checkpoint_bytes")
                        and media_state.get("available") is True
                        and media_state.get("identity") == expected
                        and media_state.get("sqlite_state") == "FAILED_RETRYABLE"
                        and media_state.get("failure_category") == "SUPERVISOR_TIMEOUT"
                        and media_state.get("owner_pid") is None
                        and media_state.get("evidence_rows") == 0
                        and media_state.get("evidence") is None
                        and media_state.get("final_exists") is False
                        and media_state.get("partial_path_status") == "SAFE"
                        and type(media_state.get("partial_bytes")) is int
                        and media_state.get("partial_bytes") == media_state.get("sqlite_checkpoint_bytes")
                        and row == (
                            "FAILED_RETRYABLE", "SUPERVISOR_TIMEOUT", media_state.get("partial_path"),
                            target["expected_bytes"], media_state.get("sqlite_checkpoint_bytes"), None,
                        )
                        and attempt is not None and attempt[0] == "FAILED_RETRYABLE"
                        and isinstance(json.loads(attempt[1] or "{}"), dict)
                        and json.loads(attempt[1] or "{}").get("failure_category") == "SUPERVISOR_TIMEOUT"
                    )
                    return {"status": "RECONCILED", **details, "idempotent_replay": True} \
                        if valid_replay else {"status": "BLOCKED", "reason": "REPLAY_STATE_MISMATCH"}
        except (OSError, sqlite3.Error, TypeError, ValueError, json.JSONDecodeError):
            return {"status": "BLOCKED", "reason": "RECONCILIATION_RECORD_INVALID"}
    already_failed_safely = (
        media_state.get("sqlite_state") == "FAILED_RETRYABLE"
        and media_state.get("failure_category") == "SUPERVISOR_TIMEOUT"
        and child_report_pid == process_pid and process_pid > 0
    )
    if (
        media_state.get("available") is not True
        or media_state.get("identity") != expected
        or media_state.get("sqlite_state") not in {"DOWNLOADING", "FAILED_RETRYABLE"}
        or (media_state.get("sqlite_state") == "FAILED_RETRYABLE" and not already_failed_safely)
        or media_state.get("evidence_rows") != 0
        or media_state.get("evidence") is not None
        or media_state.get("final_exists") is not False
        or media_state.get("partial_path_status") != "SAFE"
        or type(process_pid) is not int or process_pid <= 0
        or (
            media_state.get("sqlite_state") == "DOWNLOADING"
            and media_state.get("owner_pid") != process_pid
        )
        or (
            media_state.get("sqlite_state") == "FAILED_RETRYABLE"
            and media_state.get("owner_pid") is not None
        )
        or type(media_state.get("partial_bytes")) is not int
        or media_state.get("partial_bytes") != media_state.get("sqlite_checkpoint_bytes")
        or not isinstance(attempts_before, list)
    ):
        return result
    partial_path = media_state.get("partial_path")
    downloads = (case_root / "downloads").resolve(strict=True)
    try:
        partial = Path(partial_path)
        if (
            not isinstance(partial_path, str) or partial.is_symlink()
            or not partial.resolve(strict=True).is_relative_to(downloads)
            or not partial.is_file()
        ):
            return result
    except (OSError, ValueError):
        return result
    prior = {row.get("attempt_id") for row in attempts_before if isinstance(row, dict)}
    candidates = [
        row for row in media_state.get("attempts", [])
        if isinstance(row, dict) and row.get("attempt_id") not in prior
        and (
            row.get("status") == "SELECTED"
            or (already_failed_safely and row.get("status") == "FAILED_RETRYABLE"
                and isinstance(row.get("details"), dict)
                and row["details"].get("failure_category") == "SUPERVISOR_TIMEOUT")
        )
        and row.get("selected_mode") == mode
        and all(row.get(key) == expected[key] for key in (
            "channel_id", "message_id", "media_ordinal", "media_id", "expected_bytes",
        ))
    ]
    if len(candidates) != 1:
        return {"status": "BLOCKED", "reason": "NEW_SELECTED_ATTEMPT_NOT_UNIQUE"}
    attempt_id = candidates[0].get("attempt_id")
    invocation_id = candidates[0].get("invocation_id")
    if (
        not isinstance(invocation_id, str) or not invocation_id
        or not isinstance(attempt_id, str)
        or not attempt_id.startswith(f"s6v2:{invocation_id}:{media_state.get('media_item_id')}:")
    ):
        return {"status": "BLOCKED", "reason": "ATTEMPT_INVOCATION_IDENTITY_MISMATCH"}
    try:
        db = sqlite3.connect(database, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE IF NOT EXISTS s6_v2_supervisor_reconciliations ("
                "phase_id TEXT PRIMARY KEY, status TEXT NOT NULL, details_json TEXT NOT NULL)"
            )
            existing = db.execute(
                "SELECT status,details_json FROM s6_v2_supervisor_reconciliations WHERE phase_id=?",
                (phase_id,),
            ).fetchone()
            if existing:
                detail = json.loads(existing[1])
                return {"status": existing[0], **detail, "idempotent_replay": True}
            row = db.execute(
                "SELECT state,partial_path,expected_bytes,downloaded_bytes,owner_pid "
                "FROM downloads WHERE media_item_id=?",
                (media_state.get("media_item_id"),),
            ).fetchone()
            current_attempt = db.execute(
                "SELECT status,details_json,channel_id,telegram_message_id,media_ordinal,"
                "telegram_media_id,expected_bytes,selected_mode,invocation_id "
                "FROM s6_v2_attempts WHERE id=?",
                (attempt_id,),
            ).fetchone()
            expected_row_state = "FAILED_RETRYABLE" if already_failed_safely else "DOWNLOADING"
            expected_attempt_state = "FAILED_RETRYABLE" if already_failed_safely else "SELECTED"
            consistent = bool(
                row == (
                    expected_row_state, partial_path, target["expected_bytes"],
                    media_state["sqlite_checkpoint_bytes"],
                    None if already_failed_safely else process_pid,
                )
                and current_attempt is not None and current_attempt[0] == expected_attempt_state
                and current_attempt[2:] == (
                    target["channel_id"], target["message_id"], target["media_ordinal"],
                    target["media_id"], target["expected_bytes"], mode, invocation_id,
                )
                and (
                    not already_failed_safely
                    or json.loads(current_attempt[1] or "{}").get("failure_category")
                    == "SUPERVISOR_TIMEOUT"
                )
            )
            if not consistent:
                details = {"reason": "SQLITE_ROW_OR_ATTEMPT_CHANGED"}
                db.execute(
                    "INSERT INTO s6_v2_supervisor_reconciliations VALUES(?,?,?)",
                    (phase_id, "BLOCKED", json.dumps(details, sort_keys=True)),
                )
                db.commit()
                return {"status": "BLOCKED", **details}
            attempt_details = json.loads(current_attempt[1] or "{}")
            if not isinstance(attempt_details, dict):
                raise RuntimeError("ATTEMPT_DETAILS_INVALID")
            if already_failed_safely:
                changed_download = changed_attempt = 0
            else:
                attempt_details["failure_category"] = "SUPERVISOR_TIMEOUT"
                attempt_details["supervisor_phase_id"] = phase_id
                changed_download = db.execute(
                    "UPDATE downloads SET state='FAILED_RETRYABLE',failure_category='SUPERVISOR_TIMEOUT',"
                    "owner_pid=NULL WHERE media_item_id=? AND state='DOWNLOADING' "
                    "AND downloaded_bytes=? AND owner_pid=?",
                    (media_state["media_item_id"], media_state["sqlite_checkpoint_bytes"], process_pid),
                ).rowcount
                changed_attempt = db.execute(
                    "UPDATE s6_v2_attempts SET status='FAILED_RETRYABLE',details_json=? "
                    "WHERE id=? AND status='SELECTED'",
                    (json.dumps(attempt_details, sort_keys=True), attempt_id),
                ).rowcount
                if changed_download != 1 or changed_attempt != 1:
                    raise RuntimeError("TIMEOUT_RECONCILIATION_ROWCOUNT_MISMATCH")
            details = {
                "reason": "SUPERVISOR_TIMEOUT", "attempt_id": attempt_id,
                "media_item_id": media_state["media_item_id"],
                "partial_path": partial_path,
                "checkpoint_bytes": media_state["sqlite_checkpoint_bytes"],
                "partial_bytes": media_state["partial_bytes"],
                "already_normalized_by_child": already_failed_safely,
                "confirmed_exited_process_pid": process_pid,
                "completion_evidence_created": False,
                "result_claimed": "INCOMPLETE",
            }
            db.execute(
                "INSERT INTO s6_v2_supervisor_reconciliations VALUES(?,?,?)",
                (phase_id, "RECONCILED", json.dumps(details, sort_keys=True)),
            )
            db.commit()
            return {"status": "RECONCILED", **details, "idempotent_replay": False}
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
    except (OSError, sqlite3.Error, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as error:
        return {"status": "BLOCKED", "reason": _safe_exception_class(error) or "RECONCILIATION_ERROR"}


def _phase_state_reconciles(
    *, phase: int, target: dict[str, Any], mode: str,
    media_state: dict[str, Any], child_result: dict[str, Any] | None,
    ledger_before: dict[str, int] | None, ledger_after: dict[str, int] | None,
    ledger_delta: dict[str, int] | None, phase_attempt_ids: list[str] | None = None,
    ledger_before_is_new_root_baseline: bool = False,
    expected_ledger_before: dict[str, int] | None = None,
    child_exit_code: int | None = None, supervisor_exit_code: int | None = None,
) -> bool:
    case_name = child_result.get("case") if isinstance(child_result, dict) else None
    try:
        case = _case_budget(
            target, mode, case_name,
            child_result.get("prefix_profile") if isinstance(child_result, dict) else None,
        )
    except (RuntimeError, TypeError):
        return False
    prefix_bytes = int(case["prefix_bytes"])
    if media_state.get("available") is not True or not isinstance(child_result, dict):
        return False
    expected_identity = {
        "channel_id": target["channel_id"], "message_id": target["message_id"],
        "media_ordinal": target["media_ordinal"], "media_id": target["media_id"],
        "media_kind": target["media_kind"], "expected_bytes": target["expected_bytes"],
    }
    if (
        child_result.get("identity") != expected_identity
        or child_result.get("mode") != mode
        or child_result.get("target_name") != ("controlled" if target == CONTROLLED_TARGET else "common")
        or media_state.get("identity") != (expected_identity | {
            "catalog_expected_bytes": target["expected_bytes"],
        })
    ):
        return False

    ledger_keys = ProofLedger._COLUMNS
    if any(not isinstance(item, dict) for item in (ledger_before, ledger_after, ledger_delta)):
        return False
    before = ledger_before
    after = ledger_after
    delta = ledger_delta
    if any(
        set(item) != set(ledger_keys)
        or any(type(item[key]) is not int or item[key] < 0 for key in ledger_keys)
        for item in (before, after, delta)
    ):
        return False
    if any(after[key] - before[key] != delta[key] for key in ledger_keys):
        return False
    if phase == 1:
        if not ledger_before_is_new_root_baseline or before != dict.fromkeys(ledger_keys, 0):
            return False
    elif phase == 2:
        if expected_ledger_before is None or before != expected_ledger_before:
            return False
    for snapshot in (before, after):
        if (
            snapshot["payload_reserved"] != snapshot["getfile_calls"] * CHUNK_BYTES
            or snapshot["payload_received"] + snapshot["uncertain_bytes"] > snapshot["payload_reserved"]
        ):
            return False

    requests = child_result.get("requests_used")
    attempts = media_state.get("attempts")
    if (
        not isinstance(requests, dict) or not isinstance(attempts, list)
        or requests.get("GetFile") != delta["getfile_calls"]
        or requests.get("GetFileHashes") != delta["getfilehashes_calls"]
        or any(type(requests.get(key)) is not int or requests[key] < 0 for key in (
            "identity_GetMessages", "GetFile", "GetFileHashes",
        ))
    ):
        return False
    if any(not isinstance(row, dict) for row in attempts):
        return False
    all_attempt_ids = [row.get("attempt_id") for row in attempts]
    if (
        any(not isinstance(identity, str) or not identity for identity in all_attempt_ids)
        or len(set(all_attempt_ids)) != len(all_attempt_ids)
    ):
        return False
    attempt_by_id = {row.get("attempt_id"): row for row in attempts if isinstance(row, dict)}
    phase_attempt_ids = phase_attempt_ids or []
    phase_attempts = [attempt_by_id.get(attempt_id) for attempt_id in phase_attempt_ids]
    if (
        not phase_attempt_ids or any(not isinstance(attempt, dict) for attempt in phase_attempts)
        or len(set(phase_attempt_ids)) != len(phase_attempt_ids)
    ):
        return False
    if phase == 1:
        if len(phase_attempts) != 1:
            return False
        attempt = phase_attempts[0]
        if attempt.get("status") != "BLOCKED":
            return False
    elif phase == 2:
        evidence = media_state.get("evidence")
        if not isinstance(evidence, dict):
            return False
        attempt = attempt_by_id.get(evidence.get("attempt_id"))
        if attempt is None or attempt.get("status") != "COMPLETED":
            return False
    else:
        return False

    expected_attempt_reservation = (
        _ceil_chunks(int(target["expected_bytes"])) * CHUNK_BYTES
        if phase == 1 else int(case["resume_payload_reservation_cap_per_attempt"])
    )
    if (
        any(attempt.get(key) != expected_identity[key] for key in (
            "channel_id", "message_id", "media_ordinal", "media_id", "expected_bytes",
        ))
        or attempt.get("selected_mode") != mode
        or attempt.get("schema_version") != 1
        or attempt.get("contract_version") != 2
        or attempt.get("evidence_version") != 1
        or type(attempt.get("requests")) is not int or attempt.get("requests") < 0
        or type(attempt.get("bytes_reserved")) is not int
        or attempt.get("bytes_reserved") != expected_attempt_reservation
        or type(attempt.get("bytes_received")) is not int
        or attempt.get("bytes_received") < 0
        or not isinstance(attempt.get("attempt_id"), str) or not attempt.get("attempt_id")
        or not isinstance(attempt.get("invocation_id"), str) or not attempt.get("invocation_id")
    ):
        return False
    if any(
        not isinstance(item, dict)
        or item.get("selected_mode") != mode
        or item.get("schema_version") != 1
        or item.get("contract_version") != 2
        or item.get("evidence_version") != 1
        or any(item.get(key) != expected_identity[key] for key in (
            "channel_id", "message_id", "media_ordinal", "media_id", "expected_bytes",
        ))
        or type(item.get("requests")) is not int or item["requests"] < 0
        or type(item.get("bytes_reserved")) is not int
        or item["bytes_reserved"] != expected_attempt_reservation
        or type(item.get("bytes_received")) is not int or item["bytes_received"] < 0
        or not isinstance(item.get("attempt_id"), str) or not item["attempt_id"]
        or not isinstance(item.get("invocation_id"), str) or not item["invocation_id"]
        for item in phase_attempts
    ):
        return False

    preparation = child_result.get("preparation_receipt") if phase == 1 else None
    if phase == 1:
        preparation_valid = bool(
            _preparation_receipt_valid(
                preparation, case=case, prefix_sha256=child_result.get("prefix_sha256"),
                process_id=child_result.get("process_id"),
            )
            and preparation.get("partial_path") == media_state.get("partial_path")
            and delta["uncertain_bytes"] == 0
            and delta["payload_received"] == preparation.get("wire_bytes_received")
        )
        attempt_payload_received = preparation.get("bytes_delivered") if preparation_valid else None
    else:
        preparation_valid = True
        attempt_payload_received = delta["payload_received"]
    if (
        len(phase_attempts) > (PHASE1_TRANSFER_ATTEMPT_CAP if phase == 1 else PHASE2_TRANSFER_ATTEMPT_CAP)
        or sum(item["requests"] for item in phase_attempts)
        != requests["GetFile"] + requests["GetFileHashes"] + requests["identity_GetMessages"]
        or sum(item["bytes_received"] for item in phase_attempts) != attempt_payload_received
        or not preparation_valid
    ):
        return False

    if phase == 1:
        queue_result = child_result.get("queue_result")
        details = attempt.get("details")
        return bool(
            child_exit_code == 0 and supervisor_exit_code == 0
            and isinstance(details, dict) and details.get("reason") == "CONTROLLED_INTERRUPT"
            and
            media_state.get("sqlite_state") == "FAILED_RETRYABLE"
            and media_state.get("failure_category") == "CONTROLLED_INTERRUPT"
            and media_state.get("sqlite_checkpoint_bytes") == prefix_bytes
            and media_state.get("partial_bytes") == prefix_bytes
            and type(media_state.get("partial_sha256")) is str
            and child_result.get("prefix_bytes") == media_state.get("partial_bytes")
            and child_result.get("prefix_sha256") == media_state.get("partial_sha256")
            and isinstance(queue_result, list) and len(queue_result) == 1
            and queue_result[0] == [[
                expected_identity["channel_id"], expected_identity["message_id"],
                expected_identity["media_ordinal"],
            ], "FAILED", "CONTROLLED_INTERRUPT"]
            and media_state.get("evidence_rows") == 0 and media_state.get("evidence") is None
            and media_state.get("final_bytes") is None
            and media_state.get("final_exists") is False
            and media_state.get("final_path") == media_state.get("expected_planned_final_path")
            and isinstance(media_state.get("final_path"), str)
            and media_state.get("final_path_status") == "PLANNED_ABSENT"
        )

    evidence = media_state["evidence"]
    child_evidence = child_result.get("evidence")
    digest = media_state.get("physical_sha256")
    if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    expected_evidence = {
        "media_item_id": media_state.get("media_item_id"),
        "attempt_id": attempt.get("attempt_id"),
        "channel_id": expected_identity["channel_id"],
        "message_id": expected_identity["message_id"],
        "media_ordinal": expected_identity["media_ordinal"],
        "media_id": expected_identity["media_id"],
        "expected_bytes": expected_identity["expected_bytes"],
        "final_path": media_state.get("final_path"),
        "final_sha256": digest,
        "selected_mode": mode,
        "schema_version": 1,
        "evidence_class": "REFERENCE_MATCH" if mode == "TRUSTED_REFERENCE" else "OPERATIONAL_ONLY",
        "remote_hash_class": evidence.get("remote_hash_class"),
        "contract_version": 2,
        "evidence_version": 1,
        "plan_id": evidence.get("plan_id"),
        "invocation_id": evidence.get("invocation_id"),
    }
    child_expected_evidence = {
        "media_item_id": expected_evidence["media_item_id"],
        "attempt_id": expected_evidence["attempt_id"],
        "channel_id": expected_evidence["channel_id"],
        "telegram_message_id": expected_evidence["message_id"],
        "media_ordinal": expected_evidence["media_ordinal"],
        "telegram_media_id": expected_evidence["media_id"],
        "expected_bytes": expected_evidence["expected_bytes"],
        "final_path": expected_evidence["final_path"],
        "final_sha256": expected_evidence["final_sha256"],
        "selected_mode": expected_evidence["selected_mode"],
        "schema_version": expected_evidence["schema_version"],
        "evidence_class": expected_evidence["evidence_class"],
        "remote_hash_class": expected_evidence["remote_hash_class"],
        "contract_version": expected_evidence["contract_version"],
        "evidence_version": expected_evidence["evidence_version"],
        "plan_id": expected_evidence["plan_id"],
        "invocation_id": expected_evidence["invocation_id"],
    }
    child_evidence_matches = isinstance(child_evidence, dict) and all(
        child_evidence.get(key) == value for key, value in child_expected_evidence.items()
    )
    return bool(
        media_state.get("sqlite_state") == "COMPLETED_V2"
        and media_state.get("expected_bytes") == target["expected_bytes"]
        and media_state.get("sqlite_checkpoint_bytes") == target["expected_bytes"]
        and media_state.get("contract_version") == 2
        and media_state.get("evidence_version") == 1
        and media_state.get("final_bytes") == target["expected_bytes"]
        and media_state.get("partial_path") is not None
        and media_state.get("final_path") == evidence.get("final_path")
        and media_state.get("final_path") == media_state.get("expected_planned_final_path")
        and media_state.get("final_exists") is True
        and media_state.get("physical_sha256") == media_state.get("sqlite_sha256") == digest
        and all(evidence.get(key) == value for key, value in expected_evidence.items())
        and type(expected_evidence["plan_id"]) is str and bool(expected_evidence["plan_id"])
        and type(expected_evidence["invocation_id"]) is str and bool(expected_evidence["invocation_id"])
        and child_evidence_matches
        and child_result.get("final_bytes") == target["expected_bytes"]
        and child_result.get("final_sha256") == digest
        and media_state.get("evidence_rows") == 1
    )


def _resolve_completed_final_path(case_root: Path, *, state: str, final_path: str | None) -> Path:
    if state != "COMPLETED_V2" or not isinstance(final_path, str) or not final_path.strip():
        raise RuntimeError("COMPLETED_V2_REQUIRED")
    candidate = Path(final_path)
    downloads_root = case_root / "downloads"
    if (
        not candidate.is_absolute()
        or case_root.is_symlink()
        or downloads_root.is_symlink()
        or not downloads_root.is_dir()
    ):
        raise RuntimeError("COMPLETED_V2_REQUIRED")
    try:
        resolved_case_root = case_root.resolve(strict=True)
        resolved_downloads_root = downloads_root.resolve(strict=True)
        if resolved_downloads_root != resolved_case_root / "downloads":
            raise RuntimeError("COMPLETED_V2_REQUIRED")
        relative = candidate.relative_to(downloads_root)
        if not relative.parts or any(part in {".", ".."} for part in relative.parts):
            raise RuntimeError("COMPLETED_V2_REQUIRED")
        current = downloads_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise RuntimeError("COMPLETED_V2_REQUIRED")
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise RuntimeError("COMPLETED_V2_REQUIRED") from error
    if (
        resolved == resolved_downloads_root
        or not resolved.is_relative_to(resolved_downloads_root)
        or not resolved.is_file()
    ):
        raise RuntimeError("COMPLETED_V2_REQUIRED")
    return resolved


class ProofLedger:
    """Fresh proof-only SQLite ledger; never points at an operational database."""

    _COLUMNS = (
        "getfile_calls", "getfilehashes_calls", "payload_reserved",
        "payload_received", "uncertain_bytes",
    )

    def __init__(
        self, path: Path, *, getfile_cap: int, hash_cap: int, payload_cap: int,
        require_existing: bool = False,
    ) -> None:
        self.path = path.absolute()
        for cap in (getfile_cap, hash_cap, payload_cap):
            if type(cap) is not int or cap < 0:
                raise RuntimeError("PROOF_BUDGET_CAP_INVALID")
        self.getfile_cap = getfile_cap
        self.hash_cap = hash_cap
        self.payload_cap = payload_cap
        if require_existing:
            if not self.path.is_file() or self.path.is_symlink():
                raise RuntimeError("PROOF_BUDGET_LEDGER_MISSING")
            with sqlite3.connect(self.path) as db:
                self._validate_schema(db)
            current = self.snapshot()
            if (
                current["getfile_calls"] > self.getfile_cap
                or current["getfilehashes_calls"] > self.hash_cap
                or current["payload_reserved"] > self.payload_cap
            ):
                raise RuntimeError("PROOF_BUDGET_LEDGER_INCONSISTENT")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.path) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS proof_budget ("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton=1), getfile_calls INTEGER NOT NULL, "
                    "getfilehashes_calls INTEGER NOT NULL, payload_reserved INTEGER NOT NULL, "
                    "payload_received INTEGER NOT NULL, uncertain_bytes INTEGER NOT NULL)"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS proof_reservations ("
                    "reservation_id TEXT PRIMARY KEY, kind TEXT NOT NULL, amount INTEGER NOT NULL, "
                    "state TEXT NOT NULL DEFAULT 'PENDING', received_bytes INTEGER NOT NULL DEFAULT 0)"
                )
                db.execute("INSERT OR IGNORE INTO proof_budget VALUES(1,0,0,0,0,0)")
                self._validate_schema(db)

    @classmethod
    def _validate_schema(cls, db: sqlite3.Connection) -> None:
        expected = {
            "proof_budget": (
                "singleton", *cls._COLUMNS,
            ),
            "proof_reservations": ("reservation_id", "kind", "amount", "state", "received_bytes"),
        }
        declared_types = {
            "proof_budget": ("INTEGER",) * 6,
            "proof_reservations": ("TEXT", "TEXT", "INTEGER", "TEXT", "INTEGER"),
        }
        for table, columns in expected.items():
            rows = db.execute(f"PRAGMA table_info({table})").fetchall()
            if (
                tuple(row[1] for row in rows) != columns
                or tuple(str(row[2]).upper() for row in rows) != declared_types[table]
            ):
                raise RuntimeError("PROOF_BUDGET_LEDGER_INVALID")

    @classmethod
    def _snapshot_from_row(cls, row: tuple[Any, ...] | None) -> dict[str, int]:
        if row is None or len(row) != len(cls._COLUMNS) or any(type(value) is not int for value in row):
            raise RuntimeError("PROOF_BUDGET_LEDGER_INVALID")
        result = dict(zip(cls._COLUMNS, row, strict=True))
        if (
            any(value < 0 for value in result.values())
            or result["uncertain_bytes"] + result["payload_received"] > result["payload_reserved"]
            or result["payload_reserved"] != result["getfile_calls"] * CHUNK_BYTES
        ):
            raise RuntimeError("PROOF_BUDGET_LEDGER_INCONSISTENT")
        return result

    @classmethod
    def _reservation_counts(cls, db: sqlite3.Connection, snapshot: dict[str, int]) -> None:
        rows = db.execute(
            "SELECT reservation_id,kind,amount,state,received_bytes FROM proof_reservations"
        ).fetchall()
        counts = {"getfile": 0, "hash": 0}
        pending_bytes = received_bytes = uncertain_bytes = 0
        for reservation_id, kind, amount, state, received in rows:
            try:
                cls._validate_reservation_id(reservation_id)
            except RuntimeError as error:
                raise RuntimeError("PROOF_BUDGET_LEDGER_INCONSISTENT") from error
            if (kind == "getfile" and type(amount) is int and 0 < amount <= CHUNK_BYTES
                    and state in {"PENDING", "RECEIVED", "UNCERTAIN"}
                    and type(received) is int and 0 <= received <= amount
                    and ((state == "RECEIVED" and received <= amount)
                         or (state != "RECEIVED" and received == 0))):
                counts[kind] += 1
                if state == "PENDING":
                    pending_bytes += CHUNK_BYTES
                elif state == "RECEIVED":
                    received_bytes += received
                else:
                    uncertain_bytes += CHUNK_BYTES
            elif (kind == "hash" and type(amount) is int and amount == 0
                    and state == "RECEIVED" and type(received) is int and received == 0):
                counts[kind] += 1
            else:
                raise RuntimeError("PROOF_BUDGET_LEDGER_INCONSISTENT")
        if (
            counts["getfile"] != snapshot["getfile_calls"]
            or counts["hash"] != snapshot["getfilehashes_calls"]
            or received_bytes != snapshot["payload_received"]
            or uncertain_bytes != snapshot["uncertain_bytes"]
            or pending_bytes + received_bytes + uncertain_bytes > snapshot["payload_reserved"]
        ):
            raise RuntimeError("PROOF_BUDGET_LEDGER_INCONSISTENT")

    @staticmethod
    def _validate_reservation_id(reservation_id: str) -> None:
        if (
            not isinstance(reservation_id, str)
            or not reservation_id or len(reservation_id) > 240
            or not re.fullmatch(r"[A-Za-z0-9:_-]+", reservation_id)
        ):
            raise RuntimeError("PROOF_RESERVATION_ID_INVALID")

    def _reserve(self, kind: str, amount: int, reservation_id: str) -> int:
        self._validate_reservation_id(reservation_id)
        if kind == "getfile":
            if type(amount) is not int or not 0 < amount <= CHUNK_BYTES:
                raise RuntimeError("GETFILE_RESERVATION_INVALID")
        elif kind == "hash":
            if type(amount) is not int or amount != 0:
                raise RuntimeError("HASH_RESERVATION_INVALID")
        else:
            raise RuntimeError("PROOF_RESERVATION_KIND_INVALID")

        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            self._validate_schema(db)
            if db.execute("SELECT COUNT(*) FROM proof_budget").fetchone() != (1,):
                raise RuntimeError("PROOF_BUDGET_LEDGER_INVALID")
            snapshot = self._snapshot_from_row(db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone())
            self._reservation_counts(db, snapshot)
            existing = db.execute(
                "SELECT kind,amount FROM proof_reservations WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if existing is not None:
                if existing != (kind, amount):
                    raise RuntimeError("PROOF_RESERVATION_ID_CONFLICT")
                return snapshot["getfile_calls" if kind == "getfile" else "getfilehashes_calls"]

            if kind == "getfile":
                if (
                    snapshot["getfile_calls"] + 1 > self.getfile_cap
                    or snapshot["payload_reserved"] + CHUNK_BYTES > self.payload_cap
                ):
                    raise RuntimeError("PROOF_BUDGET_EXHAUSTED")
                db.execute(
                    "INSERT INTO proof_reservations(reservation_id,kind,amount,state,received_bytes) "
                    "VALUES(?,?,?,'PENDING',0)", (reservation_id, kind, amount),
                )
                db.execute(
                    "UPDATE proof_budget SET getfile_calls=getfile_calls+1, "
                    "payload_reserved=payload_reserved+? WHERE singleton=1", (CHUNK_BYTES,),
                )
                current = self._snapshot_from_row(db.execute(
                    "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                    "FROM proof_budget WHERE singleton=1"
                ).fetchone())
                self._reservation_counts(db, current)
                return current["getfile_calls"]

            if snapshot["getfilehashes_calls"] + 1 > self.hash_cap:
                raise RuntimeError("GETFILEHASHES_BUDGET_EXHAUSTED")
            db.execute(
                "INSERT INTO proof_reservations(reservation_id,kind,amount,state,received_bytes) "
                "VALUES(?,?,?,'RECEIVED',0)", (reservation_id, kind, amount),
            )
            db.execute("UPDATE proof_budget SET getfilehashes_calls=getfilehashes_calls+1 WHERE singleton=1")
            current = self._snapshot_from_row(db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone())
            self._reservation_counts(db, current)
            return current["getfilehashes_calls"]

    def reserve_getfile(self, amount: int, reservation_id: str | None = None) -> int:
        if reservation_id is None:
            reservation_id = f"auto-getfile-{uuid.uuid4().hex}"
        return self._reserve("getfile", amount, reservation_id)

    def reserve_hash(self, reservation_id: str | None = None) -> int:
        if reservation_id is None:
            reservation_id = f"auto-hash-{uuid.uuid4().hex}"
        return self._reserve("hash", 0, reservation_id)

    def settle_getfile(self, reservation_id: str, received: int | None) -> str:
        if received is not None and (type(received) is not int or not 0 <= received <= CHUNK_BYTES):
            raise RuntimeError("GETFILE_RESPONSE_SIZE_INVALID")
        self._validate_reservation_id(reservation_id)
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            self._validate_schema(db)
            if db.execute("SELECT COUNT(*) FROM proof_budget").fetchone() != (1,):
                raise RuntimeError("PROOF_BUDGET_LEDGER_INVALID")
            snapshot = self._snapshot_from_row(db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone())
            self._reservation_counts(db, snapshot)
            reservation = db.execute(
                "SELECT kind,amount,state,received_bytes FROM proof_reservations WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if reservation is None or reservation[0] != "getfile":
                raise RuntimeError("PROOF_RESERVATION_MISSING")
            kind, amount, state, settled_bytes = reservation
            if received is not None and received > amount:
                raise RuntimeError("GETFILE_RESPONSE_EXCEEDS_RESERVATION")
            wanted_state = "UNCERTAIN" if received is None else "RECEIVED"
            wanted_bytes = 0 if received is None else received
            if state != "PENDING":
                if state == wanted_state and settled_bytes == wanted_bytes:
                    return state
                if state == "UNCERTAIN" and received is None:
                    return state
                raise RuntimeError("PROOF_RESERVATION_ALREADY_SETTLED")
            if received is None:
                db.execute(
                    "UPDATE proof_budget SET uncertain_bytes=uncertain_bytes+? WHERE singleton=1",
                    (CHUNK_BYTES,),
                )
            else:
                db.execute(
                    "UPDATE proof_budget SET payload_received=payload_received+? WHERE singleton=1",
                    (received,),
                )
            db.execute(
                "UPDATE proof_reservations SET state=?,received_bytes=? "
                "WHERE reservation_id=? AND state='PENDING'",
                (wanted_state, wanted_bytes, reservation_id),
            )
            self._snapshot_from_row(db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone())
            return wanted_state

    def settle_pending_uncertain(self) -> int:
        """Settle each outstanding GetFile reservation once after confirmed exit."""
        settled = 0
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            self._validate_schema(db)
            snapshot = self._snapshot_from_row(db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone())
            self._reservation_counts(db, snapshot)
            pending = db.execute(
                "SELECT reservation_id FROM proof_reservations WHERE kind='getfile' AND state='PENDING' "
                "ORDER BY reservation_id"
            ).fetchall()
            for (reservation_id,) in pending:
                changed = db.execute(
                    "UPDATE proof_reservations SET state='UNCERTAIN',received_bytes=0 "
                    "WHERE reservation_id=? AND kind='getfile' AND state='PENDING'",
                    (reservation_id,),
                ).rowcount
                if changed:
                    db.execute("UPDATE proof_budget SET uncertain_bytes=uncertain_bytes+? WHERE singleton=1", (CHUNK_BYTES,))
                    settled += changed
            after = self._snapshot_from_row(db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone())
            self._reservation_counts(db, after)
        return settled

    def reservation_summary(self) -> dict[str, int]:
        with sqlite3.connect(self.path) as db:
            self._validate_schema(db)
            rows = db.execute(
                "SELECT kind,state,COUNT(*) FROM proof_reservations GROUP BY kind,state"
            ).fetchall()
        summary = {"pending": 0, "received": 0, "uncertain": 0}
        for kind, state, count in rows:
            if kind == "getfile" and state in {"PENDING", "RECEIVED", "UNCERTAIN"}:
                summary[state.lower()] += count
        return summary

    def snapshot(self) -> dict[str, int]:
        with sqlite3.connect(self.path) as db:
            self._validate_schema(db)
            row_count = db.execute("SELECT COUNT(*) FROM proof_budget").fetchone()
            if row_count != (1,):
                raise RuntimeError("PROOF_BUDGET_LEDGER_INVALID")
            snapshot = self._snapshot_from_row(db.execute(
                "SELECT getfile_calls,getfilehashes_calls,payload_reserved,payload_received,uncertain_bytes "
                "FROM proof_budget WHERE singleton=1"
            ).fetchone())
            self._reservation_counts(db, snapshot)
        return snapshot


class _BudgetLease:
    def __init__(self, inner: Any, ledger: ProofLedger, reservation_id: str) -> None:
        self.inner = inner
        self.ledger = ledger
        self.reservation_id = reservation_id
        self._settled = False

    def received(self, count: int) -> None:
        self.inner.received(count)
        self.ledger.settle_getfile(self.reservation_id, count)
        self._settled = True

    def release(self) -> None:
        self.inner.release()
        self._settled = True

    def charge_uncertain(self) -> None:
        self.inner.charge_uncertain()
        self.ledger.settle_getfile(self.reservation_id, None)
        self._settled = True


class ProofGateway:
    """Bounds and records every relevant request before delegating to Telethon."""

    def __init__(
        self, gateway: Any, ledger: ProofLedger, *, phase: int,
        phase_getfile_cap: int | None = None, phase_hash_cap: int | None = None,
        phase_identity_cap: int | None = None, interrupt_after: int | None = None,
        execution_id: str | None = None, expected_prefix_sha256: str | None = None,
        prefix_bytes: int = COMMON_PREFIX_ALIGNED, expected_overlap_bytes: bytes = b"",
        mode: str = "OPERATIONAL_ONLY", local_prefix_reference_evidence: dict[str, Any] | None = None,
        per_attempt_getfile_cap: int | None = None, per_attempt_hash_cap: int | None = None,
    ) -> None:
        self.gateway = gateway
        self.ledger = ledger
        self.phase = phase
        self.execution_id = execution_id or f"phase-{phase}-pid-{os.getpid()}"
        self.phase_getfile_cap = phase_getfile_cap
        self.phase_hash_cap = phase_hash_cap
        self.phase_identity_cap = phase_identity_cap
        self.interrupt_after = interrupt_after
        self.expected_prefix_sha256 = expected_prefix_sha256
        self.mode = mode
        self.local_prefix_reference_evidence = local_prefix_reference_evidence
        self.per_attempt_getfile_cap = per_attempt_getfile_cap
        self.per_attempt_hash_cap = per_attempt_hash_cap
        self._attempt_getfile_calls = 0
        self._attempt_hash_calls = 0
        self.prefix_bytes = prefix_bytes
        self.wire_offset = (prefix_bytes // CHUNK_BYTES) * CHUNK_BYTES
        self.overlap_bytes = prefix_bytes - self.wire_offset
        self.transfer_offset = self.wire_offset + CHUNK_BYTES if self.overlap_bytes else self.wire_offset
        self.expected_overlap_bytes = expected_overlap_bytes
        self.prefix_reread_verified = False
        self.pending_prefix_result: tuple[int, str] | None = None
        self.verified_prefix_bytes: int | None = None
        self.verified_prefix_sha256: str | None = None
        self.observed_remote_overlap = b""
        self.overlap_observation: dict[str, Any] | None = None
        self._boundary_response: dict[str, Any] | None = None
        self._next_stream_offset: int | None = None
        self.preparation_receipt = {
            "process_id": os.getpid(), "wire_request_offset": 0, "wire_bytes_received": 0,
            "bytes_delivered": 0, "bytes_persisted": 0, "preparation_discarded": 0,
            "wire_requests": [],
            "prefix_bytes": prefix_bytes, "prefix_sha256": None,
            "sqlite_checkpoint_bytes": None, "sqlite_state": None,
            "stop_condition": None,
        }
        self.identity_calls = 0
        self.identity_preflight_passed = False
        self.getfile_calls = 0
        self.getfilehashes_calls = 0
        self.restore_calls = 0
        self.getme_calls: int | None = None

    async def restore(self):
        self.restore_calls += 1
        state = await self.gateway.restore()
        # TelethonGateway.restore calls get_me once when it restores a stored session.
        self.getme_calls = 1 if getattr(state, "name", None) == "AUTHENTICATED" else 0
        _progress_event("child.session_restored", phase=self.phase, outcome="restored")
        return state

    async def validate_media_identity(self, *args, **kwargs):
        self.identity_calls += 1
        if (
            self.identity_calls > MAX_ATTEMPTS
            or (self.phase_identity_cap is not None and self.identity_calls > self.phase_identity_cap)
        ):
            raise RuntimeError("IDENTITY_REQUEST_CAP_EXHAUSTED")
        valid = await self.gateway.validate_media_identity(*args, **kwargs)
        if valid is True:
            self.identity_preflight_passed = True
            _progress_event("child.remote_identity_validated", phase=self.phase, outcome="validated")
        return valid

    async def get_file_hashes(self, *args, **kwargs):
        if not self.identity_preflight_passed:
            raise RuntimeError("REMOTE_IDENTITY_PREFLIGHT_REQUIRED")
        if self.phase_hash_cap is not None and self.getfilehashes_calls + 1 > self.phase_hash_cap:
            raise RuntimeError("PHASE_GETFILEHASHES_BUDGET_EXHAUSTED")
        if self.per_attempt_hash_cap is not None and self._attempt_hash_calls + 1 > self.per_attempt_hash_cap:
            raise RuntimeError("ATTEMPT_GETFILEHASHES_BUDGET_EXHAUSTED")
        reservation_id = f"{self.execution_id}:{self.phase}:hash:{self.getfilehashes_calls + 1}"
        self.ledger.reserve_hash(reservation_id)
        self.getfilehashes_calls += 1
        self._attempt_hash_calls += 1
        result = await self.gateway.get_file_hashes(*args, **kwargs)
        _progress_event("child.remote_hash_progress", phase=self.phase, outcome="completed",
                        counts={"getfilehashes_calls": self.getfilehashes_calls})
        return result

    async def stream_media(self, *args, reserve_chunk=None, **kwargs):
        from telegram_courses.downloads import DownloadGatewayError

        if not self.identity_preflight_passed:
            raise RuntimeError("REMOTE_IDENTITY_PREFLIGHT_REQUIRED")
        if reserve_chunk is None:
            raise RuntimeError("S5_RESERVATION_CALLBACK_REQUIRED")
        sent = 0
        persisted = 0
        offset = kwargs.get("offset", 0)
        if self.per_attempt_getfile_cap is not None:
            self._attempt_getfile_calls = 0
            self._attempt_hash_calls = 0
        is_prefix_reread = self.phase == 2 and self.mode == "OPERATIONAL_ONLY" and offset == 0
        if is_prefix_reread:
            self.pending_prefix_result = None
            self.prefix_reread_verified = False
        prefix_digest = hashlib.sha256()
        prefix_count = 0

        async def reserve(amount: int):
            lease = await reserve_chunk(amount)
            if lease is None:
                return None
            try:
                if self.phase_getfile_cap is not None and self.getfile_calls + 1 > self.phase_getfile_cap:
                    raise RuntimeError("PHASE_GETFILE_BUDGET_EXHAUSTED")
                if (
                    self.per_attempt_getfile_cap is not None
                    and self._attempt_getfile_calls + 1 > self.per_attempt_getfile_cap
                ):
                    raise RuntimeError("ATTEMPT_GETFILE_BUDGET_EXHAUSTED")
                reservation_id = f"{self.execution_id}:{self.phase}:getfile:{self.getfile_calls + 1}"
                self.ledger.reserve_getfile(amount, reservation_id)
            except BaseException:
                lease.release()
                raise
            self.getfile_calls += 1
            self._attempt_getfile_calls += 1
            return _BudgetLease(lease, self.ledger, reservation_id)

        if self.phase == 2 and offset == self.transfer_offset:
            pending = (
                (self.prefix_bytes, self.expected_prefix_sha256)
                if self.mode == "TRUSTED_REFERENCE" and self.local_prefix_reference_evidence
                and self.local_prefix_reference_evidence.get("status") == "LOCAL_PREFIX_REFERENCE_MATCH"
                else self.pending_prefix_result
            )
            if pending is None or pending[0] != self.prefix_bytes:
                _progress_event("child.full_prefix_reread", phase=self.phase, outcome="short",
                                counts={"verified_bytes": pending[0] if pending else 0})
                _progress_event("child.prefix_hash_reconciled", phase=self.phase, outcome="short",
                                counts={"verified_bytes": pending[0] if pending else 0})
                raise DownloadGatewayError("PREFIX_RECONCILIATION_REQUIRED")
            if pending[1] != self.expected_prefix_sha256:
                _progress_event("child.prefix_hash_reconciled", phase=self.phase, outcome="mismatch",
                                counts={"verified_bytes": pending[0]})
                raise DownloadGatewayError("PREFIX_RECONCILIATION_REQUIRED")
            if self.overlap_bytes and (
                self._boundary_response is None
                or self._boundary_response.get("overlap_match") is not True
                or self._boundary_response.get("reused_suffix_bytes") != CHUNK_BYTES - self.overlap_bytes
            ):
                raise DownloadGatewayError("OVERLAP_RECONCILIATION_REQUIRED")
            self.prefix_reread_verified = self.mode == "OPERATIONAL_ONLY"
            if self.mode == "OPERATIONAL_ONLY":
                self.verified_prefix_bytes = pending[0]
                self.verified_prefix_sha256 = pending[1]
            self.pending_prefix_result = None
            if self.mode == "OPERATIONAL_ONLY":
                _progress_event("child.full_prefix_reread", phase=self.phase, outcome="completed",
                                counts={"verified_bytes": pending[0]})
                _progress_event("child.prefix_hash_reconciled", phase=self.phase, outcome="matched",
                                counts={"verified_bytes": pending[0]})
            _progress_event("child.continuation_started", phase=self.phase, outcome="started_transfer")
            if self.overlap_bytes:
                self._next_stream_offset = offset
                self.overlap_observation = {
                    **self._boundary_response,
                    "next_remote_request_offset": offset,
                    "next_offset_observed": offset == self.transfer_offset,
                    "status": "PASS" if offset == self.transfer_offset else "FAIL",
                }
        elif (self.phase == 2 and offset > 0 and not self.prefix_reread_verified
              and not (self.mode == "TRUSTED_REFERENCE" and self.local_prefix_reference_evidence
                       and self.local_prefix_reference_evidence.get("status") == "LOCAL_PREFIX_REFERENCE_MATCH")):
            raise DownloadGatewayError("PREFIX_RECONCILIATION_REQUIRED")

        stream = self.gateway.stream_media(*args, reserve_chunk=reserve, **kwargs)
        try:
            async for block in stream:
                if _child_cancel_requested():
                    raise DownloadGatewayError("SUPERVISOR_CANCELLED")
                if is_prefix_reread and prefix_count < self.prefix_bytes:
                    count = min(len(block), self.prefix_bytes - prefix_count)
                    prefix_digest.update(block[:count])
                    block_start = prefix_count
                    overlap_start = self.wire_offset - block_start
                    if self.overlap_bytes and block_start <= self.wire_offset < block_start + len(block):
                        start = overlap_start
                        remote_overlap = block[start:start + self.overlap_bytes]
                        self.observed_remote_overlap = remote_overlap
                        self._boundary_response = {
                            "remote_request_offset": self.wire_offset,
                            "wire_bytes_received": len(block),
                            "overlap_bytes_compared": self.overlap_bytes,
                            "overlap_match": (
                                len(remote_overlap) == self.overlap_bytes
                                and self.expected_overlap_bytes == remote_overlap
                            ),
                            "reused_suffix_bytes": len(block) - start - self.overlap_bytes,
                        }
                    prefix_count += count
                if self.phase == 1 and self.interrupt_after is not None:
                    remaining = self.interrupt_after - sent
                    if remaining <= 0:
                        raise DownloadGatewayError("CONTROLLED_INTERRUPT")
                    if len(block) > remaining:
                        self.preparation_receipt["wire_bytes_received"] += len(block)
                        self.preparation_receipt["preparation_discarded"] += len(block) - remaining
                        self.preparation_receipt["wire_requests"].append({
                            "offset": sent, "wire_bytes_received": len(block),
                            "delivered_bytes": remaining,
                            "preparation_discarded": len(block) - remaining,
                        })
                        yield block[:remaining]
                        self.preparation_receipt["bytes_persisted"] += remaining
                        self.preparation_receipt["bytes_delivered"] += remaining
                        sent += remaining
                        self.preparation_receipt["stop_condition"] = "CONTROLLED_INTERRUPT"
                        raise DownloadGatewayError("CONTROLLED_INTERRUPT")
                    self.preparation_receipt["wire_bytes_received"] += len(block)
                    self.preparation_receipt["wire_requests"].append({
                        "offset": sent, "wire_bytes_received": len(block),
                        "delivered_bytes": len(block), "preparation_discarded": 0,
                    })
                sent += len(block)
                _progress_event(
                    "child.transfer_progress", phase=self.phase, outcome="completed",
                    counts={"stream_confirmed_bytes": sent, "verified_bytes": sent,
                            "getfile_calls": self.getfile_calls,
                            "getfilehashes_calls": self.getfilehashes_calls},
                )
                yield block
                persisted += len(block)
                if self.phase == 1 and self.interrupt_after is not None:
                    self.preparation_receipt["bytes_delivered"] += len(block)
                    self.preparation_receipt["bytes_persisted"] += len(block)
                _progress_event(
                    "child.transfer_progress", phase=self.phase, outcome="completed",
                    counts={"stream_confirmed_bytes": sent, "persisted_bytes": persisted,
                            "verified_bytes": max(sent, persisted),
                            "getfile_calls": self.getfile_calls,
                            "getfilehashes_calls": self.getfilehashes_calls},
                )
                if (
                    self.phase == 1 and self.interrupt_after is not None
                    and sent >= self.interrupt_after
                ):
                    raise DownloadGatewayError("CONTROLLED_INTERRUPT")
        finally:
            close = getattr(stream, "aclose", None)
            if callable(close):
                await close()
            if is_prefix_reread:
                self.pending_prefix_result = (prefix_count, prefix_digest.hexdigest())
    async def close(self) -> None:
        await self.gateway.close()


async def _seed_proof_catalog(database: Path, target: dict[str, Any]) -> int:
    with _probe_stage("B02_B03_seed_imports"):
        import aiosqlite

        from telegram_courses.download_repository import DownloadRepository

    repository = DownloadRepository(database)
    _probe_mark("B08_seed_migrate", "start")
    await repository.migrate()
    _probe_mark("B08_seed_migrate", "end", outcome="ok")
    _probe_mark("B08_seed_sqlite", "start")
    async with aiosqlite.connect(database) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (target["channel_id"], "S6 V2 isolated proof", "proof", "proof"),
        )
        await db.execute(
            "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
            "VALUES(?,?,?,?,?)", (target["channel_id"], target["message_id"], "2026-10-17T00:00:00Z", "proof", "proof"),
        )
        await db.execute(
            "INSERT INTO catalog_nodes(channel_id,kind,title,source_message_id,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?)", (target["channel_id"], "lesson", "S6 V2 proof item", target["message_id"], "proof", "proof"),
        )
        node_id = int((await (await db.execute("SELECT id FROM catalog_nodes")).fetchone())[0])
        await db.execute(
            "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
            "telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (target["channel_id"], target["message_id"], 0, node_id, "DOCUMENT", target["media_id"],
             "proof-document.bin", target["expected_bytes"], "proof", "proof"),
        )
        await db.execute(
            "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,"
            "source_message_count,catalog_node_count,unresolved_count) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("s6-v2-proof-run", target["channel_id"], "s6-v2-proof", "1", "COMPLETE", "proof", "proof", 1, 1, 0),
        )
        row = await (await db.execute("SELECT id FROM media_items")).fetchone()
        await db.commit()
    _probe_mark("B08_seed_sqlite", "end", outcome="ok")
    return int(row[0])


def _new_isolated_root(base: Path | None = None) -> Path:
    import tempfile

    parent = Path(base) if base else Path(tempfile.gettempdir())
    parent = Path(os.path.abspath(parent))
    if not _directory_path_is_safe(parent):
        raise RuntimeError("EVIDENCE_PARENT_UNSAFE")
    resolved_parent = parent.resolve(strict=True)
    reference = CANONICAL_TRUSTED_REFERENCE_PATH
    if reference.exists():
        resolved_reference = reference.resolve(strict=True)
        if (resolved_reference.is_relative_to(resolved_parent)
                or resolved_parent.is_relative_to(resolved_reference)):
            raise RuntimeError("REFERENCE_ALIASES_EVIDENCE_ROOT")
    production_database = (REPOSITORY_ROOT / "data/telegram_courses.sqlite3").resolve(strict=False)
    if (production_database.is_relative_to(resolved_parent)
            or resolved_parent.is_relative_to(production_database.parent)):
        raise RuntimeError("OPERATIONAL_SQLITE_PATH_REUSED")
    root = parent / f"s6t-{uuid.uuid4().hex}"
    root.mkdir(parents=False, exist_ok=False)
    if not _directory_path_is_safe(root):
        raise RuntimeError("EVIDENCE_ROOT_UNSAFE")
    _guard_native_paths((root, root / "controlled" / "downloads" / "proof-document.bin.part"))
    return root


def _guard_native_paths(paths: tuple[Path, ...] | list[Path]) -> None:
    if os.name == "nt" and any(len(str(path.absolute())) > MAX_NATIVE_PATH_CHARS for path in paths):
        raise RuntimeError("NATIVE_PATH_LIMIT_EXCEEDED")


def _require_disk_budget(root: Path, target: dict[str, Any], pending_bytes: int) -> dict[str, int]:
    from telegram_courses.s5_downloads import GIB

    margin = max(GIB, int(pending_bytes * 0.10))
    required = pending_bytes + margin
    free = shutil.disk_usage(root).free
    if free < required:
        raise RuntimeError("INSUFFICIENT_DISK_SPACE_BEFORE_RPC")
    return {"free_bytes": free, "pending_bytes": pending_bytes, "s5_margin_bytes": margin, "required_free_bytes": required}


def _validate_child_authorization(args) -> dict[str, Any]:
    root = Path(args.evidence_root).resolve(strict=True)
    report = Path(args.phase_report).resolve(strict=False)
    expected_report = (root / args.case / f"phase-{args.phase}.child.json").resolve(strict=False)
    manifest_path = Path(getattr(args, "authorization_file", root / "authorization.json")).resolve(strict=False)
    cancel_marker_text = os.environ.get("S6_V2_CANCEL_MARKER")
    expected_cancel_marker = (root / args.case / "supervisor.cancel").resolve(strict=False)
    if (
        not root.is_dir() or root.is_symlink() or not root.name.startswith(("s6t-", "s6-v2-real-proof-"))
        or report != expected_report or not report.is_relative_to(root)
        or not manifest_path.is_relative_to(root) or not manifest_path.is_file()
        or manifest_path.is_symlink() or report.exists()
        or (cancel_marker_text is not None
            and Path(cancel_marker_text).resolve(strict=False) != expected_cancel_marker)
    ):
        raise RuntimeError("CHILD_PATH_SCOPE_INVALID")
    _guard_native_paths((root, report, manifest_path, expected_report))
    authorization = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_profile = _case_budget(
        target_for(args.target), args.mode, args.case,
        getattr(args, "prefix_profile", None),
    )
    expected_case_profile = {
        "prefix_bytes": expected_profile["prefix_bytes"],
        "prefix_profile": expected_profile.get("prefix_profile"),
        "wire_offset": expected_profile["wire_offset"],
        "transfer_offset": expected_profile["transfer_offset"],
        "overlap_bytes": expected_profile["overlap_bytes"],
        "effective_caps": _case_effective_limits(args.case, args.mode, args.target, expected_profile),
        "approved_maxima": dict(
            TRUSTED_REFERENCE_APPROVED_MAXIMA if args.mode == "TRUSTED_REFERENCE" else APPROVED_LIMITS
        ),
    }
    if (
        authorization.get("evidence_root") != str(root)
        or authorization.get("target") != args.target
        or authorization.get("mode") != args.mode
        or authorization.get("contract_sha256") != V2_CONTRACT_SHA256
        or authorization.get("token_sha256") != hashlib.sha256(
            os.environ.get("S6_V2_PROOF_AUTH", "").encode("ascii", errors="ignore")
        ).hexdigest()
        or args.phase not in authorization.get("allowed_phases", [])
        or authorization.get("allowed_cases") != [args.case]
        or authorization.get("case_profile") != expected_case_profile
        or args.target not in {"common", "controlled"}
        or (args.target == "common" and args.mode != "OPERATIONAL_ONLY")
        or (args.target == "controlled" and args.mode != "TRUSTED_REFERENCE")
        or bool(args.recovered_phase1) != bool(authorization.get("recovered_phase1", False))
        or args.phase not in {1, 2}
    ):
        raise RuntimeError("CHILD_AUTHORIZATION_SCOPE_MISMATCH")
    if args.phase == 2:
        previous_report = root / args.case / "phase-1.json"
        if not previous_report.is_file() or previous_report.is_symlink():
            raise RuntimeError("PHASE1_REPORT_MISSING")
        previous = json.loads(previous_report.read_text(encoding="utf-8"))
        recovered = args.recovered_phase1 and previous.get("process_id") is None
        normal = (
            previous.get("process_id") == args.phase1_pid
            and args.phase1_pid > 0
            and previous.get("process_exit_confirmed") is True
            and previous.get("exit_code") == 0
            and previous.get("child_exit_code") == 0
            and previous.get("status") == "PROCESS_INTERRUPTED"
            and previous.get("stop_condition") == "CONTROLLED_INTERRUPT"
            and previous.get("child_report_valid") is True
        )
        if (
            previous.get("phase") != 1 or previous.get("target_name") != args.target
            or previous.get("mode") != args.mode or previous.get("case") != args.case
            or previous.get("sqlite_state") != "FAILED_RETRYABLE"
            or not (normal or (recovered and previous.get("process_exit_confirmed") is True))
        ):
            raise RuntimeError("PHASE1_REPORT_SCOPE_MISMATCH")
    return authorization


def _validate_target_profile(
    name: str, mode: str, prefix_profile: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target = target_for(name)
    if name == "common" and mode != "OPERATIONAL_ONLY":
        raise RuntimeError("COMMON_TARGET_REQUIRES_OPERATIONAL_ONLY")
    if name == "controlled" and mode != "TRUSTED_REFERENCE":
        raise RuntimeError("CONTROLLED_TARGET_REQUIRES_TRUSTED_REFERENCE")
    if name == "controlled":
        selected = prefix_profile or "8MiB"
        if selected not in CONTROLLED_PREFIX_OPTIONS:
            raise RuntimeError("UNAUTHORIZED_PREFIX_PROFILE")
        cases = [{"name": "aligned", "prefix_bytes": CONTROLLED_PREFIX_OPTIONS[selected],
                  "prefix_profile": selected}]
        return target, [proof_budget(target["expected_bytes"], item["prefix_bytes"], mode)
                        | {"case": item["name"], "prefix_profile": selected} for item in cases]
    p = COMMON_PREFIX_ALIGNED
    cases = [
        {"name": "aligned", "prefix_bytes": p},
        {"name": "unaligned-prepared", "prefix_bytes": p + 123},
    ]
    return target, [proof_budget(target["expected_bytes"], item["prefix_bytes"], mode) | {"case": item["name"]} for item in cases]


def _case_effective_limits(
    case_name: str, mode: str = "OPERATIONAL_ONLY", target_name: str = "common",
    budget: dict[str, Any] | None = None,
) -> dict[str, int]:
    if target_name == "controlled" and mode == "TRUSTED_REFERENCE":
        selected = budget or _validate_target_profile("controlled", mode)[1][0]
        return {
            "getfile_calls": int(selected["aggregate_getfile_cap"]),
            "getfilehashes_calls": int(selected["aggregate_getfilehashes_cap"]),
            "reserved_bytes": int(selected["aggregate_payload_reservation_cap"]),
            "identity_getmessages_calls": int(selected["aggregate_identity_getmessages_cap"]),
        }
    if case_name == "aligned":
        return dict(EFFECTIVE_LIMITS)
    if case_name == "unaligned-prepared":
        return dict(UNALIGNED_EFFECTIVE_LIMITS)
    raise RuntimeError("UNAUTHORIZED_PROOF_CASE")


def _case_budget(
    target: dict[str, Any], mode: str, case_name: str, prefix_profile: str | None = None,
) -> dict[str, Any]:
    target_name = "controlled" if target == CONTROLLED_TARGET else "common"
    expected_target, budgets = _validate_target_profile(target_name, mode, prefix_profile)
    matches = [item for item in budgets if item["case"] == case_name]
    if target != expected_target or len(matches) != 1:
        raise RuntimeError("AUTHORIZED_PROOF_CASE_MISSING")
    selected = matches[0]
    caps = _case_effective_limits(case_name, mode, target_name, selected)
    maxima = TRUSTED_REFERENCE_APPROVED_MAXIMA if mode == "TRUSTED_REFERENCE" else APPROVED_LIMITS
    if (
        selected["aggregate_getfile_cap"] != caps["getfile_calls"]
        or selected["aggregate_getfilehashes_cap"] != caps["getfilehashes_calls"]
        or selected["aggregate_payload_reservation_cap"] != caps["reserved_bytes"]
        or selected["aggregate_getfile_cap"] > maxima["getfile_calls"]
        or selected["aggregate_getfilehashes_cap"] > maxima["getfilehashes_calls"]
        or selected["aggregate_payload_reservation_cap"] > maxima["reserved_bytes"]
    ):
        raise RuntimeError("AUTHORIZED_PROFILE_CAP_MISMATCH")
    return selected


def _preparation_receipt_valid(
    receipt: Any, *, case: dict[str, Any], prefix_sha256: Any, process_id: Any,
    require_live_checkpoint: bool = True,
) -> bool:
    if not isinstance(receipt, dict):
        return False
    requests = receipt.get("wire_requests")
    if not isinstance(requests, list) or not requests or any(
        not isinstance(row, dict)
        or any(type(row.get(key)) is not int or row[key] < 0 for key in (
            "offset", "wire_bytes_received", "delivered_bytes", "preparation_discarded",
        ))
        or row["wire_bytes_received"] != row["delivered_bytes"] + row["preparation_discarded"]
        for row in requests
    ):
        return False
    prefix_bytes = int(case["prefix_bytes"])
    expected_request_count = _ceil_chunks(prefix_bytes)
    if len(requests) != expected_request_count or receipt.get("wire_request_offset") != 0:
        return False
    expected_wire_offset = 0
    for row in requests:
        if row["offset"] != expected_wire_offset or row["wire_bytes_received"] != CHUNK_BYTES:
            return False
        expected_wire_offset += row["wire_bytes_received"]
    wire_total = sum(row["wire_bytes_received"] for row in requests)
    delivered_total = sum(row["delivered_bytes"] for row in requests)
    discarded_total = sum(row["preparation_discarded"] for row in requests)
    overlap = int(case["overlap_bytes"])
    partial_text = receipt.get("partial_path")
    downloads_text = receipt.get("downloads_root")
    try:
        partial_path = Path(partial_text)
        downloads_root = Path(downloads_text)
        resolved_partial = partial_path.resolve(strict=require_live_checkpoint)
        resolved_downloads = downloads_root.resolve(strict=True)
        if not require_live_checkpoint and resolved_partial.exists():
            current_size, current_digest = _hash_file(resolved_partial)
            checkpoint_unchanged = (
                resolved_partial.is_file()
                and current_size == prefix_bytes
                and current_digest == prefix_sha256
            )
        else:
            checkpoint_unchanged = (
                resolved_partial.is_file()
                and resolved_partial.stat().st_size == prefix_bytes
            ) if require_live_checkpoint else True
        safe_paths = (
            partial_path.is_absolute() and downloads_root.is_absolute()
            and not partial_path.is_symlink() and not downloads_root.is_symlink()
            and resolved_partial == partial_path and resolved_downloads == downloads_root
            and resolved_partial.is_relative_to(resolved_downloads)
            and checkpoint_unchanged
        )
    except (OSError, TypeError, ValueError):
        safe_paths = False
    exact_boundary = True
    if overlap:
        exact_boundary = len(requests) >= 5 and requests[4] == {
            "offset": int(case["wire_offset"]),
            "wire_bytes_received": CHUNK_BYTES,
            "delivered_bytes": overlap,
            "preparation_discarded": CHUNK_BYTES - overlap,
        }
    return bool(
        type(process_id) is int and process_id > 0
        and receipt.get("process_id") == process_id
        and receipt.get("prefix_bytes") == prefix_bytes
        and receipt.get("prefix_sha256") == prefix_sha256
        and isinstance(prefix_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", prefix_sha256) is not None
        and receipt.get("sqlite_checkpoint_bytes") == prefix_bytes
        and receipt.get("sqlite_state") == "FAILED_RETRYABLE"
        and receipt.get("paths_safe") is True
        and safe_paths
        and receipt.get("stop_condition") == "CONTROLLED_INTERRUPT"
        and receipt.get("wire_bytes_received") == wire_total
        and receipt.get("bytes_delivered") == delivered_total == prefix_bytes
        and receipt.get("bytes_persisted") == prefix_bytes
        and receipt.get("preparation_discarded") == discarded_total
        and wire_total == delivered_total + discarded_total
        and receipt.get("wire_reconciliation") == {
            "wire_bytes_received": wire_total,
            "bytes_delivered": delivered_total,
            "preparation_discarded": discarded_total,
            "reconciled": True,
        }
        and exact_boundary
    )


def dry_run(
    target_name: str, mode: str, evidence_parent: Path | None = None,
    prefix_profile: str | None = None,
) -> tuple[int, Path]:
    """Build a no-network plan and run small synthetic end-to-end cases."""
    _verify_ratified_contract()
    target, budgets = _validate_target_profile(target_name, mode, prefix_profile)
    if target_name == "common":
        budgets = [item for item in budgets if item["case"] == "aligned"]
    import telegram_courses.downloads as downloads_module

    if downloads_module.V2_EFFECTIVE is not False:
        raise RuntimeError("V2_MUST_REMAIN_DISABLED_DURING_DRYRUN")
    evidence_root = _new_isolated_root(evidence_parent)
    proof_database = evidence_root / "proof.sqlite3"
    with sqlite3.connect(proof_database) as db:
        db.execute(
            "CREATE TABLE dryrun_scope (target TEXT NOT NULL, mode TEXT NOT NULL, created_at_utc TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO dryrun_scope VALUES(?,?,?)",
            (target_name, mode, datetime.now(UTC).isoformat()),
        )
        db.commit()
    if proof_database.resolve() == (REPOSITORY_ROOT / "data/telegram_courses.sqlite3").resolve():
        raise RuntimeError("OPERATIONAL_SQLITE_PATH_REUSED")
    if target_name == "controlled":
        manifest_path = _write_reference_manifest(evidence_root)
        ref_check = {"status": "PASS", "manifest": str(manifest_path)}
    else:
        ref_check = {"status": "NOT_APPLICABLE", "reason": "OPERATIONAL_ONLY has no reference"}
    report = {
        "activity": "S6_V2_PROOF_EXECUTION_UNBLOCK",
        "mode": "DRYRUN_ONLY",
        "target_name": target_name,
        "target": target,
        "v2_contract_sha256": V2_CONTRACT_SHA256,
        "v1_active": True,
        "v2_effective": False,
        "v2_activation_executed": False,
        "scope": "Fresh proof-only SQLite marker and evidence root; no app queue or historical .part input",
        "proof_sqlite": str(proof_database),
        "reference_gate": ref_check,
        "budget_cases": budgets,
        "approved_ceilings": dict(
            TRUSTED_REFERENCE_APPROVED_MAXIMA if mode == "TRUSTED_REFERENCE" else APPROVED_LIMITS
        ),
        "effective_proof_caps": _case_effective_limits(
            budgets[0]["case"], mode, target_name, budgets[0]
        ),
        "real_telegram_calls": 0,
        "original_sqlite_access": "NO",
        "historical_part_access": "NO",
        "evidence_root": str(evidence_root),
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    report_path = evidence_root / "s6-v2-dryrun-report.json"
    _atomic_write_json(report_path, report, replace=False)
    print(f"EVIDENCE_ROOT={evidence_root}")
    print(f"REPORT={report_path}")
    print("DRYRUN=PASS / PLAN-ONLY SQLITE / NO NETWORK / V2 FALSE")
    print("REFERENCE_GATE=" + ref_check["status"])
    print("REAL_TELEGRAM_CALLS=0 / ORIGINAL_SQLITE_ACCESS=NO / HISTORICAL_PART_ACCESS=NO")
    return 0, evidence_root


def _execute_token_valid() -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", os.environ.get("S6_V2_PROOF_AUTH", "")))


async def _real_gateway(
    ledger: ProofLedger, phase: int, interrupt_after: int | None, execution_id: str,
    expected_prefix_sha256: str | None = None, prefix_bytes: int = COMMON_PREFIX_ALIGNED,
    expected_overlap_bytes: bytes = b"", mode: str = "OPERATIONAL_ONLY",
    budget: dict[str, Any] | None = None,
    local_prefix_reference_evidence: dict[str, Any] | None = None,
):
    with _probe_stage("B02_B03_gateway_imports"):
        from telegram_courses.auth import AuthState
        from telegram_courses.config import load_telegram_credentials
        from telegram_courses.telethon_gateway import TelethonGateway

    _probe_mark("B04_synthetic_gateway_and_auth_stub", "start")
    gateway = TelethonGateway(load_telegram_credentials(), request_retries=0, connection_retries=0)
    _progress_event("child.gateway_constructed", phase=phase, outcome="created")
    _probe_mark("B04_synthetic_gateway_and_auth_stub", "end", outcome="gateway_constructed")
    budget = budget or proof_budget(COMMON_TARGET["expected_bytes"], prefix_bytes, "OPERATIONAL_ONLY")
    wrapped = ProofGateway(
        gateway, ledger, phase=phase,
        phase_getfile_cap=int(
            budget["phase1_getfile_cap"] if phase == 1
            else budget["phase2_getfile_cap_per_process"]
        ),
        phase_hash_cap=0 if phase == 1 else int(budget["phase2_getfilehashes_cap_per_process"]),
        phase_identity_cap=(
            int(budget["phase1_identity_getmessages_cap"] if phase == 1
                else budget["phase2_identity_getmessages_cap"])
        ),
        interrupt_after=interrupt_after,
        execution_id=execution_id,
        expected_prefix_sha256=expected_prefix_sha256,
        prefix_bytes=prefix_bytes,
        expected_overlap_bytes=expected_overlap_bytes,
        mode=mode, local_prefix_reference_evidence=local_prefix_reference_evidence,
        per_attempt_getfile_cap=int(
            budget["phase1_getfile_cap"] if phase == 1
            else budget["phase2_getfile_cap_per_attempt"]
        ) if mode == "TRUSTED_REFERENCE" else None,
        per_attempt_hash_cap=int(budget["phase2_getfilehashes_cap_per_attempt"])
        if mode == "TRUSTED_REFERENCE" and phase == 2 else None,
    )
    try:
        state = await _probe_await("gateway.restore", wrapped.restore())
    except BaseException:
        try:
            await _close_gateway_observed(wrapped)
        except BaseException:
            pass
        raise
    if state is not AuthState.AUTHENTICATED:
        try:
            await _close_gateway_observed(wrapped)
        except BaseException:
            pass
        raise RuntimeError("SESSION_UNAVAILABLE")
    return wrapped


async def _probe_await(stage: str, operation):
    """Record an async boundary only when the operation is actually entered."""
    _probe_mark(stage, "begin")
    try:
        value = await operation
    except BaseException as error:
        _probe_mark(stage, "end", outcome="exception", error=error)
        raise
    _probe_mark(stage, "end", outcome="ok")
    return value


async def _close_gateway_observed(gateway) -> None:
    await _probe_await("gateway.close", gateway.close())


async def _run_real_stage(
    *, root: Path, target_name: str, mode: str, case_name: str, phase: int,
    phase1_pid: int = 0, phase1_process_exit_confirmed: bool = False,
    execution_id: str, prefix_profile: str | None = None,
) -> dict[str, Any]:
    _probe_mark("B08_offline_stage_prep", "start")
    with _probe_stage("B02_B03_stage_imports"):
        from telegram_courses.download_repository import DownloadRepository
        from telegram_courses.downloads import SingleMediaDownloadApplication
        from telegram_courses.s5_downloads import (
            DownloadPlanner,
            DownloadQueue,
            DownloadSelection,
        )

    _probe_mark("B08_target_validation", "start")
    target, cases = _validate_target_profile(target_name, mode, prefix_profile)
    _probe_mark("B08_target_validation", "end", outcome="ok")
    case = next(item for item in cases if item["case"] == case_name)
    selected_budget = _case_budget(target, mode, case_name, prefix_profile)
    case_root = root / case_name
    case_root.mkdir(parents=True, exist_ok=True) if phase == 1 else None
    if phase == 2:
        from telegram_courses.download_repository import _process_is_alive

        if (
            (phase1_pid > 0 and _process_is_alive(phase1_pid))
            or (phase1_pid <= 0 and not phase1_process_exit_confirmed)
        ):
            raise RuntimeError("PROCESS_1_NOT_CLOSED")
    database = case_root / "proof.sqlite3"
    _probe_mark("B08_ledger_create", "start")
    ledger = ProofLedger(
        case_root / "budget.sqlite3",
        getfile_cap=int(case["aggregate_getfile_cap"]),
        hash_cap=int(case["aggregate_getfilehashes_cap"]),
        payload_cap=int(case["aggregate_payload_reservation_cap"]),
        require_existing=phase == 2,
    )
    _progress_event("child.ledger_created", phase=phase, outcome="created")
    _probe_mark("B08_ledger_create", "end", outcome="ok")
    if phase == 1:
        await _seed_proof_catalog(database, target)
        _progress_event("child.sqlite_created", phase=phase, outcome="created")
        if target_name == "controlled":
            _write_reference_manifest(case_root)
    elif phase != 2:
        raise RuntimeError("INVALID_PHASE")

    if phase == 2:
        local_reference_evidence = None
        if not database.is_file():
            raise RuntimeError("PROOF_DATABASE_MISSING")
        _progress_event("child.sqlite_created", phase=phase, outcome="validated")
        partial = next((case_root / "downloads").rglob("*.part"), None)
        if partial is None or not partial.is_file() or partial.is_symlink():
            raise RuntimeError("PHASE1_PARTIAL_MISSING")
        pending_bytes = target["expected_bytes"] - partial.stat().st_size
        if partial.stat().st_size != int(case["prefix_bytes"]):
            raise RuntimeError("PHASE1_PREFIX_SIZE_MISMATCH")
        local_reference_evidence = None
        if mode == "TRUSTED_REFERENCE":
            phase1_report = _read_json_object(case_root / "phase-1.json")
            checkpoint_state = _observe_isolated_media_state(case_root)
            if (
                checkpoint_state.get("available") is not True
                or checkpoint_state.get("sqlite_state") != "FAILED_RETRYABLE"
                or checkpoint_state.get("partial_bytes") != int(case["prefix_bytes"])
                or checkpoint_state.get("sqlite_checkpoint_bytes") != int(case["prefix_bytes"])
                or checkpoint_state.get("partial_path") != str(partial.resolve(strict=True))
                or phase1_report.get("prefix_bytes") != int(case["prefix_bytes"])
                or phase1_report.get("sqlite_checkpoint_bytes") != int(case["prefix_bytes"])
            ):
                raise RuntimeError("TRUSTED_REFERENCE_CHECKPOINT_RECONCILIATION_FAILED")
            local_reference_evidence = _verify_reference_prefix(
                case_root, partial, int(case["prefix_bytes"]),
                int(phase1_report.get("sqlite_checkpoint_bytes", -1)),
                str(phase1_report.get("prefix_sha256", "")),
            )
            _progress_event("child.local_prefix_reference_validated", phase=phase, outcome="matched",
                            counts={"verified_bytes": int(local_reference_evidence["bytes"])})
        _progress_event("child.phase2_checkpoint_validated", phase=phase, outcome="validated",
                        counts={"verified_bytes": partial.stat().st_size})
    else:
        pending_bytes = target["expected_bytes"]
    _probe_mark("B09_stage_ready", "end", outcome="ready")
    _probe_mark("B08_offline_stage_prep", "end", outcome="ok")
    disk_budget = _require_disk_budget(case_root, target, pending_bytes)

    interrupt_after = int(case["prefix_bytes"]) if phase == 1 else None
    expected_prefix_sha256 = os.environ.get("S6_V2_EXPECTED_PREFIX_SHA256") if phase == 2 else None
    if phase == 2 and not re.fullmatch(r"[0-9a-f]{64}", expected_prefix_sha256 or ""):
        raise RuntimeError("PHASE1_PREFIX_DIGEST_UNAVAILABLE")
    expected_overlap_bytes = b""
    if phase == 2 and int(case["overlap_bytes"]):
        with partial.open("rb") as source:
            source.seek(int(case["wire_offset"]))
            expected_overlap_bytes = source.read(int(case["overlap_bytes"]))
        if len(expected_overlap_bytes) != int(case["overlap_bytes"]):
            raise RuntimeError("PHASE1_OVERLAP_BYTES_UNAVAILABLE")
    gateway = await _real_gateway(
        ledger, phase, interrupt_after, execution_id,
        expected_prefix_sha256=expected_prefix_sha256,
        prefix_bytes=int(case["prefix_bytes"]),
        expected_overlap_bytes=expected_overlap_bytes,
        mode=mode, budget=selected_budget,
        local_prefix_reference_evidence=local_reference_evidence if phase == 2 else None,
    )
    repository = DownloadRepository(database)
    app = SingleMediaDownloadApplication(repository, gateway, case_root / "downloads")
    planner = DownloadPlanner(database, case_root / "downloads")
    try:
        plan = await _probe_await(
            "planner", planner.build(DownloadSelection(target["channel_id"]))
        )
    except BaseException:
        try:
            await _close_gateway_observed(gateway)
        except BaseException:
            pass
        raise
    if len(plan.items) != 1 or plan.items[0].identity != (
        target["channel_id"], target["message_id"], target["media_ordinal"]
    ):
        try:
            await _close_gateway_observed(gateway)
        except BaseException:
            pass
        raise RuntimeError("ISOLATED_PLAN_SCOPE_MISMATCH")
    remaining_budget = int(case["aggregate_payload_reservation_cap"]) - ledger.snapshot()["payload_reserved"]
    try:
        queue = DownloadQueue(
            repository, app, workers=MAX_WORKERS,
            attempts_per_media=(
                PHASE1_TRANSFER_ATTEMPT_CAP if phase == 1 else PHASE2_TRANSFER_ATTEMPT_CAP
            ),
            max_media_items=1,
            max_transfer_bytes=max(target["expected_bytes"], remaining_budget),
            integrity_mode=mode,
            reference_manifest_path=(case_root / "reference-manifest.v1.json") if target_name == "controlled" else None,
        )
    except BaseException:
        try:
            await _close_gateway_observed(gateway)
        except BaseException:
            pass
        raise
    dedup_result = None
    ledger_before_dedup = None
    try:
        with _scoped_v2_switch(mode, target, authorized=True):
            result = await _probe_await("queue", queue.run(plan))
            if phase == 2:
                completed_plan = await _probe_await(
                    "planner", planner.build(DownloadSelection(target["channel_id"]))
                )
                ledger_before_dedup = ledger.snapshot()
                dedup_result = await _probe_await("queue", queue.run(completed_plan))
                if ledger.snapshot() != ledger_before_dedup:
                    raise RuntimeError("DEDUPLICATION_ISSUED_REMOTE_REQUEST")
        candidate = await repository.select_candidate(
            target["channel_id"], target["message_id"], target["media_ordinal"]
        )
        if candidate is None:
            raise RuntimeError("ISOLATED_CANDIDATE_MISSING")
        record = await repository.get_record(candidate.media_item_id)
        if phase == 1:
            partial = next((case_root / "downloads").rglob("*.part"), None)
            if (
                partial is None or record is None or partial.stat().st_size != case["prefix_bytes"]
                or record.downloaded_bytes != case["prefix_bytes"]
                or record.state != "FAILED_RETRYABLE"
                or record.failure_category != "CONTROLLED_INTERRUPT"
                or not any(
                    outcome[1:] == ("FAILED", "CONTROLLED_INTERRUPT")
                    for outcome in result.outcomes
                )
            ):
                raise RuntimeError("PHASE1_PREFIX_CHECKPOINT_MISMATCH")
            prefix_size, prefix_sha256 = _hash_file(partial)
            if prefix_size != int(case["prefix_bytes"]):
                raise RuntimeError("PHASE1_PREFIX_SIZE_MISMATCH")
            _progress_event("child.phase1_checkpoint", phase=phase, outcome="validated",
                            counts={"verified_bytes": prefix_size})
            _progress_event("child.planned_interruption", phase=phase, outcome="interrupted",
                            counts={"verified_bytes": prefix_size})
            return {
                "phase": phase, "process_id": os.getpid(), "target_name": target_name,
                "mode": mode, "case": case_name, "prefix_profile": selected_budget.get("prefix_profile"),
                "queue_result": result.outcomes,
                "transfer_attempts": result.attempts,
                "identity": {
                    "channel_id": target["channel_id"], "message_id": target["message_id"],
                    "media_ordinal": target["media_ordinal"], "media_id": target["media_id"],
                    "media_kind": target["media_kind"], "expected_bytes": target["expected_bytes"],
                },
                "remote_identity_preflight": "PASS" if gateway.identity_preflight_passed else "FAIL",
                "identity_calls": gateway.identity_calls,
                "prefix_bytes": prefix_size, "prefix_sha256": prefix_sha256,
                "sqlite_state": record.state,
                "sqlite_checkpoint_bytes": record.downloaded_bytes,
                "preparation_receipt": {
                    **gateway.preparation_receipt,
                    "prefix_sha256": prefix_sha256,
                    "partial_path": str(partial.resolve(strict=True)),
                    "downloads_root": str((case_root / "downloads").resolve(strict=True)),
                    "paths_safe": (
                        not partial.is_symlink()
                        and partial.resolve(strict=True).is_relative_to(
                            (case_root / "downloads").resolve(strict=True)
                        )
                    ),
                    "sqlite_checkpoint_bytes": record.downloaded_bytes,
                    "sqlite_state": record.state,
                    "stop_condition": "CONTROLLED_INTERRUPT",
                    "wire_reconciliation": {
                        "wire_bytes_received": gateway.preparation_receipt["wire_bytes_received"],
                        "bytes_delivered": gateway.preparation_receipt["bytes_delivered"],
                        "preparation_discarded": gateway.preparation_receipt["preparation_discarded"],
                        "reconciled": gateway.preparation_receipt["wire_bytes_received"]
                        == gateway.preparation_receipt["bytes_delivered"]
                        + gateway.preparation_receipt["preparation_discarded"],
                    },
                },
                "ledger": ledger.snapshot(), "disk_budget": disk_budget,
                "requests_used": {
                    "GetFile": gateway.getfile_calls,
                    "GetFileHashes": gateway.getfilehashes_calls,
                    "identity_GetMessages": gateway.identity_calls,
                    "GetMe": gateway.getme_calls,
                    "restore_calls": gateway.restore_calls,
                    "known_remote_calls": None,
                    "counted_remote_calls_lower_bound": gateway.getfile_calls
                    + 2 * gateway.getfilehashes_calls + gateway.identity_calls + (gateway.getme_calls or 0),
                    "known_remote_calls_reason": "Lower bound omits per-stream metadata refetch calls",
                    "telethon_connect_rpc_count": None,
                    "total_api_requests": None,
                },
                "v2_restored_false_after_call": __import__("telegram_courses.downloads", fromlist=["V2_EFFECTIVE"]).V2_EFFECTIVE is False,
            }
        record = await repository.get_record(candidate.media_item_id)
        final = _resolve_completed_final_path(
            case_root,
            state=record.state if record is not None else "",
            final_path=record.final_path if record is not None else None,
        )
        size, digest = _hash_file(final)
        evidence = await repository.get_v2_evidence(candidate.media_item_id)
        if size != target["expected_bytes"] or evidence is None or evidence["final_sha256"] != digest:
            raise RuntimeError("VERSIONED_EVIDENCE_OR_FINAL_FILE_MISMATCH")
        if dedup_result is None:
            raise RuntimeError("V2_DEDUPLICATION_NOT_CONFIRMED")
        expected_dedup_status = (
            "ALREADY_COMPLETED_V2" if mode == "OPERATIONAL_ONLY" else "BLOCKED"
        )
        if not any(outcome[1] == expected_dedup_status for outcome in dedup_result.outcomes):
            raise RuntimeError("V2_DEDUPLICATION_POLICY_MISMATCH")
        if mode == "TRUSTED_REFERENCE" and not any(
            outcome[2] == "V2_COMPLETION_REQUIRES_REFERENCE_REVALIDATION"
            for outcome in dedup_result.outcomes
        ):
            raise RuntimeError("TRUSTED_REFERENCE_DEDUPLICATION_NOT_FAIL_CLOSED")
        trusted_reference_result = None
        if mode == "TRUSTED_REFERENCE":
            manifest, reference = _verify_reference_manifest(case_root)
            reference_identity = _file_identity(reference)
            _guard_native_paths((reference, final))
            if reference == final or os.path.samefile(reference, final) or _file_identity(final) == reference_identity:
                raise RuntimeError("OUTPUT_ALIASES_TRUSTED_REFERENCE")
            if _path_is_reparse_or_linked(final):
                raise RuntimeError("FINAL_OUTPUT_PATH_UNSAFE")
            final_identity = _file_identity(final)
            size, digest = _hash_file(final)
            reference_size, reference_digest = _hash_file(reference)
            if _file_identity(reference) != reference_identity:
                raise RuntimeError("TRUSTED_REFERENCE_CHANGED_DURING_FINAL_COMPARE")
            bytewise_match = False
            if reference_size == size:
                with final.open("rb") as actual, reference.open("rb") as original:
                    while True:
                        actual_block = actual.read(1024 * 1024)
                        reference_block = original.read(1024 * 1024)
                        if actual_block != reference_block:
                            break
                        if not actual_block:
                            break
                bytewise_match = not actual_block and not reference_block
            if _file_identity(reference) != reference_identity or _file_identity(final) != final_identity:
                raise RuntimeError("TRUSTED_REFERENCE_CHANGED_DURING_FINAL_COMPARE")
            if reference_size != size or reference_digest != digest or not bytewise_match:
                trusted_reference_result = {
                    "status": "TRUSTED_REFERENCE_MISMATCH", "reference_bytes": reference_size,
                    "reference_sha256": reference_digest, "final_bytes": size, "final_sha256": digest,
                    "bytewise_match": bytewise_match,
                    "comparison_method": "BYTEWISE_AND_SHA256",
                }
            else:
                trusted_reference_result = {
                    "status": "TRUSTED_REFERENCE_MATCH", "reference_bytes": reference_size,
                    "reference_sha256": reference_digest, "final_bytes": size, "final_sha256": digest,
                    "bytewise_match": True,
                    "comparison_method": "BYTEWISE_AND_SHA256",
                }
        return {
            "phase": phase, "process_id": os.getpid(), "target_name": target_name,
            "mode": mode, "case": case_name, "prefix_profile": selected_budget.get("prefix_profile"),
            "queue_result": result.outcomes,
            "transfer_attempts": result.attempts,
            "identity": {
                "channel_id": target["channel_id"], "message_id": target["message_id"],
                "media_ordinal": target["media_ordinal"], "media_id": target["media_id"],
                "media_kind": target["media_kind"], "expected_bytes": target["expected_bytes"],
            },
            "remote_identity_preflight": "PASS" if gateway.identity_preflight_passed else "FAIL",
            "identity_calls": gateway.identity_calls,
            "sqlite_state": record.state, "final_bytes": size, "final_sha256": digest,
            "final_path": str(final.resolve(strict=True)),
            "evidence": dict(evidence), "ledger": ledger.snapshot(),
            "disk_budget": disk_budget,
            "requests_used": {
                "GetFile": gateway.getfile_calls,
                "GetFileHashes": gateway.getfilehashes_calls,
                "identity_GetMessages": gateway.identity_calls,
                "GetMe": gateway.getme_calls,
                "restore_calls": gateway.restore_calls,
                "known_remote_calls": None,
                "counted_remote_calls_lower_bound": gateway.getfile_calls
                + 2 * gateway.getfilehashes_calls + gateway.identity_calls + (gateway.getme_calls or 0),
                "known_remote_calls_reason": "Lower bound omits per-stream metadata refetch calls",
                "telethon_connect_rpc_count": None,
                "total_api_requests": None,
            },
            "dedup_outcomes": dedup_result.outcomes,
            "ledger_before_dedup": ledger_before_dedup,
            "v2_restored_false_after_call": __import__("telegram_courses.downloads", fromlist=["V2_EFFECTIVE"]).V2_EFFECTIVE is False,
            "phase1_pid": phase1_pid,
            "full_prefix_reread_bytes": gateway.verified_prefix_bytes,
            "full_prefix_reread_sha256": gateway.verified_prefix_sha256,
            "prefix_sha256_expected": gateway.expected_prefix_sha256,
            "prefix_hash_reconciled": gateway.prefix_reread_verified,
            "local_prefix_reference_evidence": local_reference_evidence if phase == 2 else None,
            "trusted_reference_result": trusted_reference_result,
            "overlap_verification": (
                "NOT_APPLICABLE_ALIGNED" if gateway.overlap_bytes == 0
                else gateway.overlap_observation
            ),
        }
    except BaseException:
        try:
            await _close_gateway_observed(gateway)
        except BaseException:
            pass
        raise
    else:
        await _close_gateway_observed(gateway)


def _child_main(args) -> int:
    _start_operational_stack_capture()
    _probe_start_faulthandler()
    _probe_mark("B07_harness_bootstrap", "start")
    if not _execute_token_valid():
        _probe_mark("B07_harness_bootstrap", "end", outcome="confirmation_blocked")
        print("STOP=NATIVE_CONFIRMATION_TOKEN_REQUIRED")
        _probe_mark("B10_child_termination", "start", outcome="confirmation_blocked")
        _probe_stop_faulthandler()
        return 5
    with _probe_stage("B07_verify_contract"):
        _verify_ratified_contract()
    with _probe_stage("B07_validate_child_authorization"):
        _validate_child_authorization(args)
    _probe_mark("B07_harness_bootstrap", "end", outcome="ok")
    started_at = datetime.now(UTC).isoformat()
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    try:
        _probe_mark("B05_asyncio_run", "start")
        async def run_stage_probe():
            _probe_mark("B06_loop_setup", "end", outcome="loop_created")
            _probe_mark("B06_loop_and_first_coroutine", "start")
            try:
                _progress_event("child.event_loop_initialized", phase=args.phase,
                                outcome="ready", execution_id=args.execution_id)
                _progress_event("child.ready", phase=args.phase,
                                outcome="ready", execution_id=args.execution_id)
                value = await _run_real_stage(
                    root=Path(args.evidence_root), target_name=args.target, mode=args.mode,
                    case_name=args.case, phase=args.phase, phase1_pid=args.phase1_pid,
                    phase1_process_exit_confirmed=args.recovered_phase1,
                    execution_id=args.execution_id, prefix_profile=getattr(args, "prefix_profile", None),
                )
            except BaseException as caught:
                _probe_mark("B06_loop_and_first_coroutine", "end", outcome="exception", error=caught)
                raise
            _probe_mark("B06_loop_and_first_coroutine", "end", outcome="ok")
            return value

        try:
            _probe_mark("B06_loop_setup", "start")
            result = asyncio.run(run_stage_probe())
        except BaseException as caught:
            _probe_mark("B05_asyncio_run", "end", outcome="exception", error=caught)
            raise
        _probe_mark("B05_asyncio_run", "end", outcome="ok")
        exit_code = 0
        stop_condition = "CONTROLLED_INTERRUPT" if args.phase == 1 else None
        status = "PROCESS_INTERRUPTED" if args.phase == 1 else "PROCESS_COMPLETED"
        _progress_event("child.finalized", phase=args.phase, outcome="completed",
                        execution_id=args.execution_id)
    except BaseException as caught:
        error = caught
        exit_code = 130 if isinstance(caught, KeyboardInterrupt) else 5
        stop_condition = _safe_stop_condition(caught)
        status = "PROCESS_INTERRUPTED" if exit_code == 130 else "PROCESS_FAILED"

    ended_at = datetime.now(UTC).isoformat()
    report = {
        "schema_version": 1,
        "phase_id": f"{args.execution_id}:{args.phase}",
        "execution_id": args.execution_id,
        "phase": args.phase,
        "target_name": args.target,
        "mode": args.mode,
        "case": args.case,
        "prefix_profile": getattr(args, "prefix_profile", None),
        "process_id": os.getpid(),
        "process_started_at_utc": started_at,
        "process_ended_at_utc": ended_at,
        "child_exit_code": exit_code,
        "status": status,
        "stop_condition": stop_condition,
        "child_error_type": _safe_exception_class(error),
        "child_error": _safe_exception_class(error),
        "child_error_stage": _safe_exception_stage(error),
        "child_result": result,
    }
    try:
        _atomic_write_json(Path(args.phase_report), report, replace=False)
    except BaseException as write_error:
        print(f"STOP=PHASE_REPORT_WRITE_FAILED:{_safe_exception_class(write_error)}")
        _probe_mark("B10_child_termination", "start", outcome="report_write_failed", error=write_error)
        _probe_stop_faulthandler()
        return 5
    _progress_event("child.phase_report_written", phase=args.phase,
                    outcome="completed" if exit_code == 0 else "failed",
                    execution_id=args.execution_id)
    if error is not None:
        print(f"STOP={stop_condition}")
        _probe_mark("B10_child_termination", "start", outcome="failed", error=error)
        _probe_stop_faulthandler()
        _stop_operational_stack_capture()
        return exit_code
    print(f"PHASE={args.phase} PROCESS_ID={report['process_id']} EXECUTION_ID={args.execution_id}")
    _probe_mark("B10_child_termination", "start", outcome="ok")
    _probe_stop_faulthandler()
    _stop_operational_stack_capture()
    return 0


def _recover_phase1_checkpoint(
    root_path: Path, target: dict[str, Any], mode: str, *, case_name: str = "aligned",
) -> dict[str, Any]:
    """Accept only a phase-1 receipt with observed process identity and exit."""
    if root_path.is_symlink():
        raise RuntimeError("RECOVERY_ROOT_SYMLINK")
    root = root_path.resolve(strict=True)
    expected_parent = (REPOSITORY_ROOT / "docs/reports").resolve(strict=True)
    authorization_path = root / "authorization.json"
    if (
        root.parent != expected_parent or not root.name.startswith("s6-v2-real-proof-")
        or root.is_symlink() or not authorization_path.is_file() or authorization_path.is_symlink()
    ):
        raise RuntimeError("RECOVERY_ROOT_SCOPE_INVALID")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    recovery_profile = _case_budget(target, mode, case_name)
    expected_case_profile = {
        "prefix_bytes": recovery_profile["prefix_bytes"],
        "prefix_profile": recovery_profile.get("prefix_profile"),
        "wire_offset": recovery_profile["wire_offset"],
        "transfer_offset": recovery_profile["transfer_offset"],
        "overlap_bytes": recovery_profile["overlap_bytes"],
        "effective_caps": _case_effective_limits(
            case_name, mode, "controlled" if target == CONTROLLED_TARGET else "common", recovery_profile,
        ),
        "approved_maxima": dict(
            TRUSTED_REFERENCE_APPROVED_MAXIMA if mode == "TRUSTED_REFERENCE" else APPROVED_LIMITS
        ),
    }
    if (
        authorization.get("evidence_root") != str(root)
        or authorization.get("target") != ("controlled" if target == CONTROLLED_TARGET else "common")
        or authorization.get("mode") != mode
        or authorization.get("contract_sha256") != V2_CONTRACT_SHA256
        or authorization.get("allowed_cases") != [case_name]
        or authorization.get("case_profile") != expected_case_profile
        or authorization.get("recovered_phase1") is True
    ):
        raise RuntimeError("RECOVERY_INITIAL_ATTEMPT_SCOPE_MISMATCH")

    case_budget = recovery_profile
    case_root = root / case_name
    if case_root.is_symlink() or (case_root / "downloads").is_symlink():
        raise RuntimeError("RECOVERY_CASE_PATH_SYMLINK")
    phase1_report_path = case_root / "phase-1.json"
    phase2_report_path = case_root / "phase-2.json"
    if phase2_report_path.exists() or phase2_report_path.is_symlink():
        raise RuntimeError("RECOVERY_PHASE2_ALREADY_STARTED")
    try:
        phase1_report = _read_json_object(phase1_report_path)
    except BaseException as error:
        raise RuntimeError("RECOVERY_PHASE1_RECEIPT_MISSING_OR_INVALID") from error
    if (
        phase1_report.get("phase") != 1
        or phase1_report.get("target_name") != "common"
        or phase1_report.get("mode") != "OPERATIONAL_ONLY"
        or phase1_report.get("case") != case_name
        or phase1_report.get("status") != "PROCESS_INTERRUPTED"
        or phase1_report.get("stop_condition") != "CONTROLLED_INTERRUPT"
        or phase1_report.get("process_id") is None
        or not isinstance(phase1_report.get("process_id"), int)
        or phase1_report.get("process_id") <= 0
        or phase1_report.get("exit_code") != 0
        or phase1_report.get("child_exit_code") != 0
        or phase1_report.get("process_exit_confirmed") is not True
        or phase1_report.get("child_report_valid") is not True
        or not isinstance(phase1_report.get("execution_id"), str)
        or phase1_report.get("checkpoint_confirmed") is not True
        or type(phase1_report.get("transfer_attempts")) is not int
        or phase1_report.get("transfer_attempts") != PHASE1_TRANSFER_ATTEMPT_CAP
    ):
        raise RuntimeError("RECOVERY_PHASE1_RECEIPT_NOT_RESUMABLE")
    database = case_root / "proof.sqlite3"
    ledger_path = case_root / "budget.sqlite3"
    if any(not path.is_file() or path.is_symlink() for path in (database, ledger_path)):
        raise RuntimeError("RECOVERY_PROOF_STATE_MISSING")

    budget = case_budget
    ledger = ProofLedger(
        ledger_path, getfile_cap=int(budget["aggregate_getfile_cap"]),
        hash_cap=int(budget["aggregate_getfilehashes_cap"]),
        payload_cap=int(budget["aggregate_payload_reservation_cap"]), require_existing=True,
    ).snapshot()
    expected_prefix = int(budget["prefix_bytes"])
    expected_phase1_getfile = int(budget["phase1_getfile_cap"])
    preparation = phase1_report.get("preparation_receipt")
    if (
        not _preparation_receipt_valid(
            preparation, case=budget, prefix_sha256=phase1_report.get("prefix_sha256"),
            process_id=phase1_report.get("process_id"),
        )
        or ledger != {
        "getfile_calls": expected_phase1_getfile,
        "getfilehashes_calls": 0,
        "payload_reserved": expected_phase1_getfile * CHUNK_BYTES,
        "payload_received": preparation.get("wire_bytes_received"),
        "uncertain_bytes": 0,
        }
    ):
        raise RuntimeError("RECOVERY_PHASE1_BUDGET_STATE_MISMATCH")

    # This one synchronous connection is read-only and confined to the fresh proof database.
    db = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        download = db.execute(
            "SELECT media_item_id,state,partial_path,expected_bytes,downloaded_bytes,failure_category "
            "FROM downloads"
        ).fetchall()
        attempts = db.execute(
            "SELECT channel_id,telegram_message_id,media_ordinal,telegram_media_id,expected_bytes,"
            "selected_mode,status,remote_hash_class,details_json,requests,bytes_received "
            "FROM s6_v2_attempts"
        ).fetchall()
    finally:
        db.close()
    if len(download) != 1 or len(attempts) != 1:
        raise RuntimeError("RECOVERY_PROOF_RECORD_COUNT_MISMATCH")
    media_item_id, state, partial_text, expected_bytes, downloaded_bytes, failure_category = download[0]
    attempt = attempts[0]
    partial_source = Path(partial_text)
    if partial_source.is_symlink():
        raise RuntimeError("RECOVERY_PARTIAL_SYMLINK")
    partial = partial_source.resolve(strict=True)
    downloads_root = (case_root / "downloads").resolve(strict=True)
    if (
        not partial.is_relative_to(downloads_root) or partial.is_symlink()
        or not partial.is_file() or partial.stat().st_size != expected_prefix
        or state != "FAILED_RETRYABLE" or expected_bytes != target["expected_bytes"]
        or downloaded_bytes != expected_prefix or failure_category != "CONTROLLED_INTERRUPT"
        or attempt[:6] != (
            target["channel_id"], target["message_id"], target["media_ordinal"],
            target["media_id"], target["expected_bytes"], mode,
        )
        or attempt[9:] != (expected_phase1_getfile + 1, expected_prefix)
        or phase1_report.get("prefix_bytes") != expected_prefix
        or phase1_report.get("sqlite_checkpoint_bytes") != expected_prefix
    ):
        raise RuntimeError("RECOVERY_PREFIX_OR_ATTEMPT_MISMATCH")
    size, prefix_sha256 = _hash_file(partial)
    if size != expected_prefix:
        raise RuntimeError("RECOVERY_PREFIX_SIZE_MISMATCH")
    from telegram_courses.s5_downloads import GIB

    pending = target["expected_bytes"] - expected_prefix
    required = pending + max(GIB, int(pending * 0.10))
    free = shutil.disk_usage(case_root).free
    if free < required:
        raise RuntimeError("INSUFFICIENT_DISK_SPACE_BEFORE_RESUME")
    if phase1_report.get("prefix_sha256") != prefix_sha256:
        raise RuntimeError("RECOVERY_PREFIX_HASH_MISMATCH")
    return {
        "root": root, "authorization": authorization, "phase1": phase1_report,
        "ledger": ledger,
        "disk_budget": {"free_bytes": free, "pending_bytes": pending, "required_free_bytes": required},
    }


def _child_report_envelope_valid(
    report: Any, *, execution_id: str, phase: int, target_name: str,
    mode: str, case_name: str, prefix_profile: str | None,
    observed_process_id: int | None = None,
) -> bool:
    """Validate only the child's bounded envelope, without opening any artifact."""
    if type(report) is not dict:
        return False
    child_status = report.get("status")
    child_result = report.get("child_result")
    child_exit = report.get("child_exit_code")
    if type(child_exit) is not int:
        return False
    result_shape_valid = (
        type(child_result) is dict
        or (child_result is None and child_status == "PROCESS_FAILED" and child_exit != 0)
    )
    failure_diagnostics_valid = (
        child_status != "PROCESS_FAILED"
        or (
            type(report.get("stop_condition")) is str
            and report.get("stop_condition") in _SAFE_DOWNLOAD_ERROR_CODES | _SAFE_EXCEPTION_LABELS
            and report.get("child_error_stage") in _SAFE_DOWNLOAD_ERROR_STAGES | {None}
        )
    )
    status_exit_valid = (
        (child_status == "PROCESS_COMPLETED" and child_exit == 0 and type(child_result) is dict)
        or (child_status == "PROCESS_FAILED" and child_exit != 0)
        or (child_status == "PROCESS_INTERRUPTED" and (
            (phase == 1 and child_exit == 0
             and report.get("stop_condition") == "CONTROLLED_INTERRUPT")
            or child_exit == 130
        ))
        or (child_status == "EVIDENCE_INCOMPLETE" and child_exit != 0)
    )
    return bool(
        type(report.get("schema_version")) is int and report.get("schema_version") == 1
        and report.get("phase_id") == f"{execution_id}:{phase}"
        and report.get("execution_id") == execution_id
        and type(report.get("phase")) is int and report.get("phase") == phase
        and type(report.get("process_id")) is int and report.get("process_id") > 0
        and report.get("target_name") == target_name
        and report.get("mode") == mode
        and report.get("case") == case_name
        and report.get("prefix_profile") == prefix_profile
        and result_shape_valid and status_exit_valid and failure_diagnostics_valid
        and child_status in {
            "PROCESS_COMPLETED", "PROCESS_FAILED", "PROCESS_INTERRUPTED", "EVIDENCE_INCOMPLETE",
        }
        and type(report.get("process_started_at_utc")) is str
        and type(report.get("process_ended_at_utc")) is str
        and (observed_process_id is None or report.get("process_id") == observed_process_id)
    )


def _run_phase_child(
    command: list[str], *, evidence_root: Path, case_name: str, phase: int,
    target: dict[str, Any], mode: str, execution_id: str,
    child_report_path: Path, supervisor_report_path: Path, ledger_path: Path,
    timeout_seconds: int | None = None,
    phase1_ledger_after: dict[str, int] | None = None,
    aggregate_started_monotonic: float | None = None,
    expected_prefix_sha256: str | None = None,
    prefix_profile: str | None = None,
) -> dict[str, Any]:
    """Run one child, then persist the supervisor's observed process receipt."""
    prefix_bytes = int(_case_budget(target, mode, case_name, prefix_profile)["prefix_bytes"])
    configured_process_timeout, aggregate_deadline_seconds = _deadline_policy(mode)
    timeout_seconds = configured_process_timeout if timeout_seconds is None else timeout_seconds
    requested_timeout_seconds = timeout_seconds
    if _probe_enabled():
        try:
            timeout_seconds = min(
                timeout_seconds,
                max(1, min(int(os.environ.get("S6_V2_TEST_PROBE_TIMEOUT_SECONDS", "10")), 60)),
            )
        except ValueError:
            timeout_seconds = min(timeout_seconds, 10)
    effective_timeout_seconds = float(min(timeout_seconds, aggregate_deadline_seconds))
    started = datetime.now(UTC).isoformat()
    case_root = evidence_root / case_name
    if phase == 1:
        if not _phase1_root_is_new_and_empty(case_root, ledger_path):
            raise RuntimeError("PHASE1_ROOT_NOT_NEW_AND_EMPTY")
        before: dict[str, int] | None = dict.fromkeys(ProofLedger._COLUMNS, 0)
        before_is_new_root_baseline = True
        attempts_before: list[dict[str, Any]] | None = []
    else:
        before = _read_budget_snapshot(ledger_path)
        before_is_new_root_baseline = False
        try:
            attempts_before = _read_attempt_rows(case_root / "proof.sqlite3")
        except (sqlite3.Error, OSError, RuntimeError):
            attempts_before = None
    process: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    timed_out = False
    supervisor_error: str | None = None
    timeout_reason = None
    remaining_aggregate: float | None = None
    seen_stages: set[str] = set()
    observed_stages: set[str] = set()
    max_counts: dict[str, int] = {}
    observed_event_count = 0
    latest_stage: str | None = None
    last_semantic: float | None = None
    progress_heartbeat: dict[str, Any] = {
        "stream_confirmed_bytes": 0, "persisted_bytes": 0,
        "throughput_bytes_per_second": 0, "stage_count": 0, "event_count": 0,
        "current_stage": None,
    }
    progress_path = evidence_root / "execution-progress.jsonl"
    stack_path = evidence_root / f"stack-{execution_id}.log"
    progress_offset, progress_log_identity = _prepare_progress_log(
        path=progress_path, evidence_root=evidence_root, phase=phase, case_root=case_root,
    )
    progress_partial = b""
    try:
        child_env = dict(os.environ)
        child_env["S6_V2_PROOF_AUTH"] = os.environ["S6_V2_PROOF_AUTH"]
        child_env["S6_V2_PROGRESS_JSONL"] = str(progress_path)
        child_env["S6_V2_PROGRESS_ROOT"] = str(evidence_root.resolve())
        child_env["S6_V2_PROGRESS_EXECUTION_ID"] = execution_id
        child_env["S6_V2_PROGRESS_PHASE"] = str(phase)
        child_env["S6_V2_STACK_PATH"] = str(stack_path)
        cancel_marker = case_root / "supervisor.cancel"
        child_env["S6_V2_CANCEL_MARKER"] = str(cancel_marker)
        if expected_prefix_sha256 is not None:
            child_env["S6_V2_EXPECTED_PREFIX_SHA256"] = expected_prefix_sha256
        if _probe_enabled():
            child_env["S6_V2_TEST_PROBE_EXECUTION_ID"] = execution_id
        import_paths = [str(REPOSITORY_ROOT / "src"), str(Path(sys.prefix) / "Lib" / "site-packages")]
        if child_env.get("PYTHONPATH"):
            import_paths.append(child_env["PYTHONPATH"])
        child_env["PYTHONPATH"] = os.pathsep.join(import_paths)
        _probe_mark("B00_parent_spawn", "start", execution_id=execution_id)
        _progress_event("supervisor.initialized", phase=phase, execution_id=execution_id,
                        outcome="started", progress_path=progress_path, progress_root=evidence_root)
        process = subprocess.Popen(
            command, cwd=REPOSITORY_ROOT, env=child_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace",
        )
        spawn_mono = time.monotonic()
        if aggregate_started_monotonic is None:
            aggregate_started_monotonic = spawn_mono
        _probe_mark("B00_parent_spawn", "end", outcome="spawned", execution_id=execution_id)
        _progress_event("supervisor.child_spawned", phase=phase, execution_id=execution_id,
                        outcome="created", progress_path=progress_path, progress_root=evidence_root)
        _atomic_write_json(supervisor_report_path, {
            "schema_version": 1, "phase_id": f"{execution_id}:{phase}",
            "execution_id": execution_id, "phase": phase,
            "target_name": "controlled" if target == CONTROLLED_TARGET else "common",
            "mode": mode, "case": case_name, "process_id": None,
            "supervisor_spawn_pid": process.pid,
            "process_started_at_utc": started, "process_ended_at_utc": None,
            "exit_code": None, "process_exit_confirmed": False,
            "status": "EVIDENCE_INCOMPLETE", "stop_condition": "PROCESS_RUNNING",
            "child_report_path": str(child_report_path), "child_report_valid": False,
        }, replace=False)
        remaining_aggregate = max(
            0.0,
            aggregate_deadline_seconds - (spawn_mono - aggregate_started_monotonic),
        )
        effective_timeout_seconds = float(min(
            effective_timeout_seconds, max(0.0, remaining_aggregate - PROOF_CANCEL_GRACE_SECONDS),
        ))
        last_semantic = spawn_mono
        last_status = spawn_mono
        last_heartbeat_bytes = 0
        last_heartbeat_at = spawn_mono
        observed_event_count = 0
        latest_stage = "child_spawned"
        observed_stages = set()
        seen_stages = set()
        max_counts = {}
        last_sequence_by_pid: dict[int, int] = {}
        ready_seen = False
        timeout_reason = None
        while process.poll() is None:
            now = time.monotonic()
            if progress_path.exists():
                try:
                    with progress_path.open("rb") as stream:
                        stream.seek(progress_offset)
                        new_data = stream.read()
                        progress_offset = stream.tell()
                    pieces, progress_partial = _split_progress_buffer(progress_partial, new_data)
                    for raw_line in pieces:
                        if not raw_line:
                            continue
                        event = json.loads(raw_line.decode("utf-8"))
                        if (event.get("execution_id") != execution_id
                                or event.get("phase") != phase
                                or type(event.get("process_id")) is not int
                                or type(event.get("sequence")) is not int
                                or type(event.get("monotonic_ns")) is not int
                                or event.get("stage") not in _PROGRESS_STAGES
                                or event.get("outcome") not in _PROGRESS_OUTCOMES
                                or not isinstance(event.get("counts"), dict)
                                or set(event) != {"execution_id", "phase", "process_id", "stage", "sequence", "monotonic_ns", "outcome", "counts"}):
                            continue
                        if event["stage"].startswith("child.") and event["process_id"] != process.pid:
                            continue
                        prior_sequence = last_sequence_by_pid.get(event["process_id"], 0)
                        if event["sequence"] <= prior_sequence:
                            continue
                        last_sequence_by_pid[event["process_id"]] = event["sequence"]
                        observed_event_count += 1
                        latest_stage = event["stage"]
                        observed_stages.add(event["stage"])
                        if event["stage"] == "child.ready":
                            ready_seen = True
                        if _progress_is_semantic(event, seen_stages, max_counts):
                            last_semantic = now
                except (OSError, UnicodeError, json.JSONDecodeError):
                    # Malformed progress is ignored for liveness; required evidence fails closed later.
                    pass
            timeout_reason = _supervisor_timeout_reason(
                now=now, spawned=spawn_mono, last_semantic=last_semantic,
                ready=ready_seen, aggregate_started=aggregate_started_monotonic,
                phase_timeout=effective_timeout_seconds,
                aggregate_deadline=max(0.0, aggregate_deadline_seconds - PROOF_CANCEL_GRACE_SECONDS),
            )
            if timeout_reason:
                stage = {
                    "AGGREGATE_DEADLINE": "supervisor.aggregate_timeout",
                    "CHILD_READINESS_TIMEOUT": "supervisor.child_ready_timeout",
                    "SEMANTIC_INACTIVITY_TIMEOUT": "supervisor.semantic_idle_timeout",
                    "PHASE_PROCESS_TIMEOUT": "supervisor.semantic_idle_timeout",
                }[timeout_reason]
                _progress_event(stage, phase=phase, execution_id=execution_id, outcome="timeout",
                                progress_path=progress_path, progress_root=evidence_root)
                timed_out = True
                try:
                    _atomic_write_json(cancel_marker, {
                        "execution_id": execution_id, "phase": phase,
                        "reason": timeout_reason, "requested_at_utc": datetime.now(UTC).isoformat(),
                    }, replace=False)
                except OSError:
                    supervisor_error = "COOPERATIVE_CANCEL_MARKER_WRITE_FAILED"
                grace_left = max(0.0, aggregate_deadline_seconds - (time.monotonic() - aggregate_started_monotonic))
                grace = min(PROOF_CANCEL_GRACE_SECONDS, grace_left)
                try:
                    stdout, stderr = process.communicate(timeout=grace)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except OSError:
                        pass
                    final_wait = max(
                        0.0,
                        aggregate_started_monotonic + aggregate_deadline_seconds - time.monotonic(),
                    )
                    try:
                        stdout, stderr = process.communicate(timeout=final_wait)
                    except subprocess.TimeoutExpired:
                        supervisor_error = "PROCESS_EXIT_UNCONFIRMED_AFTER_TIMEOUT"
                break
            if now - last_status >= 15:
                current_ledger = _read_budget_snapshot(ledger_path)
                if current_ledger is not None:
                    max_counts["received_bytes"] = current_ledger["payload_received"]
                received = max_counts.get("stream_confirmed_bytes", 0)
                persisted = max_counts.get("persisted_bytes", 0)
                interval = max(now - last_heartbeat_at, 0.001)
                rate = max(0, received - last_heartbeat_bytes) / interval
                print(
                    f"PROGRESS=phase-{phase} pid={process.pid} ready={ready_seen} "
                    f"stream_confirmed_bytes={received} persisted_bytes={persisted} "
                    f"received_bytes={max_counts.get('received_bytes', 0)} "
                    f"throughput_bytes_per_second={rate:.0f} stage={latest_stage} "
                    f"stage_count={len(observed_stages)} "
                    f"semantic_stage_count={len(seen_stages)} event_count={observed_event_count}"
                )
                progress_heartbeat = {
                    "stream_confirmed_bytes": received,
                    "persisted_bytes": persisted,
                    "received_bytes": max_counts.get("received_bytes", 0),
                    "throughput_bytes_per_second": int(rate),
                    "stage_count": len(observed_stages),
                    "semantic_stage_count": len(seen_stages),
                    "event_count": observed_event_count,
                    "current_stage": latest_stage,
                    "observed_at_monotonic_seconds": now,
                }
                last_heartbeat_bytes = received
                last_heartbeat_at = now
                last_status = now
            try:
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired as waiting:
                captured_out = waiting.output or b""
                captured_err = waiting.stderr or b""
                stdout = captured_out.decode("utf-8", "replace") if isinstance(captured_out, bytes) else str(captured_out)
                stderr = captured_err.decode("utf-8", "replace") if isinstance(captured_err, bytes) else str(captured_err)
        if process.poll() is not None and not timed_out:
            stdout, stderr = process.communicate()
        if timed_out:
            timed_out = True
            _probe_mark("B10_parent_timeout", "start", outcome="terminate", execution_id=execution_id)
            _probe_mark(
                "B10_parent_timeout", "end",
                outcome="exit_confirmed" if process.returncode is not None else "exit_unconfirmed",
                execution_id=execution_id,
            )
    except BaseException as error:
        supervisor_error = _safe_exception_class(error) or "OTHER"
        if process is not None and process.poll() is None:
            try:
                _atomic_write_json(case_root / "supervisor.cancel", {
                    "execution_id": execution_id, "phase": phase,
                    "reason": "SUPERVISOR_ERROR", "requested_at_utc": datetime.now(UTC).isoformat(),
                }, replace=False)
            except OSError:
                pass
            try:
                grace = min(PROOF_CANCEL_GRACE_SECONDS, max(
                    0.0, aggregate_started_monotonic + aggregate_deadline_seconds - time.monotonic(),
                )) if aggregate_started_monotonic is not None else 0
                stdout, stderr = process.communicate(timeout=grace)
            except BaseException as wait_error:
                if process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        pass
                try:
                    stdout, stderr = process.communicate(timeout=max(
                        0.0, aggregate_started_monotonic + aggregate_deadline_seconds - time.monotonic(),
                    ))
                except BaseException:
                    pass
                supervisor_error += f";WAIT:{_safe_exception_class(wait_error)}"

    ended = datetime.now(UTC).isoformat()
    return_code = process.returncode if process is not None else None
    exit_confirmed = process is not None and return_code is not None
    _probe_mark(
        "B10_parent_child_termination", "end",
        outcome="exit_confirmed" if exit_confirmed else "exit_unconfirmed",
        execution_id=execution_id,
    )
    _progress_event("supervisor.child_exit", phase=phase, execution_id=execution_id,
                    outcome="exit_confirmed" if exit_confirmed else "exit_unconfirmed",
                    progress_path=progress_path, progress_root=evidence_root)
    ledger_timeout_settlement = {"status": "NOT_APPLICABLE"}
    if timed_out and exit_confirmed:
        try:
            settled_count = ProofLedger(
                ledger_path,
                getfile_cap=TRUSTED_REFERENCE_APPROVED_MAXIMA["getfile_calls"],
                hash_cap=TRUSTED_REFERENCE_APPROVED_MAXIMA["getfilehashes_calls"],
                payload_cap=TRUSTED_REFERENCE_APPROVED_MAXIMA["reserved_bytes"],
                require_existing=True,
            ).settle_pending_uncertain()
            ledger_timeout_settlement = {
                "status": "SETTLED", "pending_reservations_marked_uncertain": settled_count,
            }
        except (OSError, sqlite3.Error, RuntimeError, TypeError, ValueError) as error:
            ledger_timeout_settlement = {
                "status": "BLOCKED", "reason": _safe_exception_class(error) or "LEDGER_SETTLEMENT_ERROR",
            }
    if phase == 1:
        _progress_event("supervisor.phase1_exit", phase=phase, execution_id=execution_id,
                        outcome="exit_confirmed" if exit_confirmed else "exit_unconfirmed",
                        progress_path=progress_path, progress_root=evidence_root)
    after = _read_budget_snapshot(ledger_path)
    delta = None
    if before is not None and after is not None:
        delta = {key: after[key] - before[key] for key in before}
    try:
        media_state = _observe_isolated_media_state(evidence_root / case_name)
    except BaseException as error:
        media_state = {"available": False, "reason": f"OBSERVATION_FAILED:{_safe_exception_class(error)}"}
    timeout_reconciliation = {"status": "NOT_APPLICABLE"}

    child_report: dict[str, Any] | None = None
    child_report_error = None
    if child_report_path.exists() or child_report_path.is_symlink():
        try:
            child_report = _read_json_object(child_report_path)
        except BaseException as error:
            child_report_error = _safe_exception_class(error) or "OTHER"
    child_envelope_valid = _child_report_envelope_valid(
        child_report,
        execution_id=execution_id,
        phase=phase,
        target_name="controlled" if target == CONTROLLED_TARGET else "common",
        mode=mode,
        case_name=case_name,
        prefix_profile=prefix_profile,
        observed_process_id=process.pid if process is not None else None,
    )
    child_valid = bool(
        child_envelope_valid and child_report.get("child_exit_code") == return_code
    )
    if timed_out:
        if not exit_confirmed:
            timeout_reconciliation = {"status": "BLOCKED", "reason": "PROCESS_EXIT_UNCONFIRMED"}
        elif ledger_timeout_settlement.get("status") != "SETTLED":
            timeout_reconciliation = {"status": "BLOCKED", "reason": "LEDGER_SETTLEMENT_INCOMPLETE"}
        else:
            timeout_reconciliation = _reconcile_supervisor_timeout(
                case_root=evidence_root / case_name, target=target, mode=mode,
                phase_id=f"{execution_id}:{phase}:SUPERVISOR_TIMEOUT",
                media_state=media_state, attempts_before=attempts_before,
                process_pid=process.pid,
                child_report_pid=(
                    child_report.get("process_id") if child_valid else None
                ),
            )
            media_state = _observe_isolated_media_state(evidence_root / case_name)
    declared_exit_code = child_report.get("child_exit_code") if child_envelope_valid else None
    if timed_out and exit_confirmed:
        status, stop_condition = "PROCESS_INTERRUPTED", "SUPERVISOR_TIMEOUT"
    elif timed_out:
        status, stop_condition = "EVIDENCE_INCOMPLETE", "SUPERVISOR_TIMEOUT_EXIT_UNCONFIRMED"
    elif supervisor_error:
        status, stop_condition = "EVIDENCE_INCOMPLETE", supervisor_error
    elif process is None:
        status, stop_condition = "PROCESS_FAILED", "PROCESS_SPAWN_FAILED"
    elif child_envelope_valid and declared_exit_code != return_code:
        status = "EVIDENCE_INCOMPLETE"
        stop_condition = f"CHILD_EXIT_CODE_MISMATCH:declared={declared_exit_code}:observed={return_code}"
    elif return_code != 0:
        status = "PROCESS_FAILED" if child_valid else "EVIDENCE_INCOMPLETE"
        stop_condition = child_report.get("stop_condition") if child_valid else "CHILD_REPORT_MISSING_OR_INVALID"
    elif not child_valid:
        status = "EVIDENCE_INCOMPLETE"
        stop_condition = "CHILD_REPORT_CORRUPT" if child_report_error else "CHILD_REPORT_MISSING_OR_INVALID"
    elif child_report.get("process_id") != process.pid:
        status, stop_condition = "EVIDENCE_INCOMPLETE", "CHILD_PID_MISMATCH"
    else:
        status = str(child_report["status"])
        stop_condition = child_report.get("stop_condition")

    child_result = child_report.get("child_result") if child_valid else None
    progress_heartbeat.update({
        "stream_confirmed_bytes": max_counts.get("stream_confirmed_bytes", 0),
        "persisted_bytes": max_counts.get("persisted_bytes", 0),
        "received_bytes": max_counts.get("received_bytes", 0),
        "stage_count": len(observed_stages) if process is not None else 0,
        "semantic_stage_count": len(seen_stages),
        "event_count": observed_event_count,
        "current_stage": latest_stage,
        "semantic_progress_monotonic_seconds": last_semantic,
        "timeout_reason": timeout_reason,
    })
    progress_events: list[dict[str, Any]] = []
    progress_valid = False
    required_stages = {
        "supervisor.initialized", "supervisor.child_spawned", "child.event_loop_initialized",
        "child.ready", "child.sqlite_created", "child.ledger_created", "child.gateway_constructed",
        "child.session_restored", "child.remote_identity_validated", "child.phase_report_written",
        "supervisor.sqlite_ledger_reconciled", "supervisor.child_exit",
    }
    if phase == 1:
        required_stages |= {"child.phase1_checkpoint", "child.planned_interruption", "supervisor.phase1_exit"}
    else:
        required_stages |= {
            "child.phase2_checkpoint_validated", "child.full_prefix_reread",
            "child.prefix_hash_reconciled", "child.continuation_started", "child.finalized",
        }
        if mode == "TRUSTED_REFERENCE":
            required_stages -= {"child.full_prefix_reread", "child.prefix_hash_reconciled"}
            required_stages.add("child.local_prefix_reference_validated")
    requests_used = (child_result or {}).get("requests_used") if isinstance(child_result, dict) else None
    requests_observation = (
        "CHILD_GATEWAY_COUNTERS; TELETHON_CONNECT_RPC_COUNT_UNKNOWN"
        if requests_used is not None else "PARTIAL_LEDGER_ONLY"
    )
    if requests_used is None and delta is not None:
        requests_used = {
            "GetFile": delta.get("getfile_calls"),
            "GetFileHashes": delta.get("getfilehashes_calls"),
            "identity_GetMessages": None,
            "GetMe": None,
            "restore_calls": None,
            "known_remote_calls": None,
            "telethon_connect_rpc_count": None,
            "total_api_requests": None,
        }
    elif requests_used is None:
        requests_observation = "UNKNOWN"
    receipt: dict[str, Any] = dict(child_result or {})
    media_attempts = media_state.get("attempts") if isinstance(media_state, dict) else None
    prior_attempt_ids = {
        item.get("attempt_id") for item in (attempts_before or []) if isinstance(item, dict)
    }
    phase_attempt_ids = [
        item.get("attempt_id") for item in (media_attempts or [])
        if isinstance(item, dict) and item.get("attempt_id") not in prior_attempt_ids
    ] if attempts_before is not None else None
    expected_before_matches = (
        before_is_new_root_baseline if phase == 1
        else _phase2_ledger_before_matches(
            phase=phase, ledger_before=before, phase1_ledger_after=phase1_ledger_after,
        )
    )
    phase_state_reconciled = _phase_state_reconciles(
        phase=phase, target=target, mode=mode, media_state=media_state,
        child_result=child_result, ledger_before=before, ledger_after=after,
        ledger_delta=delta, phase_attempt_ids=phase_attempt_ids,
        ledger_before_is_new_root_baseline=before_is_new_root_baseline,
        expected_ledger_before=phase1_ledger_after,
        child_exit_code=declared_exit_code, supervisor_exit_code=return_code,
    )
    _progress_event(
        "supervisor.sqlite_ledger_reconciled", phase=phase, execution_id=execution_id,
        outcome="completed" if phase_state_reconciled else "failed",
        progress_path=progress_path, progress_root=evidence_root,
    )
    try:
        final_progress_info = _progress_log_stat(progress_path, evidence_root)
        progress_identity_unchanged = (
            (final_progress_info.st_dev, final_progress_info.st_ino) == progress_log_identity
        )
    except RuntimeError:
        progress_identity_unchanged = False
    try:
        progress_events = [
            json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        relevant = [event for event in progress_events if event.get("execution_id") == execution_id]
        pids: dict[int, tuple[int, int]] = {}
        ordered = True
        for event in relevant:
            pid, seq, stamp = event.get("process_id"), event.get("sequence"), event.get("monotonic_ns")
            if (event.get("phase") != phase or type(pid) is not int or type(seq) is not int
                    or type(stamp) is not int or event.get("stage") not in _PROGRESS_STAGES
                    or event.get("outcome") not in _PROGRESS_OUTCOMES
                    or not isinstance(event.get("counts"), dict)
                    or any(key not in _PROGRESS_COUNTS or type(value) is not int or value < 0
                           for key, value in event.get("counts", {}).items())
                    or set(event) != {"execution_id", "phase", "process_id", "stage", "sequence", "monotonic_ns", "outcome", "counts"}):
                ordered = False
                break
            expected_pid = process.pid if event["stage"].startswith("child.") else os.getpid()
            if pid != expected_pid:
                ordered = False
                break
            previous = pids.get(pid)
            if previous is not None and (seq <= previous[0] or stamp < previous[1]):
                ordered = False
                break
            pids[pid] = (seq, stamp)
        stages = {event.get("stage") for event in relevant}
        successful = {
            "child.ready": "ready", "child.event_loop_initialized": "ready",
            "child.sqlite_created": "created" if phase == 1 else "validated",
            "child.ledger_created": "created", "child.gateway_constructed": "created",
            "child.session_restored": "restored", "child.remote_identity_validated": "validated",
            "child.phase_report_written": "completed", "supervisor.child_exit": "exit_confirmed",
            "supervisor.sqlite_ledger_reconciled": "completed",
        }
        if phase == 1:
            successful.update({
                "child.phase1_checkpoint": "validated",
                "child.planned_interruption": "interrupted",
                "supervisor.phase1_exit": "exit_confirmed",
            })
        else:
            successful.update({
                "child.phase2_checkpoint_validated": "validated",
                "child.continuation_started": "started_transfer",
                "child.finalized": "completed",
            })
            if mode == "TRUSTED_REFERENCE":
                successful["child.local_prefix_reference_validated"] = "matched"
            else:
                successful["child.full_prefix_reread"] = "completed"
                successful["child.prefix_hash_reconciled"] = "matched"
        success_status = all(
            any(event.get("stage") == stage and event.get("outcome") == outcome for event in relevant)
            for stage, outcome in successful.items()
        )
        progress_valid = (
            progress_identity_unchanged and ordered
            and required_stages.issubset(stages) and success_status
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        progress_valid = False
    receipt.update({
        "schema_version": 1,
        "phase_id": f"{execution_id}:{phase}",
        "execution_id": execution_id,
        "phase": phase,
        "timeout_requested_seconds": requested_timeout_seconds,
        "timeout_effective_seconds": effective_timeout_seconds,
        "aggregate_hard_deadline_seconds": aggregate_deadline_seconds,
        "aggregate_started_monotonic_seconds": aggregate_started_monotonic,
        "aggregate_deadline_remaining_seconds_at_spawn": remaining_aggregate,
        "timeout_reason": timeout_reason,
        "termination_method": (
            "COOPERATIVE_CANCEL_THEN_FORCE" if timed_out else "NATURAL_EXIT"
        ),
        "progress_heartbeat": progress_heartbeat,
        "ledger_timeout_settlement": ledger_timeout_settlement,
        "timeout_reconciliation": timeout_reconciliation,
        "timeout_operational_default_seconds": 60 * 60,
        "target_name": "controlled" if target == CONTROLLED_TARGET else "common",
        "mode": mode,
        "case": case_name,
        "prefix_profile": prefix_profile,
        "process_id": child_report.get("process_id") if child_valid else None,
        "supervisor_spawn_pid": process.pid if process else None,
        "process_handle_pid_matches_child_pid": bool(
            process is not None and child_valid and child_report.get("process_id") == process.pid
        ),
        "child_process_id_source": "CHILD_OS_GETPID" if child_valid else None,
        "process_started_at_utc": started,
        "process_ended_at_utc": ended if exit_confirmed else None,
        "exit_code": return_code,
        "child_exit_code": declared_exit_code,
        "process_exit_confirmed": exit_confirmed,
        "status": status,
        "stop_condition": stop_condition,
        "child_error_stage": child_report.get("child_error_stage") if child_valid else None,
        "child_report_path": str(child_report_path),
        "child_report_valid": child_valid,
        "progress_evidence_valid": progress_valid,
        "progress_log_identity": {
            "device": progress_log_identity[0], "inode": progress_log_identity[1],
        },
        "progress_required_stages": sorted(required_stages),
        "progress_observed_stages": sorted({event.get("stage") for event in relevant}),
        "child_report_error": child_report_error,
        "child_status": child_report.get("status") if child_valid else None,
        "child_result": child_result,
        "requests_used": requests_used,
        "requests_observation": requests_observation,
        "bytes_persisted": {
            "partial": media_state.get("partial_bytes"),
            "final": media_state.get("final_bytes"),
        },
        "bytes_reserved": delta.get("payload_reserved") if delta else None,
        "bytes_received": delta.get("payload_received") if delta else None,
        "uncertain_bytes": delta.get("uncertain_bytes") if delta else None,
        "child_output_stop": next(
            (line[:160] for line in stdout.splitlines() if line.startswith("STOP=")), None
        ),
        "stderr_observed": bool(stderr),
        "ledger_before": before,
        "ledger_before_is_new_root_baseline": before_is_new_root_baseline,
        "ledger_before_matches_phase1_after": expected_before_matches,
        "ledger_after": after,
        "ledger_delta": delta,
        "prior_phase_attempt_ids": sorted(prior_attempt_ids),
        "phase_attempt_ids": phase_attempt_ids,
        "media_state_observed": media_state,
        "phase_state_reconciled": phase_state_reconciled,
        "checkpoint_confirmed": bool(
            phase == 1 and phase_state_reconciled and media_state.get("available") is True
            and media_state.get("sqlite_state") == "FAILED_RETRYABLE"
            and media_state.get("partial_bytes") == prefix_bytes
            and media_state.get("sqlite_checkpoint_bytes") == prefix_bytes
            and child_result is not None
            and child_result.get("prefix_sha256") == media_state.get("partial_sha256")
        ),
        "final_file_confirmed": bool(
            phase == 2 and phase_state_reconciled and media_state.get("available") is True
            and media_state.get("sqlite_state") == "COMPLETED_V2"
            and media_state.get("final_bytes") == target["expected_bytes"]
            and media_state.get("physical_sha256") == media_state.get("sqlite_sha256")
            and media_state.get("physical_sha256") == (media_state.get("evidence") or {}).get("final_sha256")
            and media_state.get("evidence_rows") == 1
        ),
    })
    try:
        _atomic_write_json(supervisor_report_path, receipt, replace=True)
    except BaseException:
        # Keep a previously published RUNNING receipt; its status remains fail-closed.
        raise
    return receipt


def _phase_receipt_is_acceptable(
    receipt: dict[str, Any], phase: int, *, require_live_checkpoint: bool = True,
) -> bool:
    requests = receipt.get("requests_used")
    delta = receipt.get("ledger_delta")
    case_name = receipt.get("case")
    target_name = receipt.get("target_name")
    mode = receipt.get("mode")
    try:
        target = target_for(target_name)
        budget = _case_budget(target, mode, case_name, receipt.get("prefix_profile"))
        prefix_bytes = int(budget["prefix_bytes"])
    except (RuntimeError, TypeError, ValueError):
        return False
    payload_cap = int(
        budget["phase1_payload_reservation_cap"] if phase == 1
        else budget["phase2_payload_reservation_cap_per_process"]
    )
    getfile_cap = int(
        budget["phase1_getfile_cap"] if phase == 1
        else budget["phase2_getfile_cap_per_process"]
    )
    hash_cap = 0 if phase == 1 else int(budget["phase2_getfilehashes_cap_per_process"])
    identity_cap = int(
        budget["phase1_identity_getmessages_cap"] if phase == 1
        else budget["phase2_identity_getmessages_cap"]
    )
    timeout_requested = receipt.get("timeout_requested_seconds")
    timeout_effective = receipt.get("timeout_effective_seconds")
    timeout_requested_valid = type(timeout_requested) is int and timeout_requested > 0
    if type(timeout_effective) is int:
        timeout_effective_valid = (
            timeout_requested_valid and timeout_effective > 0
            and timeout_effective <= timeout_requested
        )
    elif type(timeout_effective) is float:
        timeout_effective_valid = (
            timeout_requested_valid and math.isfinite(timeout_effective)
            and timeout_effective > 0 and timeout_effective <= timeout_requested
        )
    else:
        timeout_effective_valid = False
    timeout_values_valid = timeout_requested_valid and timeout_effective_valid
    try:
        start = datetime.fromisoformat(receipt["process_started_at_utc"])
        end = datetime.fromisoformat(receipt["process_ended_at_utc"])
    except (KeyError, TypeError, ValueError):
        return False
    if (
        type(receipt.get("process_id")) is not int
        or receipt.get("process_id") <= 0 or receipt.get("process_exit_confirmed") is not True
        or receipt.get("process_handle_pid_matches_child_pid") is not True
        or type(receipt.get("exit_code")) is not int or receipt.get("exit_code") != 0
        or receipt.get("child_report_valid") is not True
        or receipt.get("child_exit_code") != 0
        or receipt.get("child_exit_code") != receipt.get("exit_code")
        or receipt.get("execution_id") != receipt.get("phase_id", "").rsplit(":", 1)[0]
        or receipt.get("child_result") is None
        or receipt.get("phase_state_reconciled") is not True
        or receipt.get("progress_evidence_valid") is not True
        or target_name not in {"common", "controlled"}
        or (target_name == "common" and mode != "OPERATIONAL_ONLY")
        or (target_name == "controlled" and mode != "TRUSTED_REFERENCE")
        or receipt.get("case") != case_name
        or receipt.get("identity") != {
            "channel_id": target["channel_id"],
            "message_id": target["message_id"],
            "media_ordinal": target["media_ordinal"],
            "media_id": target["media_id"],
            "media_kind": target["media_kind"],
            "expected_bytes": target["expected_bytes"],
        }
        or type(receipt.get("transfer_attempts")) is not int
        or receipt.get("transfer_attempts") < 1
        or receipt.get("transfer_attempts") > (
            PHASE1_TRANSFER_ATTEMPT_CAP if phase == 1 else PHASE2_TRANSFER_ATTEMPT_CAP
        )
        or start > end
        or not isinstance(requests, dict) or not isinstance(delta, dict)
        or requests.get("GetFile") != delta.get("getfile_calls")
        or requests.get("GetFileHashes") != delta.get("getfilehashes_calls")
        or not isinstance(requests.get("identity_GetMessages"), int)
        or not isinstance(requests.get("GetMe"), int)
        or not isinstance(requests.get("restore_calls"), int)
        or requests.get("GetFile", getfile_cap + 1) > getfile_cap
        or requests.get("GetFileHashes", hash_cap + 1) > hash_cap
        or requests.get("identity_GetMessages", identity_cap + 1) > identity_cap
        or requests.get("GetMe", 2) > 1
        or requests.get("restore_calls", 2) != 1
        or delta.get("payload_reserved", 0) > payload_cap
        or delta.get("payload_reserved") != delta.get("getfile_calls", -1) * CHUNK_BYTES
        or delta.get("payload_received", 0) + delta.get("uncertain_bytes", 0)
        > delta.get("payload_reserved", -1)
        or delta.get("uncertain_bytes") != 0
        or not timeout_values_valid
        or receipt.get("timeout_operational_default_seconds") != 60 * 60
    ):
        return False
    if phase == 2 and mode == "OPERATIONAL_ONLY" and (
        receipt.get("full_prefix_reread_bytes") != prefix_bytes
        or receipt.get("full_prefix_reread_sha256") != receipt.get("prefix_sha256_expected")
        or receipt.get("prefix_hash_reconciled") is not True
        or (
            receipt.get("overlap_verification") != "NOT_APPLICABLE_ALIGNED"
            if budget["overlap_bytes"] == 0
            else not isinstance(receipt.get("overlap_verification"), dict)
            or receipt.get("overlap_verification", {}).get("status") != "PASS"
            or receipt.get("overlap_verification", {}).get("remote_request_offset") != budget["wire_offset"]
            or receipt.get("overlap_verification", {}).get("overlap_bytes_compared") != budget["overlap_bytes"]
            or receipt.get("overlap_verification", {}).get("reused_suffix_bytes") != CHUNK_BYTES - budget["overlap_bytes"]
            or receipt.get("overlap_verification", {}).get("next_remote_request_offset") != budget["transfer_offset"]
        )
    ):
        return False
    if phase == 1:
        return bool(
            receipt.get("ledger_before_is_new_root_baseline") is True
            and receipt.get("ledger_before_matches_phase1_after") is True
            and isinstance(receipt.get("ledger_after"), dict)
            and receipt.get("status") == "PROCESS_INTERRUPTED"
            and receipt.get("stop_condition") == "CONTROLLED_INTERRUPT"
            and receipt.get("checkpoint_confirmed") is True
            and receipt.get("sqlite_state") == "FAILED_RETRYABLE"
            and receipt.get("prefix_bytes") == prefix_bytes
            and receipt.get("prefix_sha256") == (
                receipt.get("media_state_observed", {}).get("partial_sha256")
            )
            and _preparation_receipt_valid(
                receipt.get("preparation_receipt"), case=budget,
                prefix_sha256=receipt.get("prefix_sha256"), process_id=receipt.get("process_id"),
                require_live_checkpoint=require_live_checkpoint,
            )
            and receipt.get("preparation_receipt", {}).get("partial_path")
            == receipt.get("media_state_observed", {}).get("partial_path")
            and receipt.get("preparation_receipt", {}).get("wire_bytes_received")
            == receipt.get("bytes_received")
            and receipt.get("uncertain_bytes") == 0
            and receipt.get("remote_identity_preflight") == "PASS"
        )
    return bool(
        receipt.get("ledger_before_is_new_root_baseline") is False
        and receipt.get("ledger_before_matches_phase1_after") is True
        and isinstance(receipt.get("ledger_before"), dict)
        and isinstance(receipt.get("ledger_after"), dict)
        and receipt.get("status") == "PROCESS_COMPLETED"
        and receipt.get("stop_condition") is None
        and receipt.get("final_file_confirmed") is True
        and receipt.get("sqlite_state") == "COMPLETED_V2"
        and receipt.get("final_bytes") == target["expected_bytes"]
        and type(receipt.get("final_sha256")) is str
        and re.fullmatch(r"[0-9a-f]{64}", receipt.get("final_sha256", "")) is not None
        and receipt.get("final_sha256") == receipt.get("media_state_observed", {}).get("physical_sha256")
        and receipt.get("remote_identity_preflight") == "PASS"
        and (mode != "TRUSTED_REFERENCE" or isinstance(receipt.get("trusted_reference_result"), dict)
             and receipt["trusted_reference_result"].get("status") in {
                 "TRUSTED_REFERENCE_MATCH", "TRUSTED_REFERENCE_MISMATCH"
             })
    )


def _trusted_reference_mismatch_proven(phase_result: dict[str, Any]) -> bool:
    """Recognize explicit mismatch evidence without guessing from generic failures."""
    child = phase_result.get("child_result")
    child = child if isinstance(child, dict) else {}
    if (
        isinstance(child.get("trusted_reference_result"), dict)
        and child["trusted_reference_result"].get("status") == "TRUSTED_REFERENCE_MISMATCH"
    ):
        return True

    def contains_explicit_mismatch(value: Any) -> bool:
        if value == "REFERENCE_MISMATCH":
            return True
        if isinstance(value, dict):
            return any(contains_explicit_mismatch(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains_explicit_mismatch(item) for item in value)
        return False

    media_state = phase_result.get("media_state_observed")
    media_state = media_state if isinstance(media_state, dict) else {}
    evidence_sources = (
        child.get("queue_result"), child.get("stop_condition"),
        phase_result.get("stop_condition"), media_state.get("failure_category"),
        media_state.get("attempts"),
    )
    return any(contains_explicit_mismatch(source) for source in evidence_sources)


def execute(
    target_name: str, mode: str, evidence_parent: Path | None = None, *, case_name: str,
    resume_evidence_root: Path | None = None, prefix_profile: str | None = None,
) -> tuple[int, Path]:
    if resume_evidence_root is not None:
        raise RuntimeError("FRESH_PROOF_ROOT_REQUIRED")
    if not _execute_token_valid():
        raise RuntimeError("NATIVE_CONFIRMATION_TOKEN_REQUIRED")
    _verify_ratified_contract()
    if (target_name, mode) not in {
        ("common", "OPERATIONAL_ONLY"), ("controlled", "TRUSTED_REFERENCE"),
    }:
        raise RuntimeError("REAL_PROOF_SCOPE_NOT_AUTHORIZED")
    target, budgets = _validate_target_profile(target_name, mode, prefix_profile)
    selected_budget = _case_budget(target, mode, case_name, prefix_profile)
    cases = [item for item in budgets if item["case"] == case_name]
    if len(cases) != 1:
        raise RuntimeError("AUTHORIZED_PROOF_CASE_MISSING")
    if cases[0] != selected_budget:
        raise RuntimeError("AUTHORIZED_PROFILE_CAP_MISMATCH")
    recovery = None
    if target_name == "controlled":
        import tempfile
        short_parent = Path(tempfile.gettempdir()) / "s6v2"
        short_parent.mkdir(parents=True, exist_ok=True)
        evidence_parent = short_parent
    evidence_root = _new_isolated_root(evidence_parent)
    _guard_native_paths((
        evidence_root / "authorization.json",
        evidence_root / case_name / "phase-1.json",
        evidence_root / case_name / "phase-2.json",
        evidence_root / case_name / "phase-1.child.json",
        evidence_root / case_name / "phase-2.child.json",
        evidence_root / case_name / "downloads" / "proof-document.bin.part",
        evidence_root / case_name / "reference-manifest.v1.json",
        evidence_root / "s6-v2-proof-report.json",
    ))
    token = os.environ["S6_V2_PROOF_AUTH"]
    aggregate_execution_id = uuid.uuid4().hex
    execution_lock = _acquire_execution_lock(evidence_root, aggregate_execution_id)
    authorization_path = (
        evidence_root / f"authorization-resume-{aggregate_execution_id}.json"
        if recovery else evidence_root / "authorization.json"
    )
    if authorization_path.exists() or authorization_path.is_symlink():
        raise RuntimeError("AUTHORIZATION_EVIDENCE_ALREADY_EXISTS")
    authorization = {
        "evidence_root": str(evidence_root.resolve()),
        "target": target_name,
        "mode": mode,
        "contract_sha256": V2_CONTRACT_SHA256,
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "allowed_cases": [case_name],
        "case_profile": {
            "prefix_bytes": selected_budget["prefix_bytes"],
            "prefix_profile": selected_budget.get("prefix_profile"),
            "wire_offset": selected_budget["wire_offset"],
            "transfer_offset": selected_budget["transfer_offset"],
            "overlap_bytes": selected_budget["overlap_bytes"],
            "effective_caps": _case_effective_limits(case_name, mode, target_name, selected_budget),
            "approved_maxima": dict(
                TRUSTED_REFERENCE_APPROVED_MAXIMA if mode == "TRUSTED_REFERENCE" else APPROVED_LIMITS
            ),
        },
        "allowed_phases": [2] if recovery else [1, 2],
        "recovered_phase1": bool(recovery),
        "aggregate_execution_id": aggregate_execution_id,
        "recovery_from_evidence_root": str(evidence_root) if recovery else None,
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    _atomic_write_json(authorization_path, authorization, replace=False)

    phase_results: list[dict[str, Any]] = [recovery["phase1"]] if recovery else []
    stop: str | None = None
    phase1_pid = int(recovery["phase1"]["process_id"]) if recovery else 0
    aggregate_started_monotonic = None
    for case in cases:
        phases = (2,) if recovery else (1, 2)
        if not recovery:
            case_root = evidence_root / case["case"]
            if case_root.exists() or case_root.is_symlink():
                stop = f"{case['case']}_PHASE_1_ROOT_ALREADY_EXISTS"
                break
            (case_root / "downloads").mkdir(parents=True)
        for phase in phases:
            report = evidence_root / case["case"] / f"phase-{phase}.json"
            child_report = evidence_root / case["case"] / f"phase-{phase}.child.json"
            if report.exists() or report.is_symlink() or child_report.exists() or child_report.is_symlink():
                stop = f"{case['case']}_PHASE_{phase}_EVIDENCE_ALREADY_EXISTS"
                break
            phase_execution_id = uuid.uuid4().hex
            command = [
                getattr(sys, "_base_executable", sys.executable), str(Path(__file__).resolve()), "--child",
                "--target", target_name, "--mode", mode, "--case", case["case"],
                "--phase", str(phase), "--evidence-root", str(evidence_root),
                "--phase-report", str(child_report), "--phase1-pid", str(phase1_pid),
                "--execution-id", phase_execution_id,
                "--authorization-file", str(authorization_path),
            ]
            if prefix_profile:
                command.extend(("--prefix-profile", prefix_profile))
            if recovery:
                command.append("--recovered-phase1")
            receipt = _run_phase_child(
                command, evidence_root=evidence_root, case_name=case["case"], phase=phase,
                target=target, mode=mode, execution_id=phase_execution_id,
                child_report_path=child_report, supervisor_report_path=report,
                ledger_path=evidence_root / case["case"] / "budget.sqlite3",
                phase1_ledger_after=(phase_results[0].get("ledger_after") if phase == 2 else None),
                aggregate_started_monotonic=aggregate_started_monotonic,
                expected_prefix_sha256=(phase_results[0].get("prefix_sha256") if phase == 2 else None),
                prefix_profile=prefix_profile,
            )
            phase_results.append(receipt)
            if aggregate_started_monotonic is None:
                aggregate_started_monotonic = receipt.get("aggregate_started_monotonic_seconds")
            if not _phase_receipt_is_acceptable(receipt, phase):
                stop = f"{case['case']}_PHASE_{phase}_{receipt.get('status', 'INCOMPLETE')}"
                break
            if phase == 1:
                phase1_pid = int(receipt["process_id"])
        if stop:
            break

    process_boundary = {"two_process_proof": "INCOMPLETE"}
    if len(phase_results) == 2:
        first, second = phase_results
        first_ended = first.get("process_ended_at_utc")
        second_started = second.get("process_started_at_utc")
        try:
            ordering_valid = datetime.fromisoformat(first_ended) <= datetime.fromisoformat(second_started)
        except (TypeError, ValueError):
            ordering_valid = False
        pids_distinct = (
            isinstance(first.get("process_id"), int) and isinstance(second.get("process_id"), int)
            and first["process_id"] > 0 and second["process_id"] > 0
            and first["process_id"] != second["process_id"]
        )
        executions_distinct = first.get("execution_id") != second.get("execution_id")
        both_phases_valid = (
            _phase_receipt_is_acceptable(first, 1, require_live_checkpoint=False)
            and _phase_receipt_is_acceptable(second, 2)
            and type(first.get("transfer_attempts")) is int
            and type(second.get("transfer_attempts")) is int
            and first["transfer_attempts"] + second["transfer_attempts"] <= MAX_ATTEMPTS
            and second.get("prefix_sha256_expected") == first.get("prefix_sha256")
            and (
                second.get("full_prefix_reread_sha256") == first.get("prefix_sha256")
                if mode == "OPERATIONAL_ONLY"
                else second.get("local_prefix_reference_evidence", {}).get("status")
                == "LOCAL_PREFIX_REFERENCE_MATCH"
                and second.get("trusted_reference_result", {}).get("status")
                == "TRUSTED_REFERENCE_MATCH"
            )
        )
        if pids_distinct and executions_distinct and ordering_valid and both_phases_valid:
            process_boundary = {
                "two_process_proof": "PASS", "phase1_pid": first["process_id"],
                "phase2_pid": second["process_id"], "phase1_execution_id": first["execution_id"],
                "phase2_execution_id": second["execution_id"],
                "phase1_exit_before_phase2_start": True,
            }
        else:
            stop = stop or "TWO_PROCESS_PROOF_INCOMPLETE"
            process_boundary = {
                "two_process_proof": "INCOMPLETE", "pids_distinct": pids_distinct,
                "execution_ids_distinct": executions_distinct,
                "phase1_exit_before_phase2_start": ordering_valid,
            }
    else:
        stop = stop or "TWO_PROCESS_PROOF_INCOMPLETE"

    supervisor_reference_result: dict[str, Any] | None = None
    if mode == "TRUSTED_REFERENCE":
        phase2_child = (
            phase_results[1].get("child_result")
            if len(phase_results) > 1 and isinstance(phase_results[1].get("child_result"), dict)
            else None
        )
        final_path = phase2_child.get("final_path") if phase2_child else None
        if isinstance(final_path, str):
            supervisor_reference_result = _supervisor_compare_reference(
                evidence_root / case_name, final_path,
            )
        else:
            supervisor_reference_result = {"status": "INCOMPLETE", "reason": "FINAL_FILE_EVIDENCE_MISSING"}
    reference_post_verification = (
        _post_verify_reference_integrity(evidence_root / case_name)
        if mode == "TRUSTED_REFERENCE"
        else {"status": "NOT_APPLICABLE"}
    )

    budgets = [item for item in budgets if item["case"] == case_name]
    budget = budgets[0]
    ledger = _read_budget_snapshot(evidence_root / case_name / "budget.sqlite3")
    reservation_summary = None
    ledger_health = "AVAILABLE" if ledger is not None else "UNAVAILABLE_OR_INVALID"
    if ledger is not None:
        try:
            reservation_summary = ProofLedger(
                evidence_root / case_name / "budget.sqlite3",
                getfile_cap=int(budget["aggregate_getfile_cap"]),
                hash_cap=int(budget["aggregate_getfilehashes_cap"]),
                payload_cap=int(budget["aggregate_payload_reservation_cap"]),
                require_existing=True,
            ).reservation_summary()
        except (OSError, sqlite3.Error, RuntimeError, TypeError, ValueError):
            ledger_health = "CORRUPT_OR_INCONSISTENT"
    phase_requests = [item.get("requests_used") for item in phase_results]
    request_counts_available = bool(phase_requests) and all(
        isinstance(item, dict)
        and type(item.get("GetFile")) is int and item["GetFile"] >= 0
        and type(item.get("GetFileHashes")) is int and item["GetFileHashes"] >= 0
        and type(item.get("identity_GetMessages")) is int and item["identity_GetMessages"] >= 0
        and type(item.get("GetMe")) is int and item["GetMe"] >= 0
        for item in phase_requests
    )
    identity_total = (
        sum(item["identity_GetMessages"] for item in phase_requests)
        if request_counts_available else None
    )
    getme_total = (
        sum(item["GetMe"] for item in phase_requests)
        if request_counts_available else None
    )
    counted_remote_calls_lower_bound = (
        sum(
            item["GetFile"] + 2 * item["GetFileHashes"]
            + item["identity_GetMessages"] + item["GetMe"]
            for item in phase_requests
        )
        if request_counts_available else None
    )
    known_remote_calls_total = None
    request_budget_within_caps = bool(
        request_counts_available
        and identity_total <= int(budget["aggregate_identity_getmessages_cap"])
        and getme_total <= int(budget["session_restore_getme_cap"])
    )
    effective_caps = _case_effective_limits(
        case_name, mode, target_name, budget,
    )
    approved_maxima = (
        TRUSTED_REFERENCE_APPROVED_MAXIMA if mode == "TRUSTED_REFERENCE" else APPROVED_LIMITS
    )
    budget_within_caps = bool(
        ledger is not None
        and ledger["getfile_calls"] <= int(budget["aggregate_getfile_cap"])
        and ledger["getfilehashes_calls"] <= int(budget["aggregate_getfilehashes_cap"])
        and ledger["payload_reserved"] <= int(budget["aggregate_payload_reservation_cap"])
        and ledger["getfile_calls"] <= effective_caps["getfile_calls"]
        and ledger["getfilehashes_calls"] <= effective_caps["getfilehashes_calls"]
        and ledger["payload_reserved"] <= effective_caps["reserved_bytes"]
        and identity_total is not None
        and identity_total <= effective_caps.get(
            "identity_getmessages_calls", int(budget["aggregate_identity_getmessages_cap"]),
        )
        and ledger["getfile_calls"] <= approved_maxima["getfile_calls"]
        and ledger["getfilehashes_calls"] <= approved_maxima["getfilehashes_calls"]
        and ledger["payload_reserved"] <= approved_maxima["reserved_bytes"]
        and ledger["uncertain_bytes"] == 0
        and request_budget_within_caps
    )
    numeric_cap_exceeded = bool(ledger is not None and (
        ledger["getfile_calls"] > int(budget["aggregate_getfile_cap"])
        or ledger["getfilehashes_calls"] > int(budget["aggregate_getfilehashes_cap"])
        or ledger["payload_reserved"] > int(budget["aggregate_payload_reservation_cap"])
        or ledger["getfile_calls"] > effective_caps["getfile_calls"]
        or ledger["getfilehashes_calls"] > effective_caps["getfilehashes_calls"]
        or ledger["payload_reserved"] > effective_caps["reserved_bytes"]
        or ledger["getfile_calls"] > approved_maxima["getfile_calls"]
        or ledger["getfilehashes_calls"] > approved_maxima["getfilehashes_calls"]
        or ledger["payload_reserved"] > approved_maxima["reserved_bytes"]
    ))
    if not budget_within_caps:
        stop = stop or "AGGREGATE_BUDGET_INCONSISTENT"
    mismatch_observed = mode == "TRUSTED_REFERENCE" and any(
        _trusted_reference_mismatch_proven(item) for item in phase_results
    )
    mismatch_observed = mismatch_observed or bool(
        supervisor_reference_result
        and supervisor_reference_result.get("status") == "TRUSTED_REFERENCE_MISMATCH"
    )
    reference_match = mode == "TRUSTED_REFERENCE" and any(
        isinstance((item.get("child_result") or {}).get("trusted_reference_result"), dict)
        and item["child_result"]["trusted_reference_result"].get("status")
        == "TRUSTED_REFERENCE_MATCH"
        for item in phase_results
    )
    child_reference_match = reference_match
    reference_match = _trusted_reference_match_allowed(
        child_reference_match, supervisor_reference_result, reference_post_verification,
    )
    blocked_condition = any(
        any(term in str(item.get("stop_condition", "")) for term in (
            "REFERENCE", "PATH", "BUDGET", "AUTHORIZATION", "SCOPE", "CHECKPOINT",
            "OWNERSHIP", "IDENTITY", "RECONCILIATION",
        ))
        for item in phase_results
    )
    if mode == "TRUSTED_REFERENCE":
        phase2_child = phase_results[1].get("child_result") if len(phase_results) > 1 else None
        phase2_evidence = phase2_child.get("evidence") if isinstance(phase2_child, dict) else None
        remote_hash_class = (
            phase2_evidence.get("remote_hash_class") if isinstance(phase2_evidence, dict) else None
        )
        remote_hash_veto = any(
            term in str(item.get("stop_condition", ""))
            for item in phase_results
            for term in (
                "REMOTE_HASH", "REMOTE_IDENTITY", "IDENTITY",
            )
        )
        remote_hash_result = (
            "VETO" if remote_hash_veto
            else remote_hash_class or "INCOMPLETE"
        )
        reference_result = (
            "TRUSTED_REFERENCE_MISMATCH" if mismatch_observed
            else "TRUSTED_REFERENCE_MATCH" if reference_match
            else "BLOCKED" if supervisor_reference_result
            and supervisor_reference_result.get("status") == "BLOCKED"
            or reference_post_verification.get("status") == "BLOCKED"
            or any(
                any(term in str(item.get("stop_condition", "")) for term in (
                    "REFERENCE", "PATH", "CHECKPOINT", "OWNERSHIP",
                ))
                for item in phase_results
            )
            else "INCOMPLETE"
        )
        operational_result = (
            "PASS" if process_boundary["two_process_proof"] == "PASS" and budget_within_caps
            else "BLOCKED" if blocked_condition or not budget_within_caps
            else "INCOMPLETE"
        )
        resume_result = (
            "LOCAL_PREFIX_REFERENCE_MATCH" if len(phase_results) > 1
            and isinstance((phase_results[1].get("child_result") or {}).get(
                "local_prefix_reference_evidence"
            ), dict)
            and phase_results[1]["child_result"]["local_prefix_reference_evidence"].get("status")
            == "LOCAL_PREFIX_REFERENCE_MATCH"
            else "BLOCKED" if any(
                any(term in str(item.get("stop_condition", "")) for term in (
                    "REFERENCE", "PATH", "CHECKPOINT", "OWNERSHIP", "RECONCILIATION",
                ))
                for item in phase_results
            )
            else "INCOMPLETE"
        )
        aggregate_result = (
            "TRUSTED_REFERENCE_MISMATCH" if mismatch_observed
            else "TRUSTED_REFERENCE_MATCH"
            if not stop and process_boundary["two_process_proof"] == "PASS"
            and budget_within_caps and reference_match and not remote_hash_veto
            else "BLOCKED" if blocked_condition or not budget_within_caps or remote_hash_veto
            or reference_post_verification.get("status") == "BLOCKED"
            or (supervisor_reference_result is not None and supervisor_reference_result.get("status") == "BLOCKED")
            else "INCOMPLETE"
        )
    else:
        reference_result = "NOT_APPLICABLE"
        remote_hash_result = "NOT_APPLICABLE"
        operational_result = "PASS" if not stop and process_boundary["two_process_proof"] == "PASS" else "INCOMPLETE"
        resume_result = "NOT_APPLICABLE"
        aggregate_result = "PASS" if not stop and process_boundary["two_process_proof"] == "PASS" else "INCOMPLETE"
    report = {
        "activity": "S6_V2_PROOF_EXECUTION",
        "target": target,
        "mode": mode,
        "case": case_name,
        "phases": phase_results,
        "process_boundary": process_boundary,
        "budget": {
            "within_caps": budget_within_caps, "ledger": ledger, "limits": budget,
            "effective_caps": effective_caps,
            "approved_ceilings": dict(approved_maxima),
            "effective_proof_caps": effective_caps,
            "numeric_caps_exceeded": numeric_cap_exceeded,
            "child_counters_complete": request_counts_available,
            "missing_child_counters": [
                name for name, available in (
                    ("identity_GetMessages", identity_total is not None),
                    ("GetMe", getme_total is not None),
                ) if not available
            ],
            "reservation_accounting": reservation_summary,
            "ledger_health": ledger_health,
            "request_counts": {
                "GetFile": ledger["getfile_calls"] if ledger else None,
                "GetFileHashes": ledger["getfilehashes_calls"] if ledger else None,
                "identity_GetMessages": identity_total,
                "GetMe": getme_total,
                "known_remote_calls": known_remote_calls_total,
                "counted_remote_calls_lower_bound": counted_remote_calls_lower_bound,
                "known_remote_calls_reason": "No total is available; lower bound omits per-stream metadata refetch calls",
                "telethon_connect_rpc_count": None,
                "total_api_requests": None,
                "total_api_requests_reason": "Telethon.connect performs internal sender RPCs outside this harness counter",
                "within_caps": request_budget_within_caps,
            },
        },
        "result": aggregate_result,
        "trusted_reference_outcome": (
            aggregate_result if mode == "TRUSTED_REFERENCE" else "NOT_APPLICABLE"
        ),
        "supervisor_reference_comparison": supervisor_reference_result,
        "reference_integrity_post_verification": reference_post_verification,
        "reference_result": reference_result,
        "remote_hash_result": remote_hash_result,
        "operational_result": operational_result,
        "resume_result": resume_result,
        "stop_condition": stop,
        "overlap_verification": (
            "NOT_APPLICABLE_ALIGNED" if budget["overlap_bytes"] == 0
            else phase_results[-1].get("overlap_verification") if phase_results else None
        ),
        "aggregate_hard_deadline_seconds": _deadline_policy(mode)[1],
        "requested_process_timeout_seconds": _deadline_policy(mode)[0],
        "readiness_timeout_seconds": PROOF_STARTUP_TIMEOUT_SECONDS,
        "semantic_inactivity_timeout_seconds": PROOF_SEMANTIC_IDLE_TIMEOUT_SECONDS,
        "v1_active": True,
        "v2_effective": False,
        "v2_activation_scope": "CHILD_PROCESS_SINGLE_PROOF_INVOCATION_ONLY",
        "real_telegram_calls": "RECORDED_PER_PHASE",
        "original_sqlite_access": "NO",
        "historical_part_access": "NO",
        "evidence_root": str(evidence_root),
        "recovered_phase1": bool(recovery),
        "authorization_path": str(authorization_path),
    }
    path = evidence_root / (
        f"s6-v2-proof-report-resume-{aggregate_execution_id}.json"
        if recovery else "s6-v2-proof-report.json"
    )
    _atomic_write_json(path, report, replace=False)
    _release_execution_lock(execution_lock, aggregate_execution_id)
    print(f"REPORT={path}")
    print(f"PROOF_RESULT={report['result']}")
    return (0 if report["result"] in {"PASS", "TRUSTED_REFERENCE_MATCH"} else 5), evidence_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preconfirmation-status-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--secure-preflight-status-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--timeout-policy-status-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--target", choices=("common", "controlled"))
    parser.add_argument("--mode", choices=("OPERATIONAL_ONLY", "TRUSTED_REFERENCE"))
    parser.add_argument("--evidence-parent", type=Path)
    parser.add_argument("--resume-evidence-root", type=Path)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--native-launcher-confirmed", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--expected-timeout-policy-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--case", choices=("aligned", "unaligned-prepared"))
    parser.add_argument("--prefix-profile", choices=tuple(CONTROLLED_PREFIX_OPTIONS))
    parser.add_argument("--phase", type=int, choices=(1, 2))
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--phase-report", type=Path)
    parser.add_argument("--authorization-file", type=Path)
    parser.add_argument("--execution-id")
    parser.add_argument("--phase1-pid", type=int, default=0)
    parser.add_argument("--recovered-phase1", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.secure_preflight_status_only:
            status = _status_only_secure_preflight()
            print(json.dumps(status, separators=(",", ":")))
            return 0 if status["credential_vault"] == "YES" and status["protected_session"] == "YES" else 5
        if args.timeout_policy_status_only:
            if not args.target or not args.mode:
                raise RuntimeError("TIMEOUT_POLICY_CONFIGURATION_MISSING")
            policy = _effective_timeout_policy(args.target, args.mode)
            print(json.dumps(policy, separators=(",", ":")))
            return 0 if policy["contract_match"] else 5
        if args.preconfirmation_status_only:
            if not args.target or not args.mode:
                raise RuntimeError("PRECONFIRMATION_PROFILE_MISSING")
            status = _preconfirmation_status(
                args.target, args.mode, args.prefix_profile, args.evidence_parent,
            )
            print(json.dumps(status, separators=(",", ":")))
            return 0
        if args.child:
            if not all((
                args.target, args.mode, args.case, args.phase, args.evidence_root,
                args.phase_report, args.execution_id, args.authorization_file,
            )):
                raise RuntimeError("CHILD_SCOPE_INCOMPLETE")
            return _child_main(args)
        if not args.target or not args.mode:
            raise RuntimeError("TARGET_AND_EXPLICIT_MODE_REQUIRED")
        if args.dry_run:
            if args.resume_evidence_root is not None:
                raise RuntimeError("DRYRUN_CANNOT_RESUME_REAL_PROOF")
            return dry_run(args.target, args.mode, args.evidence_parent, args.prefix_profile)[0]
        if not args.native_launcher_confirmed:
            raise RuntimeError("USE_NATIVE_LAUNCHER_CONFIRMATION")
        if not args.expected_timeout_policy_sha256:
            raise RuntimeError("TIMEOUT_POLICY_CONFIRMATION_MISSING")
        effective_policy = _effective_timeout_policy(args.target, args.mode)
        if not effective_policy["contract_match"]:
            raise RuntimeError("TIMEOUT_POLICY_CONTRACT_DIVERGENCE")
        if args.expected_timeout_policy_sha256 != effective_policy["policy_sha256"]:
            raise RuntimeError("TIMEOUT_POLICY_CHANGED_AFTER_CONFIRMATION")
        return execute(
            args.target, args.mode, args.evidence_parent,
            case_name=args.case or "aligned",
            resume_evidence_root=args.resume_evidence_root,
            prefix_profile=args.prefix_profile,
        )[0]
    except BaseException as error:
        print(f"STOP={_safe_exception_class(error)}")
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
