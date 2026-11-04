from __future__ import annotations

import json

import pytest
from tools.manual_proofs import s6_controlled_eof_hash_probe as probe
from tools.manual_proofs.s6_resume_harness import (
    BudgetStop,
    DurableBudgetLedger,
    _persist_hash_coverage_event,
    validate_hash_response,
)

from telegram_courses.downloads import RemoteFileHash


def test_controlled_probe_has_exact_target_and_zero_transfer_budget() -> None:
    probe._validate_constants()
    assert probe.HASH_OFFSET == 1_119_092_736
    assert probe.EXPECTED_BYTES - probe.HASH_OFFSET == 36_954
    assert probe.MAX_GETFILEHASHES_CALLS == 1
    assert probe.MAX_GETFILE_CALLS == 0
    assert probe.MAX_MEDIA_PAYLOAD_BYTES == 0


def test_hash_ledger_allows_exactly_one_query_and_denies_getfile(tmp_path) -> None:
    ledger = DurableBudgetLedger(
        tmp_path / "budget.sqlite3", getfile_cap=0, payload_cap=0, hash_cap=1
    )
    reservation = ledger.reserve_hash_call()
    reservation.received()
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_BUDGET_EXHAUSTED"):
        ledger.reserve_hash_call()
    with pytest.raises(BudgetStop, match="TRANSFER_BUDGET_EXHAUSTED"):
        ledger.reserve_getfile(1)
    snapshot = ledger.snapshot()
    assert snapshot["getfilehashes_calls_reserved"] == 1
    assert snapshot["getfile_calls_reserved"] == 0
    assert snapshot["payload_bytes_reserved"] == 0
    assert snapshot["payload_bytes_received"] == 0


def test_eof_geometry_is_contiguous_and_eof_crossing_fails_closed() -> None:
    accepted: dict[str, object] = {}
    response = (RemoteFileHash(probe.HASH_OFFSET, probe.EOF_REMAINDER, b"x" * 32),)
    assert validate_hash_response(
        probe.HASH_OFFSET, response, probe.EXPECTED_BYTES, diagnostics=accepted
    ) == probe.EXPECTED_BYTES
    assert accepted["returned_ranges"] == [{
        "index": 0,
        "offset": probe.HASH_OFFSET,
        "limit": probe.EOF_REMAINDER,
        "length": probe.EOF_REMAINDER,
        "end": probe.EXPECTED_BYTES,
        "digest_length": 32,
    }]
    assert "sha256" not in json.dumps(accepted).lower()

    rejected: dict[str, object] = {}
    with pytest.raises(BudgetStop, match="HASH_COVERAGE_INVALID"):
        validate_hash_response(
            probe.HASH_OFFSET,
            (RemoteFileHash(probe.HASH_OFFSET, probe.EOF_REMAINDER + 1, b"y" * 32),),
            probe.EXPECTED_BYTES,
            diagnostics=rejected,
        )
    assert rejected["rejection_classification"] == "HASH_RANGE_EXTENDS_BEYOND_EOF"
    assert rejected["returned_ranges"][0]["end"] == probe.EXPECTED_BYTES + 1
    assert "sha256" not in json.dumps(rejected).lower()


def test_sanitized_hash_evidence_never_contains_digest(tmp_path) -> None:
    evidence = tmp_path / "hash-coverage.jsonl"
    _persist_hash_coverage_event(evidence, {
        "requested_offset": probe.HASH_OFFSET,
        "returned_ranges": [{"offset": probe.HASH_OFFSET, "limit": 36_954, "digest_length": 32}],
    })
    stored = evidence.read_text(encoding="utf-8")
    assert "sha256" not in stored.lower()
    assert "do-not-persist-this" not in stored


def test_dry_run_validates_reference_artifacts_without_session_or_rpc(tmp_path) -> None:
    code, evidence_root = probe._dry_run(tmp_path / "dry-run")
    report = json.loads((evidence_root / "s6-controlled-eof-hash-probe-dryrun.json").read_text())
    assert code == 0
    assert report["reference_manifest_gate"] == "PASS"
    assert report["registered_remote_identity_gate"] == "PASS"
    assert report["real_telegram_calls"] == 0
    assert report["session_restore"] == "NOT_ATTEMPTED"
    assert report["max_getfilehashes_calls"] == 1
    assert report["max_getfile_calls"] == 0
    assert report["max_media_payload_bytes"] == 0


def test_execute_without_native_confirmation_stops_before_session_restore(monkeypatch) -> None:
    monkeypatch.delenv(probe.AUTH_ENV, raising=False)
    assert probe.execute() == 5
