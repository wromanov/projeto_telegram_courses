"""One-call S6 EOF hash probe for the separately uploaded controlled reference."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from tools.manual_proofs.s6_resume_harness import (
    BudgetStop,
    DurableBudgetLedger,
    _real_gateway,
    validate_hash_response,
)

PROJECT_ID = "projeto_telegram_courses"
CHANNEL_ID = -1002368271467
MESSAGE_ID = 7603
MEDIA_ID = "5089068167339181674"
MEDIA_ORDINAL = 0
MEDIA_KIND = "DOCUMENT"
EXPECTED_BYTES = 1_119_129_690
ALIGNMENT_BYTES = 128 * 1024
HASH_OFFSET = 1_119_092_736
EOF_REMAINDER = 36_954
MAX_GETFILEHASHES_CALLS = 1
MAX_GETFILE_CALLS = 0
MAX_MEDIA_PAYLOAD_BYTES = 0
WORKERS = 1
AUTOMATIC_RETRIES = 0
AUTH_ENV = "S6_CONTROLLED_EOF_HASH_PROBE_AUTH"
CONFIRMATION = "EXECUTE S6 CONTROLLED EOF HASH PROBE 7603"

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_MANIFEST = ROOT / "docs/reports/S6_CONTROLLED_REFERENCE_PREPARATION_2026-10-17/reference_manifest.json"
UPLOAD_RESULT = ROOT / "docs/reports/S6_CONTROLLED_UPLOAD_AND_EOF_GATE_2026-10-17/controlled_upload_result.json"


def _validate_constants() -> None:
    if not (
        HASH_OFFSET == ((EXPECTED_BYTES - 1) // ALIGNMENT_BYTES) * ALIGNMENT_BYTES
        and EXPECTED_BYTES - HASH_OFFSET == EOF_REMAINDER
        and HASH_OFFSET % ALIGNMENT_BYTES == 0
        and MAX_GETFILEHASHES_CALLS == 1
        and MAX_GETFILE_CALLS == MAX_MEDIA_PAYLOAD_BYTES == 0
        and WORKERS == 1
        and AUTOMATIC_RETRIES == 0
    ):
        raise ValueError("STATIC_PROBE_CONFIGURATION_INVALID")


def _validate_reference_artifacts() -> tuple[dict[str, object], dict[str, object]]:
    _validate_constants()
    manifest = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    upload = json.loads(UPLOAD_RESULT.read_text(encoding="utf-8"))
    source = manifest
    remote = upload.get("refetched_message", {})
    target = upload.get("target", {})
    upload_source = upload.get("source_file", {})
    if not (
        manifest.get("project_id") == PROJECT_ID
        and manifest.get("reference_gate") == "PASS"
        and manifest.get("source_file_path") == r"C:\Users\walac\Downloads\64Gram Desktop\Teste Telegram.rar"
        and source.get("source_file_type") == "regular_file"
        and source.get("source_file_extension") == ".rar"
        and source.get("source_file_size_bytes") == EXPECTED_BYTES
        and source.get("source_file_sha256") == "3ae30a0b9028a4cafa1301a3792845ba328aa83350faaa46deb8219e34c2ab2c"
        and upload.get("project_id") == PROJECT_ID
        and upload.get("reference_gate") == "PASS"
        and upload_source.get("source_file_path") == manifest.get("source_file_path")
        and upload_source.get("source_file_size_bytes") == manifest.get("source_file_size_bytes")
        and upload_source.get("source_file_sha256") == manifest.get("source_file_sha256")
        and upload_source.get("source_file_last_write_utc") == manifest.get("source_file_last_write_utc")
        and target.get("channel_id_verified_before_upload") is True
        and target.get("title_verified_before_upload") is True
        and target.get("expected_title") == "Clone Pessoal - WRomanov"
        and target.get("expected_channel_id") == CHANNEL_ID
        and remote.get("channel_id") == CHANNEL_ID
        and remote.get("message_id") == MESSAGE_ID
        and str(remote.get("media_id")) == MEDIA_ID
        and remote.get("ordinal") == MEDIA_ORDINAL
        and remote.get("kind") == MEDIA_KIND
        and remote.get("document_size_bytes") == EXPECTED_BYTES
        and remote.get("identity_gate") == "PASS"
    ):
        raise ValueError("REFERENCE_OR_REMOTE_IDENTITY_GATE_FAILED")
    return manifest, upload


def _verify_local_reference(manifest: dict[str, object]) -> str:
    """Recheck the source against its recorded size, mtime, and digest, streaming."""
    path = Path(str(manifest["source_file_path"]))
    before = path.stat()
    expected_size = manifest["source_file_size_bytes"]
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not path.is_file()
        or path.is_symlink()
        or getattr(before, "st_file_attributes", 0) & reparse_point
        or before.st_size != expected_size
    ):
        raise ValueError("LOCAL_REFERENCE_SIZE_OR_TYPE_CHANGED")
    recorded_time = datetime.fromisoformat(
        str(manifest["source_file_last_write_utc"]).replace("Z", "+00:00")
    ).astimezone(UTC)
    current_time = datetime.fromtimestamp(before.st_mtime, UTC)
    if abs((current_time - recorded_time).total_seconds()) > 0.000001:
        raise ValueError("LOCAL_REFERENCE_TIMESTAMP_CHANGED")
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError("LOCAL_REFERENCE_CHANGED_DURING_READ")
    if not hmac.compare_digest(digest.hexdigest(), str(manifest["source_file_sha256"])):
        raise ValueError("LOCAL_REFERENCE_SHA256_MISMATCH")
    return "PASS"


def _dry_run(evidence_root: Path | None = None) -> tuple[int, Path]:
    manifest, upload = _validate_reference_artifacts()
    local_reference_gate = _verify_local_reference(manifest)
    temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if evidence_root is None:
        if not temp:
            raise RuntimeError("TEMP_UNAVAILABLE")
        evidence_root = Path(temp) / f"s6-controlled-eof-hash-probe-{uuid4().hex}"
    evidence_root = evidence_root.expanduser().absolute()
    evidence_root.mkdir(parents=True, exist_ok=False)
    report = {
        "project_id": PROJECT_ID,
        "activity": "S6_CONTROLLED_EOF_HASH_PROBE",
        "mode": "DRY_RUN / NO TELEGRAM / NO SESSION RESTORE",
        "reference_manifest_gate": "PASS",
        "local_reference_integrity_gate": local_reference_gate,
        "registered_remote_identity_gate": "PASS",
        "target": {
            "channel_id": CHANNEL_ID,
            "message_id": MESSAGE_ID,
            "media_id": MEDIA_ID,
            "ordinal": MEDIA_ORDINAL,
            "kind": MEDIA_KIND,
            "expected_bytes": manifest["source_file_size_bytes"],
        },
        "requested_offset": HASH_OFFSET,
        "alignment_bytes": ALIGNMENT_BYTES,
        "expected_eof_remainder_bytes": EOF_REMAINDER,
        "max_getfilehashes_calls": MAX_GETFILEHASHES_CALLS,
        "max_getfile_calls": MAX_GETFILE_CALLS,
        "max_media_payload_bytes": MAX_MEDIA_PAYLOAD_BYTES,
        "workers": WORKERS,
        "automatic_retries": AUTOMATIC_RETRIES,
        "floodwait": "STOP",
        "real_telegram_calls": 0,
        "session_restore": "NOT_ATTEMPTED",
        "media_payload_bytes": 0,
        "remote_digests_persisted": False,
        "safety_gate": "PASS",
        "upload_result_status": upload["activity_status"],
    }
    path = evidence_root / "s6-controlled-eof-hash-probe-dryrun.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EVIDENCE_ROOT={evidence_root}")
    print(f"REPORT={path}")
    print("DRY_RUN=PASS REAL_TELEGRAM_CALLS=0 SESSION_RESTORE=NO")
    print("BUDGET=1_GETFILEHASHES/0_GETFILE/0_MEDIA_PAYLOAD_BYTES")
    return 0, evidence_root


class _HashOnlyGateway:
    """Expose only GetFileHashes and close; no streaming/GetFile capability."""

    def __init__(self, gateway: object) -> None:
        self._gateway = gateway

    async def get_file_hashes(self, *args: object, **kwargs: object):
        return await self._gateway.get_file_hashes(*args, **kwargs)

    async def close(self) -> None:
        await self._gateway.close()


def _classify_hash_response_event(
    event: dict[str, object], fallback_stop: str | None
) -> tuple[str, str | None, str | None]:
    """Keep remote request failures distinct from local response rejection."""
    if event.get("response_received") is True and event.get("validation_result") == "REJECTED":
        return (
            "LOCAL_HASH_RESPONSE_VALIDATION_REJECTED",
            str(event.get("failure_category") or fallback_stop or "HASH_RESPONSE_REJECTED"),
            "LOCAL_RESPONSE_VALIDATION",
        )
    return "REMOTE_IDENTITY_OR_HASH_REQUEST_REJECTED", fallback_stop, None


def _compare_remote_ranges_to_reference(ranges: tuple[object, ...], source_path: Path) -> str:
    before = source_path.stat()
    if not source_path.is_file() or before.st_size != EXPECTED_BYTES:
        return "LOCAL_REFERENCE_CHANGED"
    matches = True
    with source_path.open("rb", buffering=0) as source:
        for item in ranges:
            digest = item.sha256
            if isinstance(digest, str):
                try:
                    remote_digest = bytes.fromhex(digest)
                except ValueError:
                    return "REMOTE_DIGEST_INVALID"
            elif isinstance(digest, bytes):
                remote_digest = digest
            else:
                return "REMOTE_DIGEST_INVALID"
            source.seek(item.offset)
            local_hash = hashlib.sha256()
            remaining = item.limit
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    return "LOCAL_RANGE_SHORT_READ"
                local_hash.update(chunk)
                remaining -= len(chunk)
            matches = matches and hmac.compare_digest(local_hash.digest(), remote_digest)
    after = source_path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        return "LOCAL_REFERENCE_CHANGED"
    return "MATCHED_LOCAL_REFERENCE_BYTES" if matches else "MISMATCHED_LOCAL_REFERENCE_BYTES"


async def _execute_probe(root: Path) -> dict[str, object]:
    from telegram_courses.downloads import DownloadGatewayError

    manifest, _upload = _validate_reference_artifacts()
    local_reference_gate = _verify_local_reference(manifest)
    ledger = DurableBudgetLedger(
        root / "probe-ledger.sqlite3",
        getfile_cap=MAX_GETFILE_CALLS,
        payload_cap=MAX_MEDIA_PAYLOAD_BYTES,
        hash_cap=MAX_GETFILEHASHES_CALLS,
    )
    real_gateway = await _real_gateway(ledger, phase=1)
    gateway = _HashOnlyGateway(real_gateway)
    client = real_gateway.gateway._client
    from telethon.tl.functions.upload import GetFileHashesRequest

    original_call = client._call
    client_rpc_calls = 0

    async def counted_call(sender, request, *args, **kwargs):
        nonlocal client_rpc_calls
        if isinstance(request, GetFileHashesRequest):
            client_rpc_calls += 1
        return await original_call(sender, request, *args, **kwargs)

    client._call = counted_call
    remote_ranges: tuple[object, ...] = ()
    stop = None
    diagnostics: dict[str, object] = {}
    try:
        remote_ranges = await gateway.get_file_hashes(
            CHANNEL_ID,
            MESSAGE_ID,
            MEDIA_ORDINAL,
            telegram_media_id=MEDIA_ID,
            expected_bytes=EXPECTED_BYTES,
            offset=HASH_OFFSET,
        )
        cursor = validate_hash_response(
            HASH_OFFSET, remote_ranges, EXPECTED_BYTES, diagnostics=diagnostics
        )
        if cursor == EXPECTED_BYTES:
            geometry = "CONTIGUOUS_COVERAGE_REACHED_EOF"
            crypto = _compare_remote_ranges_to_reference(
                remote_ranges, Path(_validate_reference_artifacts()[0]["source_file_path"])
            )
        else:
            geometry = "VALID_RANGES_DID_NOT_REACH_EOF"
            crypto = "NOT_ESTABLISHED"
    except BudgetStop as error:
        stop = str(error)
        geometry = "REJECTED_RANGE_GEOMETRY"
        crypto = "NOT_ESTABLISHED"
    except DownloadGatewayError as error:
        stop = error.category
        geometry = "REMOTE_IDENTITY_OR_HASH_REQUEST_REJECTED"
        crypto = "NOT_ESTABLISHED"
    except Exception as error:
        stop = type(error).__name__
        geometry = "INCOMPLETE_DIAGNOSTIC"
        crypto = "NOT_ESTABLISHED"
    finally:
        await gateway.close()

    events_path = root / "hash-coverage.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()] if events_path.exists() else []
    if events:
        last = events[-1]
        diagnostics = {
            "requested_offset": last.get("requested_offset"),
            "returned_ranges": last.get("returned_ranges", []),
            "range_count_received": last.get("range_count_received"),
            "range_count_inspected": last.get("range_count_inspected"),
            "first_rejected_index": last.get("first_rejected_index"),
            "cursor_after": last.get("cursor_after"),
            "validation_result": last.get("validation_result"),
            "rejection_classification": last.get("rejection_classification"),
            "diagnostic_classification": last.get("diagnostic_classification"),
            "rejection_reason": last.get("rejection_reason"),
        }
        if stop is not None:
            geometry, stop, source = _classify_hash_response_event(last, stop)
            if source is not None:
                diagnostics["rejection_source"] = source
    budget = ledger.snapshot()
    eof_valid = geometry == "CONTIGUOUS_COVERAGE_REACHED_EOF"
    crypto_match = crypto == "MATCHED_LOCAL_REFERENCE_BYTES"
    if eof_valid and crypto_match and budget["getfilehashes_calls_reserved"] == 1:
        result = "GO_FOR_FULL_PROOF_PLANNING"
    else:
        result = "NO_GO_FULL_DOWNLOAD"
    return {
        "result": result,
        "requested_offset": HASH_OFFSET,
        "expected_eof": EXPECTED_BYTES,
        "local_reference_gate": local_reference_gate,
        "hash_range_classification": geometry,
        "cryptographic_compatibility": crypto,
        "stop_condition": stop,
        "diagnostics": diagnostics,
        "getfilehashes_calls_reserved": budget["getfilehashes_calls_reserved"],
        "getfilehashes_telethon_client_calls": client_rpc_calls,
        "getfile_calls": budget["getfile_calls_reserved"],
        "media_payload_bytes": budget["payload_bytes_received"],
        "remote_digests_persisted": False,
        "safety_gate": "PASS" if budget["getfilehashes_calls_reserved"] <= 1 and budget["getfile_calls_reserved"] == 0 and budget["payload_bytes_received"] == 0 else "FAIL",
    }


def execute() -> int:
    token = os.environ.get(AUTH_ENV, "")
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        print("STOP=NATIVE_POWERSHELL_CONFIRMATION_REQUIRED")
        return 5
    try:
        _validate_reference_artifacts()
    except Exception as error:
        print(f"STOP=REFERENCE_GATE_FAILED CLASS={type(error).__name__}")
        return 5
    temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if not temp:
        print("STOP=TEMP_UNAVAILABLE")
        return 5
    root = (Path(temp) / f"s6-controlled-eof-hash-probe-{uuid4().hex}").absolute()
    root.mkdir(parents=True, exist_ok=False)
    try:
        report = asyncio.run(_execute_probe(root))
    except Exception as error:
        ledger_path = root / "probe-ledger.sqlite3"
        budget = DurableBudgetLedger(
            ledger_path,
            getfile_cap=MAX_GETFILE_CALLS,
            payload_cap=MAX_MEDIA_PAYLOAD_BYTES,
            hash_cap=MAX_GETFILEHASHES_CALLS,
        ).snapshot() if ledger_path.exists() else {}
        report = {
            "result": "NO_GO_FULL_DOWNLOAD",
            "stop_condition": type(error).__name__,
            "getfilehashes_calls_reserved": budget.get("getfilehashes_calls_reserved", 0),
            "getfilehashes_telethon_client_calls": "UNKNOWN_AFTER_INTERNAL_FAILURE",
            "getfile_calls": budget.get("getfile_calls_reserved", 0),
            "media_payload_bytes": budget.get("payload_bytes_received", 0),
            "remote_digests_persisted": False,
            "safety_gate": "FAIL_CLOSED",
        }
    report.update({
        "project_id": PROJECT_ID,
        "activity": "S6_CONTROLLED_EOF_HASH_PROBE",
        "mode": "REAL_HASH_ONLY_DIAGNOSTIC",
        "target": {
            "channel_id": CHANNEL_ID,
            "message_id": MESSAGE_ID,
            "media_id": MEDIA_ID,
            "ordinal": MEDIA_ORDINAL,
            "kind": MEDIA_KIND,
            "expected_bytes": EXPECTED_BYTES,
        },
        "max_getfilehashes_calls": MAX_GETFILEHASHES_CALLS,
        "max_getfile_calls": MAX_GETFILE_CALLS,
        "max_media_payload_bytes": MAX_MEDIA_PAYLOAD_BYTES,
        "workers": WORKERS,
        "automatic_retries": AUTOMATIC_RETRIES,
        "floodwait": "STOP",
        "session_restore": "EXISTING_PROTECTED_SESSION_ONLY",
        "original_sqlite_access": "NO",
        "full_download_authorized": "NO",
        "s6_formal_acceptance": "PENDING",
        "sprint_checkpoint": "DEFERRED",
    })
    report_path = root / "s6-controlled-eof-hash-probe-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"EVIDENCE_ROOT={root}")
    print(f"REPORT={report_path}")
    print(f"RESULT={report['result']}")
    print(f"GETFILEHASHES_CALLS={report.get('getfilehashes_telethon_client_calls', 0)}")
    print("GETFILE_CALLS=0 MEDIA_PAYLOAD_BYTES=0 REMOTE_DIGESTS_PERSISTED=NO")
    print(f"SAFETY_GATE={report['safety_gate']}")
    return 0 if report["safety_gate"] == "PASS" else 5


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--dry-run"]:
        code, _root = _dry_run()
        return code
    if args == ["--execute"]:
        return execute()
    print("USAGE=--dry-run|--execute")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
