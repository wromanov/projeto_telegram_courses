"""Fail-closed Windows process supervision for the S9 offline/real-run gates.

This module is deliberately external to the application CLI.  It does not add
arguments to the application and never interprets a successful process exit as
an application-level limit check.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

MIB = 1024 * 1024
SAMPLE_INTERVAL_SECONDS = 0.250
BASELINE_WINDOW_SECONDS = 2.0
COOPERATIVE_CANCEL_SECONDS = 15.0
TREE_CONTAINMENT_SECONDS = 30.0
GLOBAL_DEADLINE_SECONDS = 3600.0
MAX_WORKING_SET_BYTES = 512 * MIB
MAX_WORKING_SET_GROWTH_BYTES = 128 * MIB
_RUN_ID = re.compile(r"[0-9a-f]{32}\Z")

STAGE_TIMEOUTS_SECONDS: dict[str, int] = {
    "discovery": 120,
    "scan": 120,
    "catalog": 60,
    "inspection": 60,
    "queue_f": 600,
    "queue_m": 1800,
    "verification_local": 300,
}

_CREATE_SUSPENDED = 0x00000004
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
_JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010
_THREAD_SUSPEND_RESUME = 0x0002
_CTRL_BREAK_EVENT = 1


class SupervisorError(RuntimeError):
    """Sanitized supervisor failure with a stable, non-sensitive reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ProcessSample:
    timestamp_utc: str
    elapsed_seconds: float
    process_count: int
    working_set_bytes: int
    private_bytes: int


@dataclass
class MemoryMonitor:
    """Measured process-tree memory and the prompt-anchored S9 baseline."""

    samples: list[ProcessSample] = field(default_factory=list)
    baseline_samples: list[ProcessSample] = field(default_factory=list)
    effective_intervals: list[float] = field(default_factory=list)
    baseline_ready: bool = False
    baseline_status: str = "BLOCKED_PROMPT_SIGNAL_UNAVAILABLE"
    baseline_working_set_bytes: int | None = None
    baseline_private_bytes: int | None = None
    peak_observed_working_set_bytes: int = 0
    peak_observed_private_bytes: int = 0
    peak_sum_process_working_set_bytes: int = 0
    peak_after_baseline_working_set_bytes: int = 0

    def add(
        self,
        sample: ProcessSample,
        process_metrics: dict[tuple[int, int], tuple[int, int, int]],
    ) -> None:
        if self.samples:
            previous = self.samples[-1]
            self.effective_intervals.append(sample.elapsed_seconds - previous.elapsed_seconds)
        self.samples.append(sample)
        self.peak_observed_working_set_bytes = max(
            self.peak_observed_working_set_bytes, sample.working_set_bytes
        )
        self.peak_observed_private_bytes = max(
            self.peak_observed_private_bytes, sample.private_bytes
        )
        if self.baseline_ready:
            self.peak_after_baseline_working_set_bytes = max(
                self.peak_after_baseline_working_set_bytes,
                sample.working_set_bytes,
            )
        # Aggregate only the processes present in this tree sample. Summing
        # lifetime peaks from already-exited descendants would double count
        # disjoint processes and inflate the measured tree maximum.
        active_tree_peak = sum(value[2] for value in process_metrics.values())
        self.peak_sum_process_working_set_bytes = max(
            self.peak_sum_process_working_set_bytes, active_tree_peak
        )

    def baseline(self, samples: list[ProcessSample]) -> None:
        if not samples:
            self.baseline_status = "BLOCKED_BASELINE_SAMPLES_MISSING"
            return
        self.baseline_samples = samples
        self.baseline_working_set_bytes = int(
            median(sample.working_set_bytes for sample in samples)
        )
        self.baseline_private_bytes = int(median(sample.private_bytes for sample in samples))
        self.baseline_ready = True
        self.baseline_status = "PASS_PROMPT_SIGNAL_AND_TWO_SECOND_WINDOW"

    def receipt(self) -> dict[str, object]:
        intervals = self.effective_intervals
        return {
            "baseline_status": self.baseline_status,
            "baseline_samples": [sample.__dict__ for sample in self.baseline_samples],
            "baseline_working_set_bytes": self.baseline_working_set_bytes,
            "baseline_private_bytes": self.baseline_private_bytes,
            "sample_count": len(self.samples),
            "samples": [sample.__dict__ for sample in self.samples],
            "target_sampling_interval_ms": int(SAMPLE_INTERVAL_SECONDS * 1000),
            "effective_sampling_interval_min_ms": round(min(intervals) * 1000, 3)
            if intervals else None,
            "effective_sampling_interval_max_ms": round(max(intervals) * 1000, 3)
            if intervals else None,
            "effective_sampling_interval_mean_ms": round(
                sum(intervals) / len(intervals) * 1000, 3
            ) if intervals else None,
            "peak_observed_working_set_bytes": self.peak_observed_working_set_bytes,
            "peak_observed_private_bytes": self.peak_observed_private_bytes,
            "peak_working_set_bytes": self.peak_sum_process_working_set_bytes,
            "sampled_peak_private_bytes": self.peak_observed_private_bytes,
            "peak_active_tree_working_set_bytes": self.peak_sum_process_working_set_bytes,
            "peak_working_set_basis": "sum_of_active_process_peak_counters_per_sample",
            "memory_source": "WINDOWS_PROCESS_MEMORY_COUNTERS_EX",
        }


@dataclass(frozen=True)
class SupervisorResult:
    run_id: str
    result: str
    reason: str
    exit_code: int | None
    receipt_path: Path
    receipt_persisted: bool
    supervisor_gate: str
    process_control_gate: str
    memory_monitoring_gate: str
    limit_check_result: str = "UNKNOWN"
    critical_audit_gate: str = "BLOCKED"
    receipt_attested: bool = False


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_stage(stage: str, timeout_seconds: int | None) -> tuple[str, int]:
    if not isinstance(stage, str) or stage not in STAGE_TIMEOUTS_SECONDS:
        raise SupervisorError("STAGE_NOT_ALLOWLISTED")
    maximum = STAGE_TIMEOUTS_SECONDS[stage]
    if timeout_seconds is None:
        return stage, maximum
    if type(timeout_seconds) is not int or timeout_seconds <= 0 or timeout_seconds > maximum:
        raise SupervisorError("STAGE_TIMEOUT_OUTSIDE_CONTRACT")
    return stage, timeout_seconds


def _windows_api() -> tuple[Any, ...]:
    if os.name != "nt":
        raise SupervisorError("WINDOWS_JOB_OBJECT_REQUIRED")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    def bind(name: str, argtypes: list[Any], restype: Any = ctypes.c_int, library: Any = kernel32) -> Any:
        function = getattr(library, name)
        function.argtypes = argtypes
        function.restype = restype
        return function

    create_job = bind("CreateJobObjectW", [ctypes.c_void_p, ctypes.c_wchar_p], ctypes.c_void_p)
    set_info = bind(
        "SetInformationJobObject",
        [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32],
    )
    assign = bind("AssignProcessToJobObject", [ctypes.c_void_p, ctypes.c_void_p])
    query = bind(
        "QueryInformationJobObject",
        [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p],
    )
    terminate = bind("TerminateJobObject", [ctypes.c_void_p, ctypes.c_uint32])
    close = bind("CloseHandle", [ctypes.c_void_p])
    open_thread = bind(
        "OpenThread", [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32], ctypes.c_void_p
    )
    resume_thread = bind("ResumeThread", [ctypes.c_void_p], ctypes.c_uint32)
    generate_ctrl = bind(
        "GenerateConsoleCtrlEvent", [ctypes.c_uint32, ctypes.c_uint32]
    )
    create_snapshot = bind(
        "CreateToolhelp32Snapshot", [ctypes.c_uint32, ctypes.c_uint32], ctypes.c_void_p
    )
    thread_first = bind("Thread32First", [ctypes.c_void_p, ctypes.c_void_p])
    thread_next = bind("Thread32Next", [ctypes.c_void_p, ctypes.c_void_p])
    open_process = bind(
        "OpenProcess", [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32], ctypes.c_void_p
    )
    get_times = bind(
        "GetProcessTimes",
        [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p],
    )
    get_memory = bind(
        "GetProcessMemoryInfo", [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32],
        library=psapi,
    )
    return (
        kernel32, create_job, set_info, assign, query, terminate, close, open_thread,
        resume_thread, generate_ctrl, create_snapshot, thread_first, thread_next,
        open_process, get_times, get_memory,
    )


class _BasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", ctypes.c_uint32), ("TotalProcesses", ctypes.c_uint32),
        ("ActiveProcesses", ctypes.c_uint32), ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


class _ThreadEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32),
        ("th32ThreadID", ctypes.c_uint32), ("th32OwnerProcessID", ctypes.c_uint32),
        ("tpBasePri", ctypes.c_int32), ("tpDeltaPri", ctypes.c_int32),
        ("dwFlags", ctypes.c_uint32),
    ]


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


class _BasicProcessIdList(ctypes.Structure):
    _fields_ = [
        ("NumberOfAssignedProcesses", ctypes.c_uint32),
        ("NumberOfProcessIdsInList", ctypes.c_uint32),
        ("ProcessIdList", ctypes.c_size_t * 1),
    ]


def _process_ids(query: Any, job_handle: Any) -> set[int]:
    prefix = _BasicProcessIdList.ProcessIdList.offset
    capacity = 16
    while capacity <= 4096:
        size = prefix + capacity * ctypes.sizeof(ctypes.c_size_t)
        buffer = ctypes.create_string_buffer(size)
        returned = ctypes.c_uint32()
        success = query(
            job_handle, _JOB_OBJECT_BASIC_PROCESS_ID_LIST,
            ctypes.byref(buffer), size, ctypes.byref(returned),
        )
        header = ctypes.cast(buffer, ctypes.POINTER(_BasicProcessIdList)).contents
        assigned = int(header.NumberOfAssignedProcesses)
        count = int(header.NumberOfProcessIdsInList)
        if count > capacity or assigned > capacity:
            capacity = min(4097, max(capacity * 2, count, assigned))
            continue
        if not success:
            raise SupervisorError("JOB_OBJECT_PID_QUERY_FAILED")
        values = (ctypes.c_size_t * count).from_address(ctypes.addressof(buffer) + prefix)
        return {int(values[index]) for index in range(count)}
    raise SupervisorError("JOB_OBJECT_PID_CAP_EXCEEDED")


def _active_count(query: Any, job_handle: Any) -> int:
    info = _BasicAccountingInformation()
    if not query(
        job_handle, _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
        ctypes.byref(info), ctypes.sizeof(info), None,
    ):
        raise SupervisorError("JOB_OBJECT_ACCOUNTING_QUERY_FAILED")
    return int(info.ActiveProcesses)


def _thread_id_for_process(snapshot_fn: Any, first_fn: Any, next_fn: Any, close_fn: Any, pid: int) -> int:
    snapshot = snapshot_fn(0x00000004, 0)  # TH32CS_SNAPTHREAD
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        raise SupervisorError("PRIMARY_THREAD_SNAPSHOT_FAILED")
    entry = _ThreadEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        success = first_fn(snapshot, ctypes.byref(entry))
        while success:
            if entry.th32OwnerProcessID == pid:
                return int(entry.th32ThreadID)
            success = next_fn(snapshot, ctypes.byref(entry))
    finally:
        close_fn(snapshot)
    raise SupervisorError("PRIMARY_THREAD_NOT_FOUND")


def _creation_time(open_process: Any, get_times: Any, close_fn: Any, pid: int) -> int:
    handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        raise SupervisorError("PROCESS_IDENTITY_UNAVAILABLE")
    created, exited, kernel, user = (_FileTime() for _ in range(4))
    try:
        if not get_times(
            handle, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel), ctypes.byref(user),
        ):
            raise SupervisorError("PROCESS_IDENTITY_QUERY_FAILED")
        return (int(created.high) << 32) | int(created.low)
    finally:
        close_fn(handle)


def _memory_for_pid(
    open_process: Any, get_memory: Any, close_fn: Any, pid: int,
) -> tuple[int, int, int]:
    handle = open_process(_PROCESS_QUERY_INFORMATION | _PROCESS_VM_READ, False, pid)
    if not handle:
        raise SupervisorError("PROCESS_MEMORY_ACCESS_DENIED")
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    try:
        if not get_memory(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
            raise SupervisorError("PROCESS_MEMORY_QUERY_FAILED")
        return (
            int(counters.WorkingSetSize), int(counters.PrivateUsage),
            int(counters.PeakWorkingSetSize),
        )
    finally:
        close_fn(handle)


def _launch_in_job(
    command: Sequence[str], api: tuple[Any, ...], *, cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
    confirm_child: Callable[[int, int], None],
) -> tuple[subprocess.Popen[bytes], Any, int, int]:
    (
        _kernel32, create_job, set_info, assign, query, terminate, close, open_thread,
        resume_thread, _ctrl, create_snapshot, thread_first, thread_next,
        _open_process, _get_times, _get_memory,
    ) = api
    job = create_job(None, None)
    if not job:
        raise SupervisorError("JOB_OBJECT_CREATE_FAILED")

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
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
    limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not set_info(
        job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits), ctypes.sizeof(limits),
    ):
        close(job)
        raise SupervisorError("JOB_OBJECT_CONFIGURATION_FAILED")

    process: subprocess.Popen[bytes] | None = None
    thread_handle: Any = None
    try:
        # Preserve standard console handles while excluding unrelated inheritable
        # handles. Suspended creation prevents work before Job Object assignment
        # and the durable child-process audit acknowledgement.
        process = subprocess.Popen(
            list(command), stdin=None, stdout=None, stderr=None,
            creationflags=_CREATE_SUSPENDED | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True, cwd=cwd,
            env=dict(environment) if environment is not None else None,
        )
        thread_id = _thread_id_for_process(
            create_snapshot, thread_first, thread_next, close, process.pid
        )
        thread_handle = open_thread(_THREAD_SUSPEND_RESUME, False, thread_id)
        if not thread_handle:
            raise SupervisorError("PRIMARY_THREAD_OPEN_FAILED")
        if not assign(job, int(process._handle)):
            raise SupervisorError("JOB_OBJECT_ASSIGNMENT_FAILED")
        if _active_count(query, job) != 1 or process.pid not in _process_ids(query, job):
            raise SupervisorError("ROOT_JOB_MEMBERSHIP_UNCONFIRMED")
        creation = _creation_time(_open_process, _get_times, close, process.pid)
        confirm_child(process.pid, creation)
        if resume_thread(thread_handle) == 0xFFFFFFFF:
            raise SupervisorError("PRIMARY_THREAD_RESUME_FAILED")
        return process, job, process.pid, creation
    except BaseException:
        try:
            terminate(job, 1)
        finally:
            if process is not None:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            close(job)
        raise
    finally:
        if thread_handle:
            close(thread_handle)


def _send_cooperative_cancel(api: tuple[Any, ...], process_group_id: int) -> bool:
    generate_ctrl = api[9]
    return bool(generate_ctrl(_CTRL_BREAK_EVENT, process_group_id))


def _terminate_job(api: tuple[Any, ...], job_handle: Any, exit_code: int = 0xE9) -> bool:
    return bool(api[5](job_handle, exit_code))


def _sample_tree(
    api: tuple[Any, ...], job_handle: Any, start_monotonic: float,
) -> tuple[ProcessSample, dict[tuple[int, int], tuple[int, int, int]]]:
    query, close, open_process, get_times, get_memory = api[4], api[6], api[13], api[14], api[15]
    pids = _process_ids(query, job_handle)
    if not pids:
        raise SupervisorError("PROCESS_TREE_EMPTY_DURING_SAMPLE")
    metrics: dict[tuple[int, int], tuple[int, int, int]] = {}
    for pid in sorted(pids):
        created = _creation_time(open_process, get_times, close, pid)
        metrics[(pid, created)] = _memory_for_pid(open_process, get_memory, close, pid)
    return ProcessSample(
        timestamp_utc=_utc_now(), elapsed_seconds=time.monotonic() - start_monotonic,
        process_count=len(metrics),
        working_set_bytes=sum(value[0] for value in metrics.values()),
        private_bytes=sum(value[1] for value in metrics.values()),
    ), metrics


def _tree_gone(api: tuple[Any, ...], job_handle: Any) -> bool:
    return _active_count(api[4], job_handle) == 0 and not _process_ids(api[4], job_handle)


def _wait_for_tree(api: tuple[Any, ...], process: subprocess.Popen[bytes], job_handle: Any, until: float) -> bool:
    while time.monotonic() < until:
        if process.poll() is not None and _tree_gone(api, job_handle):
            return True
        time.sleep(min(0.025, max(0.0, until - time.monotonic())))
    return process.poll() is not None and _tree_gone(api, job_handle)


def _rename_no_overwrite_durable(source: Path, destination: Path) -> None:
    if os.name != "nt":
        os.rename(source, destination)
        return
    move_file = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move_file.restype = ctypes.c_int
    # MOVEFILE_WRITE_THROUGH without REPLACE_EXISTING: the final name is
    # durable before its ledger attestation is committed.
    if not move_file(str(source), str(destination), 0x00000008):
        error = ctypes.get_last_error()
        raise OSError(error, "receipt rename failed")


def _write_no_overwrite_json(
    path: Path,
    payload: dict[str, object],
    *,
    before_rename: Callable[[bytes], None],
    after_rename: Callable[[bytes], None],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SupervisorError("RECEIPT_ALREADY_EXISTS")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = (json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # The durable ledger acknowledges these exact bytes before the final
        # receipt name becomes visible. Readers require both artifacts.
        before_rename(encoded)
        _rename_no_overwrite_durable(temporary, path)
        after_rename(encoded)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class WindowsCliSupervisor:
    """Supervise one CLI invocation as a Windows Job Object process tree."""

    def __init__(
        self,
        *,
        receipt_path: Path,
        cancel_event: threading.Event | None = None,
        require_tty: bool = True,
        max_working_set_bytes: int = MAX_WORKING_SET_BYTES,
        max_working_set_growth_bytes: int = MAX_WORKING_SET_GROWTH_BYTES,
        sample_interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
        baseline_window_seconds: float = BASELINE_WINDOW_SECONDS,
        cooperative_cancel_seconds: float = COOPERATIVE_CANCEL_SECONDS,
        tree_containment_seconds: float = TREE_CONTAINMENT_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        critical_audit_writer: Callable[..., Mapping[str, object]] | None = None,
        ledger_run_id: str | None = None,
    ) -> None:
        self.receipt_path = Path(receipt_path)
        self.cancel_event = cancel_event or threading.Event()
        self.require_tty = require_tty
        self.max_working_set_bytes = max_working_set_bytes
        self.max_working_set_growth_bytes = max_working_set_growth_bytes
        self.sample_interval_seconds = sample_interval_seconds
        self.baseline_window_seconds = baseline_window_seconds
        self.cooperative_cancel_seconds = cooperative_cancel_seconds
        self.tree_containment_seconds = tree_containment_seconds
        self.monotonic = monotonic
        self.sleep = sleep
        self.critical_audit_writer = critical_audit_writer
        self.ledger_run_id = ledger_run_id
        if (
            type(max_working_set_bytes) is not int or not 0 < max_working_set_bytes <= MAX_WORKING_SET_BYTES
            or type(max_working_set_growth_bytes) is not int or not 0 < max_working_set_growth_bytes <= MAX_WORKING_SET_GROWTH_BYTES
            or type(sample_interval_seconds) not in {int, float}
            or type(baseline_window_seconds) not in {int, float}
            or type(cooperative_cancel_seconds) not in {int, float}
            or type(tree_containment_seconds) not in {int, float}
            or not 0 < sample_interval_seconds <= SAMPLE_INTERVAL_SECONDS
            or sample_interval_seconds != SAMPLE_INTERVAL_SECONDS
            or not math.isfinite(baseline_window_seconds)
            or baseline_window_seconds != BASELINE_WINDOW_SECONDS
            or not math.isfinite(cooperative_cancel_seconds)
            or not math.isfinite(tree_containment_seconds)
            or cooperative_cancel_seconds < 0 or tree_containment_seconds <= 0
            or tree_containment_seconds > TREE_CONTAINMENT_SECONDS
            or cooperative_cancel_seconds > COOPERATIVE_CANCEL_SECONDS
        ):
            raise SupervisorError("SUPERVISOR_LIMIT_CONFIGURATION_INVALID")

    def run(
        self,
        command: Sequence[str],
        *,
        stage: str,
        baseline_prompt_ready: Callable[[], bool] | None = None,
        release_confirmation: Callable[[], None] | None = None,
        timeout_seconds: int | None = None,
        allow_message_limit_exit: bool = False,
        global_deadline_monotonic: float | None = None,
        global_started_monotonic: float | None = None,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        release_ledger_writer: Callable[[Mapping[str, object]], None] | None = None,
        readmit_ledger_writer: Callable[[Mapping[str, object]], None] | None = None,
    ) -> SupervisorResult:
        """Run a command without capturing standard streams or inventing CLI flags.

        Queue stages require a ready signal and a release callback. Integration
        observes the CLI's own TTY prompt, allows a two-second measurement
        window for the complete process tree, and only then releases the prompt
        so the application can read the user's answer. No CLI flag is added.
        """
        run_id = self.ledger_run_id or uuid.uuid4().hex
        if not _RUN_ID.fullmatch(run_id):
            run_id = uuid.uuid4().hex
        started = self.monotonic()
        wall_started = _utc_now()
        stage_name = "unknown"
        operation_deadline = started
        global_deadline = started
        api: tuple[Any, ...] | None = None
        process: subprocess.Popen[bytes] | None = None
        job_handle: Any = None
        pid: int | None = None
        creation: int | None = None
        memory = MemoryMonitor()
        samples_baseline_started: float | None = None
        prompt_window: list[ProcessSample] = []
        reason = "SUPERVISOR_EXCEPTION"
        process_exit: int | None = None
        result = "BLOCKED"
        tree_confirmed = False
        cooperative_signal_sent = False
        containment_attempted = False
        forced_termination = False
        process_identity: dict[int, int] = {}
        sample_failure: str | None = None
        memory_limit_exceeded = False
        timeout: int | None = None
        confirmation_released = False
        elapsed = 0.0
        audit_acknowledgements: list[dict[str, object]] = []
        audit_counter = 0
        critical_audit_gate = "PASS"
        receipt_attestation_event_id: str | None = None
        child_handoff: dict[str, object] | None = None
        parent_readmitted = False

        def event_id() -> str:
            nonlocal audit_counter
            audit_counter += 1
            return hashlib.sha256(
                f"{run_id}:{stage_name}:{audit_counter}".encode("ascii")
            ).hexdigest()[:32]

        def record_audit(
            event_type: str,
            details: Mapping[str, object],
            *,
            selected_event_id: str | None = None,
        ) -> str:
            nonlocal critical_audit_gate
            if self.critical_audit_writer is None:
                critical_audit_gate = "BLOCKED"
                raise SupervisorError("CRITICAL_AUDIT_UNAVAILABLE")
            current_event_id = selected_event_id or event_id()
            try:
                ack = self.critical_audit_writer(
                    event_type, details=dict(details), event_id=current_event_id,
                )
            except Exception:
                critical_audit_gate = "BLOCKED"
                raise SupervisorError("CRITICAL_AUDIT_ACK_FAILED") from None
            if (
                not isinstance(ack, Mapping)
                or ack.get("run_id") != run_id
                or ack.get("event_id") != current_event_id
                or type(ack.get("sequence")) is not int
                or ack.get("sequence", 0) < 1
                or not isinstance(ack.get("event_hash"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", str(ack.get("event_hash")))
            ):
                critical_audit_gate = "BLOCKED"
                raise SupervisorError("CRITICAL_AUDIT_ACK_INVALID")
            audit_acknowledgements.append(dict(ack))
            return current_event_id

        try:
            stage_name, timeout = _safe_stage(stage, timeout_seconds)
            if type(allow_message_limit_exit) is not bool or (
                allow_message_limit_exit and stage_name != "scan"
            ):
                raise SupervisorError("MESSAGE_LIMIT_EXIT_NOT_ALLOWED_FOR_STAGE")
            if stage_name not in {"queue_f", "queue_m"}:
                memory.baseline_status = "NOT_APPLICABLE_STAGE"
            if not command or any(not isinstance(arg, str) or "\x00" in arg for arg in command):
                raise SupervisorError("COMMAND_INVALID")
            if self.critical_audit_writer is None:
                raise SupervisorError("CRITICAL_AUDIT_UNAVAILABLE")
            if self.ledger_run_id is not None and not _RUN_ID.fullmatch(self.ledger_run_id):
                raise SupervisorError("CRITICAL_AUDIT_RUN_ID_INVALID")
            if self.receipt_path.exists():
                raise SupervisorError("RECEIPT_ALREADY_EXISTS")
            if self.require_tty and not all(
                getattr(stream, "isatty", lambda: False)()
                for stream in (sys.stdin, sys.stdout, sys.stderr)
            ):
                reason = "TTY_REQUIRED_BUT_UNAVAILABLE"
                raise SupervisorError(reason)
            if stage_name in {"queue_f", "queue_m"} and (
                baseline_prompt_ready is None or release_confirmation is None
            ):
                reason = "PRECONFIRMATION_PROMPT_SIGNAL_UNAVAILABLE"
                raise SupervisorError(reason)
            api = _windows_api()
            global_start = started if global_started_monotonic is None else global_started_monotonic
            configured_deadline = (
                global_start + GLOBAL_DEADLINE_SECONDS
                if global_deadline_monotonic is None else global_deadline_monotonic
            )
            if (
                type(global_start) not in {int, float}
                or type(configured_deadline) not in {int, float}
                or not math.isfinite(global_start)
                or not math.isfinite(configured_deadline)
                or global_start > started
                or configured_deadline > global_start + GLOBAL_DEADLINE_SECONDS
            ):
                reason = "GLOBAL_DEADLINE_INVALID"
                raise SupervisorError(reason)
            global_deadline = min(configured_deadline, global_start + GLOBAL_DEADLINE_SECONDS)
            operation_deadline = min(started + timeout, global_deadline)
            if operation_deadline <= started:
                reason = "GLOBAL_DEADLINE_EXCEEDED_BEFORE_LAUNCH"
                raise SupervisorError(reason)

            record_audit("RUN_INITIALIZED", {"stage": stage_name})
            record_audit("PREFLIGHT_CONFIRMED", {"stage": stage_name})
            record_audit("GATE_STARTED", {"stage": stage_name})

            def confirm_child(child_pid: int, child_creation: int) -> None:
                nonlocal child_handoff, critical_audit_gate
                child_event_id = record_audit("CHILD_PROCESS_CONFIRMED", {
                    "stage": stage_name, "pid": child_pid,
                    "process_creation_time": child_creation,
                })
                if release_ledger_writer is not None:
                    ack = audit_acknowledgements[-1]
                    child_handoff = {
                        "run_id": run_id,
                        "event_id": child_event_id,
                        "sequence": ack["sequence"],
                        "event_hash": ack["event_hash"],
                        "child_pid": child_pid,
                        "creation_time": child_creation,
                        "stage": stage_name,
                    }
                    try:
                        release_ledger_writer(dict(child_handoff))
                    except Exception:
                        critical_audit_gate = "BLOCKED"
                        raise SupervisorError("LEDGER_WRITER_RELEASE_FAILED") from None

            process, job_handle, pid, creation = _launch_in_job(
                command, api, cwd=cwd, environment=environment,
                confirm_child=confirm_child,
            )
            process_identity[pid] = creation
            reason = "PROCESS_RUNNING"
            last_sample_at = 0.0
            while True:
                now = self.monotonic()
                exit_value = process.poll()
                try:
                    current_ids = _process_ids(api[4], job_handle)
                    for active_pid in current_ids:
                        process_identity.setdefault(
                            active_pid,
                            _creation_time(api[13], api[14], api[6], active_pid),
                        )
                except SupervisorError as error:
                    sample_failure = error.reason
                    reason = "PROCESS_TREE_OBSERVATION_FAILED"
                    break

                if exit_value is not None and not current_ids:
                    process_exit = exit_value
                    reason = "PROCESS_EXITED"
                    break

                if now - last_sample_at >= self.sample_interval_seconds:
                    try:
                        sample, metrics = _sample_tree(api, job_handle, started)
                        memory.add(sample, metrics)
                        last_sample_at = self.monotonic()
                        if memory.peak_sum_process_working_set_bytes > self.max_working_set_bytes:
                            memory_limit_exceeded = True
                            reason = "WORKING_SET_LIMIT_EXCEEDED"
                            break
                        if memory.baseline_ready and (
                            memory.peak_after_baseline_working_set_bytes
                            > memory.baseline_working_set_bytes + self.max_working_set_growth_bytes
                        ):
                            memory_limit_exceeded = True
                            reason = "WORKING_SET_GROWTH_LIMIT_EXCEEDED"
                            break
                    except SupervisorError as error:
                        sample_failure = error.reason
                        reason = "MEMORY_MONITORING_FAILED"
                        break

                if stage_name in {"queue_f", "queue_m"} and not memory.baseline_ready:
                    if baseline_prompt_ready():
                        samples_baseline_started = now
                        prompt_window = []
                        # This interval starts only after the integration's
                        # explicit pre-confirmation prompt signal.
                        while self.monotonic() - samples_baseline_started < self.baseline_window_seconds:
                            if process.poll() is not None:
                                break
                            now = self.monotonic()
                            if now >= operation_deadline:
                                break
                            if self.monotonic() - last_sample_at >= self.sample_interval_seconds:
                                try:
                                    sample, metrics = _sample_tree(api, job_handle, started)
                                    memory.add(sample, metrics)
                                    prompt_window.append(sample)
                                    last_sample_at = self.monotonic()
                                    if memory.peak_sum_process_working_set_bytes > self.max_working_set_bytes:
                                        memory_limit_exceeded = True
                                        reason = "WORKING_SET_LIMIT_EXCEEDED"
                                        break
                                except SupervisorError as error:
                                    sample_failure = error.reason
                                    reason = "MEMORY_MONITORING_FAILED"
                                    break
                            self.sleep(min(
                                self.sample_interval_seconds,
                                max(0.0, self.baseline_window_seconds - (self.monotonic() - samples_baseline_started)),
                            ))
                        if memory_limit_exceeded or sample_failure:
                            break
                        if self.monotonic() - samples_baseline_started >= self.baseline_window_seconds:
                            memory.baseline(prompt_window)
                            try:
                                release_confirmation()
                                confirmation_released = True
                            except Exception:
                                reason = "PRECONFIRMATION_RELEASE_FAILED"
                                sample_failure = reason
                                break
                        else:
                            memory.baseline_status = "BLOCKED_PROMPT_WINDOW_INCOMPLETE"

                if self.cancel_event.is_set():
                    reason = "USER_CANCELLATION_REQUESTED"
                    break
                if now >= global_deadline:
                    reason = "GLOBAL_DEADLINE_EXCEEDED"
                    break
                if now >= operation_deadline:
                    reason = (
                        "PRECONFIRMATION_PROMPT_NOT_OBSERVED"
                        if stage_name in {"queue_f", "queue_m"} and not memory.baseline_ready
                        else "STAGE_TIMEOUT"
                    )
                    break
                if exit_value is not None:
                    process_exit = exit_value
                    if not current_ids:
                        reason = "PROCESS_EXITED"
                        break
                    reason = "DESCENDANT_REMAINS_AFTER_ROOT_EXIT"
                    break
                self.sleep(min(
                    self.sample_interval_seconds,
                    max(0.0, min(operation_deadline, global_deadline) - now),
                ))

            containment_started = self.monotonic()
            if reason not in {"PROCESS_EXITED"} and process is not None and job_handle is not None:
                try:
                    cooperative_signal_sent = _send_cooperative_cancel(api, process.pid)
                except BaseException:
                    cooperative_signal_sent = False
                cooperative_until = min(
                    containment_started + self.cooperative_cancel_seconds,
                    containment_started + self.tree_containment_seconds,
                )
                if cooperative_signal_sent:
                    tree_confirmed = _wait_for_tree(api, process, job_handle, cooperative_until)
                if not tree_confirmed:
                    containment_attempted = True
                    forced_termination = _terminate_job(api, job_handle)
                    hard_until = containment_started + self.tree_containment_seconds
                    tree_confirmed = _wait_for_tree(api, process, job_handle, hard_until)
                if not tree_confirmed:
                    reason = "PROCESS_TREE_CONTAINMENT_UNCONFIRMED"
                elif forced_termination:
                    reason = reason if reason != "DESCENDANT_REMAINS_AFTER_ROOT_EXIT" else "ORPHAN_DESCENDANT_TERMINATED"

            if process is not None:
                process_exit = process.poll()
                if process_exit is not None and job_handle is not None:
                    try:
                        tree_confirmed = _tree_gone(api, job_handle)
                    except SupervisorError:
                        tree_confirmed = False
                if not tree_confirmed and process.poll() is not None and job_handle is not None:
                    # Normal root exit still needs whole-tree reconciliation.
                    try:
                        if _tree_gone(api, job_handle):
                            tree_confirmed = True
                        else:
                            containment_attempted = True
                            _terminate_job(api, job_handle)
                            tree_confirmed = _wait_for_tree(
                                api, process, job_handle,
                                self.monotonic() + max(0.0, self.tree_containment_seconds - (self.monotonic() - containment_started)),
                            )
                    except SupervisorError:
                        tree_confirmed = False

            process_exit = process.poll() if process is not None else None
            elapsed = self.monotonic() - started
            if not tree_confirmed:
                result = "BLOCKED"
                reason = "PROCESS_TREE_CONTAINMENT_UNCONFIRMED"
            elif reason == "PROCESS_EXITED" and process_exit == 0:
                result = "COMPLETED"
            elif (
                reason == "PROCESS_EXITED" and stage_name == "scan"
                and allow_message_limit_exit and process_exit == 4
            ):
                result = "COMPLETED"
                reason = "EXPECTED_MESSAGE_LIMIT_EXIT"
            elif reason == "PROCESS_EXITED":
                result = "FAILED"
                reason = "CHILD_EXIT_NONZERO"
            elif reason in {"STAGE_TIMEOUT", "GLOBAL_DEADLINE_EXCEEDED"}:
                result = "TIMED_OUT"
            elif reason == "USER_CANCELLATION_REQUESTED":
                result = "CANCELLED"
            elif reason in {"WORKING_SET_LIMIT_EXCEEDED", "WORKING_SET_GROWTH_LIMIT_EXCEEDED"}:
                result = "BLOCKED"
            elif reason == "DESCENDANT_REMAINS_AFTER_ROOT_EXIT":
                result = "BLOCKED"
            elif reason == "PROCESS_TREE_OBSERVATION_FAILED" or reason == "MEMORY_MONITORING_FAILED":
                result = "BLOCKED"
            else:
                result = "BLOCKED"

            if stage_name in {"queue_f", "queue_m"} and memory.baseline_status != "PASS_PROMPT_SIGNAL_AND_TWO_SECOND_WINDOW" and result == "COMPLETED":
                # Do not turn a zero exit into proof of the pre-confirmation
                # memory gate. The operation can complete, but the gate is held.
                result = "BLOCKED"
                reason = "L14_PRECONFIRMATION_BASELINE_NOT_PROVEN"
            if sample_failure:
                result = "BLOCKED"
                reason = "MEMORY_OR_PROCESS_METRIC_UNAVAILABLE"

            if job_handle is not None:
                api[6](job_handle)
                job_handle = None

        except SupervisorError as error:
            reason = error.reason
            result = "BLOCKED"
            elapsed = self.monotonic() - started
            if process is not None and job_handle is not None and api is not None:
                try:
                    containment_attempted = True
                    _terminate_job(api, job_handle)
                    tree_confirmed = _wait_for_tree(
                        api, process, job_handle,
                        self.monotonic() + self.tree_containment_seconds,
                    )
                    process_exit = process.poll()
                except BaseException:
                    tree_confirmed = False
            if job_handle is not None and api is not None:
                try:
                    api[6](job_handle)
                except BaseException:
                    pass
                job_handle = None
        except Exception:
            reason = "SUPERVISOR_INTERNAL_FAILURE"
            result = "BLOCKED"
            elapsed = self.monotonic() - started
            if process is not None and job_handle is not None and api is not None:
                try:
                    containment_attempted = True
                    _terminate_job(api, job_handle)
                    tree_confirmed = _wait_for_tree(
                        api, process, job_handle,
                        self.monotonic() + self.tree_containment_seconds,
                    )
                    process_exit = process.poll()
                except BaseException:
                    tree_confirmed = False
            if job_handle is not None and api is not None:
                try:
                    api[6](job_handle)
                except BaseException:
                    pass
                job_handle = None
        except KeyboardInterrupt:
            reason = "USER_CANCELLATION_REQUESTED"
            result = "CANCELLED"
            elapsed = self.monotonic() - started
            if process is not None and job_handle is not None and api is not None:
                try:
                    cooperative_signal_sent = _send_cooperative_cancel(api, process.pid)
                    stop_at = self.monotonic() + self.cooperative_cancel_seconds
                    if cooperative_signal_sent:
                        tree_confirmed = _wait_for_tree(api, process, job_handle, stop_at)
                    if not tree_confirmed:
                        containment_attempted = True
                        forced_termination = _terminate_job(api, job_handle)
                        tree_confirmed = _wait_for_tree(
                            api, process, job_handle,
                            self.monotonic() + self.tree_containment_seconds,
                        )
                    process_exit = process.poll()
                except BaseException:
                    tree_confirmed = False
            if job_handle is not None and api is not None:
                try:
                    api[6](job_handle)
                except BaseException:
                    pass
                job_handle = None

        if child_handoff is not None:
            if process_exit is not None and tree_confirmed and readmit_ledger_writer is not None:
                try:
                    readmit_ledger_writer(dict(child_handoff))
                    parent_readmitted = True
                except Exception:
                    critical_audit_gate = "BLOCKED"
                    result = "BLOCKED"
                    reason = "LEDGER_WRITER_READMISSION_FAILED"
            else:
                critical_audit_gate = "BLOCKED"
                result = "BLOCKED"
                reason = "PROCESS_TREE_NOT_CONFIRMED_FOR_LEDGER_READMISSION"

        memory_gate = "PASS" if (
            bool(memory.samples)
            and sample_failure is None
            and (stage_name not in {"queue_f", "queue_m"} or memory.baseline_ready)
            and (not memory_limit_exceeded or tree_confirmed)
        ) else "BLOCKED"
        elapsed = self.monotonic() - started
        process_gate = "PASS" if tree_confirmed and process_exit is not None else "BLOCKED"
        acceptable_process_exit = process_exit == 0 or (
            stage_name == "scan" and allow_message_limit_exit and process_exit == 4
        )
        supervisor_gate = "PASS" if (
            result == "COMPLETED" and acceptable_process_exit and process_gate == "PASS"
            and memory_gate == "PASS"
        ) else "BLOCKED"
        if self.critical_audit_writer is not None and (
            child_handoff is None or parent_readmitted
        ):
            try:
                if reason == "USER_CANCELLATION_REQUESTED":
                    record_audit("RUN_CANCELLED", {
                        "stage": stage_name, "tree_confirmed": tree_confirmed,
                    })
                if reason in {
                    "STAGE_TIMEOUT", "GLOBAL_DEADLINE_EXCEEDED",
                    "GLOBAL_DEADLINE_EXCEEDED_BEFORE_LAUNCH",
                }:
                    record_audit("PROCESS_TIMEOUT", {
                        "stage": stage_name, "tree_confirmed": tree_confirmed,
                    })
                if containment_attempted or (process is not None and not tree_confirmed):
                    record_audit("PROCESS_CONTAINMENT", {
                        "stage": stage_name, "tree_confirmed": tree_confirmed,
                    })
                record_audit("SUPERVISOR_RUN_FINISHED", {
                    "stage": stage_name, "result": result,
                    "exit_code": process_exit, "tree_confirmed": tree_confirmed,
                })
            except SupervisorError:
                result = "BLOCKED"
                reason = "CRITICAL_AUDIT_ACK_FAILED"
                critical_audit_gate = "BLOCKED"
                supervisor_gate = "BLOCKED"
        receipt: dict[str, object] = {
            "schema": "telegram-courses-s9-supervisor-receipt-v1",
            "run_id": run_id,
            "stage": stage_name,
            "started_at_utc": wall_started,
            "finished_at_utc": _utc_now(),
            "result": result,
            "reason": reason,
            "external_exit_code": process_exit,
            "message_limit_exit_allowed": allow_message_limit_exit,
            "pid": pid,
            "process_creation_filetime": creation,
            "observed_process_identities": [
                {"pid": process_id, "creation_filetime": created}
                for process_id, created in sorted(process_identity.items())
            ],
            "process_tree_termination_confirmed": tree_confirmed,
            "cooperative_cancel_signal_sent": cooperative_signal_sent,
            "hard_containment_attempted": containment_attempted,
            "hard_containment_sent": forced_termination,
            "elapsed_seconds": round(elapsed, 6),
            "stage_timeout_seconds": timeout_seconds or STAGE_TIMEOUTS_SECONDS.get(stage_name),
            "operation_deadline_monotonic": operation_deadline,
            "global_deadline_monotonic": global_deadline,
            "limit_check_result": (
                "PASS"
                if stage_name in {"queue_f", "queue_m"}
                and confirmation_released
                and memory.baseline_ready
                else "UNKNOWN"
            ),
            "ledger_run_id": run_id,
            "critical_audit_gate": critical_audit_gate,
            "critical_audit_acknowledgements": audit_acknowledgements,
            "receipt_attestation_event_id": None,
            "supervisor_offline_gate": supervisor_gate,
            "process_control_offline_gate": process_gate,
            "memory_monitoring_offline_gate": memory_gate,
            "tty_required": self.require_tty,
            "tty_available": all(
                getattr(stream, "isatty", lambda: False)()
                for stream in (sys.stdin, sys.stdout, sys.stderr)
            ),
            "preconfirmation_prompt_signal_available": baseline_prompt_ready is not None,
            "preconfirmation_release_callback_available": release_confirmation is not None,
            "preconfirmation_confirmation_released": confirmation_released,
            "memory": memory.receipt(),
            "metric_failure_reason": sample_failure,
            "command_recorded": False,
            "network_observation": "NOT_INSTRUMENTED_BY_SUPERVISOR",
        }
        persisted = False
        receipt_created = False
        receipt_attested = False
        if critical_audit_gate == "PASS":
            receipt_prepared_event_id = event_id()
            receipt_attestation_event_id = event_id()
            receipt["receipt_prepared_event_id"] = receipt_prepared_event_id
            receipt["receipt_attestation_event_id"] = receipt_attestation_event_id

            def prepare_receipt(encoded: bytes) -> None:
                digest = hashlib.sha256(encoded).hexdigest()
                record_audit(
                    "RECEIPT_PREPARED", {"receipt_sha256": digest},
                    selected_event_id=receipt_prepared_event_id,
                )

            def attest_receipt(encoded: bytes) -> None:
                nonlocal receipt_attested, receipt_created
                receipt_created = True
                digest = hashlib.sha256(encoded).hexdigest()
                record_audit(
                    "RECEIPT_PERSISTED", {"receipt_sha256": digest},
                    selected_event_id=receipt_attestation_event_id,
                )
                receipt_attested = True

            try:
                _write_no_overwrite_json(
                    self.receipt_path, receipt, before_rename=prepare_receipt,
                    after_rename=attest_receipt,
                )
                persisted = True
            except (OSError, SupervisorError) as error:
                persisted = receipt_created
                result = "BLOCKED"
                reason = (
                    error.reason
                    if isinstance(error, SupervisorError)
                    and error.reason == "RECEIPT_ALREADY_EXISTS"
                    else "RECEIPT_PERSISTENCE_FAILED"
                )
                supervisor_gate = "BLOCKED"
                receipt_attested = False
        else:
            result = "BLOCKED"
            supervisor_gate = "BLOCKED"
        return SupervisorResult(
            run_id=run_id, result=result, reason=reason, exit_code=process_exit,
            receipt_path=self.receipt_path, receipt_persisted=persisted,
            supervisor_gate=supervisor_gate, process_control_gate=process_gate,
            memory_monitoring_gate=memory_gate,
            limit_check_result=(
                "PASS"
                if stage_name in {"queue_f", "queue_m"}
                and confirmation_released
                and memory.baseline_ready
                else "UNKNOWN"
            ),
            critical_audit_gate=critical_audit_gate,
            receipt_attested=receipt_attested,
        )


__all__ = [
    "BASELINE_WINDOW_SECONDS", "GLOBAL_DEADLINE_SECONDS", "MAX_WORKING_SET_BYTES",
    "MAX_WORKING_SET_GROWTH_BYTES", "MemoryMonitor", "ProcessSample", "STAGE_TIMEOUTS_SECONDS",
    "SupervisorError", "SupervisorResult", "WindowsCliSupervisor",
]
