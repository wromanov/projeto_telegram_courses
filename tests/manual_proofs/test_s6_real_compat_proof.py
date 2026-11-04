from __future__ import annotations

import hashlib
import json
import logging
import os
from types import SimpleNamespace
from typing import Any

import pytest
from tools.manual_proofs import s6_real_compat_proof as proof


class _FakeGateway:
    def __init__(self, responses: list[list[Any]]) -> None:
        self.responses = iter(responses)

    async def get_file_hashes(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return next(self.responses)


class _TransientGatewayFailure(Exception):
    category = "NETWORK"


class _RetryStreamGateway:
    def __init__(self) -> None:
        self.offsets: list[int] = []
        self.fail_offset_once: int | None = None
        self.requests: list[dict[str, Any]] = []

    def stream_media(self, *_args: Any, offset: int, **_kwargs: Any):
        self.offsets.append(offset)
        record = {
            "sample_index": next(
                index for index, (sample_offset, _length) in enumerate(proof.SAMPLES)
                if sample_offset == offset
            )
        }
        self.requests.append(record)

        async def chunks():
            if offset == self.fail_offset_once:
                self.fail_offset_once = None
                raise _TransientGatewayFailure()
            length = proof.SAMPLES[record["sample_index"]][1]
            record["received_bytes"] = length
            yield bytes(length)

        return chunks()


class _FakeLease:
    def __init__(self) -> None:
        self.settlements: list[tuple[str, int | None]] = []

    def received(self, amount: int) -> None:
        self.settlements.append(("received", amount))

    def release(self) -> None:
        self.settlements.append(("release", None))

    def charge_uncertain(self) -> None:
        self.settlements.append(("uncertain", None))


def _remote_hash(offset: int, payload: bytes) -> SimpleNamespace:
    return SimpleNamespace(
        offset=offset,
        limit=len(payload),
        sha256=hashlib.sha256(payload).digest(),
    )


def _run_immediate(coroutine: Any) -> Any:
    """Run an async helper whose fake awaitables never suspend on I/O."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("offline fake unexpectedly suspended")


def test_static_contract_checks_pass() -> None:
    checks = proof._check_static_contract()

    assert checks
    assert all(checks.values()), checks


def test_hash_ranges_reject_gap_in_remote_coverage() -> None:
    evidence = proof.Evidence(python_version="test", telethon_version="test")
    gateway = _FakeGateway([
        [_remote_hash(0, b"abcd")],
        [_remote_hash(5, b"efgh")],
    ])

    with pytest.raises(proof.StopProof, match="REMOTE_HASH_RESPONSE_INCOMPATIBLE"):
        _run_immediate(proof._hash_ranges(gateway, evidence))

    assert [call["parse_status"] for call in evidence.hash_calls or []] == ["VALID", "INVALID"]
    assert [call["parsed_range_count"] for call in evidence.hash_calls or []] == [1, 0]


def test_hash_ranges_prove_two_128k_ranges_for_each_256k_sample() -> None:
    class SplitHashGateway:
        def __init__(self) -> None:
            self.offsets: list[int] = []

        async def get_file_hashes(self, *_args: Any, offset: int, **_kwargs: Any) -> list[Any]:
            self.offsets.append(offset)
            half = 128 * 1024
            return [
                _remote_hash(offset, b"a" * half),
                _remote_hash(offset + half, b"b" * half),
            ]

    evidence = proof.Evidence(python_version="test", telethon_version="test")
    gateway = SplitHashGateway()
    ranges = _run_immediate(proof._hash_ranges(gateway, evidence))

    assert gateway.offsets == [0, 262144, 524288]
    assert [(item.offset, item.limit) for item in ranges] == [
        (base + delta, 128 * 1024)
        for base in (0, 262144, 524288)
        for delta in (0, 128 * 1024)
    ]
    assert [call["parsed_range_count"] for call in evidence.hash_calls or []] == [2, 2, 2]


def test_hash_call_failure_is_reported_without_claiming_parsed_ranges() -> None:
    class _FailingGateway:
        def __init__(self) -> None:
            self.calls = 0

        async def get_file_hashes(self, *_args: Any, **_kwargs: Any) -> list[Any]:
            self.calls += 1
            if self.calls == 1:
                return [_remote_hash(0, b"abcd")]
            raise RuntimeError("offline failure")

    evidence = proof.Evidence(python_version="test", telethon_version="test")

    with pytest.raises(RuntimeError, match="offline failure"):
        _run_immediate(proof._hash_ranges(_FailingGateway(), evidence))

    assert evidence.hash_calls is not None
    assert evidence.hash_calls[0]["parse_status"] == "VALID"
    assert evidence.hash_calls[0]["parsed_range_count"] == 1
    assert evidence.hash_calls[1]["wire_status"] == "NOT_EMITTED"
    assert evidence.hash_calls[1]["parse_status"] == "NO_RESPONSE"


def test_sanitized_diagnostics_are_included_in_harness_evidence() -> None:
    evidence = proof.Evidence(
        python_version="test",
        telethon_version="test",
        gateway_diagnostics=[],
    )
    handler = proof._SafeGatewayDiagnosticHandler(evidence)
    record = logging.LogRecord(
        "telegram_courses.telethon_gateway",
        logging.WARNING,
        "C:\\Users\\private\\telethon_gateway.py",
        900,
        "authentication diagnostic FAILURE_STAGE=%s SANITIZED_EXCEPTION_CLASS=%s "
        "PROJECT_ERROR_CATEGORY=%s SANITIZED_TRACEBACK=%s",
        ("MEDIA_HASH", "TypeError", "ADAPTER", "upload.py:147:_bytes"),
        None,
    )

    handler.emit(record)

    assert evidence.gateway_diagnostics == [
        "authentication diagnostic FAILURE_STAGE=MEDIA_HASH "
        "SANITIZED_EXCEPTION_CLASS=TypeError PROJECT_ERROR_CATEGORY=ADAPTER "
        "SANITIZED_TRACEBACK=upload.py:147:_bytes"
    ]
    assert "C:\\Users\\private" not in evidence.gateway_diagnostics[0]


def test_unexpected_failure_traceback_contains_only_sanitized_locations() -> None:
    def raise_synthetic_error() -> None:
        raise TypeError("synthetic-secret-value")

    try:
        raise_synthetic_error()
    except TypeError as error:
        locations = proof._safe_traceback_locations(error)

    assert any("test_s6_real_compat_proof.py:" in location for location in locations)
    assert any("raise_synthetic_error" in location for location in locations)
    assert all("C:\\Users\\" not in location for location in locations)
    assert all("synthetic-secret-value" not in location for location in locations)


def test_download_retry_repeats_only_the_unaccepted_sample() -> None:
    from telegram_courses.downloads import DownloadError

    gateway = _RetryStreamGateway()
    gateway.fail_offset_once = proof.SAMPLES[1][0]
    evidence = proof.Evidence(python_version="test", telethon_version="test")
    app = proof.ProbeApplication(gateway, evidence, proof.Path("."))
    app.request_ledger = gateway.requests

    with pytest.raises(DownloadError) as error:
        _run_immediate(app.download())
    assert error.value.category == "NETWORK"
    assert app.accepted_sample_count == 1
    assert (proof.SAMPLES[0][0], proof.SAMPLES[0][1]) in app.samples

    result = _run_immediate(app.download())

    assert result.transferred_bytes == sum(length for _, length in proof.SAMPLES)
    assert gateway.offsets == [0, 262144, 262144, 524288]
    assert app.accepted_sample_count == len(proof.SAMPLES)
    assert evidence.media_attempts == 2


def test_download_stops_before_fourth_media_attempt() -> None:
    from telegram_courses.downloads import DownloadError

    class _AlwaysFailingGateway:
        def __init__(self) -> None:
            self.offsets: list[int] = []

        def stream_media(self, *_args: Any, offset: int, **_kwargs: Any):
            self.offsets.append(offset)

            async def chunks():
                raise _TransientGatewayFailure()
                yield b""  # Keep this an async generator for the stream protocol.

            return chunks()

    gateway = _AlwaysFailingGateway()
    evidence = proof.Evidence(python_version="test", telethon_version="test")
    app = proof.ProbeApplication(gateway, evidence, proof.Path("."))

    for _attempt in range(proof.MAX_ATTEMPTS_PER_MEDIA):
        with pytest.raises(DownloadError):
            _run_immediate(app.download())

    with pytest.raises(proof.StopProof, match="ATTEMPT_LIMIT_EXCEEDED"):
        _run_immediate(app.download())

    assert gateway.offsets == [0, 0, 0]
    assert evidence.media_attempts == proof.MAX_ATTEMPTS_PER_MEDIA + 1


def test_compare_ranges_only_compares_ranges_fully_inside_a_sample() -> None:
    sample = b"abcdefgh"
    samples = {(0, len(sample)): sample}
    ranges = [
        _remote_hash(0, sample[:4]),
        _remote_hash(4, sample[4:]),
        _remote_hash(0, sample + b"outside"),
    ]

    comparisons = proof._compare_ranges(ranges, samples)

    assert [(item["range_start"], item["range_end"]) for item in comparisons] == [
        (0, 4),
        (4, 8),
    ]
    assert all(item["match_result"] for item in comparisons)


def test_received_lease_accounts_for_actual_received_bytes() -> None:
    evidence = proof.Evidence(python_version="test", telethon_version="test")
    evidence.reservations = 1
    evidence.reserved_in_flight = proof.MAX_GETFILE_REQUEST_SIZE
    lease = _FakeLease()

    proof.Lease(lease, evidence).received(96)

    assert lease.settlements == [("received", 96)]
    assert evidence.received_bytes == 96
    assert evidence.uncertain_bytes == 0
    assert evidence.consumed_bytes == 96
    assert evidence.reserved_in_flight == 0
    assert evidence.remaining_bytes == proof.MAX_TRANSFER_BYTES - 96


def test_uncertain_lease_charges_the_full_reserved_request() -> None:
    evidence = proof.Evidence(python_version="test", telethon_version="test")
    evidence.reservations = 1
    evidence.reserved_in_flight = proof.MAX_GETFILE_REQUEST_SIZE
    lease = _FakeLease()

    proof.Lease(lease, evidence).charge_uncertain()

    assert lease.settlements == [("uncertain", None)]
    assert evidence.received_bytes == 0
    assert evidence.uncertain_bytes == proof.MAX_GETFILE_REQUEST_SIZE
    assert evidence.consumed_bytes == proof.MAX_GETFILE_REQUEST_SIZE
    assert evidence.reserved_in_flight == 0
    assert evidence.remaining_bytes == proof.MAX_TRANSFER_BYTES - proof.MAX_GETFILE_REQUEST_SIZE


def test_released_lease_frees_reservation_without_consuming_budget() -> None:
    evidence = proof.Evidence(python_version="test", telethon_version="test")
    evidence.reservations = 1
    evidence.reserved_in_flight = proof.MAX_GETFILE_REQUEST_SIZE
    lease = _FakeLease()

    proof.Lease(lease, evidence).release()

    assert lease.settlements == [("release", None)]
    assert evidence.received_bytes == 0
    assert evidence.uncertain_bytes == 0
    assert evidence.consumed_bytes == 0
    assert evidence.reserved_in_flight == 0
    assert evidence.remaining_bytes == proof.MAX_TRANSFER_BYTES


@pytest.mark.parametrize(
    ("offset", "invalid_payload", "expected_bytes", "drain_all"),
    [
        (0, None, 11649955, False),
        (262144, None, 11649955, False),
        (524288, None, 11649955, False),
        (1048576, None, 11649955, False),
        (262144, "memoryview", 11649955, False),
        (262144, "empty", 11649955, False),
        (262144, "oversize", 11649955, False),
        (0, None, 3 * 256 * 1024, True),
        (2 * 256 * 1024, None, 5 * 256 * 1024, True),
    ],
)
def test_telethon_145_aligned_offsets_use_direct_iterator_and_yield_bytes(
    offset: int, invalid_payload: str | None, expected_bytes: int, drain_all: bool
) -> None:
    """Exercise Telethon's real selector and iterator with an offline synthetic RPC."""
    import asyncio
    import logging
    from datetime import UTC, datetime

    from telethon.client.downloads import DownloadMethods
    from telethon.tl.types import Document, PeerChannel

    from telegram_courses.auth import AuthState
    from telegram_courses.telethon_gateway import TelethonGateway

    chunk_bytes = 256 * 1024
    document = Document(
        id=5175124468544046445,
        access_hash=7,
        file_reference=b"synthetic",
        date=datetime.now(UTC),
        mime_type="application/octet-stream",
        size=expected_bytes,
        dc_id=2,
        attributes=[],
    )
    timeline: list[tuple[str, int | None]] = []

    class Reservation:
        def __init__(self) -> None:
            self.events: list[tuple[str, int | None]] = []

        def received(self, amount: int) -> None:
            self.events.append(("received", amount))
            timeline.append(("received", amount))

        def release(self) -> None:
            self.events.append(("released", None))

        def charge_uncertain(self) -> None:
            self.events.append(("uncertain", None))
            timeline.append(("uncertain", None))

    reservation = Reservation()

    class OfflineClient:
        _request_retries = 0

        def __init__(self) -> None:
            self._sender = object()
            self.session = SimpleNamespace(dc_id=2)
            self._log = {"telethon.client.downloads": logging.getLogger("offline.telethon")}
            self.requests: list[tuple[int, int]] = []

        async def get_input_entity(self, _channel_id: int) -> str:
            return "peer"

        async def get_messages(self, _entity: str, *, ids: int) -> Any:
            return SimpleNamespace(
                id=ids,
                peer_id=PeerChannel(2758699600),
                media=SimpleNamespace(document=document),
            )

        def iter_download(self, file: Any, **kwargs: Any) -> Any:
            return DownloadMethods._iter_download(self, file, **kwargs)

        async def _call(self, _sender: Any, request: Any) -> Any:
            self.requests.append((request.offset, request.limit))
            timeline.append(("rpc", request.offset))
            if invalid_payload == "memoryview":
                payload = memoryview(bytearray(b"x" * chunk_bytes))
            elif invalid_payload == "empty":
                payload = b""
            elif invalid_payload == "oversize":
                payload = b"x" * (chunk_bytes + 1)
            else:
                payload = b"x" * chunk_bytes
            return SimpleNamespace(bytes=payload)

    client = OfflineClient()
    adapter = object.__new__(TelethonGateway)
    adapter._client = client
    adapter._state = AuthState.AUTHENTICATED
    adapter._strict_budget_lock = asyncio.Lock()
    adapter._strict_budget_streams = 0
    adapter._strict_budget_previous_retries = None
    adapter._record_failure = lambda *_args: None

    async def reserve(amount: int) -> Reservation:
        assert amount == chunk_bytes
        timeline.append(("reserve", amount))
        return reservation

    async def exercise() -> None:
        stream = adapter._iterate_media(
            -1002758699600,
            598,
            0,
            telegram_media_id=str(document.id),
            expected_bytes=expected_bytes,
            chunk_bytes=chunk_bytes,
            reserve_chunk=reserve,
            offset=offset,
        )
        if invalid_payload is not None:
            from telegram_courses.downloads import DownloadGatewayError

            try:
                await stream.__anext__()
            except DownloadGatewayError as error:
                assert error.category == "INVALID_CHUNK"
            else:
                raise AssertionError("memoryview chunk was accepted")
            assert reservation.events == [("uncertain", None)]
            assert timeline == [
                ("reserve", chunk_bytes), ("rpc", offset), ("uncertain", None)
            ]
        elif drain_all:
            chunks = [chunk async for chunk in stream]
            assert chunks == [b"x" * chunk_bytes] * 3
            assert client.requests == [
                (offset, chunk_bytes),
                (offset + chunk_bytes, chunk_bytes),
                (offset + 2 * chunk_bytes, chunk_bytes),
            ]
            assert reservation.events == [("received", chunk_bytes)] * 3
            assert timeline == [
                event
                for request_offset in (offset, offset + chunk_bytes, offset + 2 * chunk_bytes)
                for event in (
                    ("reserve", chunk_bytes),
                    ("rpc", request_offset),
                    ("received", chunk_bytes),
                )
            ]
        else:
            assert await stream.__anext__() == b"x" * chunk_bytes
            assert reservation.events == [("received", chunk_bytes)]
            assert timeline == [
                ("reserve", chunk_bytes), ("rpc", offset), ("received", chunk_bytes)
            ]
            assert len(client.requests) == 1
            assert client.requests[0] == (offset, chunk_bytes)
        await stream.aclose()
        assert adapter._strict_budget_streams == 0

    _run_immediate(exercise())


def test_direct_download_limit_rejects_incompatible_geometry() -> None:
    from telegram_courses.downloads import DownloadGatewayError
    from telegram_courses.telethon_gateway import _direct_download_limit

    with pytest.raises(DownloadGatewayError, match="DIRECT_ITERATOR_INCOMPATIBLE"):
        _direct_download_limit(100, 7)


def test_getfile_attempt_counters_separate_rpc_sample_and_media_ordinals() -> None:
    records: list[dict[str, Any]] = []
    sequence = [(0, 1), (1, 1), (1, 2), (2, 2)]
    actual = []

    for sample_index, media_attempt in sequence:
        counters = proof._getfile_attempt_counters(
            records,
            sample_index=sample_index,
            media_attempt=media_attempt,
        )
        actual.append(counters)
        records.append({"kind": "GetFileRequest", **counters})

    assert [item["getfile_rpc_index"] for item in actual] == [1, 2, 3, 4]
    assert [item["sample_request_ordinal"] for item in actual] == [1, 1, 2, 1]
    assert [item["sample_index"] for item in actual] == [0, 1, 1, 2]
    assert [item["media_attempt"] for item in actual] == [1, 1, 2, 2]


def test_invalid_chunk_diagnostic_is_allowlisted_and_memoryview_remains_rejected(caplog) -> None:
    from telegram_courses.telethon_gateway import _log_invalid_chunk

    secret_payload = memoryview(bytearray(b"private-payload"))
    _log_invalid_chunk("CHUNK_TYPE", secret_payload, chunk_bytes=262144)

    message = caplog.records[-1].getMessage()
    assert "FAILURE_CATEGORY=INVALID_CHUNK" in message
    assert "CHUNK_CODE=CHUNK_TYPE" in message
    assert "MEMORYVIEW_NDIM=1" in message
    assert "MEMORYVIEW_C_CONTIGUOUS=True" in message
    assert "private-payload" not in message


def _sample_hash_comparisons() -> list[dict[str, Any]]:
    digest = hashlib.sha256(b"sample range").hexdigest()
    return [
        {
            "range_start": start + delta,
            "range_end": start + delta + 128 * 1024,
            "remote_hash": digest,
            "local_hash": digest,
            "match_result": True,
        }
        for start, _length in proof.SAMPLES
        for delta in (0, 128 * 1024)
    ]


def _real_evidence_or_skip() -> dict[str, Any]:
    path = os.environ.get("S6_REAL_EVIDENCE_PATH")
    if not path:
        pytest.skip("S6_REAL_EVIDENCE_PATH não foi definido")
    with open(path, encoding="utf-8") as evidence_file:
        return json.load(evidence_file)


def test_t01_six_matching_128k_ranges_cover_all_three_samples() -> None:
    coverage, result = proof._evaluate_sample_hashes(_sample_hash_comparisons())

    assert result == "PASS_SAMPLED_RANGES_ONLY"
    assert [(item["start"], item["end"]) for item in coverage] == list(
        (start, start + length) for start, length in proof.SAMPLES
    )
    assert all(item["fully_compared"] for item in coverage)


def test_t02_different_digest_is_a_hash_mismatch() -> None:
    comparisons = _sample_hash_comparisons()
    comparisons[0]["remote_hash"] = hashlib.sha256(b"different").hexdigest()

    _coverage, result = proof._evaluate_sample_hashes(comparisons)

    assert result == "HASH_MISMATCH"


def test_t03_missing_tail_is_incomplete() -> None:
    comparisons = _sample_hash_comparisons()[:-1]

    coverage, result = proof._evaluate_sample_hashes(comparisons)

    assert result == "INCOMPLETE"
    assert coverage[-1]["fully_compared"] is False


def test_t04_internal_gap_fails_closed_as_invalid_coverage() -> None:
    comparisons = _sample_hash_comparisons()
    comparisons[1]["range_start"] += 1

    _coverage, result = proof._evaluate_sample_hashes(comparisons)

    assert result == "INVALID_COVERAGE"


def test_t05_overlapping_ranges_fail_closed_as_invalid_coverage() -> None:
    comparisons = _sample_hash_comparisons()
    comparisons[1]["range_start"] -= 1

    _coverage, result = proof._evaluate_sample_hashes(comparisons)

    assert result == "INVALID_COVERAGE"


def test_t06_partial_comparisons_cannot_approve_samples() -> None:
    _coverage, result = proof._evaluate_sample_hashes(_sample_hash_comparisons()[:2])

    assert result == "INCOMPLETE"
    assert result != "PASS_SAMPLED_RANGES_ONLY"


def test_t07_real_getfile_records_match_reservations_and_budget() -> None:
    evidence = _real_evidence_or_skip()
    requests = evidence["getfile_requests"]

    assert len(requests) == evidence["reservations"] == 3
    assert [item["offset"] for item in requests] == [
        start for start, _ in proof.SAMPLES
    ]
    assert all(item["limit"] == proof.MAX_GETFILE_REQUEST_SIZE for item in requests)
    assert [item["getfile_rpc_index"] for item in requests] == [1, 2, 3]
    assert [item["sample_request_ordinal"] for item in requests] == [1, 1, 1]
    assert [item["sample_index"] for item in requests] == [0, 1, 2]
    assert [item["media_attempt"] for item in requests] == [1, 1, 1]
    assert evidence["media_attempts"] == 1
    assert all(item["accepted"] is True for item in requests)
    assert all(
        item["received_bytes"] == length
        for item, (_start, length) in zip(requests, proof.SAMPLES)
    )
    assert evidence["received_bytes"] == evidence["consumed_bytes"] == sum(
        item["received_bytes"] for item in requests
    ) == 786432
    assert evidence["consumed_bytes"] == (
        evidence["received_bytes"] + evidence["uncertain_bytes"]
    )
    assert evidence["uncertain_bytes"] == evidence["reserved_in_flight"] == 0
    assert evidence["remaining_bytes"] == (
        proof.MAX_TRANSFER_BYTES - evidence["consumed_bytes"]
    )
    assert (
        evidence["consumed_bytes"]
        + evidence["reserved_in_flight"]
        + evidence["remaining_bytes"]
        == proof.MAX_TRANSFER_BYTES
    )
    assert evidence["reservations"] <= proof.MAX_GETFILE_REQUESTS
    assert len(requests) <= proof.MAX_GETFILE_REQUESTS
    assert evidence["consumed_bytes"] <= proof.MAX_TRANSFER_BYTES
    assert all(item["kind"] == "GetFileRequest" for item in requests)


def test_t08_real_evidence_replay_ignores_stored_verdict_and_coverage_flags() -> None:
    evidence = _real_evidence_or_skip()
    assert evidence["telethon_version"] == "1.45.0"
    assert evidence["authentication"] == "AUTHENTICATED"
    identity = evidence["remote_identity"]
    assert identity["match"] is True
    assert identity["channel_id"] == proof.CHANNEL_ID
    assert identity["message_id"] == proof.MESSAGE_ID
    assert identity["media_ordinal"] == proof.MEDIA_ORDINAL
    assert identity["media_kind"] == proof.MEDIA_KIND
    assert identity["telegram_media_id"] == proof.TELEGRAM_MEDIA_ID
    assert identity["expected_bytes"] == proof.EXPECTED_BYTES
    assert identity["media_item_id"] == proof.MEDIA_ITEM_ID

    hash_calls = evidence["hash_calls"]
    assert len(hash_calls) == 1
    hash_call = hash_calls[0]
    assert hash_call["offset"] == 0
    assert hash_call["wire_status"] == "SUCCEEDED"
    assert hash_call["parse_status"] == "VALID"
    assert hash_call["range_count"] == hash_call["parsed_range_count"] == 8
    assert evidence["hash_requests"] == [{"offset": 0}]

    raw_ranges = evidence["hash_ranges"]
    assert len(raw_ranges) == 8
    cursor = 0
    for item in raw_ranges:
        assert type(item["offset"]) is int
        assert item["offset"] == cursor
        assert type(item["length"]) is int and item["length"] > 0
        assert len(bytes.fromhex(item["sha256"])) == 32
        cursor += item["length"]
    assert cursor == 1048576

    comparisons = evidence["hash_comparisons"]
    expected_offsets = [
        0,
        131072,
        262144,
        393216,
        524288,
        655360,
    ]
    assert len(comparisons) == len(expected_offsets)
    assert [item["range_start"] for item in comparisons] == expected_offsets
    assert [item["range_end"] - item["range_start"] for item in comparisons] == [
        131072
    ] * 6
    # Recorded booleans and the old result are intentionally not inputs to replay.
    for item in comparisons:
        item.pop("match_result", None)
    coverage, result = proof._evaluate_sample_hashes(comparisons)

    assert evidence["result"] == "HASH_MISMATCH"
    assert [
        item["fully_compared"] for item in evidence["compared_sample_coverage"]
    ] == [False, False, True]
    assert result == "PASS_SAMPLED_RANGES_ONLY"
    assert all(item["fully_compared"] for item in coverage)
    assert len(comparisons) == 6
    assert all(item["remote_hash"] == item["local_hash"] for item in comparisons)
    raw_ranges_by_offset = {
        item["offset"]: item for item in evidence["hash_ranges"]
    }
    assert all(
        item["range_start"] in raw_ranges_by_offset
        and item["range_end"]
        == item["range_start"] + raw_ranges_by_offset[item["range_start"]]["length"]
        and item["remote_hash"] == raw_ranges_by_offset[item["range_start"]]["sha256"]
        for item in comparisons
    )
    hash_coverage = evidence["hash_coverage"]
    assert hash_coverage["contiguous_from_zero_bytes"] == 1048576
    assert hash_coverage["requested_region_end_bytes"] == proof.HASH_COVERAGE_END
    assert hash_coverage["requested_region_fully_covered"] is True
    assert hash_coverage["gaps"] == []
    assert evidence["errors"] == [] and evidence["stop_condition"] is None
    assert evidence["gateway_diagnostics"] == [
        "media diagnostic ITERATOR_CLASS=_DirectDownloadIter "
        "DOWNLOAD_LIMIT=64 CHUNK_COUNT=45"
    ] * 3


def test_t09_only_sampled_pass_returns_zero_exit_code() -> None:
    assert proof._result_exit_code("PASS_SAMPLED_RANGES_ONLY") == 0
    for result in (
        "HASH_MISMATCH",
        "INCOMPLETE",
        "INVALID_COVERAGE",
        "INCONCLUSIVE",
        "NOT_RUN",
    ):
        assert proof._result_exit_code(result) == 4


def test_t10_pure_evaluator_does_not_enter_telegram_execution(monkeypatch) -> None:
    def forbidden_execute(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("offline evaluator must not execute the Telegram harness")

    monkeypatch.setattr(proof, "_execute", forbidden_execute)
    coverage, result = proof._evaluate_sample_hashes(_sample_hash_comparisons())

    assert result == "PASS_SAMPLED_RANGES_ONLY"
    assert len(coverage) == len(proof.SAMPLES)
