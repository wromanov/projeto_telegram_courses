"""Run an offline, bounded two-process proof of the frozen S6 resume path."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CHANNEL_ID = -1002758699600
MESSAGE_ID = 598
MEDIA_ORDINAL = 0
MEDIA_KIND = "DOCUMENT"
TELEGRAM_MEDIA_ID = "5175124468544046445"
EXPECTED_BYTES = 11_649_955
MEDIA_ITEM_ID = 5
HISTORICAL_SHA256_CANDIDATE = "3bfe15fabb50cd47ddc2b40aa06881bf5a17faff6bb5729c2e34d38ef1edd5c4"
PREFIX_BYTES = 1_048_699
WIRE_OFFSET = 1_048_576
OVERLAP_BYTES = 123
REQUEST_BYTES = 256 * 1024
MAX_TRANSFER_BYTES = 13_369_344
MAX_GETFILE_REQUESTS = 51
MAX_GETFILEHASHES_REQUESTS = 16
HASH_PROBE_OFFSET = 11_534_336
HASH_PROBE_MAX_CALLS = 2
HASH_PROBE_MAX_GETFILE_CALLS = 0
HASH_PROBE_MAX_MEDIA_PAYLOAD_BYTES = 0
WORKERS = 1
MAX_MEDIA_ITEMS = 1

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


@dataclass(frozen=True)
class SafetyPreflight:
    getfile_cap: int
    getfile_payload_cap: int
    getfilehashes_cap: int
    request_size: int
    workers: int
    media_items: int
    automatic_retries: int
    reservation_is_durable: bool
    reservations_survive_restart: bool
    uncertain_operations_are_charged: bool
    passes: bool
    reason: str


def _validate_constants() -> None:
    if not (
        CHANNEL_ID == -1002758699600
        and MESSAGE_ID == 598
        and MEDIA_ORDINAL == 0
        and MEDIA_KIND == "DOCUMENT"
        and TELEGRAM_MEDIA_ID == "5175124468544046445"
        and EXPECTED_BYTES == 11_649_955
        and PREFIX_BYTES % REQUEST_BYTES == OVERLAP_BYTES
        and WIRE_OFFSET == PREFIX_BYTES - OVERLAP_BYTES
        and WIRE_OFFSET % REQUEST_BYTES == 0
        and MAX_GETFILE_REQUESTS * REQUEST_BYTES == MAX_TRANSFER_BYTES
        and MAX_GETFILEHASHES_REQUESTS == 16
        and WORKERS == MAX_MEDIA_ITEMS == 1
    ):
        raise ValueError("STATIC_PROOF_CONFIGURATION_INVALID")


def _validate_hash_probe_constants() -> None:
    _validate_constants()
    if not (
        HASH_PROBE_OFFSET == 11_534_336
        and HASH_PROBE_MAX_CALLS == 2
        and HASH_PROBE_MAX_GETFILE_CALLS == 0
        and HASH_PROBE_MAX_MEDIA_PAYLOAD_BYTES == 0
        and WORKERS == 1
    ):
        raise ValueError("HASH_PROBE_CONFIGURATION_INVALID")


def _safe_probe_stop_reason(error: BaseException) -> str:
    category = getattr(error, "category", None)
    if isinstance(category, str) and re.fullmatch(r"[A-Z0-9_]{1,80}", category):
        return category
    if isinstance(error, RuntimeError) and str(error) == "SESSION_UNAVAILABLE":
        return "SESSION_UNAVAILABLE"
    return type(error).__name__


def compare_remote_range_digest(
    *, remote_offset: int, remote_limit: int, remote_digest: object,
    local_offset: int, local_bytes: bytes | bytearray | memoryview | None,
) -> dict[str, object]:
    """Compare one Telegram FileHash with the exact local range, without retaining digests."""
    result: dict[str, object] = {
        "status": "INCONCLUSIVE",
        "reason": "LOCAL_RANGE_UNAVAILABLE",
        "remote_offset": remote_offset,
        "remote_limit": remote_limit,
    }
    if not isinstance(remote_offset, int) or isinstance(remote_offset, bool) or remote_offset < 0:
        result["reason"] = "REMOTE_RANGE_INVALID"
        return result
    if not isinstance(remote_limit, int) or isinstance(remote_limit, bool) or remote_limit <= 0:
        result["reason"] = "REMOTE_RANGE_INVALID"
        return result
    if not isinstance(remote_digest, bytes) or len(remote_digest) != hashlib.sha256().digest_size:
        result["reason"] = "REMOTE_DIGEST_INVALID"
        return result
    if local_bytes is None:
        return result
    if not isinstance(local_bytes, (bytes, bytearray, memoryview)):
        result["reason"] = "LOCAL_RANGE_INVALID"
        return result
    local_view = memoryview(local_bytes)
    if local_offset != remote_offset or len(local_view) != remote_limit:
        result["reason"] = "LOCAL_RANGE_GEOMETRY_MISMATCH"
        result["local_offset"] = local_offset
        result["local_length"] = len(local_view)
        return result
    local_digest = hashlib.sha256(local_view).digest()
    result["status"] = "MATCH" if hmac.compare_digest(local_digest, remote_digest) else "NO_MATCH"
    result["reason"] = "EXACT_RANGE_SHA256_COMPARISON"
    result["local_offset"] = local_offset
    result["local_length"] = len(local_view)
    return result


def _wiring_checks() -> dict[str, bool]:
    modules = (
        "telegram_courses.downloads",
        "telegram_courses.download_repository",
        "telegram_courses.sqlite_repository",
        "telegram_courses.catalog_repository",
        "tools.manual_proofs.s6_resume_harness",
    )
    return {name: importlib.util.find_spec(name) is not None for name in modules}


def dry_run(evidence_root: Path | None = None) -> tuple[int, Path]:
    _validate_constants()
    checks = _wiring_checks()
    if not all(checks.values()):
        raise RuntimeError("OFFLINE_WIRING_CHECK_FAILED")
    temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if evidence_root is None:
        if not temp:
            raise RuntimeError("TEMP_UNAVAILABLE")
        evidence_root = Path(temp) / f"s6-real-resume-proof-{uuid4().hex}"
    evidence_root = evidence_root.expanduser().absolute()
    evidence_root.mkdir(parents=True, exist_ok=False)

    from tools.manual_proofs.s6_resume_harness import (
        exercise_budget_edge_cases,
        run_two_process_proof,
    )

    proof = run_two_process_proof(evidence_root / "two-process-proof")
    edges = exercise_budget_edge_cases(evidence_root / "control-probes")
    phases = (proof["phase1"], proof["phase2"])
    phase2 = proof["phase2"]
    ledger = phase2["ledger_after"]
    safety_pass = (
        phases[0]["process_id"] != phases[1]["process_id"]
        and phases[0]["partial_bytes"] == PREFIX_BYTES
        and phases[0]["sqlite_checkpoint_bytes"] == PREFIX_BYTES
        and phase2["sqlite_state"] == "DOWNLOADED"
        and phase2["final_bytes"] == EXPECTED_BYTES
        and phase2["overlap_bytes"] == OVERLAP_BYTES
        and ledger["getfile_calls_reserved"] <= MAX_GETFILE_REQUESTS
        and ledger["payload_bytes_reserved"] <= MAX_TRANSFER_BYTES
        and ledger["getfilehashes_calls_reserved"] <= MAX_GETFILEHASHES_REQUESTS
        and edges["getfile_cap_stop"] == "TRANSFER_BUDGET_EXHAUSTED"
        and edges["hash_cap_stop"] == "HASH_COVERAGE_BUDGET_EXHAUSTED"
        and edges["crash_conservative_reconciliation"]["uncertain_reservations"] == 1
    )
    report = {
        "activity": "S6-REAL-RESUME-PROOF-PREP-01",
        "continuation": "CONDITIONAL_BUDGET_GATE_AND_HARNESS",
        "mode": "DRY_RUN / SYNTHETIC_OFFLINE_PROOF",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "safety_preflight": "PASS" if safety_pass else "FAIL",
        "expected_feasibility": "UNKNOWN / ACTUAL TELEGRAM HASH COVERAGE IS UNOBSERVED",
        "evidence_completeness_gate": "PASS / SYNTHETIC FIXTURE ONLY",
        "real_evidence_completeness": (
            "NOT_EVALUATED / real PASS requires complete remote coverage of [0,E)"
        ),
        "real_evidence": "NOT_EXECUTED",
        "hash_coverage_policy": "INCREMENTAL / DURABLE GLOBAL CAP 16 / FAIL CLOSED",
        "target": {
            "channel_id": CHANNEL_ID,
            "message_id": MESSAGE_ID,
            "media_ordinal": MEDIA_ORDINAL,
            "media_kind": MEDIA_KIND,
            "telegram_media_id": TELEGRAM_MEDIA_ID,
            "expected_bytes": EXPECTED_BYTES,
            "isolated_media_item_id": proof["phase1"].get("isolated_media_item_id"),
            "historical_sha256_candidate": HISTORICAL_SHA256_CANDIDATE,
            "historical_sha256_status": "CANDIDATE_ONLY_PROVENANCE_NOT_RECORROBORATED",
        },
        "prefix": {
            "physical_candidate": PREFIX_BYTES,
            "wire_offset": WIRE_OFFSET,
            "overlap_bytes": OVERLAP_BYTES,
        },
        "limits": asdict(SafetyPreflight(
            getfile_cap=MAX_GETFILE_REQUESTS,
            getfile_payload_cap=MAX_TRANSFER_BYTES,
            getfilehashes_cap=MAX_GETFILEHASHES_REQUESTS,
            request_size=REQUEST_BYTES,
            workers=WORKERS,
            media_items=MAX_MEDIA_ITEMS,
            automatic_retries=0,
            reservation_is_durable=True,
            reservations_survive_restart=True,
            uncertain_operations_are_charged=True,
            passes=safety_pass,
            reason="Safety bounded independently of actual API coverage or proof success.",
        )),
        "offline_wiring_checks": checks,
        "two_process_restart": {
            "passed": phases[0]["process_id"] != phases[1]["process_id"],
            "phase1": proof["phase1"],
            "phase2": proof["phase2"],
        },
        "control_probes": edges,
        "python_version": sys.version.split()[0],
        "telethon_version": importlib.metadata.version("Telethon"),
        "real_telegram_calls": 0,
        "real_payload_bytes": 0,
        "original_sqlite_access": "NO",
        "session_restore": "NOT_ATTEMPTED",
        "execute_mode": "ENABLED_ONLY_AFTER_NATIVE_POWERSHELL_CONFIRMATION / NOT_STARTED_BY_DRY_RUN",
        "human_authorization": "PENDING_NATIVE_CONFIRMATION",
    }
    report_path = evidence_root / "s6-real-resume-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EVIDENCE_ROOT={evidence_root}")
    print(f"REPORT={report_path}")
    print(f"SAFETY_PREFLIGHT={'PASS' if safety_pass else 'FAIL'}")
    print("EXPECTED_FEASIBILITY=UNKNOWN")
    print("REAL_EVIDENCE=NOT_EXECUTED")
    print("HASH_COVERAGE_POLICY=INCREMENTAL / CAP 16 / STOPS ON STALL OR EXHAUSTION")
    print(f"TWO_PROCESS_RESTART={'PASS' if report['two_process_restart']['passed'] else 'FAIL'}")
    print("REAL_TELEGRAM_CALLS=0 REAL_PAYLOAD_BYTES=0 ORIGINAL_SQLITE_ACCESS=NO")
    return (0 if safety_pass else 5), evidence_root


def execute() -> int:
    authorization = os.environ.get("S6_REAL_EXECUTE_AUTH", "")
    if not re.fullmatch(r"[0-9a-f]{64}", authorization):
        print("STOP=NATIVE_POWERSHELL_CONFIRMATION_REQUIRED")
        return 5
    _validate_constants()
    temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if not temp:
        print("STOP=TEMP_UNAVAILABLE")
        return 5
    root = (Path(temp) / f"s6-real-resume-exec-{uuid4().hex}").absolute()
    root.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).resolve()
    phase_reports: list[dict[str, object]] = []
    process_ids: list[int] = []
    stop = ""
    for phase in (1, 2):
        output_path = root / f"phase-{phase}-report.json"
        args = [sys.executable, str(script), f"--real-phase-{phase}",
                "--evidence-root", str(root), "--phase-output", str(output_path)]
        if phase == 2:
            args.extend(("--phase1-pid", str(process_ids[0])))
        try:
            completed = subprocess.run(args, cwd=REPOSITORY_ROOT, capture_output=True,
                                       timeout=60 * 60, check=False)
            return_code = completed.returncode
        except subprocess.TimeoutExpired:
            stop = f"PHASE_{phase}_TIMEOUT"
            break
        except KeyboardInterrupt:
            stop = "USER_INTERRUPTED"
            break
        if not output_path.is_file():
            stop = f"PHASE_{phase}_REPORT_MISSING"
            break
        data = json.loads(output_path.read_text(encoding="utf-8"))
        phase_reports.append(data)
        process_ids.append(int(data["process_id"]))
        if return_code != 0:
            stop = str(data.get("stop_condition") or f"PHASE_{phase}_FAILED_EXIT_{return_code}")
            break
    phase1_done = bool(phase_reports and "partial_bytes" in phase_reports[0])
    restart_pass = len(process_ids) == 2 and process_ids[0] != process_ids[1]
    final = phase_reports[-1] if len(phase_reports) == 2 else {}
    ledger_path = root / "budget-ledger.sqlite3"
    ledger_snapshot: dict[str, int] = {}
    uncertain_bytes = 0
    if ledger_path.exists():
        from tools.manual_proofs.s6_resume_harness import DurableBudgetLedger
        ledger_snapshot = DurableBudgetLedger(ledger_path).snapshot()
        import sqlite3
        with sqlite3.connect(ledger_path) as db:
            uncertain_bytes = db.execute(
                "SELECT COALESCE(SUM(reserved_bytes),0) FROM reservations "
                "WHERE status IN ('UNCERTAIN','RESERVED')"
            ).fetchone()[0]
    result = "INCONCLUSIVE"
    first = phase_reports[0] if phase_reports else {}
    if (restart_pass and phase1_done
            and first.get("partial_bytes") == PREFIX_BYTES
            and first.get("sqlite_state") == "FAILED_RETRYABLE"
            and first.get("sqlite_checkpoint_bytes") == PREFIX_BYTES
            and first.get("remote_identity_rechecked") is True
            and final.get("outcome") == "DOWNLOADED"
            and final.get("final_bytes") == EXPECTED_BYTES
            and bool(final.get("final_sha256"))
            and final.get("sqlite_state") == "DOWNLOADED"
            and final.get("sqlite_checkpoint_bytes") == EXPECTED_BYTES
            and final.get("partial_exists_after_finalize") is False
            and final.get("prefix_validated") is True
            and final.get("hash_complement_validated") is True
            and final.get("overlap_bytes") == OVERLAP_BYTES
            and final.get("remote_full_coverage") is True
            and ledger_snapshot.get("getfile_calls_reserved", MAX_GETFILE_REQUESTS + 1) <= MAX_GETFILE_REQUESTS
            and ledger_snapshot.get("payload_bytes_reserved", MAX_TRANSFER_BYTES + 1) <= MAX_TRANSFER_BYTES
            and ledger_snapshot.get("getfilehashes_calls_reserved", MAX_GETFILEHASHES_REQUESTS + 1) <= MAX_GETFILEHASHES_REQUESTS
            and ledger_snapshot.get("open_reservations", 1) == 0
            and ledger_snapshot.get("uncertain_reservations", 1) == 0):
        result = "PASS"
    elif stop:
        result = "FAIL" if phase1_done else "BLOCKED"
    report = {
        "activity": "S6-REAL-RESUME-PROOF-EXEC-01", "result": result,
        "stop_condition": stop or None, "real_execution_authorized": True,
        "real_execution_environment": "NATIVE_POWERSHELL_CHILD_PROCESSES",
        "session_authentication": (
            "SESSION_UNAVAILABLE" if stop == "SESSION_UNAVAILABLE"
            else "RESTORED_EXISTING_PROTECTED_SESSION" if phase_reports and "partial_bytes" in phase_reports[0]
            else "NOT_CONFIRMED"
        ),
        "media_identity": "PASS" if phase_reports and phase_reports[0].get("remote_identity_rechecked") else "INCOMPLETE",
        "target": {"channel_id": CHANNEL_ID, "message_id": MESSAGE_ID,
                   "media_ordinal": MEDIA_ORDINAL, "media_kind": MEDIA_KIND,
                   "telegram_media_id": TELEGRAM_MEDIA_ID, "expected_bytes": EXPECTED_BYTES},
        "phase1_pid": process_ids[0] if process_ids else None,
        "phase2_pid": process_ids[1] if len(process_ids) > 1 else None,
        "process_restart": "PASS" if restart_pass else "INCOMPLETE",
        "prefix_bytes": phase_reports[0].get("partial_bytes") if phase_reports else None,
        "prefix_hash_validation": "PASS" if final.get("prefix_validated") else "INCOMPLETE",
        "hash_complement_validation": "PASS" if final.get("hash_complement_validated") else "INCOMPLETE",
        "overlap_validation": "PASS" if final.get("overlap_bytes") == OVERLAP_BYTES else "INCOMPLETE",
        "phase_reports": phase_reports, "budget": ledger_snapshot,
        "getfile_calls": ledger_snapshot.get("getfile_calls_reserved"),
        "getfilehashes_calls": ledger_snapshot.get("getfilehashes_calls_reserved"),
        "total_received_bytes": ledger_snapshot.get("payload_bytes_received"),
        "uncertain_bytes": uncertain_bytes,
        "budget_remaining": {
            "getfile_calls": max(0, MAX_GETFILE_REQUESTS - ledger_snapshot.get("getfile_calls_reserved", 0)),
            "getfilehashes_calls": max(0, MAX_GETFILEHASHES_REQUESTS - ledger_snapshot.get("getfilehashes_calls_reserved", 0)),
            "payload_bytes": max(0, MAX_TRANSFER_BYTES - ledger_snapshot.get("payload_bytes_reserved", 0)),
        },
        "final_size": final.get("final_bytes"), "final_sha256": final.get("final_sha256"),
        "historical_sha256_match": final.get("historical_sha256_match"),
        "remote_hash_coverage": "PASS" if final.get("remote_full_coverage") else "INCOMPLETE",
        "sqlite_final_state": final.get("sqlite_state"),
        "checkpoint_validation": "PASS" if final.get("sqlite_checkpoint_bytes") == EXPECTED_BYTES else "INCOMPLETE",
        "no_overwrite": "PASS" if final.get("outcome") == "DOWNLOADED" else "INCOMPLETE",
        "original_sqlite_access": "NO", "original_downloads_modified": "NO",
        "session_restore": "ATTEMPTED_ONLY_AFTER_NATIVE_CONFIRMATION",
        "evidence_path": str(root),
        "git_add": "NO", "git_commit": "NO", "git_push": "NO",
        "s6_formal_acceptance": "PENDING", "next_action": "INDEPENDENT_ACCEPTANCE_REVIEW",
    }
    report_path = root / "s6-real-resume-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EVIDENCE_ROOT={root}")
    print(f"REPORT={report_path}")
    print(f"PROCESS_RESTART={'PASS' if restart_pass else 'INCOMPLETE'}")
    print(f"RESULT={result}")
    if stop:
        print(f"STOP_CONDITION={stop}")
    print("ORIGINAL_SQLITE_ACCESS=NO ORIGINAL_DOWNLOADS_MODIFIED=NO")
    return 0 if result == "PASS" else 5


def hash_probe_dry_run(evidence_root: Path | None = None) -> tuple[int, Path]:
    """Validate the dedicated hash-only launcher path without restoring a session."""
    _validate_hash_probe_constants()
    temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if evidence_root is None:
        if not temp:
            raise RuntimeError("TEMP_UNAVAILABLE")
        evidence_root = Path(temp) / f"s6-hash-eof-probe-{uuid4().hex}"
    evidence_root = evidence_root.expanduser().absolute()
    evidence_root.mkdir(parents=True, exist_ok=False)
    report = {
        "activity": "S6-REAL-RESUME-PROOF-EXEC-01",
        "continuation": "HASH_EOF_TARGETED_PROBE",
        "mode": "DRY_RUN / NO TELEGRAM / NO SESSION RESTORE",
        "target": {
            "channel_id": CHANNEL_ID,
            "message_id": MESSAGE_ID,
            "media_id": TELEGRAM_MEDIA_ID,
            "expected_bytes": EXPECTED_BYTES,
        },
        "initial_hash_offset": HASH_PROBE_OFFSET,
        "max_getfilehashes_calls": HASH_PROBE_MAX_CALLS,
        "max_getfile_calls": HASH_PROBE_MAX_GETFILE_CALLS,
        "max_media_payload_bytes": HASH_PROBE_MAX_MEDIA_PAYLOAD_BYTES,
        "workers": WORKERS,
        "automatic_retries": 0,
        "floodwait": "STOP",
        "second_call_rule": "ONLY_AFTER_FIRST_RESPONSE_VALIDATES_AND_ADVANCES_CURSOR",
        "real_telegram_calls": 0,
        "real_payload_bytes": 0,
        "session_restore": "NOT_ATTEMPTED",
        "original_sqlite_access": "NO",
        "safety_gate": "PASS",
    }
    report_path = evidence_root / "s6-hash-eof-probe-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EVIDENCE_ROOT={evidence_root}")
    print(f"REPORT={report_path}")
    print("SAFETY_GATE=PASS")
    print("REAL_TELEGRAM_CALLS=0 REAL_PAYLOAD_BYTES=0 ORIGINAL_SQLITE_ACCESS=NO")
    return 0, evidence_root


class HashOnlyGateway:
    """Narrow capability wrapper: no stream/GetFile method is exposed."""

    def __init__(self, gateway) -> None:
        self._gateway = gateway

    async def get_file_hashes(self, *args, **kwargs):
        return await self._gateway.get_file_hashes(*args, **kwargs)

    async def close(self) -> None:
        await self._gateway.close()


async def _real_hash_gateway(ledger):
    from tools.manual_proofs.s6_resume_harness import _real_gateway

    return await _real_gateway(ledger, phase=1)


async def _run_hash_eof_probe(root: Path) -> dict[str, object]:
    from tools.manual_proofs.s6_resume_harness import (
        DurableBudgetLedger,
    )

    from telegram_courses.downloads import DownloadGatewayError

    ledger = DurableBudgetLedger(
        root / "hash-probe-ledger.sqlite3",
        getfile_cap=HASH_PROBE_MAX_GETFILE_CALLS,
        payload_cap=HASH_PROBE_MAX_MEDIA_PAYLOAD_BYTES,
        hash_cap=HASH_PROBE_MAX_CALLS,
    )
    real_gateway = await _real_hash_gateway(ledger)
    gateway = HashOnlyGateway(real_gateway)
    cursor = HASH_PROBE_OFFSET
    stop_condition = None
    second_call_justification = None
    calls: list[dict[str, object]] = []
    complete = False
    try:
        for call_index in range(1, HASH_PROBE_MAX_CALLS + 1):
            cursor_before = cursor
            if call_index == 2:
                if not calls or calls[0].get("validation_result") != "PASS":
                    stop_condition = "SECOND_CALL_NOT_JUSTIFIED"
                    break
                if cursor <= int(calls[0]["cursor_before"]) or cursor >= EXPECTED_BYTES:
                    stop_condition = "SECOND_CALL_NO_VERIFIABLE_PROGRESS"
                    break
                second_call_justification = "FIRST_RESPONSE_VALIDATED_AND_ADVANCED_CURSOR"
            real_gateway.call_index = call_index - 1
            real_gateway.next_justification = second_call_justification
            try:
                ranges = await gateway.get_file_hashes(
                    CHANNEL_ID,
                    MESSAGE_ID,
                    MEDIA_ORDINAL,
                    telegram_media_id=TELEGRAM_MEDIA_ID,
                    expected_bytes=EXPECTED_BYTES,
                    offset=cursor,
                )
            except DownloadGatewayError as error:
                stop_condition = error.category
                break
            except Exception as error:
                # Store only a coarse exception class; raw messages can contain remote data.
                stop_condition = _safe_probe_stop_reason(error)
                break

            event_path = root / "hash-coverage.jsonl"
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[-1])
            calls.append({
                "call_index": call_index,
                "reservation_id": event["reservation_id"],
                "correlation_id": event["correlation_id"],
                "requested_offset": cursor_before,
                "expected_bytes": EXPECTED_BYTES,
                "range_count": len(ranges),
                "ranges": event["returned_ranges"],
                "cursor_before": cursor_before,
                "cursor_after": event["cursor_after"],
                "validation_result": event["validation_result"],
                "rejection_classification": event["rejection_classification"],
                "rejection_reason": event["rejection_reason"],
                "justification": event.get("justification"),
            })
            cursor = int(event["cursor_after"])
            if cursor >= EXPECTED_BYTES:
                complete = True
                break
            if cursor <= cursor_before:
                stop_condition = "HASH_CURSOR_NO_PROGRESS"
                break
            if call_index == HASH_PROBE_MAX_CALLS:
                stop_condition = "HASH_PROBE_CALL_LIMIT_REACHED"
    finally:
        await gateway.close()

    snapshot = ledger.snapshot()
    hash_response_path = root / "hash-coverage.jsonl"
    hash_responses = (
        [json.loads(line) for line in hash_response_path.read_text(encoding="utf-8").splitlines()]
        if hash_response_path.exists() else []
    )
    return {
        "result": "CONTIGUOUS_COVERAGE_REACHED_EOF" if complete else "INCOMPLETE_DIAGNOSTIC",
        "stop_condition": stop_condition,
        "target": {
            "channel_id": CHANNEL_ID,
            "message_id": MESSAGE_ID,
            "media_id": TELEGRAM_MEDIA_ID,
            "expected_bytes": EXPECTED_BYTES,
        },
        "initial_hash_offset": HASH_PROBE_OFFSET,
        "final_cursor": cursor,
        "calls": calls,
        "hash_responses": hash_responses,
        "budget": snapshot,
        "getfile_calls": snapshot["getfile_calls_reserved"],
        "media_payload_bytes": snapshot["payload_bytes_received"],
        "real_telegram_calls": snapshot["getfilehashes_calls_reserved"],
        "session_restore": "ATTEMPTED_ONLY_AFTER_NATIVE_CONFIRMATION",
        "original_sqlite_access": "NO",
        "media_content_stored": "NO",
    }


def execute_hash_eof_probe() -> int:
    authorization = os.environ.get("S6_HASH_PROBE_AUTH", "")
    if not re.fullmatch(r"[0-9a-f]{64}", authorization):
        print("STOP=NATIVE_POWERSHELL_CONFIRMATION_REQUIRED")
        return 5
    _validate_hash_probe_constants()
    temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if not temp:
        print("STOP=TEMP_UNAVAILABLE")
        return 5
    root = (Path(temp) / f"s6-hash-eof-probe-{uuid4().hex}").absolute()
    root.mkdir(parents=True, exist_ok=False)
    try:
        report = asyncio.run(_run_hash_eof_probe(root))
    except Exception as error:
        from tools.manual_proofs.s6_resume_harness import DurableBudgetLedger
        ledger_path = root / "hash-probe-ledger.sqlite3"
        budget = DurableBudgetLedger(
            ledger_path,
            getfile_cap=HASH_PROBE_MAX_GETFILE_CALLS,
            payload_cap=HASH_PROBE_MAX_MEDIA_PAYLOAD_BYTES,
            hash_cap=HASH_PROBE_MAX_CALLS,
        ).snapshot() if ledger_path.exists() else None
        evidence_path = root / "hash-coverage.jsonl"
        hash_responses = (
            [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
            if evidence_path.exists() else []
        )
        report = {
            "result": "INCOMPLETE_DIAGNOSTIC",
            "stop_condition": _safe_probe_stop_reason(error),
            "calls": [],
            "hash_responses": hash_responses,
            "budget": budget,
            "real_telegram_calls": budget["getfilehashes_calls_reserved"] if budget else 0,
            "getfile_calls": budget["getfile_calls_reserved"] if budget else 0,
            "media_payload_bytes": budget["payload_bytes_received"] if budget else 0,
            "original_sqlite_access": "NO",
        }
    report.update({
        "activity": "S6-REAL-RESUME-PROOF-EXEC-01",
        "continuation": "HASH_EOF_TARGETED_PROBE",
        "mode": "REAL_HASH_ONLY_DIAGNOSTIC",
        "evidence_path": str(root),
        "max_getfilehashes_calls": HASH_PROBE_MAX_CALLS,
        "max_getfile_calls": HASH_PROBE_MAX_GETFILE_CALLS,
        "max_media_payload_bytes": HASH_PROBE_MAX_MEDIA_PAYLOAD_BYTES,
        "workers": 1,
        "automatic_retries": 0,
        "floodwait": "STOP",
        "safety_gate": "PASS" if report.get("getfile_calls") == 0
        and report.get("media_payload_bytes") == 0
        and report.get("real_telegram_calls", 0) <= HASH_PROBE_MAX_CALLS else "FAIL",
        "git_add": "NO",
        "git_commit": "NO",
        "git_push": "NO",
        "s6_formal_acceptance": "PENDING",
        "next_action": "CLASSIFY_HASH_RESPONSE_AND_REVIEW_CRYPTOGRAPHIC_IMPLICATIONS",
    })
    report_path = root / "s6-hash-eof-probe-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EVIDENCE_ROOT={root}")
    print(f"REPORT={report_path}")
    print(f"RESULT={report['result']}")
    print(f"REAL_GETFILEHASHES_CALLS={report.get('real_telegram_calls', 0)}")
    print("GETFILE_CALLS=0 MEDIA_PAYLOAD_BYTES=0 ORIGINAL_SQLITE_ACCESS=NO")
    print(f"SAFETY_GATE={report['safety_gate']}")
    return 0 if report["safety_gate"] == "PASS" else 5


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--hash-eof-probe-dry-run", action="store_true")
    mode.add_argument("--hash-eof-probe-execute", action="store_true")
    parser.add_argument("--phase-1", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--phase-2", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--evidence-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--phase-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--crash-after-reserve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ledger-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--real-phase-1", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--real-phase-2", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--phase1-pid", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.crash_after_reserve:
        if args.ledger_path is None or args.phase_1 or args.phase_2:
            parser.error("invalid internal crash-probe invocation")
        from tools.manual_proofs.s6_resume_harness import (
            CHUNK_BYTES,
            DurableBudgetLedger,
        )
        DurableBudgetLedger(args.ledger_path).reserve_getfile(CHUNK_BYTES)
        os._exit(77)  # Intentional process death after durable reservation, before response.
    if args.real_phase_1 or args.real_phase_2:
        if (args.real_phase_1 == args.real_phase_2 or args.evidence_root is None
                or args.phase_output is None or not re.fullmatch(
                    r"[0-9a-f]{64}", os.environ.get("S6_REAL_EXECUTE_AUTH", "")
                )):
            parser.error("invalid protected real phase invocation")
        from tools.manual_proofs.s6_resume_harness import real_phase_main
        return real_phase_main(
            1 if args.real_phase_1 else 2, args.evidence_root,
            args.phase_output, args.phase1_pid,
        )
    if args.phase_1 or args.phase_2:
        if args.phase_1 == args.phase_2 or args.evidence_root is None or args.phase_output is None:
            parser.error("invalid internal phase invocation")
        from tools.manual_proofs.s6_resume_harness import phase_main
        return phase_main(1 if args.phase_1 else 2, args.evidence_root, args.phase_output)
    if not any((args.dry_run, args.execute, args.hash_eof_probe_dry_run,
                args.hash_eof_probe_execute)):
        parser.error("one proof mode is required")
    if args.dry_run:
        code, _root = dry_run()
        return code
    if args.hash_eof_probe_dry_run:
        code, _root = hash_probe_dry_run()
        return code
    if args.hash_eof_probe_execute:
        return execute_hash_eof_probe()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
