"""Bounded, manual S6 Telethon compatibility probe (no SQLite writes)."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import logging
import os
import sys
import tempfile
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

CHANNEL_ID = -1002758699600
MESSAGE_ID = 598
MEDIA_ORDINAL = 0
MEDIA_KIND = "DOCUMENT"
TELEGRAM_MEDIA_ID = "5175124468544046445"
EXPECTED_BYTES = 11649955
MEDIA_ITEM_ID = 5

MAX_MEDIA_ITEMS = 1
WORKERS = 1
MAX_TRANSFER_BYTES = 4 * 1024 * 1024
MAX_GETFILE_REQUESTS = 16
MAX_GETFILEHASHES_REQUESTS = 8
MAX_GETFILE_REQUEST_SIZE = 256 * 1024
MAX_ATTEMPTS_PER_MEDIA = 3
SAMPLES = ((0, 262144), (262144, 262144), (524288, 262144))
HASH_COVERAGE_END = 786432
CONFIRMATION = "EXECUTE S6 PROOF 598"


class StopProof(Exception):
    def __init__(self, condition: str) -> None:
        self.condition = condition
        super().__init__(condition)


@dataclass
class Evidence:
    python_version: str
    telethon_version: str
    authentication: str = "NOT_ATTEMPTED"
    remote_identity: dict[str, Any] | None = None
    hash_calls: list[dict[str, Any]] | None = None
    hash_requests: list[dict[str, Any]] | None = None
    hash_ranges: list[dict[str, Any]] | None = None
    hash_coverage: dict[str, Any] | None = None
    hash_comparisons: list[dict[str, Any]] | None = None
    compared_sample_coverage: list[dict[str, Any]] | None = None
    getfile_requests: list[dict[str, Any]] | None = None
    reservations: int = 0
    reserved_in_flight: int = 0
    received_bytes: int = 0
    uncertain_bytes: int = 0
    consumed_bytes: int = 0
    remaining_bytes: int = MAX_TRANSFER_BYTES
    media_attempts: int = 0
    stop_condition: str | None = None
    errors: list[str] | None = None
    gateway_diagnostics: list[str] | None = None
    failure_traceback: list[str] | None = None
    result: str = "NOT_RUN"


class _SafeGatewayDiagnosticHandler(logging.Handler):
    """Capture the adapter's already-sanitized diagnostic line in evidence."""

    def __init__(self, evidence: Evidence) -> None:
        super().__init__(level=logging.WARNING)
        self.evidence = evidence

    def emit(self, record: logging.LogRecord) -> None:
        if (
            record.name != "telegram_courses.telethon_gateway"
            or not isinstance(record.msg, str)
            or not record.msg.startswith((
                "authentication diagnostic FAILURE_STAGE=",
                "media diagnostic ",
            ))
        ):
            return
        try:
            assert self.evidence.gateway_diagnostics is not None
            self.evidence.gateway_diagnostics.append(record.getMessage())
        except Exception:
            self.evidence.gateway_diagnostics = ["SANITIZED_DIAGNOSTIC_CAPTURE_FAILED"]


def _safe_traceback_locations(error: BaseException) -> list[str]:
    locations: list[str] = []
    for frame in traceback.extract_tb(error.__traceback__)[-8:]:
        filename = frame.filename.replace("\\", "/").rsplit("/", 1)[-1]
        function = frame.name
        if (
            not filename.isascii()
            or not filename
            or any(not (char.isalnum() or char in "._-") for char in filename)
        ):
            filename = "UNKNOWN_FILE"
        if (
            not function.isascii()
            or not function
            or any(not (char.isalnum() or char in "_<>-") for char in function)
        ):
            function = "UNKNOWN_FUNCTION"
        locations.append(f"{filename}:{frame.lineno}:{function}")
    return locations


class Lease:
    def __init__(self, lease: Any, evidence: Evidence) -> None:
        self._lease = lease
        self._evidence = evidence
        self._settled = False

    def received(self, amount: int) -> None:
        self._lease.received(amount)
        self._settled = True
        self._evidence.reserved_in_flight -= MAX_GETFILE_REQUEST_SIZE
        self._evidence.received_bytes += amount
        self._evidence.consumed_bytes += amount
        self._evidence.remaining_bytes -= amount

    def release(self) -> None:
        self._lease.release()
        self._settled = True
        self._evidence.reserved_in_flight -= MAX_GETFILE_REQUEST_SIZE

    def charge_uncertain(self) -> None:
        self._lease.charge_uncertain()
        self._settled = True
        self._evidence.reserved_in_flight -= MAX_GETFILE_REQUEST_SIZE
        self._evidence.uncertain_bytes += MAX_GETFILE_REQUEST_SIZE
        self._evidence.consumed_bytes += MAX_GETFILE_REQUEST_SIZE
        self._evidence.remaining_bytes -= MAX_GETFILE_REQUEST_SIZE


class ProbeApplication:
    """Runs only three fixed ranges; it never writes media or finalizes a file."""

    def __init__(self, gateway: Any, evidence: Evidence, output: Path) -> None:
        self.gateway = gateway
        self.evidence = evidence
        self.download_root = output
        self.chunk_reserver = None
        self.chunk_callback = None
        self.progress_callback = None
        self.pre_append_check = None
        self.samples: dict[tuple[int, int], bytes] = {}
        self.stop_condition: str | None = None
        self.accepted_sample_count = 0
        self.media_attempts = 0
        self.request_ledger: list[dict[str, Any]] = []

    @property
    def expected_sample(self) -> tuple[int, int] | None:
        if self.accepted_sample_count >= len(SAMPLES):
            return None
        return SAMPLES[self.accepted_sample_count]

    async def download(self, *_identity: int) -> Any:
        self.media_attempts += 1
        self.evidence.media_attempts = self.media_attempts
        if self.media_attempts > MAX_ATTEMPTS_PER_MEDIA:
            self.stop_condition = "ATTEMPT_LIMIT_EXCEEDED"
            raise StopProof(self.stop_condition)
        while self.expected_sample is not None:
            offset, length = self.expected_sample
            stream = self.gateway.stream_media(
                CHANNEL_ID,
                MESSAGE_ID,
                MEDIA_ORDINAL,
                telegram_media_id=TELEGRAM_MEDIA_ID,
                expected_bytes=EXPECTED_BYTES,
                chunk_bytes=MAX_GETFILE_REQUEST_SIZE,
                reserve_chunk=self._gateway_reservation,
                offset=offset,
            )
            captured = bytearray()
            try:
                async for chunk in stream:
                    if len(captured) + len(chunk) > length:
                        raise StopProof("UNPLANNED_SAMPLE_BYTES")
                    captured.extend(chunk)
                    if self.chunk_callback is not None:
                        self.chunk_callback(len(chunk))
                    if len(captured) == length:
                        break
            except Exception as error:
                category = getattr(error, "category", None)
                if self.stop_condition is not None:
                    raise StopProof(self.stop_condition) from None
                if category == "RATE_LIMITED":
                    self.stop_condition = "FLOODWAIT_STOP_IMMEDIATELY"
                    raise StopProof(self.stop_condition) from None
                if category not in {"NETWORK", "GATEWAY_FAILURE", "TRANSFER_FAILED"}:
                    self.stop_condition = category or "SAMPLE_STREAM_FAILED"
                    raise StopProof(self.stop_condition) from None
                from telegram_courses.downloads import DownloadError

                raise DownloadError(category) from None
            finally:
                await stream.aclose()
            if len(captured) != length:
                from telegram_courses.downloads import DownloadError

                raise DownloadError("TRANSFER_FAILED")
            accepted_request = next((
                record for record in reversed(self.request_ledger)
                if record.get("sample_index") == self.accepted_sample_count
                and record.get("received_bytes") == length
            ), None)
            if accepted_request is None:
                self.stop_condition = "SAMPLE_RECEIPT_UNPROVEN"
                raise StopProof(self.stop_condition)
            accepted_request["accepted"] = True
            self.samples[(offset, length)] = bytes(captured)
            self.accepted_sample_count += 1
        return SimpleNamespace(result="PROBE_COMPLETE", transferred_bytes=sum(map(len, self.samples.values())))

    async def _gateway_reservation(self, _amount: int) -> Any:
        # Each actual GetFile is reserved at TelegramClient._call below.
        # This satisfies the gateway hook while avoiding a duplicate lease.
        return SimpleNamespace(
            received=lambda _size: None,
            release=lambda: None,
            charge_uncertain=lambda: None,
        )


def _check_static_contract() -> dict[str, Any]:
    import inspect

    import telethon
    from telethon.client.downloads import _DirectDownloadIter
    from telethon.tl.functions.upload import GetFileHashesRequest, GetFileRequest

    from telegram_courses import downloads, s5_downloads, telethon_gateway
    from telegram_courses.telethon_session import _ProtectedSessionVault

    direct_request_source = inspect.getsource(_DirectDownloadIter._request)
    budget_source = inspect.getsource(telethon_gateway.TelethonGateway._begin_strict_budget_stream)
    direct_limit = telethon_gateway._direct_download_limit(EXPECTED_BYTES, MAX_GETFILE_REQUEST_SIZE)
    expected_chunk_count = (
        EXPECTED_BYTES + MAX_GETFILE_REQUEST_SIZE - 1
    ) // MAX_GETFILE_REQUEST_SIZE
    probe_source = inspect.getsource(ProbeApplication.download)
    execute_source = inspect.getsource(_execute)
    reservation_position = execute_source.index("lease = await app.chunk_reserver")
    rpc_position = execute_source.index(
        "response = await original_call(sender, request", reservation_position
    )
    checks = {
        "telethon_expected": telethon.__version__ == "1.45.0",
        "vault_interface": callable(getattr(_ProtectedSessionVault, "_load", None)),
        "gateway_restore": callable(getattr(telethon_gateway.TelethonGateway, "restore", None)),
        "gateway_hashes": callable(getattr(telethon_gateway.TelethonGateway, "get_file_hashes", None)),
        "gateway_stream_offset": "offset" in inspect.signature(
            telethon_gateway.TelethonGateway.stream_media
        ).parameters,
        "s5_queue_budget": callable(getattr(s5_downloads.DownloadQueue, "run", None)),
        "s5_budget_constructor": "max_transfer_bytes" in inspect.signature(
            s5_downloads.DownloadQueue
        ).parameters,
        "single_media_path_not_used": downloads.SingleMediaDownloadApplication.__name__ not in ProbeApplication.__bases__
        and "SingleMediaDownloadApplication" not in ProbeApplication.download.__code__.co_names,
        "wire_request_types": GetFileRequest.__name__ == "GetFileRequest"
        and GetFileHashesRequest.__name__ == "GetFileHashesRequest",
        "direct_iterator_request_hook": callable(getattr(_DirectDownloadIter, "_request", None)),
        "direct_limit_covers_all_chunks": direct_limit >= expected_chunk_count,
        "direct_limit_is_power_of_two": direct_limit > 0 and (direct_limit & (direct_limit - 1)) == 0,
        "direct_limit_preserves_aligned_offsets": MAX_GETFILE_REQUEST_SIZE % direct_limit == 0,
        "wire_call_interception": "self._client._call(self._sender, self.request)" in direct_request_source,
        "gateway_retry_suppression": "self._client._request_retries = 0" in budget_source,
        "actual_rpc_reserved_first": reservation_position < rpc_position,
        "probe_does_not_call_full_download": "SingleMediaDownloadApplication" not in execute_source
        and "SingleMediaDownloadApplication" not in probe_source,
        "fixed_probe_offsets": "while self.expected_sample is not None" in probe_source
        and "offset, length = self.expected_sample" in probe_source
        and SAMPLES == ((0, 262144), (262144, 262144), (524288, 262144)),
        "max_transfer_fixed": MAX_TRANSFER_BYTES == 4194304,
        "per_sample_attempts_fixed": MAX_ATTEMPTS_PER_MEDIA == 3,
        "samples_fixed": SAMPLES == ((0, 262144), (262144, 262144), (524288, 262144)),
    }
    return checks


def _dry_run() -> int:
    checks = _check_static_contract()
    target = {
        "channel_id": CHANNEL_ID,
        "message_id": MESSAGE_ID,
        "media_ordinal": MEDIA_ORDINAL,
        "media_kind": MEDIA_KIND,
        "telegram_media_id": TELEGRAM_MEDIA_ID,
        "expected_bytes": EXPECTED_BYTES,
        "media_item_id": MEDIA_ITEM_ID,
    }
    limits = {
        "max_media_items": MAX_MEDIA_ITEMS,
        "workers": WORKERS,
        "max_transfer_bytes": MAX_TRANSFER_BYTES,
        "max_getfile_requests": MAX_GETFILE_REQUESTS,
        "max_getfilehashes_requests": MAX_GETFILEHASHES_REQUESTS,
        "max_getfile_request_size": MAX_GETFILE_REQUEST_SIZE,
        "max_attempts_per_media": MAX_ATTEMPTS_PER_MEDIA,
        "planned_samples": [{"offset": start, "length": size} for start, size in SAMPLES],
        "planned_payload_bytes": sum(size for _, size in SAMPLES),
    }
    print(json.dumps({
        "mode": "DRY_RUN",
        "python_version": sys.version.split()[0],
        "telethon_version": importlib.metadata.version("Telethon"),
        "target": target,
        "limits": limits,
        "static_checks": checks,
        "telegram_operations": 0,
        "session_restore": False,
        "sqlite_operations": 0,
        "media_writes": 0,
        "full_download_requested": False,
    }, indent=2))
    return 0 if all(checks.values()) else 2


def _verify_remote_identity(message: Any, utils: Any) -> None:
    document = getattr(getattr(message, "media", None), "document", None)
    peer = getattr(message, "peer_id", None)
    if (
        message is None
        or type(getattr(message, "id", None)) is not int
        or message.id != MESSAGE_ID
        or peer is None
        or utils.get_peer_id(peer) != CHANNEL_ID
        or document is None
        or str(getattr(document, "id", "")) != TELEGRAM_MEDIA_ID
        or type(getattr(document, "size", None)) is not int
        or document.size != EXPECTED_BYTES
        or MEDIA_ORDINAL != 0
    ):
        raise StopProof("MEDIA_IDENTITY_MISMATCH")


async def _hash_ranges(gateway: Any, evidence: Evidence) -> list[Any]:
    collected: list[Any] = []
    calls = evidence.hash_calls if evidence.hash_calls is not None else []
    evidence.hash_calls = calls
    cursor = 0
    while cursor < HASH_COVERAGE_END and len(calls) < MAX_GETFILEHASHES_REQUESTS:
        call = {
            "offset": cursor,
            "wire_status": "NOT_EMITTED",
            "range_count": None,
            "parse_status": "NOT_PARSED",
            "parsed_range_count": 0,
        }
        calls.append(call)
        try:
            response = await gateway.get_file_hashes(
                CHANNEL_ID,
                MESSAGE_ID,
                MEDIA_ORDINAL,
                telegram_media_id=TELEGRAM_MEDIA_ID,
                expected_bytes=EXPECTED_BYTES,
                offset=cursor,
            )
        except BaseException:
            call["parse_status"] = "NO_RESPONSE"
            raise
        call["parse_status"] = "INVALID"
        if not isinstance(response, (tuple, list)) or not response:
            call["range_count"] = len(response) if isinstance(response, (tuple, list)) else 0
            raise StopProof("REMOTE_HASHES_UNAVAILABLE")
        call["range_count"] = len(response)
        next_cursor = cursor
        for item in response:
            start = getattr(item, "offset", None)
            length = getattr(item, "limit", None)
            digest = getattr(item, "sha256", None)
            evidence.hash_ranges = evidence.hash_ranges or []
            evidence.hash_ranges.append({
                "offset": start if type(start) is int else None,
                "length": length if type(length) is int else None,
                "sha256": digest.hex() if isinstance(digest, bytes) else None,
            })
            if (
                type(start) is not int or type(length) is not int or length <= 0
                or start != next_cursor or start + length > EXPECTED_BYTES
                or not isinstance(digest, bytes) or len(digest) != hashlib.sha256().digest_size
            ):
                raise StopProof("REMOTE_HASH_RESPONSE_INCOMPATIBLE")
            collected.append(item)
            call["parsed_range_count"] += 1
            next_cursor = start + length
        if next_cursor <= cursor:
            raise StopProof("REMOTE_HASHES_NO_PROGRESS")
        call["parse_status"] = "VALID"
        cursor = next_cursor
    return collected


def _compare_ranges(ranges: list[Any], samples: dict[tuple[int, int], bytes]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for item in ranges:
        start, end = item.offset, item.offset + item.limit
        containing = next(
            ((sample_start, sample) for (sample_start, _), sample in samples.items()
             if sample_start <= start and end <= sample_start + len(sample)),
            None,
        )
        if containing is None:
            continue
        sample_start, sample = containing
        local_hash = hashlib.sha256(sample[start - sample_start:end - sample_start]).digest()
        comparisons.append({
            "range_start": start,
            "range_end": end,
            "remote_hash": item.sha256.hex(),
            "local_hash": local_hash.hex(),
            "match_result": local_hash == item.sha256,
        })
    return comparisons


def _evaluate_sample_hashes(
    comparisons: list[dict[str, Any]],
    samples: tuple[tuple[int, int], ...] = SAMPLES,
) -> tuple[list[dict[str, Any]], str]:
    """Classify sampled SHA-256 coverage from recorded intervals and digest strings.

    Stored ``match_result`` and ``fully_compared`` fields are intentionally ignored;
    this evaluator is also used to replay prior evidence independently.
    """
    coverage: list[dict[str, Any]] = []
    intervals: list[tuple[int, int, bytes, bytes]] = []
    for item in comparisons:
        if not isinstance(item, dict):
            return coverage, "INVALID_COVERAGE"
        start, end = item.get("range_start"), item.get("range_end")
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            return coverage, "INVALID_COVERAGE"
        try:
            remote = bytes.fromhex(item.get("remote_hash", ""))
            local = bytes.fromhex(item.get("local_hash", ""))
        except (TypeError, ValueError):
            return coverage, "INVALID_COVERAGE"
        digest_size = hashlib.sha256().digest_size
        if len(remote) != digest_size or len(local) != digest_size:
            return coverage, "INVALID_COVERAGE"
        intervals.append((start, end, remote, local))

    if not intervals:
        return [
            {"start": start, "end": start + length, "fully_compared": False}
            for start, length in samples
        ], "INCOMPLETE"

    intervals.sort(key=lambda item: (item[0], item[1]))
    has_mismatch = any(remote != local for _start, _end, remote, local in intervals)
    interval_index = 0
    for sample_start, sample_length in samples:
        sample_end = sample_start + sample_length
        relevant: list[tuple[int, int, bytes, bytes]] = []
        while (
            interval_index < len(intervals)
            and intervals[interval_index][0] < sample_end
        ):
            interval = intervals[interval_index]
            interval_index += 1
            if interval[0] < sample_start or interval[1] > sample_end:
                return coverage, "INVALID_COVERAGE"
            relevant.append(interval)

        cursor = sample_start
        fully_compared = False
        for start, end, _remote, _local in relevant:
            if start < cursor:
                return coverage, "INVALID_COVERAGE"
            if start > cursor:
                if cursor != sample_start:
                    # A later interval after a hole is an incompatible partition.
                    return coverage, "INVALID_COVERAGE"
                break
            cursor = end
        fully_compared = cursor == sample_end
        coverage.append({
            "start": sample_start,
            "end": sample_end,
            "fully_compared": fully_compared,
        })

    if interval_index != len(intervals):
        return coverage, "INVALID_COVERAGE"
    if has_mismatch:
        return coverage, "HASH_MISMATCH"
    if not all(item["fully_compared"] for item in coverage):
        return coverage, "INCOMPLETE"
    return coverage, "PASS_SAMPLED_RANGES_ONLY"


def _result_exit_code(result: str) -> int:
    return 0 if result == "PASS_SAMPLED_RANGES_ONLY" else 4


def _getfile_attempt_counters(
    observed: list[dict[str, Any]], *, sample_index: int, media_attempt: int
) -> dict[str, int]:
    """Separate global RPC order from sample request order and media attempts."""
    getfile_records = [item for item in observed if item.get("kind") == "GetFileRequest"]
    sample_records = [
        item for item in getfile_records if item.get("sample_index") == sample_index
    ]
    return {
        "getfile_rpc_index": len(getfile_records) + 1,
        "sample_request_ordinal": len(sample_records) + 1,
        "sample_index": sample_index,
        "media_attempt": media_attempt,
    }


async def _execute(output_root: Path, evidence: Evidence) -> None:
    from telethon import utils
    from telethon.tl.functions.upload import GetFileHashesRequest, GetFileRequest

    from telegram_courses.auth import AuthState
    from telegram_courses.config import load_telegram_credentials
    from telegram_courses.download_repository import DownloadCandidate
    from telegram_courses.downloads import DownloadGatewayError
    from telegram_courses.s5_downloads import (
        DownloadPlan,
        DownloadQueue,
        DownloadSelection,
        PlanItem,
    )
    from telegram_courses.telethon_gateway import TelethonGateway

    # Environment credentials are deliberately ignored: this probe must use the
    # account's existing protected credential vault and protected session vault.
    credentials = load_telegram_credentials(environ={})
    gateway = TelethonGateway(credentials, request_retries=0, connection_retries=0)
    try:
        state = await gateway.restore()
    except Exception:
        await gateway.close()
        raise StopProof("SESSION_UNAVAILABLE") from None
    evidence.authentication = state.name
    if state is not AuthState.AUTHENTICATED:
        await gateway.close()
        raise StopProof("SESSION_UNAVAILABLE")

    client = gateway._client
    if client is None:
        await gateway.close()
        raise StopProof("SESSION_UNAVAILABLE")

    try:
        message = await client.get_messages(await client.get_input_entity(CHANNEL_ID), ids=MESSAGE_ID)
        _verify_remote_identity(message, utils)
    except StopProof:
        await gateway.close()
        raise
    except Exception:
        await gateway.close()
        raise StopProof("REMOTE_IDENTITY_LOOKUP_FAILED") from None
    evidence.remote_identity = {
        "channel_id": CHANNEL_ID,
        "message_id": MESSAGE_ID,
        "media_ordinal": MEDIA_ORDINAL,
        "media_kind": MEDIA_KIND,
        "telegram_media_id": TELEGRAM_MEDIA_ID,
        "expected_bytes": EXPECTED_BYTES,
        "media_item_id": MEDIA_ITEM_ID,
        "match": True,
    }

    observed: list[dict[str, Any]] = []
    original_call = client._call
    app: ProbeApplication | None = None

    async def instrumented_call(sender: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(request, GetFileHashesRequest):
            call_record = next((
                item for item in reversed(evidence.hash_calls or [])
                if item["offset"] == int(request.offset) and item["wire_status"] == "NOT_EMITTED"
            ), None)
            if sum(item["kind"] == "GetFileHashesRequest" for item in observed) >= MAX_GETFILEHASHES_REQUESTS:
                if call_record is not None:
                    call_record["wire_status"] = "REJECTED_LIMIT"
                raise StopProof("GETFILEHASHES_REQUEST_LIMIT")
            record = {"kind": "GetFileHashesRequest", "offset": int(request.offset)}
            observed.append(record)
            if call_record is not None:
                call_record["wire_status"] = "IN_FLIGHT"
            try:
                response = await original_call(sender, request, *args, **kwargs)
            except BaseException as error:
                if call_record is not None:
                    call_record["wire_status"] = "FAILED"
                    call_record["rpc_error"] = type(error).__name__
                raise
            if call_record is not None:
                call_record["wire_status"] = "SUCCEEDED"
                call_record["range_count"] = len(response) if isinstance(response, (tuple, list)) else 0
            return response
        if isinstance(request, GetFileRequest):
            if app is None or app.chunk_reserver is None:
                raise DownloadGatewayError("BUDGET_ENFORCEMENT_UNPROVEN")
            counters = _getfile_attempt_counters(
                observed,
                sample_index=app.accepted_sample_count,
                media_attempt=app.media_attempts,
            )
            getfile_rpc_index = counters["getfile_rpc_index"]
            if getfile_rpc_index > MAX_GETFILE_REQUESTS:
                raise DownloadGatewayError("GETFILE_REQUEST_LIMIT")
            expected_request = app.expected_sample
            if expected_request is None:
                raise DownloadGatewayError("UNPLANNED_GETFILE_REQUEST")
            sample_attempts = counters["sample_request_ordinal"] - 1
            if sample_attempts >= MAX_ATTEMPTS_PER_MEDIA:
                raise DownloadGatewayError("SAMPLE_REQUEST_LIMIT")
            limit = request.limit
            offset = request.offset
            if (
                type(limit) is not int or limit <= 0 or limit > MAX_GETFILE_REQUEST_SIZE
                or (offset, limit) != expected_request
            ):
                raise DownloadGatewayError("UNPLANNED_GETFILE_REQUEST")
            lease = await app.chunk_reserver(MAX_GETFILE_REQUEST_SIZE)
            if lease is None:
                raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
            evidence.reservations += 1
            evidence.reserved_in_flight += MAX_GETFILE_REQUEST_SIZE
            lease = Lease(lease, evidence)
            record = {
                "kind": "GetFileRequest",
                "offset": offset,
                "limit": limit,
                **counters,
            }
            observed.append(record)
            try:
                response = await original_call(sender, request, *args, **kwargs)
            except BaseException:
                lease.charge_uncertain()
                raise
            payload = getattr(response, "bytes", None)
            if not isinstance(payload, bytes) or len(payload) > limit:
                lease.charge_uncertain()
                app.stop_condition = "GETFILE_RESPONSE_INVALID"
                raise StopProof("GETFILE_RESPONSE_INVALID")
            lease.received(len(payload))
            record["received_bytes"] = len(payload)
            return response
        return await original_call(sender, request, *args, **kwargs)

    client._call = instrumented_call
    try:
        try:
            ranges = await _hash_ranges(gateway, evidence)
        except DownloadGatewayError as error:
            if error.category == "RATE_LIMITED":
                raise StopProof("FLOODWAIT_STOP_IMMEDIATELY") from None
            raise StopProof(error.category) from None
        app = ProbeApplication(gateway, evidence, output_root)
        app.request_ledger = observed
        candidate = DownloadCandidate(
            media_item_id=MEDIA_ITEM_ID,
            channel_id=CHANNEL_ID,
            telegram_message_id=MESSAGE_ID,
            media_ordinal=MEDIA_ORDINAL,
            telegram_media_id=TELEGRAM_MEDIA_ID,
            expected_bytes=EXPECTED_BYTES,
            original_filename="s6-probe.bin",
            lineage=(("lesson", "S6 manual proof"),),
        )
        plan = DownloadPlan(
            plan_id="S6-REAL-COMPAT-PROOF-01",
            selection=DownloadSelection(channel_id=CHANNEL_ID, scope="lesson", node_id=1),
            scope_title="S6 manual proof",
            catalog_complete=False,
            lesson_count=1,
            items=(PlanItem(
                identity=(CHANNEL_ID, MESSAGE_ID, MEDIA_ORDINAL),
                candidate=candidate,
                status="PENDING",
                estimated_payload_bytes=sum(length for _, length in SAMPLES),
                estimated_additional_disk_bytes=0,
            ),),
        )
        queue = DownloadQueue(
            repository=object(),  # queue uses no repository for its in-memory plan
            application=app,  # type: ignore[arg-type]
            workers=WORKERS,
            attempts_per_media=MAX_ATTEMPTS_PER_MEDIA,
            free_space=lambda _path: 2 * 1024**3,
            max_media_items=MAX_MEDIA_ITEMS,
            max_transfer_bytes=MAX_TRANSFER_BYTES,
        )
        outcome = await queue.run(plan)
        has_failed_or_blocked_item = any(
            status in {"FAILED", "BLOCKED"}
            for _identity, status, _reason in outcome.outcomes
        )
        if outcome.failed or has_failed_or_blocked_item:
            category = next(
                (
                    reason for _identity, status, reason in outcome.outcomes
                    if status in {"FAILED", "BLOCKED"} and reason is not None
                ),
                None,
            )
            raise StopProof(app.stop_condition or category or "PROBE_QUEUE_STOPPED")
        comparisons = _compare_ranges(ranges, app.samples)
        evidence.hash_comparisons = comparisons
        coverage_end = 0
        for item in ranges:
            if item.offset != coverage_end:
                break
            coverage_end = item.offset + item.limit
        evidence.hash_coverage = {
            "contiguous_from_zero_bytes": coverage_end,
            "requested_region_end_bytes": HASH_COVERAGE_END,
            "requested_region_fully_covered": coverage_end >= HASH_COVERAGE_END,
            "gaps": [
                {"start": coverage_end, "end": HASH_COVERAGE_END}
            ] if coverage_end < HASH_COVERAGE_END else [],
        }
        compared_coverage, hash_verdict = _evaluate_sample_hashes(comparisons)
        evidence.compared_sample_coverage = compared_coverage
        evidence.getfile_requests = [
            item for item in observed if item["kind"] == "GetFileRequest"
        ]
        accepted_requests = [
            item for item in evidence.getfile_requests if item.get("accepted") is True
        ]
        if (
            app.accepted_sample_count != len(SAMPLES)
            or sorted(item.get("sample_index") for item in accepted_requests)
            != list(range(len(SAMPLES)))
        ):
            raise StopProof("OFFSET_REQUEST_COVERAGE_INCOMPLETE")
        if sum(item.get("received_bytes", 0) for item in accepted_requests) != sum(
            len(data) for data in app.samples.values()
        ):
            raise StopProof("ACCEPTED_BYTE_ACCOUNTING_MISMATCH")
        evidence.result = hash_verdict
    finally:
        evidence.getfile_requests = [
            item for item in observed if item["kind"] == "GetFileRequest"
        ]
        evidence.hash_requests = [
            {"offset": item["offset"]}
            for item in observed if item["kind"] == "GetFileHashesRequest"
        ]
        if evidence.hash_calls is None:
            evidence.hash_calls = evidence.hash_requests
        client._call = original_call
        await gateway.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        return _dry_run()

    if input(f"Digite {CONFIRMATION!r} para continuar; qualquer outra resposta cancela: ") != CONFIRMATION:
        print("STOP=USER_CONFIRMATION_MISSING")
        return 3
    configured_output = os.environ.get("S6_PROOF_EVIDENCE_DIR")
    if not configured_output:
        print("STOP=EVIDENCE_DIRECTORY_UNSET")
        return 3
    output_root = Path(configured_output)
    if output_root.exists() and any(output_root.iterdir()):
        print("STOP=EVIDENCE_DIRECTORY_NOT_EMPTY")
        return 3
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="s6-real-compat-proof-", dir=output_root))
    evidence = Evidence(
        python_version=sys.version.split()[0],
        telethon_version=importlib.metadata.version("Telethon"),
        hash_calls=[],
        hash_ranges=[],
        hash_comparisons=[],
        getfile_requests=[],
        errors=[],
        gateway_diagnostics=[],
        failure_traceback=[],
    )
    diagnostic_logger = logging.getLogger("telegram_courses.telethon_gateway")
    diagnostic_handler = _SafeGatewayDiagnosticHandler(evidence)
    diagnostic_logger.addHandler(diagnostic_handler)
    try:
        asyncio.run(_execute(run_dir, evidence))
    except StopProof as error:
        evidence.stop_condition = error.condition
        evidence.errors.append(error.condition)
        evidence.result = "INCONCLUSIVE"
    except Exception as error:  # report only safe class, never exception text
        evidence.stop_condition = "UNEXPECTED_SANITIZED_FAILURE"
        evidence.errors.append(type(error).__name__)
        evidence.failure_traceback = _safe_traceback_locations(error)
        evidence.result = "INCONCLUSIVE"
    finally:
        diagnostic_logger.removeHandler(diagnostic_handler)
        diagnostic_handler.close()
    report_path = run_dir / "evidence.json"
    evidence.reserved_in_flight = max(0, evidence.reserved_in_flight)
    evidence.remaining_bytes = MAX_TRANSFER_BYTES - evidence.consumed_bytes - evidence.reserved_in_flight
    report_path.write_text(json.dumps(asdict(evidence), indent=2), encoding="utf-8")
    print(f"EVIDENCE={report_path}")
    print(json.dumps(asdict(evidence), indent=2))
    return _result_exit_code(evidence.result)


if __name__ == "__main__":
    raise SystemExit(main())
