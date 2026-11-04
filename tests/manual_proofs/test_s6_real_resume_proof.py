from __future__ import annotations

import asyncio
import hashlib
import json

import pytest
from tools.manual_proofs import s6_real_resume_proof as proof
from tools.manual_proofs.s6_resume_harness import (
    BudgetedRealGateway,
    BudgetStop,
    DurableBudgetLedger,
    RemoteFileHash,
    exercise_budget_edge_cases,
    validate_hash_response,
)

from telegram_courses.downloads import (
    CHUNK_BYTES,
    DownloadError,
    DownloadGatewayError,
    _finalize_no_overwrite,
)


def test_config_preserves_frozen_s6_target_and_budgets() -> None:
    proof._validate_constants()
    assert proof.MAX_GETFILE_REQUESTS == 51
    assert proof.MAX_GETFILEHASHES_REQUESTS == 16
    assert proof.MAX_TRANSFER_BYTES == 13_369_344
    assert proof.PREFIX_BYTES == 1_048_699
    assert proof.WIRE_OFFSET == 1_048_576
    assert proof.OVERLAP_BYTES == 123


def test_incremental_hash_coverage_accepts_variable_ranges_and_fails_closed() -> None:
    first_end = validate_hash_response(
        0, (RemoteFileHash(0, 900_001, b"a" * 32),), proof.PREFIX_BYTES
    )
    assert first_end == 900_001
    assert validate_hash_response(
        first_end,
        (RemoteFileHash(first_end, proof.PREFIX_BYTES - first_end, b"b" * 32),),
        proof.PREFIX_BYTES,
    ) == proof.PREFIX_BYTES
    assert validate_hash_response(
        0, (RemoteFileHash(0, proof.EXPECTED_BYTES, b"c" * 32),), proof.EXPECTED_BYTES
    ) == proof.EXPECTED_BYTES

    for intervals, expected in (
        ((), "HASH_COVERAGE_STALLED"),
        ((RemoteFileHash(1, 1, b"a" * 32),), "HASH_COVERAGE_GAP"),
        (
            (RemoteFileHash(0, 2, b"a" * 32), RemoteFileHash(1, 1, b"b" * 32)),
            "HASH_COVERAGE_OVERLAP",
        ),
        ((RemoteFileHash(0, proof.EXPECTED_BYTES + 1, b"a" * 32),), "HASH_COVERAGE_INVALID"),
        ((RemoteFileHash(0, 1, "not-hex"),), "HASH_COVERAGE_INVALID"),
        ((RemoteFileHash(0, 1, b"short"),), "HASH_COVERAGE_INVALID"),
    ):
        with pytest.raises(BudgetStop, match=expected):
            validate_hash_response(0, intervals, proof.EXPECTED_BYTES)


def test_hash_response_rejection_classifications_preserve_range_geometry() -> None:
    eof_range = RemoteFileHash(
        proof.HASH_PROBE_OFFSET,
        proof.EXPECTED_BYTES - proof.HASH_PROBE_OFFSET,
        b"e" * 32,
    )
    accepted: dict[str, object] = {}
    assert validate_hash_response(
        proof.HASH_PROBE_OFFSET, (eof_range,), proof.EXPECTED_BYTES,
        diagnostics=accepted,
    ) == proof.EXPECTED_BYTES
    assert accepted["returned_ranges"][0]["end"] == proof.EXPECTED_BYTES
    assert accepted["failure_category"] is None

    cases = (
        (0, (RemoteFileHash(0, proof.EXPECTED_BYTES + 1, b"e" * 32),),
         "HASH_RANGE_EXTENDS_BEYOND_EOF", "range_exceeds_expected_bytes"),
        (proof.EXPECTED_BYTES + 1, (), "INVALID_HASH_OFFSET", "invalid_request_bounds"),
        (0, (RemoteFileHash(0, 0, b"e" * 32),), "INVALID_HASH_LENGTH", "invalid_range_length"),
        (0, (RemoteFileHash(0, 1, "not-hex"),), "INVALID_HASH_LENGTH", "digest_not_hex"),
        (0, (RemoteFileHash(0, 4, b"e" * 32), RemoteFileHash(2, 2, b"e" * 32)),
         "HASH_INTERVAL_OVERLAP", "range_overlap"),
        (0, (RemoteFileHash(0, 2, b"e" * 32), RemoteFileHash(3, 1, b"e" * 32)),
         "HASH_INTERVAL_GAP", "range_gap"),
        (0, (), "HASH_CURSOR_NO_PROGRESS", "empty_or_non_sequence_response"),
    )
    for offset, ranges, classification, reason in cases:
        diagnostics: dict[str, object] = {}
        with pytest.raises(BudgetStop):
            validate_hash_response(offset, ranges, proof.EXPECTED_BYTES, diagnostics=diagnostics)
        assert diagnostics["rejection_classification"] == classification
        assert diagnostics["rejection_reason"] == reason
        if reason == "range_overlap":
            assert diagnostics["diagnostic_classification"] == "ACTUAL_RANGE_OVERLAP"


def test_hash_response_window_diagnostics_distinguish_before_from_overlap() -> None:
    cursor = 100
    before = {"offset": 20, "limit": 30, "digest_length": 32}
    diagnostics: dict[str, object] = {}
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_OVERLAP"):
        validate_hash_response(
            cursor, (RemoteFileHash(20, 30, b"a" * 32),), 200,
            diagnostics=diagnostics,
        )
    assert before.items() <= diagnostics["returned_ranges"][0].items()
    assert diagnostics["rejection_reason"] == "range_before_cursor"
    assert diagnostics["diagnostic_classification"] == "RANGE_BEFORE_CURSOR"
    assert diagnostics["rejection_classification"] == "HASH_INTERVAL_OVERLAP"
    assert diagnostics["cursor_before"] == diagnostics["cursor_after"] == cursor
    assert diagnostics["range_count_received"] == 1
    assert diagnostics["range_count_inspected"] == 1
    assert diagnostics["first_rejected_index"] == 0

    overlap: dict[str, object] = {}
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_OVERLAP"):
        validate_hash_response(
            cursor, (RemoteFileHash(90, 20, b"b" * 32),), 200,
            diagnostics=overlap,
        )
    assert overlap["rejection_reason"] == "range_overlap"
    assert overlap["diagnostic_classification"] == "ACTUAL_RANGE_OVERLAP"


def test_three_range_geometry_is_captured_before_fail_fast_validation() -> None:
    response = (
        RemoteFileHash(0, 4, b"a" * 32),
        RemoteFileHash(4, 3, b"b" * 32),
        RemoteFileHash(7, 1, b"c" * 32),
    )
    diagnostics: dict[str, object] = {}
    assert validate_hash_response(0, response, 8, diagnostics=diagnostics) == 8
    assert diagnostics["range_count_received"] == 3
    assert diagnostics["range_count_inspected"] == 3
    assert diagnostics["first_rejected_index"] is None
    assert [entry["index"] for entry in diagnostics["returned_ranges"]] == [0, 1, 2]

    posterior_overlap = (
        RemoteFileHash(0, 4, b"a" * 32),
        RemoteFileHash(4, 3, b"b" * 32),
        RemoteFileHash(6, 2, b"c" * 32),
    )
    failed: dict[str, object] = {}
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_OVERLAP"):
        validate_hash_response(0, posterior_overlap, 8, diagnostics=failed)
    assert failed["diagnostic_classification"] == "ACTUAL_RANGE_OVERLAP"
    assert failed["range_count_received"] == 3
    assert failed["range_count_inspected"] == 3
    assert failed["first_rejected_index"] == 2
    assert len(failed["returned_ranges"]) == 3


def test_hash_response_diagnostic_classifies_eof_and_invalid_digest() -> None:
    eof: dict[str, object] = {}
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_INVALID"):
        validate_hash_response(
            0, (RemoteFileHash(0, 9, b"a" * 32),), 8, diagnostics=eof
        )
    assert eof["diagnostic_classification"] == "RANGE_EXTENDS_BEYOND_EOF"

    for digest in (None, "not-hex"):
        invalid: dict[str, object] = {}
        with pytest.raises(BudgetStop, match="HASH_COVERAGE_INVALID"):
            validate_hash_response(
                0, (RemoteFileHash(0, 8, digest),), 8, diagnostics=invalid
            )
        assert invalid["diagnostic_classification"] == "INVALID_RANGE"


def test_telemetry_capture_failure_does_not_mask_fail_closed_rejection(monkeypatch) -> None:
    import tools.manual_proofs.s6_resume_harness as harness

    def fail_capture(_ranges):
        raise OSError("synthetic telemetry failure")

    monkeypatch.setattr(harness, "_capture_hash_range_geometry", fail_capture)
    diagnostics: dict[str, object] = {}
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_OVERLAP"):
        validate_hash_response(
            100, (RemoteFileHash(20, 30, b"a" * 32),), 200,
            diagnostics=diagnostics,
        )
    assert diagnostics["telemetry_capture_status"] == "FAILED"
    assert diagnostics["rejection_reason"] == "range_before_cursor"
    assert diagnostics["first_rejected_index"] == 0


def test_rejected_hash_response_persistence_failure_preserves_external_category(
    tmp_path, monkeypatch
) -> None:
    import tools.manual_proofs.s6_resume_harness as harness

    class FixtureGateway:
        async def get_file_hashes(self, *args, **kwargs):
            return (RemoteFileHash(20, 30, b"a" * 32),)

    def fail_persist(*_args, **_kwargs):
        raise OSError("synthetic evidence write failure")

    monkeypatch.setattr(harness, "_persist_hash_coverage_event", fail_persist)
    gateway = BudgetedRealGateway(FixtureGateway(), DurableBudgetLedger(tmp_path / "budget.sqlite3"), phase=1)
    with pytest.raises(DownloadGatewayError, match="HASH_COVERAGE_OVERLAP"):
        asyncio.run(gateway.get_file_hashes(
            proof.CHANNEL_ID, proof.MESSAGE_ID, proof.MEDIA_ORDINAL,
            telegram_media_id=proof.TELEGRAM_MEDIA_ID, expected_bytes=200, offset=100,
        ))


def test_controlled_probe_labels_received_rejection_as_local_validation() -> None:
    from tools.manual_proofs import s6_controlled_eof_hash_probe as probe

    geometry, stop, source = probe._classify_hash_response_event({
        "response_received": True,
        "validation_result": "REJECTED",
        "failure_category": "HASH_COVERAGE_OVERLAP",
    }, "HASH_COVERAGE_OVERLAP")
    assert geometry == "LOCAL_HASH_RESPONSE_VALIDATION_REJECTED"
    assert stop == "HASH_COVERAGE_OVERLAP"
    assert source == "LOCAL_RESPONSE_VALIDATION"

    geometry, stop, source = probe._classify_hash_response_event({
        "response_received": False,
        "validation_result": "NOT_VALIDATED",
    }, "REMOTE_REQUEST_FAILED")
    assert geometry == "REMOTE_IDENTITY_OR_HASH_REQUEST_REJECTED"
    assert stop == "REMOTE_REQUEST_FAILED"
    assert source is None


def test_persistent_ledger_caps_and_uncertain_crash_reservation(tmp_path) -> None:
    result = exercise_budget_edge_cases(tmp_path / "probes")
    assert result["getfile_cap_stop"] == "TRANSFER_BUDGET_EXHAUSTED"
    assert result["hash_cap_stop"] == "HASH_COVERAGE_BUDGET_EXHAUSTED"
    assert result["no_progress_stop"] == "HASH_COVERAGE_STALLED"
    assert result["incomplete_coverage_stop"] == "HASH_COVERAGE_BUDGET_EXHAUSTED"
    assert result["crash_reopen"]["open_reservations"] == 1
    assert result["crash_conservative_reconciliation"]["uncertain_reservations"] == 1
    assert result["variable_coverage_contiguous_end"] == proof.PREFIX_BYTES
    assert result["full_coverage_end"] == proof.EXPECTED_BYTES


def test_ledger_refuses_oversized_request_before_reserving(tmp_path) -> None:
    ledger = DurableBudgetLedger(tmp_path / "budget.sqlite3")
    with pytest.raises(BudgetStop, match="TRANSFER_BUDGET_RESERVATION_INVALID"):
        ledger.reserve_getfile(256 * 1024 + 1)
    assert ledger.snapshot()["getfile_calls_reserved"] == 0


def test_offline_two_process_proof_reopens_sqlite_and_completes_resume(tmp_path) -> None:
    code, root = proof.dry_run(tmp_path / "offline-proof")
    report = json.loads((root / "s6-real-resume-report.json").read_text(encoding="utf-8"))
    first = report["two_process_restart"]["phase1"]
    second = report["two_process_restart"]["phase2"]
    assert code == 0
    assert report["safety_preflight"] == "PASS"
    assert report["expected_feasibility"].startswith("UNKNOWN")
    assert report["evidence_completeness_gate"] == "PASS / SYNTHETIC FIXTURE ONLY"
    assert report["real_evidence_completeness"].startswith("NOT_EVALUATED")
    assert report["real_evidence"] == "NOT_EXECUTED"
    assert first["process_id"] != second["process_id"]
    assert first["partial_bytes"] == first["sqlite_checkpoint_bytes"] == proof.PREFIX_BYTES
    assert second["wire_offset"] == proof.WIRE_OFFSET
    assert second["overlap_bytes"] == proof.OVERLAP_BYTES
    assert second["outcome"] == "DOWNLOADED"
    assert second["sqlite_state"] == "DOWNLOADED"
    assert second["final_bytes"] == proof.EXPECTED_BYTES
    assert second["partial_exists_after_finalize"] is False
    assert second["ledger_after"]["getfile_calls_reserved"] <= proof.MAX_GETFILE_REQUESTS
    assert second["ledger_after"]["payload_bytes_reserved"] <= proof.MAX_TRANSFER_BYTES
    assert second["ledger_after"]["getfilehashes_calls_reserved"] <= proof.MAX_GETFILEHASHES_REQUESTS
    assert report["real_telegram_calls"] == 0
    assert report["original_sqlite_access"] == "NO"


def test_execute_requires_native_confirmation_token(capsys, monkeypatch) -> None:
    monkeypatch.delenv("S6_REAL_EXECUTE_AUTH", raising=False)
    assert proof.execute() == 5
    output = capsys.readouterr().out
    assert "STOP=NATIVE_POWERSHELL_CONFIRMATION_REQUIRED" in output
    assert "EVIDENCE_ROOT=" not in output


def test_protected_real_gateway_applies_hash_ledger_offline(tmp_path) -> None:
    class FixtureGateway:
        async def get_file_hashes(self, *args, **kwargs):
            return (RemoteFileHash(0, 8, b"x" * 32),)

    ledger = DurableBudgetLedger(tmp_path / "budget.sqlite3")
    gateway = BudgetedRealGateway(FixtureGateway(), ledger, phase=2)
    ranges = asyncio.run(gateway.get_file_hashes(
        proof.CHANNEL_ID, proof.MESSAGE_ID, proof.MEDIA_ORDINAL,
        telegram_media_id=proof.TELEGRAM_MEDIA_ID, expected_bytes=8, offset=0,
    ))
    assert ranges == (RemoteFileHash(0, 8, b"x" * 32),)
    assert gateway.hash_ranges == [(0, 8)]
    assert ledger.snapshot()["getfilehashes_calls_reserved"] == 1
    event = json.loads((tmp_path / "hash-coverage.jsonl").read_text(encoding="utf-8"))
    assert event["reservation_id"] == 1
    assert event["call_index"] == 1
    assert event["correlation_id"] == "GETFILEHASHES-0001"
    assert event["requested_offset"] == 0
    assert event["range_count"] == 1
    assert event["validation_result"] == "PASS"
    assert event["returned_ranges"] == [{
        "index": 0, "offset": 0, "limit": 8, "length": 8, "end": 8, "digest_length": 32,
    }]
    assert event["cursor_before"] == 0
    assert event["cursor_after"] == 8
    assert event["failure_category"] is None
    assert "sha256" not in event


def test_protected_real_gateway_persists_eof_rejection_reason_offline(tmp_path) -> None:
    class FixtureGateway:
        async def get_file_hashes(self, *args, **kwargs):
            return (
                RemoteFileHash(0, 4, b"a" * 32),
                RemoteFileHash(4, 5, b"b" * 32),
            )

    ledger = DurableBudgetLedger(tmp_path / "budget.sqlite3")
    gateway = BudgetedRealGateway(FixtureGateway(), ledger, phase=2)
    with pytest.raises(DownloadGatewayError, match="HASH_COVERAGE_INVALID"):
        asyncio.run(gateway.get_file_hashes(
            proof.CHANNEL_ID, proof.MESSAGE_ID, proof.MEDIA_ORDINAL,
            telegram_media_id=proof.TELEGRAM_MEDIA_ID, expected_bytes=8, offset=0,
        ))

    event = json.loads((tmp_path / "hash-coverage.jsonl").read_text(encoding="utf-8"))
    assert event["reservation_id"] == 1
    assert event["call_index"] == 1
    assert event["correlation_id"] == "GETFILEHASHES-0001"
    assert event["response_received"] is True
    assert event["range_count"] == 2
    assert event["requested_offset"] == 0
    assert event["expected_bytes"] == 8
    assert event["returned_ranges"] == [
        {"index": 0, "offset": 0, "limit": 4, "length": 4, "end": 4, "digest_length": 32},
        {"index": 1, "offset": 4, "limit": 5, "length": 5, "end": 9, "digest_length": 32},
    ]
    assert event["cursor_before"] == 0
    assert event["cursor_after"] == 4
    assert event["failure_category"] == "HASH_COVERAGE_INVALID"
    assert event["rejection_reason"] == "range_exceeds_expected_bytes"
    assert "sha256" not in event
    assert ledger.snapshot()["getfilehashes_calls_reserved"] == 1


def test_protected_real_gateway_cannot_exceed_hash_cap_offline(tmp_path) -> None:
    class FixtureGateway:
        async def get_file_hashes(self, *args, **kwargs):
            return (RemoteFileHash(0, 8, b"x" * 32),)

    ledger = DurableBudgetLedger(tmp_path / "budget.sqlite3")
    for _ in range(proof.MAX_GETFILEHASHES_REQUESTS):
        ledger.reserve_hash_call().received()
    gateway = BudgetedRealGateway(FixtureGateway(), ledger, phase=2)
    with pytest.raises(DownloadGatewayError, match="HASH_COVERAGE_BUDGET_EXHAUSTED"):
        asyncio.run(gateway.get_file_hashes(
            proof.CHANNEL_ID, proof.MESSAGE_ID, proof.MEDIA_ORDINAL,
            telegram_media_id=proof.TELEGRAM_MEDIA_ID, expected_bytes=8, offset=0,
        ))


def test_target_eof_probe_uses_second_call_only_after_valid_progress_offline(
    tmp_path, monkeypatch
) -> None:
    requested_offsets = []

    class FixtureGateway:
        async def get_file_hashes(self, channel_id, message_id, media_ordinal, **kwargs):
            offset = kwargs["offset"]
            requested_offsets.append(offset)
            size = 60_000 if len(requested_offsets) == 1 else proof.EXPECTED_BYTES - offset
            return (RemoteFileHash(offset, size, b"d" * 32),)

        async def close(self):
            return None

    async def factory(ledger):
        phase = 1
        assert phase == 1
        assert ledger.getfile_cap == 0
        assert ledger.payload_cap == 0
        assert ledger.hash_cap == 2
        return BudgetedRealGateway(FixtureGateway(), ledger, phase=phase)

    monkeypatch.setattr(proof, "_real_hash_gateway", factory)
    result = asyncio.run(proof._run_hash_eof_probe(tmp_path / "probe"))

    assert result["result"] == "CONTIGUOUS_COVERAGE_REACHED_EOF"
    assert requested_offsets == [proof.HASH_PROBE_OFFSET, proof.HASH_PROBE_OFFSET + 60_000]
    assert result["calls"][1]["justification"] == (
        "FIRST_RESPONSE_VALIDATED_AND_ADVANCED_CURSOR"
    )
    assert result["real_telegram_calls"] == 2
    assert result["getfile_calls"] == 0
    assert result["media_payload_bytes"] == 0
    assert result["budget"]["payload_bytes_reserved"] == 0


def test_target_eof_probe_fails_closed_on_eof_crossing_and_sanitizes_offline(
    tmp_path, monkeypatch
) -> None:
    requested_offsets = []
    marker_digest = b"unique synthetic digest that must not be logged"

    class FixtureGateway:
        async def get_file_hashes(self, channel_id, message_id, media_ordinal, **kwargs):
            requested_offsets.append(kwargs["offset"])
            return (RemoteFileHash(proof.HASH_PROBE_OFFSET, 200_000, marker_digest),)

        async def close(self):
            return None

    async def factory(ledger):
        phase = 1
        return BudgetedRealGateway(FixtureGateway(), ledger, phase=phase)

    monkeypatch.setattr(proof, "_real_hash_gateway", factory)
    result = asyncio.run(proof._run_hash_eof_probe(tmp_path / "probe"))

    assert requested_offsets == [proof.HASH_PROBE_OFFSET]
    assert result["result"] == "INCOMPLETE_DIAGNOSTIC"
    assert result["calls"] == []
    assert result["real_telegram_calls"] == 1
    evidence = (tmp_path / "probe" / "hash-coverage.jsonl").read_text(encoding="utf-8")
    event = json.loads(evidence)
    assert event["validation_result"] == "REJECTED"
    assert event["rejection_classification"] == "HASH_RANGE_EXTENDS_BEYOND_EOF"
    assert event["returned_ranges"] == [{
        "index": 0,
        "offset": proof.HASH_PROBE_OFFSET,
        "limit": 200_000,
        "length": 200_000,
        "end": proof.HASH_PROBE_OFFSET + 200_000,
        "digest_length": len(marker_digest),
    }]
    assert marker_digest.decode() not in evidence
    assert "sha256" not in evidence


def test_remote_hash_comparison_requires_exact_available_range_and_sanitizes() -> None:
    local_range = b"l" * 131_072
    remote_digest = hashlib.sha256(local_range).digest()

    matching = proof.compare_remote_range_digest(
        remote_offset=7_340_032, remote_limit=131_072,
        remote_digest=remote_digest, local_offset=7_340_032,
        local_bytes=local_range,
    )
    mismatch = proof.compare_remote_range_digest(
        remote_offset=7_340_032, remote_limit=131_072,
        remote_digest=hashlib.sha256(b"x" * 131_072).digest(),
        local_offset=7_340_032, local_bytes=local_range,
    )
    short_range = proof.compare_remote_range_digest(
        remote_offset=7_340_032, remote_limit=131_072,
        remote_digest=remote_digest, local_offset=7_340_032,
        local_bytes=b"l" * 115_619,
    )
    invalid_digest = proof.compare_remote_range_digest(
        remote_offset=7_340_032, remote_limit=131_072,
        remote_digest=b"invalid", local_offset=7_340_032,
        local_bytes=local_range,
    )
    unavailable = proof.compare_remote_range_digest(
        remote_offset=7_340_032, remote_limit=131_072,
        remote_digest=remote_digest, local_offset=7_340_032,
        local_bytes=None,
    )

    assert matching["status"] == "MATCH"
    assert mismatch["status"] == "NO_MATCH"
    assert short_range["status"] == "INCONCLUSIVE"
    assert short_range["reason"] == "LOCAL_RANGE_GEOMETRY_MISMATCH"
    assert short_range["local_length"] == 115_619
    assert invalid_digest["status"] == "INCONCLUSIVE"
    assert invalid_digest["reason"] == "REMOTE_DIGEST_INVALID"
    assert unavailable["status"] == "INCONCLUSIVE"
    assert all("digest" not in key.lower() or key == "reason" for item in (
        matching, mismatch, short_range, invalid_digest, unavailable
    ) for key in item)
    assert remote_digest.hex() not in repr((matching, mismatch, short_range, invalid_digest, unavailable))


def test_hash_only_budget_blocks_any_getfile_or_third_hash_offline(tmp_path) -> None:
    ledger = DurableBudgetLedger(
        tmp_path / "budget.sqlite3", getfile_cap=0, payload_cap=0, hash_cap=2
    )
    for _ in range(2):
        ledger.reserve_hash_call().received()
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_BUDGET_EXHAUSTED"):
        ledger.reserve_hash_call()
    with pytest.raises(BudgetStop, match="TRANSFER_BUDGET_EXHAUSTED"):
        ledger.reserve_getfile(CHUNK_BYTES)
    snapshot = ledger.snapshot()
    assert snapshot["getfile_calls_reserved"] == 0
    assert snapshot["payload_bytes_reserved"] == 0
    assert snapshot["payload_bytes_received"] == 0
    assert snapshot["getfilehashes_calls_reserved"] == 2


def test_hash_probe_dryrun_records_strict_caps_without_session_restore(tmp_path) -> None:
    code, root = proof.hash_probe_dry_run(tmp_path / "probe-dryrun")
    report = json.loads((root / "s6-hash-eof-probe-report.json").read_text(encoding="utf-8"))
    assert code == 0
    assert report["initial_hash_offset"] == proof.HASH_PROBE_OFFSET
    assert report["max_getfilehashes_calls"] == 2
    assert report["max_getfile_calls"] == 0
    assert report["max_media_payload_bytes"] == 0
    assert report["second_call_rule"] == "ONLY_AFTER_FIRST_RESPONSE_VALIDATES_AND_ADVANCES_CURSOR"
    assert report["session_restore"] == "NOT_ATTEMPTED"
    assert report["real_telegram_calls"] == report["real_payload_bytes"] == 0
    hash_only = proof.HashOnlyGateway(object())
    assert not hasattr(hash_only, "stream_media")
    assert not hasattr(hash_only, "get_file")


def test_hash_probe_execute_requires_native_confirmation(capsys, monkeypatch) -> None:
    monkeypatch.delenv("S6_HASH_PROBE_AUTH", raising=False)
    assert proof.execute_hash_eof_probe() == 5
    assert "STOP=NATIVE_POWERSHELL_CONFIRMATION_REQUIRED" in capsys.readouterr().out


def test_real_gateway_phase1_stops_at_exact_physical_prefix_offline(tmp_path) -> None:
    class FixtureGateway:
        async def stream_media(self, *args, **kwargs):
            for _ in range(5):
                yield b"p" * CHUNK_BYTES

    async def collect():
        wrapped = BudgetedRealGateway(
            FixtureGateway(), DurableBudgetLedger(tmp_path / "budget.sqlite3"), phase=1
        )
        chunks = []
        try:
            async for chunk in wrapped.stream_media():
                chunks.append(chunk)
        except DownloadGatewayError as error:
            assert error.category == "CONTROLLED_INTERRUPTION_AFTER_DURABLE_PREFIX"
        return chunks, wrapped.prefix_bytes_yielded

    chunks, total = asyncio.run(collect())
    assert total == proof.PREFIX_BYTES
    assert sum(map(len, chunks)) == proof.PREFIX_BYTES
    assert len(chunks[-1]) == proof.OVERLAP_BYTES


def test_finalization_never_overwrites_existing_destination(tmp_path) -> None:
    partial = tmp_path / "media.bin.part"
    final = tmp_path / "media.bin"
    partial.write_bytes(b"new synthetic bytes")
    final.write_bytes(b"pre-existing destination")
    with pytest.raises(DownloadError) as error:
        _finalize_no_overwrite(partial, final)
    assert error.value.category == "DESTINATION_EXISTS"
    assert final.read_bytes() == b"pre-existing destination"
    assert partial.read_bytes() == b"new synthetic bytes"
