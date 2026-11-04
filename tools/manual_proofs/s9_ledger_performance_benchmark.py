"""Synthetic, ledger-only S9 performance benchmark.

This utility measures the ledger accounting path. It does not run the CLI,
gateway, Telegram RPCs, or media downloads, and must not be reported as the
contractual 1 GiB CLI E2E gate.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import statistics
import sys
import time
import uuid
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from telegram_courses import s9_operational_ledger as ledger_module  # noqa: E402, I001


MIB = 1024 * 1024
GIB = 1024 * MIB
CHUNK_BYTES = 256 * 1024
DEFAULT_OUTPUT_ROOT = Path(
    r"C:\Users\walac\.codex\visualizations\2026\11\01"
    r"\01a194e1-c732-70c0-8413-665ce643a367"
)
FILE_SAMPLE_EVERY_COMMITS = 128


class _ProcessIoCounters(ctypes.Structure):
    _fields_ = [
        ("read_operation_count", ctypes.c_ulonglong),
        ("write_operation_count", ctypes.c_ulonglong),
        ("other_operation_count", ctypes.c_ulonglong),
        ("read_transfer_count", ctypes.c_ulonglong),
        ("write_transfer_count", ctypes.c_ulonglong),
        ("other_transfer_count", ctypes.c_ulonglong),
    ]


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("page_fault_count", wintypes.DWORD),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_nonpaged_pool_usage", ctypes.c_size_t),
        ("quota_nonpaged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
        ("private_usage", ctypes.c_size_t),
    ]


class _WindowsMeasurements:
    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("This benchmark requires Windows process counters.")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        self._kernel32.GetProcessIoCounters.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ProcessIoCounters),
        ]
        self._kernel32.GetProcessIoCounters.restype = wintypes.BOOL
        self._psapi = ctypes.WinDLL("psapi", use_last_error=True)
        self._psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ProcessMemoryCountersEx),
            wintypes.DWORD,
        ]
        self._psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        self._handle = self._kernel32.GetCurrentProcess()

    def io_counters(self) -> _ProcessIoCounters:
        counters = _ProcessIoCounters()
        if not self._kernel32.GetProcessIoCounters(
            self._handle,
            ctypes.byref(counters),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters

    def memory_counters(self) -> _ProcessMemoryCountersEx:
        counters = _ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        if not self._psapi.GetProcessMemoryInfo(
            self._handle,
            ctypes.byref(counters),
            counters.cb,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters


def _percentile_ms(samples: list[float], percentile: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index] * 1000, 4)


def _timing_summary(samples: list[float]) -> dict[str, int | float | None]:
    return {
        "count": len(samples),
        "avg_ms": round(statistics.mean(samples) * 1000, 4) if samples else None,
        "p95_ms": _percentile_ms(samples, 0.95),
        "total_ms": round(sum(samples) * 1000, 4),
    }


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _new_metrics(db_path: Path) -> dict[str, Any]:
    return {
        "db_path": db_path,
        "wal_path": db_path.with_name(db_path.name + "-wal"),
        "reserve_seconds": [],
        "settle_seconds": [],
        "commit_seconds": [],
        "validation_seconds": [],
        "fresh_replay_seconds": [],
        "commit_count": 0,
        "db_bytes_peak_sampled": 0,
        "wal_bytes_peak_sampled": 0,
        "working_set_bytes_peak_sampled": 0,
    }


def _timed_method(
    samples: Callable[[], list[float]],
    method: Callable[..., Any],
) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return method(*args, **kwargs)
        finally:
            samples().append(time.perf_counter() - started)

    return wrapped


def _run_case(
    label: str,
    total_bytes: int,
    profile: str,
    media_count: int,
    metrics: dict[str, Any],
    output_root: Path,
    process: _WindowsMeasurements,
) -> dict[str, Any]:
    run_root = output_root / label
    run_root.mkdir()
    directory_guard = ledger_module._create_private_directory(
        run_root / "ledger-private",
    )
    db_path = directory_guard.path / "operational-ledger.sqlite3"
    directory_guard.close()

    if metrics["db_path"] != db_path:
        raise RuntimeError("Instrumentation paths do not match the case ledger.")
    io_start = process.io_counters()
    memory_start = process.memory_counters()
    cpu_start = time.process_time()
    total_started = time.perf_counter()
    ledger = ledger_module.S9OperationalLedger.create(db_path)

    connection = ledger._epoch.connection
    if connection is None:
        raise RuntimeError("Writer connection was not opened.")
    journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
    if journal_mode != "wal" or synchronous != 2:
        raise RuntimeError(
            f"Ledger PRAGMAs differ from the contract: journal={journal_mode}, "
            f"synchronous={synchronous}."
        )

    deadline_ns = ledger.start_global_deadline(3600)
    aliases = [
        ledger.register_media(
            f"synthetic-ledger-benchmark:{label}:{index}",
            profile=profile,
            expected_bytes=total_bytes // media_count,
            fresh=True,
        )
        for index in range(media_count)
    ]
    ledger.update_execution(
        gate="G5",
        status="RUNNING",
        elapsed_ms=0,
        deadline_ns=deadline_ns,
        process_state="RUNNING",
        result="PASS",
    )
    for alias in aliases:
        ledger.begin_attempt(alias)

    hot_started = time.perf_counter()
    blocks = total_bytes // CHUNK_BYTES
    for block_index in range(blocks):
        alias = aliases[block_index % media_count]
        amount = min(CHUNK_BYTES, total_bytes - block_index * CHUNK_BYTES)
        reservation_id = ledger.reserve_bytes(alias, amount)
        ledger.settle_bytes(
            reservation_id,
            observed=amount,
            measurement_source="SYNTHETIC_TEST",
        )
        if (block_index + 1) % 1024 == 0:
            print(
                json.dumps(
                    {
                        "event": "blocks_completed",
                        "case": label,
                        "blocks": block_index + 1,
                        "bytes": min((block_index + 1) * CHUNK_BYTES, total_bytes),
                    }
                ),
                flush=True,
            )
        if (block_index + 1) % 128 == 0:
            memory = process.memory_counters()
            metrics["working_set_bytes_peak_sampled"] = max(
                metrics["working_set_bytes_peak_sampled"],
                int(memory.working_set_size),
            )
    hot_finished = time.perf_counter()

    elapsed_ms = int((hot_finished - total_started) * 1000)
    ledger.update_execution(
        gate="G5",
        status="RUNNING",
        elapsed_ms=elapsed_ms,
        deadline_ns=deadline_ns,
        process_state="RUNNING",
        result="PASS",
        observed_bytes=total_bytes,
    )
    before_checkpoint = ledger.snapshot()
    checkpoint_started = time.perf_counter()
    ledger.checkpoint()
    checkpoint_finished = time.perf_counter()
    ledger.close()

    reopen_started = time.perf_counter()
    reopened = ledger_module.S9OperationalLedger(db_path)
    reopened_snapshot = reopened.snapshot()
    connection = reopened._epoch.connection
    if connection is None:
        raise RuntimeError("Fresh replay did not reopen a writer connection.")
    integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
    foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    final_journal_mode = str(
        connection.execute("PRAGMA journal_mode").fetchone()[0]
    ).lower()
    final_synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
    reopened.close()
    finished = time.perf_counter()

    metrics["db_bytes_peak_sampled"] = max(
        metrics["db_bytes_peak_sampled"],
        _size(db_path),
    )
    metrics["wal_bytes_peak_sampled"] = max(
        metrics["wal_bytes_peak_sampled"],
        _size(db_path.with_name(db_path.name + "-wal")),
    )
    memory_end = process.memory_counters()
    io_end = process.io_counters()
    cpu_end = time.process_time()

    budget = reopened_snapshot["budgets"][profile]
    event_count = int(reopened_snapshot["critical_audit"]["event_count"])
    expected_event_count = 4 + 2 * media_count + 2 * blocks
    accounting_exact = (
        int(budget["observed"]) == total_bytes
        and int(budget["reserved"]) == 0
        and int(budget["uncertain"]) == 0
        and int(before_checkpoint["budgets"][profile]["observed"]) == total_bytes
    )
    checks_pass = (
        integrity_rows == [("ok",)]
        and not foreign_key_rows
        and not reopened_snapshot["critical_audit"]["quarantined"]
        and final_journal_mode == "wal"
        and final_synchronous == 2
        and event_count == expected_event_count
    )

    result = {
        "case": label,
        "scope": "LEDGER_ONLY_SYNTHETIC_NOT_CLI_E2E",
        "profile": profile,
        "bytes": total_bytes,
        "blocks_256KiB": blocks,
        "media_count": media_count,
        "audit_event_count": event_count,
        "audit_event_count_expected": expected_event_count,
        "elapsed_seconds_total_including_setup_and_final_replay": round(
            finished - total_started,
            4,
        ),
        "elapsed_seconds_hot_path": round(hot_finished - hot_started, 4),
        "throughput_MiB_per_second_hot_path": round(
            (total_bytes / MIB) / (hot_finished - hot_started),
            4,
        ),
        "operation_timings": {
            "reserve": _timing_summary(metrics["reserve_seconds"]),
            "settle": _timing_summary(metrics["settle_seconds"]),
            "commit_including_synchronous_FULL": _timing_summary(
                metrics["commit_seconds"],
            ),
            "full_validation": _timing_summary(metrics["validation_seconds"]),
        },
        "checkpoint_timings_seconds": [
            round(value, 4) for value in metrics["fresh_replay_seconds"]
        ],
        "explicit_checkpoint_and_reopen_seconds": {
            "checkpoint": round(checkpoint_finished - checkpoint_started, 4),
            "reopen_and_integrity": round(finished - reopen_started, 4),
        },
        "cpu_seconds_process": round(cpu_end - cpu_start, 4),
        "working_set_bytes": {
            "at_start": int(memory_start.working_set_size),
            "at_end": int(memory_end.working_set_size),
            "peak_sampled_during_hot_path": metrics["working_set_bytes_peak_sampled"],
            "sampling_interval_blocks": 128,
        },
        "process_write_transfer_bytes": (
            int(io_end.write_transfer_count - io_start.write_transfer_count)
        ),
        "process_write_transfer_scope": "whole Python process; not SQLite-only",
        "sqlite_file_sizes_bytes": {
            "database_final": _size(db_path),
            "wal_final": _size(db_path.with_name(db_path.name + "-wal")),
            "database_high_water_sampled": metrics["db_bytes_peak_sampled"],
            "wal_high_water_sampled_after_commits": metrics["wal_bytes_peak_sampled"],
            "high_water_sampling_interval_commits": FILE_SAMPLE_EVERY_COMMITS,
        },
        "journal_mode": final_journal_mode,
        "synchronous_pragma": final_synchronous,
        "commit_timing_note": (
            "The measured SQLite COMMIT duration includes synchronous=FULL behavior; "
            "a separate physical fsync duration is not exposed by this harness."
        ),
        "accounting": {
            "expected_bytes": total_bytes,
            "observed_bytes": int(budget["observed"]),
            "reserved_bytes": int(budget["reserved"]),
            "uncertain_bytes": int(budget["uncertain"]),
            "exact": accounting_exact,
        },
        "integrity_check": integrity_rows,
        "foreign_key_check_row_count": len(foreign_key_rows),
        "quarantined": bool(reopened_snapshot["critical_audit"]["quarantined"]),
        "acceptance": "PASS" if accounting_exact and checks_pass else "FAIL",
    }
    if not accounting_exact or not checks_pass:
        raise RuntimeError(json.dumps(result, indent=2))
    return result


def _install_instrumentation(
    metrics_ref: dict[str, Any],
    process: _WindowsMeasurements,
) -> Callable[[], None]:
    originals: dict[str, Any] = {
        "commit": ledger_module._commit_durable,
        "validate": ledger_module.S9OperationalLedger._validate,
        "fresh_replay": ledger_module.S9OperationalLedger._fresh_replay,
        "reserve": ledger_module.S9OperationalLedger.reserve_bytes,
        "settle": ledger_module.S9OperationalLedger.settle_bytes,
    }

    def commit(db: Any) -> None:
        started = time.perf_counter()
        try:
            originals["commit"](db)
        finally:
            metrics_ref["commit_seconds"].append(time.perf_counter() - started)
            metrics_ref["commit_count"] += 1
            if metrics_ref["commit_count"] % FILE_SAMPLE_EVERY_COMMITS == 0:
                metrics_ref["db_bytes_peak_sampled"] = max(
                    metrics_ref["db_bytes_peak_sampled"],
                    _size(metrics_ref["db_path"]),
                )
                metrics_ref["wal_bytes_peak_sampled"] = max(
                    metrics_ref["wal_bytes_peak_sampled"],
                    _size(metrics_ref["wal_path"]),
                )
                memory = process.memory_counters()
                metrics_ref["working_set_bytes_peak_sampled"] = max(
                    metrics_ref["working_set_bytes_peak_sampled"],
                    int(memory.working_set_size),
                )

    def validate(db: Any) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            return originals["validate"](db)
        finally:
            metrics_ref["validation_seconds"].append(time.perf_counter() - started)

    def fresh_replay(self: Any) -> None:
        started = time.perf_counter()
        try:
            originals["fresh_replay"](self)
        finally:
            metrics_ref["fresh_replay_seconds"].append(
                time.perf_counter() - started,
            )

    ledger_module._commit_durable = commit
    ledger_module.S9OperationalLedger._validate = staticmethod(validate)
    ledger_module.S9OperationalLedger._fresh_replay = fresh_replay
    ledger_module.S9OperationalLedger.reserve_bytes = _timed_method(
        lambda: metrics_ref["reserve_seconds"],
        originals["reserve"],
    )
    ledger_module.S9OperationalLedger.settle_bytes = _timed_method(
        lambda: metrics_ref["settle_seconds"],
        originals["settle"],
    )

    def restore() -> None:
        ledger_module._commit_durable = originals["commit"]
        ledger_module.S9OperationalLedger._validate = staticmethod(
            originals["validate"],
        )
        ledger_module.S9OperationalLedger._fresh_replay = originals["fresh_replay"]
        ledger_module.S9OperationalLedger.reserve_bytes = originals["reserve"]
        ledger_module.S9OperationalLedger.settle_bytes = originals["settle"]

    return restore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Approved writable location outside the repository for synthetic ledgers.",
    )
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This Windows S9 ledger benchmark requires Windows.")
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if output_root == REPO_ROOT or REPO_ROOT in output_root.parents:
        parser.error("Benchmark output must be outside the repository checkout.")
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_root = output_root / f"s9-ledger-perf-{run_id}"
    run_root.mkdir()
    process = _WindowsMeasurements()
    active: dict[str, Any] = {}
    restore = _install_instrumentation(active, process)
    cases = [
        ("64_MiB_F", 64 * MIB, "F", 1),
        ("256_MiB_F", 256 * MIB, "F", 2),
        ("1_GiB_M", GIB, "M", 1),
    ]
    results = []
    try:
        for label, size, profile, media_count in cases:
            case_root = run_root / label
            db_path = case_root / "ledger-private" / "operational-ledger.sqlite3"
            active.clear()
            active.update(_new_metrics(db_path))
            print(
                json.dumps({"event": "case_started", "case": label}),
                flush=True,
            )
            result = _run_case(
                label,
                size,
                profile,
                media_count,
                active,
                run_root,
                process,
            )
            result["ledger_directory"] = str(case_root / "ledger-private")
            results.append(result)
            print(
                json.dumps(
                    {
                        "event": "case_completed",
                        "case": label,
                        "hot_path_seconds": result["elapsed_seconds_hot_path"],
                        "acceptance": result["acceptance"],
                    }
                ),
                flush=True,
            )
    finally:
        restore()

    report = {
        "schema": "s9-ledger-only-performance-observation-v1",
        "run_directory": str(run_root),
        "scope": "LEDGER_ONLY_SYNTHETIC_NOT_CLI_E2E",
        "chunk_bytes": CHUNK_BYTES,
        "cases": results,
    }
    report_path = run_root / "results.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"event": "report_written", "path": str(report_path)}), flush=True)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
