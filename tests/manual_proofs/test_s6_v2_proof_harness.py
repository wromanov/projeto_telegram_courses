from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools.manual_proofs import s6_v2_proof_harness as harness


def _install_controlled_reference_inputs(monkeypatch, tmp_path: Path, payload: bytes) -> tuple[Path, str]:
    repository = tmp_path / "reference-fixture-repository"
    reports = repository / "docs" / "reports"
    source_dir = reports / "S6_CONTROLLED_REFERENCE_PREPARATION_2026-10-17"
    upload_dir = reports / "S6_CONTROLLED_UPLOAD_AND_EOF_GATE_2026-10-17"
    source_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    reference = tmp_path / "reference.bin"
    reference.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    target = dict(harness.CONTROLLED_TARGET, expected_bytes=len(payload))
    monkeypatch.setattr(harness, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(harness, "CANONICAL_TRUSTED_REFERENCE_PATH", reference)
    monkeypatch.setattr(harness, "CANONICAL_TRUSTED_REFERENCE_SHA256", digest)
    monkeypatch.setattr(harness, "CONTROLLED_TARGET", target)
    (source_dir / "reference_manifest.json").write_text(json.dumps({
        "reference_gate": "PASS",
        "source_file_path": str(reference),
        "source_file_size_bytes": len(payload),
        "source_file_sha256": digest,
        "provenance_informed": "SYNTHETIC_TEST_FIXTURE",
    }), encoding="utf-8")
    (upload_dir / "controlled_upload_result.json").write_text(json.dumps({
        "reference_gate": "PASS",
        "refetched_message": {
            "channel_id": target["channel_id"],
            "message_id": target["message_id"],
            "media_id": target["media_id"],
            "ordinal": 0,
            "kind": "DOCUMENT",
            "document_size_bytes": len(payload),
        },
    }), encoding="utf-8")
    return reference, digest


@pytest.mark.parametrize("read_only", [False, True])
def test_trusted_reference_preflight_accepts_both_windows_readonly_attribute_states(
    tmp_path, monkeypatch, read_only,
) -> None:
    payload = b"trusted reference stays read only by access mode"
    reference, digest = _install_controlled_reference_inputs(monkeypatch, tmp_path, payload)
    if read_only:
        reference.chmod(stat.S_IREAD)
    try:
        output = tmp_path / "evidence-parent"
        output.mkdir()
        result = harness._trusted_reference_preflight(output)
        assert result["reference_size"] == len(payload)
        assert result["sha256"] == digest
        assert result["reference_path"] == str(reference)
        assert result["file_identity"] == harness._file_identity(reference)
        assert reference.read_bytes() == payload
    finally:
        reference.chmod(stat.S_IREAD | stat.S_IWRITE)


@pytest.mark.parametrize("mutation", ["digest", "size"])
def test_trusted_reference_preflight_blocks_expected_digest_or_size_divergence(
    tmp_path, monkeypatch, mutation,
) -> None:
    reference, _digest = _install_controlled_reference_inputs(monkeypatch, tmp_path, b"expected source")
    if mutation == "digest":
        monkeypatch.setattr(harness, "CANONICAL_TRUSTED_REFERENCE_SHA256", "0" * 64)
    else:
        target = dict(harness.CONTROLLED_TARGET, expected_bytes=999)
        monkeypatch.setattr(harness, "CONTROLLED_TARGET", target)
    with pytest.raises(RuntimeError, match="CONTROLLED_REFERENCE_.*|CONTROLLED_REFERENCE_MANIFEST_GATE_FAILED"):
        harness._trusted_reference_preflight()
    assert reference.read_bytes() == b"expected source"


def test_trusted_reference_preflight_blocks_missing_or_unreadable_reference(tmp_path, monkeypatch) -> None:
    reference, _digest = _install_controlled_reference_inputs(monkeypatch, tmp_path, b"source")
    reference.unlink()
    with pytest.raises(RuntimeError, match="CONTROLLED_REFERENCE_MISSING_OR_UNSAFE"):
        harness._trusted_reference_preflight()

    reference, _digest = _install_controlled_reference_inputs(monkeypatch, tmp_path, b"source")
    monkeypatch.setattr(harness, "_hash_file", lambda _path: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(RuntimeError, match="TRUSTED_REFERENCE_UNAVAILABLE"):
        harness._trusted_reference_preflight()


def test_trusted_reference_change_after_preflight_is_detected(tmp_path, monkeypatch) -> None:
    payload = b"before"
    reference, _digest = _install_controlled_reference_inputs(monkeypatch, tmp_path, payload)
    case_root = tmp_path / "proof-case"
    case_root.mkdir()
    harness._write_reference_manifest(case_root)
    reference.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="CONTROLLED_REFERENCE_INTEGRITY_MISMATCH"):
        harness._verify_reference_manifest(case_root)


def test_post_proof_reference_verification_missing_or_diverged_never_passes(tmp_path, monkeypatch) -> None:
    missing = harness._post_verify_reference_integrity(tmp_path / "case-without-manifest")
    assert missing == {"status": "INCOMPLETE", "reason": "POST_PROOF_REFERENCE_MANIFEST_MISSING"}
    assert not harness._trusted_reference_match_allowed(
        True, {"status": "TRUSTED_REFERENCE_MATCH"}, missing,
    )

    reference, _digest = _install_controlled_reference_inputs(monkeypatch, tmp_path, b"before")
    case_root = tmp_path / "case-with-manifest"
    case_root.mkdir()
    harness._write_reference_manifest(case_root)
    reference.write_bytes(b"after!")
    changed = harness._post_verify_reference_integrity(case_root)
    assert changed["status"] == "BLOCKED"
    assert changed["reason"] == "CONTROLLED_REFERENCE_INTEGRITY_MISMATCH"


def test_trusted_reference_preflight_rejects_output_root_alias(tmp_path, monkeypatch) -> None:
    reference, _digest = _install_controlled_reference_inputs(monkeypatch, tmp_path, b"source")
    with pytest.raises(RuntimeError, match="REFERENCE_ALIASES_EVIDENCE_ROOT"):
        harness._trusted_reference_preflight(reference.parent)
    assert reference.read_bytes() == b"source"


def test_new_isolated_root_rejects_invalid_native_evidence_parent(tmp_path, monkeypatch) -> None:
    parent = tmp_path / "unsafe-root"
    parent.mkdir()
    monkeypatch.setattr(harness, "_directory_path_is_safe", lambda _path: False)
    with pytest.raises(RuntimeError, match="EVIDENCE_PARENT_UNSAFE"):
        harness._new_isolated_root(parent)
    assert list(parent.iterdir()) == []


def test_request_and_payload_budgets_differ_by_resume_mode() -> None:
    common = harness.proof_budget(
        harness.COMMON_TARGET["expected_bytes"],
        harness.COMMON_PREFIX_ALIGNED,
        "OPERATIONAL_ONLY",
    )
    controlled_operational = harness.proof_budget(
        harness.CONTROLLED_TARGET["expected_bytes"],
        harness.CONTROLLED_PREFIX_OPTIONS["128MiB"],
        "OPERATIONAL_ONLY",
    )
    controlled_trusted = harness.proof_budget(
        harness.CONTROLLED_TARGET["expected_bytes"],
        harness.CONTROLLED_PREFIX_OPTIONS["128MiB"],
        "TRUSTED_REFERENCE",
    )

    assert common["resume_getfile_cap_per_attempt"] == 45
    assert controlled_operational["resume_getfile_cap_per_attempt"] == 4_270
    assert controlled_trusted["resume_getfile_cap_per_attempt"] == 3_758
    assert controlled_operational["aggregate_payload_reservation_cap"] > controlled_trusted[
        "aggregate_payload_reservation_cap"
    ]
    assert controlled_operational["aggregate_getfilehashes_cap"] == controlled_trusted[
        "aggregate_getfilehashes_cap"
    ]


def test_authorized_common_aligned_budget_matches_user_caps() -> None:
    budget = harness.proof_budget(
        harness.COMMON_TARGET["expected_bytes"], harness.COMMON_PREFIX_ALIGNED,
        "OPERATIONAL_ONLY",
    )
    assert budget["aggregate_getfile_cap"] == 94
    assert budget["aggregate_getfilehashes_cap"] == 92
    assert budget["aggregate_payload_reservation_cap"] == 24_641_536
    assert budget["phase1_getfile_cap"] == 4
    assert budget["resume_getfile_cap_per_attempt"] == 45
    assert budget["phase1_transfer_attempt_cap"] == 1
    assert budget["phase2_transfer_attempt_cap"] == 2
    assert budget["s5_attempts_per_media_across_phases"] == 3
    assert budget["s5_attempts_per_resume_process"] == 2
    assert budget["floodwait_seconds_per_resume_process"] == 120


def test_trusted_reference_prefix_profiles_have_separate_reconciled_budgets() -> None:
    small = harness._case_budget(
        harness.CONTROLLED_TARGET, "TRUSTED_REFERENCE", "aligned", "8MiB",
    )
    large = harness._case_budget(
        harness.CONTROLLED_TARGET, "TRUSTED_REFERENCE", "aligned", "128MiB",
    )
    assert small["prefix_bytes"] == 8 * 1024 * 1024
    assert large["prefix_bytes"] == 128 * 1024 * 1024
    assert (
        small["phase1_getfile_cap"],
        small["phase2_getfile_cap_per_attempt"],
        small["aggregate_getfile_cap"],
        small["aggregate_getfilehashes_cap"],
        small["aggregate_payload_reservation_cap"],
    ) == (32, 4238, 8508, 8542, 2_230_321_152)
    assert (
        large["phase1_getfile_cap"],
        large["phase2_getfile_cap_per_attempt"],
        large["aggregate_getfile_cap"],
        large["aggregate_getfilehashes_cap"],
        large["aggregate_payload_reservation_cap"],
    ) == (512, 3758, 8028, 8542, 2_104_492_032)
    assert small["aggregate_getfile_cap"] > large["aggregate_getfile_cap"]
    assert small["aggregate_payload_reservation_cap"] > large["aggregate_payload_reservation_cap"]
    assert harness.CONTROLLED_PREFIX_ALIGNED == harness.CONTROLLED_PREFIX_OPTIONS["8MiB"]
    assert small["aggregate_selected_media_rpc_total"] is None
    assert small["aggregate_selected_media_rpc_lower_bound"] == (
        small["aggregate_getfile_cap"] + 2 * small["aggregate_getfilehashes_cap"]
        + small["aggregate_identity_getmessages_cap"] + small["session_restore_getme_cap"]
    )
    assert "lower bound omits per-stream metadata refetch calls" in (
        small["aggregate_selected_media_rpc_total_reason"]
    )


def test_explicit_reference_mismatch_evidence_is_not_generic_process_failure() -> None:
    assert harness._trusted_reference_mismatch_proven({
        "status": "PROCESS_FAILED",
        "media_state_observed": {
            "attempts": [{"details": {"reason": "REFERENCE_MISMATCH"}}],
        },
    })
    assert harness._trusted_reference_mismatch_proven({
        "child_result": {"queue_result": [[[1, 2, 0], "FAILED", "REFERENCE_MISMATCH"]]},
    })
    assert not harness._trusted_reference_mismatch_proven({
        "status": "PROCESS_FAILED",
        "stop_condition": "CHILD_REPORT_MISSING_OR_INVALID",
    })


def _install_test_reference_manifest(monkeypatch, reference: Path, payload: bytes) -> None:
    manifest = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "expected_bytes": len(payload),
    }
    monkeypatch.setattr(
        harness, "_verify_reference_manifest", lambda _case_root: (manifest, reference),
    )


def test_trusted_reference_prefix_comparison_accepts_equal_prefix(tmp_path, monkeypatch) -> None:
    reference_bytes = b"the immutable reference payload"
    reference = tmp_path / "reference.bin"
    reference.write_bytes(reference_bytes)
    downloads = tmp_path / "case" / "downloads"
    downloads.mkdir(parents=True)
    partial = downloads / "proof.bin.part"
    partial.write_bytes(reference_bytes[:12])
    _install_test_reference_manifest(monkeypatch, reference, reference_bytes)

    evidence = harness._verify_reference_prefix(
        downloads.parent, partial, 12, 12, hashlib.sha256(reference_bytes[:12]).hexdigest(),
    )

    assert evidence == {
        "status": "LOCAL_PREFIX_REFERENCE_MATCH",
        "bytes": 12,
        "sha256": hashlib.sha256(reference_bytes[:12]).hexdigest(),
        "reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
        "source": "LOCAL_IMMUTABLE_REFERENCE",
        "remote_reread": False,
    }


def test_trusted_reference_prefix_comparison_rejects_byte_mismatch(tmp_path, monkeypatch) -> None:
    reference_bytes = b"reference payload"
    partial_bytes = b"reference payloXd"
    reference = tmp_path / "reference.bin"
    reference.write_bytes(reference_bytes)
    downloads = tmp_path / "case" / "downloads"
    downloads.mkdir(parents=True)
    partial = downloads / "proof.bin.part"
    partial.write_bytes(partial_bytes)
    _install_test_reference_manifest(monkeypatch, reference, reference_bytes)

    with pytest.raises(RuntimeError, match="TRUSTED_REFERENCE_PREFIX_MISMATCH"):
        harness._verify_reference_prefix(
            downloads.parent, partial, len(partial_bytes), len(partial_bytes),
            hashlib.sha256(partial_bytes).hexdigest(),
        )


@pytest.mark.parametrize(
    ("actual", "checkpoint_bytes", "checkpoint_digest", "error"),
    [
        (b"short", 8, hashlib.sha256(b"short").hexdigest(), "TRUSTED_REFERENCE_PREFIX_SIZE_MISMATCH"),
        (b"corrupt!", 8, "0" * 64, "TRUSTED_REFERENCE_PREFIX_CHECKPOINT_MISMATCH"),
    ],
)
def test_trusted_reference_prefix_rejects_short_or_corrupt_checkpoint(
    tmp_path, monkeypatch, actual, checkpoint_bytes, checkpoint_digest, error,
) -> None:
    reference_bytes = b"shorter corrupt checkpoint fixture"
    reference = tmp_path / "reference.bin"
    reference.write_bytes(reference_bytes)
    downloads = tmp_path / "case" / "downloads"
    downloads.mkdir(parents=True)
    partial = downloads / "proof.bin.part"
    partial.write_bytes(actual)
    _install_test_reference_manifest(monkeypatch, reference, reference_bytes)

    with pytest.raises(RuntimeError, match=error):
        harness._verify_reference_prefix(
            downloads.parent, partial, 8, checkpoint_bytes, checkpoint_digest,
        )


def test_trusted_reference_prefix_fails_closed_when_reference_is_unavailable(
    tmp_path, monkeypatch,
) -> None:
    downloads = tmp_path / "case" / "downloads"
    downloads.mkdir(parents=True)
    partial = downloads / "proof.bin.part"
    partial.write_bytes(b"prefix")

    def unavailable(_case_root):
        raise RuntimeError("TRUSTED_REFERENCE_UNAVAILABLE")

    monkeypatch.setattr(harness, "_verify_reference_manifest", unavailable)
    with pytest.raises(RuntimeError, match="TRUSTED_REFERENCE_UNAVAILABLE"):
        harness._verify_reference_prefix(
            downloads.parent, partial, 6, 6, hashlib.sha256(b"prefix").hexdigest(),
        )


def _trusted_reference_case(tmp_path, reference_bytes: bytes, final_bytes: bytes):
    case_root = tmp_path / "case"
    downloads = case_root / "downloads"
    downloads.mkdir(parents=True)
    reference = tmp_path / "reference.bin"
    reference.write_bytes(reference_bytes)
    final = downloads / "proof.bin"
    final.write_bytes(final_bytes)
    return case_root, reference, final


def test_supervisor_reference_comparison_accepts_full_equality(tmp_path, monkeypatch) -> None:
    payload = b"completed immutable reference"
    case_root, reference, final = _trusted_reference_case(tmp_path, payload, payload)
    _install_test_reference_manifest(monkeypatch, reference, payload)

    comparison = harness._supervisor_compare_reference(case_root, str(final))

    assert comparison["status"] == "TRUSTED_REFERENCE_MATCH"
    assert comparison["bytewise_match"] is True
    assert comparison["comparison_method"] == "BYTEWISE_AND_SHA256"
    assert comparison["final_sha256"] == comparison["reference_sha256"]


def test_supervisor_reference_comparison_reports_full_divergence(tmp_path, monkeypatch) -> None:
    case_root, reference, final = _trusted_reference_case(
        tmp_path, b"reference bytes", b"different bytes",
    )
    _install_test_reference_manifest(monkeypatch, reference, b"reference bytes")

    comparison = harness._supervisor_compare_reference(case_root, str(final))

    assert comparison["status"] == "TRUSTED_REFERENCE_MISMATCH"
    assert comparison["bytewise_match"] is False


def test_supervisor_bytewise_check_catches_synthetic_same_size_same_sha_divergence(
    tmp_path, monkeypatch,
) -> None:
    case_root, reference, final = _trusted_reference_case(tmp_path, b"AAAA", b"BBBB")
    monkeypatch.setattr(
        harness, "_verify_reference_manifest",
        lambda _case_root: ({"sha256": "a" * 64, "expected_bytes": 4}, reference),
    )
    monkeypatch.setattr(harness, "_hash_file", lambda path: (4, "a" * 64))

    comparison = harness._supervisor_compare_reference(case_root, str(final))

    assert comparison["status"] == "TRUSTED_REFERENCE_MISMATCH"
    assert comparison["final_bytes"] == comparison["reference_bytes"] == 4
    assert comparison["final_sha256"] == comparison["reference_sha256"]
    assert comparison["bytewise_match"] is False


@pytest.mark.parametrize("invalid_reference", [False, True])
def test_supervisor_reference_comparison_blocks_missing_or_invalid_reference(
    tmp_path, monkeypatch, invalid_reference,
) -> None:
    case_root, _reference, final = _trusted_reference_case(
        tmp_path, b"reference bytes", b"reference bytes",
    )

    if invalid_reference:
        missing_reference = tmp_path / "missing-reference.bin"
        monkeypatch.setattr(
            harness, "_verify_reference_manifest",
            lambda _case_root: ({"sha256": "0" * 64, "expected_bytes": 15}, missing_reference),
        )
    else:
        def unavailable(_case_root):
            raise RuntimeError("TRUSTED_REFERENCE_UNAVAILABLE")

        monkeypatch.setattr(harness, "_verify_reference_manifest", unavailable)
    comparison = harness._supervisor_compare_reference(case_root, str(final))

    assert comparison["status"] == "BLOCKED"
    if not invalid_reference:
        assert comparison["reason"] == "TRUSTED_REFERENCE_UNAVAILABLE"


def test_supervisor_reference_comparison_blocks_reference_alias(tmp_path, monkeypatch) -> None:
    payload = b"single original file"
    case_root, reference, final = _trusted_reference_case(tmp_path, payload, payload)
    _install_test_reference_manifest(monkeypatch, reference, payload)

    samefile = os.path.samefile

    def simulated_samefile(left, right):
        if Path(left) == reference and Path(right) == final:
            return True
        return samefile(left, right)

    monkeypatch.setattr(harness.os.path, "samefile", simulated_samefile)
    alias_comparison = harness._supervisor_compare_reference(case_root, str(final))

    assert alias_comparison["status"] == "BLOCKED"
    assert alias_comparison["reason"] == "OUTPUT_ALIASES_TRUSTED_REFERENCE"


def test_supervisor_reference_comparison_blocks_outside_final_path(tmp_path, monkeypatch) -> None:
    payload = b"reference remains outside the output root"
    case_root, reference, final = _trusted_reference_case(tmp_path, payload, payload)
    _install_test_reference_manifest(monkeypatch, reference, payload)

    outside_comparison = harness._supervisor_compare_reference(case_root, str(reference))

    assert outside_comparison["status"] == "BLOCKED"


def test_trusted_reference_budget_rejects_profile_over_approved_cap(monkeypatch) -> None:
    monkeypatch.setattr(
        harness, "TRUSTED_REFERENCE_APPROVED_MAXIMA",
        {"getfile_calls": 8507, "getfilehashes_calls": 8542, "reserved_bytes": 2_230_321_152},
    )

    with pytest.raises(RuntimeError, match="AUTHORIZED_PROFILE_CAP_MISMATCH"):
        harness._case_budget(
            harness.CONTROLLED_TARGET, "TRUSTED_REFERENCE", "aligned", "8MiB",
        )


def test_unaligned_prepared_budget_is_immutable_and_within_approved_maxima() -> None:
    budget = harness._case_budget(
        harness.COMMON_TARGET, "OPERATIONAL_ONLY", "unaligned-prepared",
    )

    assert (budget["prefix_bytes"], budget["wire_offset"], budget["overlap_bytes"]) == (
        1_048_699, 1_048_576, 123,
    )
    assert budget["transfer_offset"] == 1_310_720
    assert (
        budget["aggregate_getfile_cap"],
        budget["aggregate_getfilehashes_cap"],
        budget["aggregate_payload_reservation_cap"],
    ) == (95, 92, 24_903_680)
    assert budget["aggregate_getfile_cap"] <= harness.APPROVED_LIMITS["getfile_calls"]
    assert budget["aggregate_getfilehashes_cap"] <= harness.APPROVED_LIMITS["getfilehashes_calls"]
    assert budget["aggregate_payload_reservation_cap"] <= harness.APPROVED_LIMITS["reserved_bytes"]


def test_operational_progress_is_allowlisted_without_test_probe(tmp_path, monkeypatch) -> None:
    progress = tmp_path / "progress.jsonl"
    monkeypatch.delenv("S6_V2_TEST_PROBE", raising=False)
    monkeypatch.setenv("S6_V2_PROGRESS_JSONL", str(progress))
    monkeypatch.setenv("S6_V2_PROGRESS_ROOT", str(tmp_path))
    harness._progress_event(
        "child.transfer_progress", phase=2, execution_id="offline-exec",
        outcome="completed", counts={"verified_bytes": 262144, "secret": "must-not-appear"},
    )
    row = json.loads(progress.read_text(encoding="utf-8"))
    assert set(row) == {
        "execution_id", "phase", "process_id", "stage", "sequence",
        "monotonic_ns", "outcome", "counts",
    }
    assert row["counts"] == {"verified_bytes": 262144}
    assert "secret" not in progress.read_text(encoding="utf-8")


def test_semantic_progress_ignores_heartbeats_duplicates_and_bad_counts() -> None:
    seen: set[str] = set()
    counts: dict[str, int] = {}
    assert not harness._progress_is_semantic(
        {"stage": "child.ready", "outcome": "started", "counts": {}}, seen, counts,
    )
    first = {"stage": "child.transfer_progress", "outcome": "completed", "counts": {"verified_bytes": 10}}
    assert harness._progress_is_semantic(first, seen, counts)
    assert not harness._progress_is_semantic(first, seen, counts)
    assert not harness._progress_is_semantic(
        {"stage": "child.prefix_hash_reconciled", "outcome": "mismatch", "counts": {"verified_bytes": 20}},
        seen, counts,
    )
    assert counts["verified_bytes"] == 10
    assert not harness._progress_is_semantic(
        {"stage": "supervisor.poll", "outcome": "completed", "counts": {}}, seen, counts,
    )


def test_progress_line_reader_preserves_partial_jsonl_record() -> None:
    complete, pending = harness._split_progress_buffer(b'{"stage":', b'"child.ready"}\n{"stage":')
    assert complete == [b'{"stage":"child.ready"}']
    assert pending == b'{"stage":'


def test_supervisor_timeouts_use_semantic_clock_and_aggregate_deadline() -> None:
    assert harness._supervisor_timeout_reason(
        now=30, spawned=0, last_semantic=29, ready=False,
        aggregate_started=0, phase_timeout=900,
    ) == "CHILD_READINESS_TIMEOUT"
    assert harness._supervisor_timeout_reason(
        now=180, spawned=0, last_semantic=0, ready=True,
        aggregate_started=0, phase_timeout=900,
    ) == "SEMANTIC_INACTIVITY_TIMEOUT"
    assert harness._supervisor_timeout_reason(
        now=900, spawned=800, last_semantic=899, ready=True,
        aggregate_started=0, phase_timeout=900,
    ) == "AGGREGATE_DEADLINE"
    assert harness._supervisor_timeout_reason(
        now=179, spawned=0, last_semantic=0, ready=True,
        aggregate_started=0, phase_timeout=900,
    ) is None


def test_scenario_deadline_policies_and_near_deadline_progress_do_not_extend_hard_limit() -> None:
    assert harness._deadline_policy("OPERATIONAL_ONLY") == (3600, 900)
    assert harness._deadline_policy("TRUSTED_REFERENCE") == (4500, 4800)
    assert harness._supervisor_timeout_reason(
        now=4770, spawned=0, last_semantic=4769, ready=True,
        aggregate_started=0, phase_timeout=4500, aggregate_deadline=4770,
    ) == "AGGREGATE_DEADLINE"


def test_transfer_byte_progress_is_semantic_but_heartbeat_is_not_an_event() -> None:
    seen: set[str] = set()
    counts: dict[str, int] = {}
    first = {
        "stage": "child.transfer_progress", "outcome": "completed",
        "counts": {"stream_confirmed_bytes": 262144, "persisted_bytes": 131072},
    }
    assert harness._progress_is_semantic(first, seen, counts)
    first["counts"]["stream_confirmed_bytes"] = 524288
    assert harness._progress_is_semantic(first, seen, counts)
    assert counts["stream_confirmed_bytes"] == 524288
    assert "heartbeat" not in harness._PROGRESS_STAGES


def test_secure_preflight_status_only_uses_synthetic_providers(monkeypatch) -> None:
    from telegram_courses import config, telethon_session

    class SyntheticSessionVault:
        def __init__(self):
            pass

        def _load(self):
            return "synthetic-protected-session"

    monkeypatch.setattr(config, "load_telegram_credentials", lambda environ: object())
    monkeypatch.setattr(telethon_session, "_ProtectedSessionVault", SyntheticSessionVault)
    status = harness._status_only_secure_preflight()
    assert status == {
        "credential_vault": "YES", "protected_session": "YES",
        "provider": "WINDOWS_PROTECTED_VAULT",
    }


def test_execute_launcher_displays_fixed_profile_and_requires_fresh_native_confirmation() -> None:
    launcher = (harness.REPOSITORY_ROOT / "tools/manual_proofs/Invoke-S6V2Proof.ps1").read_text(encoding="utf-8")
    for required in (
        "WINDOWS_USER=", "WINDOWS_PROFILE=", "PROTECTED_SESSION_PATH=",
        "TARGET_CHANNEL=$targetChannel", "TARGET_MESSAGE=$targetMessage", "TARGET_TYPE=DOCUMENT",
        "TARGET_SIZE=$targetBytes", "MODE=$IntegrityMode", "SCENARIO=$scenario",
        "GETFILE_APPROVED_MAX=$getfileApprovedMax; GETFILE_EFFECTIVE_CAP=$getfileEffectiveCap",
        "GETFILEHASHES_APPROVED_MAX=$getfilehashesApprovedMax; GETFILEHASHES_EFFECTIVE_CAP=$getfilehashesEffectiveCap",
        "RESERVED_BYTES_APPROVED_MAX=$reservedBytesApprovedMax; RESERVED_BYTES_EFFECTIVE_CAP=$reservedBytesEffectiveCap",
        "--secure-preflight-status-only", "FRESH_ISOLATED_ROOT=YES",
    ):
        assert required in launcher
    assert "TRUSTED_REFERENCE; PREFIX_PROFILE=$PrefixProfile; PREFIX_BYTES=$prefixBytes;" in launcher
    assert "$PrefixProfile -ceq '8MiB'" in launcher
    assert "$getfileEffectiveCap = 8508" in launcher
    assert "$getfileEffectiveCap = 8028" in launcher
    assert "$reservedBytesEffectiveCap = 2230321152" in launcher
    assert "$reservedBytesEffectiveCap = 2104492032" in launcher
    assert "$getfileEffectiveCap = 94" in launcher
    assert "$reservedBytesEffectiveCap = 24641536" in launcher
    assert "unaligned-prepared; PREFIX_BYTES=1048699; REMOTE_ALIGNED_OFFSET=1048576; CHUNK_BYTES=262144; OVERLAP=123" in launcher
    assert "$getfileEffectiveCap = 95" in launcher
    assert "$reservedBytesEffectiveCap = 24903680" in launcher
    assert '"EXECUTE S6 V2 PROOF controlled TRUSTED_REFERENCE channel=-1002368271467 message=7603 media=5089068167339181674 bytes=1119129690 aligned PREFIX_PROFILE=$PrefixProfile PREFIX_BYTES=$prefixBytes GETFILE_CAP=$getfileEffectiveCap HASHES_CAP=$getfilehashesEffectiveCap IDENTITY_GETMESSAGES_CAP=$identityGetMessagesEffectiveCap RESERVED_BYTES=$reservedBytesEffectiveCap"' in launcher
    assert "$profileLocalAppData = $env:LOCALAPPDATA" in launcher
    assert "LOCALAPPDATA_SOURCE=INHERITED_UNMODIFIED" in launcher
    assert "if ([string]::IsNullOrWhiteSpace($profileLocalAppData))" in launcher
    assert "Inherited LOCALAPPDATA is unavailable; proof execution is blocked." in launcher
    assert "$env:LOCALAPPDATA =" not in launcher
    assert "resume is disabled" in launcher



def test_preconfirmation_status_is_static_and_includes_read_only_reference_fingerprint(
    tmp_path, monkeypatch, capsys,
) -> None:
    payload = b"s" * (harness.CHUNK_BYTES + 1)
    _install_controlled_reference_inputs(monkeypatch, tmp_path, payload)
    monkeypatch.setattr(
        harness, "CONTROLLED_PREFIX_OPTIONS",
        {"8MiB": harness.CHUNK_BYTES, "128MiB": harness.CHUNK_BYTES},
    )
    monkeypatch.setattr(harness, "_verify_ratified_contract", lambda: None)
    evidence_parent = tmp_path / "native-evidence-parent"
    evidence_parent.mkdir()
    monkeypatch.setattr(sys, "argv", [
        "s6_v2_proof_harness.py", "--preconfirmation-status-only",
        "--target", "controlled", "--mode", "TRUSTED_REFERENCE",
        "--prefix-profile", "8MiB", "--evidence-parent", str(evidence_parent),
    ])

    assert harness.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "PASS"
    assert result["rpc_calls"] == 0
    assert result["target"]["channel_id"] == -1002368271467
    assert result["target"]["message_id"] == 7603
    assert result["target"]["media_id"] == "5089068167339181674"
    assert result["target"]["media_kind"] == "DOCUMENT"
    assert result["reference"]["bytes"] == len(payload)
    assert result["reference"]["access_mode"] == "READ_ONLY_BINARY"
    assert result["v1_active"] is True and result["v2_global_effective"] is False
    assert not any(path.name.startswith("s6t-") for path in evidence_parent.iterdir())


def test_human_confirmation_absence_stops_before_root_creation_or_gateway(tmp_path, monkeypatch, capsys) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("execution path must not reach root creation or a gateway")

    monkeypatch.setattr(harness, "_new_isolated_root", forbidden)
    monkeypatch.setattr(harness, "_real_gateway", forbidden)
    monkeypatch.setattr(sys, "argv", [
        "s6_v2_proof_harness.py", "--target", "controlled", "--mode", "TRUSTED_REFERENCE",
        "--evidence-parent", str(tmp_path), "--prefix-profile", "8MiB",
    ])

    assert harness.main() == 5
    assert capsys.readouterr().out == "STOP=RuntimeError\n"
    assert list(tmp_path.iterdir()) == []


def test_preconfirmation_launcher_gates_are_before_human_confirmation() -> None:
    launcher = (harness.REPOSITORY_ROOT / "tools/manual_proofs/Invoke-S6V2Proof.ps1").read_text(
        encoding="utf-8"
    )
    preflight = launcher.index("'--preconfirmation-status-only'")
    confirmation = launcher.index("$confirmation = Read-Host")
    assert preflight < confirmation
    assert "TARGET_DECLARED_IDENTITY_PREFLIGHT=PASS; RPC_CALLS=0" in launcher
    assert "REFERENCE_SHA256_PREFLIGHT=$($preflightReference.sha256)" in launcher
    assert "Assert-NoReparseDirectoryPath -Path $EvidenceParent" in launcher
    assert "IsReadOnly" not in launcher


def test_final_short_chunk_fits_request_quantized_reservation(tmp_path) -> None:
    expected = harness.CONTROLLED_TARGET["expected_bytes"]
    tail_bytes = expected % harness.CHUNK_BYTES
    assert tail_bytes > 0
    ledger = harness.ProofLedger(
        tmp_path / "proof-budget.sqlite3",
        getfile_cap=1,
        hash_cap=0,
        payload_cap=harness.CHUNK_BYTES,
    )
    # At EOF, S5 still reserves one full C-sized request for the short tail.
    ledger.reserve_getfile(tail_bytes, "short-tail")
    ledger.settle_getfile("short-tail", tail_bytes)

    snapshot = ledger.snapshot()
    assert snapshot["getfile_calls"] == 1
    assert snapshot["payload_received"] == tail_bytes
    assert snapshot["payload_reserved"] == harness.CHUNK_BYTES
    with pytest.raises(RuntimeError, match="PROOF_BUDGET_EXHAUSTED"):
        ledger.reserve_getfile(harness.CHUNK_BYTES)


def test_proof_ledger_reservation_is_transactional_and_idempotent(tmp_path) -> None:
    ledger = harness.ProofLedger(
        tmp_path / "proof-budget.sqlite3", getfile_cap=1, hash_cap=1,
        payload_cap=harness.CHUNK_BYTES,
    )
    assert ledger.reserve_getfile(7, "phase-1:getfile:1") == 1
    assert ledger.reserve_getfile(7, "phase-1:getfile:1") == 1
    assert ledger.snapshot() == {
        "getfile_calls": 1, "getfilehashes_calls": 0,
        "payload_reserved": harness.CHUNK_BYTES, "payload_received": 0,
        "uncertain_bytes": 0,
    }
    with pytest.raises(RuntimeError, match="PROOF_RESERVATION_ID_CONFLICT"):
        ledger.reserve_getfile(8, "phase-1:getfile:1")
    with pytest.raises(RuntimeError, match="PROOF_BUDGET_EXHAUSTED"):
        ledger.reserve_getfile(1, "phase-1:getfile:2")
    assert ledger.reserve_hash("phase-1:hash:1") == 1
    assert ledger.reserve_hash("phase-1:hash:1") == 1
    assert ledger.snapshot()["getfilehashes_calls"] == 1


def test_proof_reservation_settlement_is_idempotent_and_pending_becomes_uncertain_once(tmp_path) -> None:
    ledger = harness.ProofLedger(
        tmp_path / "proof-budget.sqlite3", getfile_cap=2, hash_cap=0,
        payload_cap=2 * harness.CHUNK_BYTES,
    )
    ledger.reserve_getfile(7, "phase-1:getfile:received")
    ledger.reserve_getfile(9, "phase-1:getfile:pending")
    assert ledger.settle_getfile("phase-1:getfile:received", 7) == "RECEIVED"
    assert ledger.settle_getfile("phase-1:getfile:received", 7) == "RECEIVED"
    assert ledger.settle_pending_uncertain() == 1
    assert ledger.settle_pending_uncertain() == 0
    assert ledger.reservation_summary() == {"pending": 0, "received": 1, "uncertain": 1}
    assert ledger.snapshot() == {
        "getfile_calls": 2, "getfilehashes_calls": 0,
        "payload_reserved": 2 * harness.CHUNK_BYTES, "payload_received": 7,
        "uncertain_bytes": harness.CHUNK_BYTES,
    }


@pytest.mark.parametrize(
    ("column", "value", "expected_error"),
    [
        ("getfile_calls", -1, "PROOF_BUDGET_LEDGER_INCONSISTENT"),
        ("payload_reserved", 1, "PROOF_BUDGET_LEDGER_INCONSISTENT"),
        ("payload_received", "not-an-integer", "PROOF_BUDGET_LEDGER_INVALID"),
        ("uncertain_bytes", harness.CHUNK_BYTES + 1, "PROOF_BUDGET_LEDGER_INCONSISTENT"),
        ("getfilehashes_calls", 2, "PROOF_BUDGET_LEDGER_INCONSISTENT"),
    ],
)
def test_corrupt_proof_ledger_fails_before_gateway_access(
    tmp_path, column, value, expected_error,
) -> None:
    path = tmp_path / "proof-budget.sqlite3"
    ledger = harness.ProofLedger(
        path, getfile_cap=1, hash_cap=1, payload_cap=harness.CHUNK_BYTES,
    )
    ledger.reserve_getfile(1, "seed:getfile:1")
    with sqlite3.connect(path) as db:
        db.execute(f"UPDATE proof_budget SET {column}=? WHERE singleton=1", (value,))

    class NeverGateway:
        restore_called = False

        async def restore(self):
            self.restore_called = True

    gateway = NeverGateway()
    with pytest.raises(RuntimeError, match=expected_error):
        harness.ProofLedger(
            path, getfile_cap=1, hash_cap=1, payload_cap=harness.CHUNK_BYTES,
            require_existing=True,
        )
        harness.ProofGateway(gateway, ledger, phase=2)
    assert gateway.restore_called is False


def test_resume_refuses_to_initialize_missing_persistent_ledger(tmp_path) -> None:
    missing = tmp_path / "missing-budget.sqlite3"
    with pytest.raises(RuntimeError, match="PROOF_BUDGET_LEDGER_MISSING"):
        harness.ProofLedger(
            missing, getfile_cap=1, hash_cap=1, payload_cap=harness.CHUNK_BYTES,
            require_existing=True,
        )
    assert not missing.exists()


def test_scoped_activation_is_explicit_targeted_and_restored() -> None:
    import telegram_courses.downloads as downloads_module

    assert downloads_module.V2_EFFECTIVE is False
    with harness._scoped_v2_switch(
        "OPERATIONAL_ONLY", harness.target_for("common"), authorized=True
    ):
        assert downloads_module.V2_EFFECTIVE is True
    assert downloads_module.V2_EFFECTIVE is False

    with pytest.raises(RuntimeError, match="HOMOLOGATION_SCOPE_NOT_AUTHORIZED"):
        harness._scoped_v2_switch(
            "OPERATIONAL_ONLY", harness.target_for("common"), authorized=False
        )
    with pytest.raises(RuntimeError, match="EXPLICIT_V2_MODE_REQUIRED"):
        harness._scoped_v2_switch(
            "REMOTE_HASH_REQUIRED", harness.target_for("common"), authorized=True
        )
    assert downloads_module.V2_EFFECTIVE is False
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with harness._scoped_v2_switch(
            "OPERATIONAL_ONLY", harness.target_for("common"), authorized=True
        ):
            raise RuntimeError("synthetic failure")
    assert downloads_module.V2_EFFECTIVE is False


@pytest.mark.parametrize(
    ("target", "mode"),
    [
        ("common", "TRUSTED_REFERENCE"),
        ("controlled", "OPERATIONAL_ONLY"),
    ],
)
def test_target_mode_mismatch_fails_closed(target: str, mode: str) -> None:
    with pytest.raises(RuntimeError, match="REQUIRES_"):
        harness._validate_target_profile(target, mode)


def test_child_authorization_binds_target_mode_root_and_report(tmp_path, monkeypatch) -> None:
    token = "a" * 64
    monkeypatch.setenv("S6_V2_PROOF_AUTH", token)
    root = tmp_path / "s6-v2-real-proof-test"
    root.mkdir()
    profile = harness._case_budget(harness.COMMON_TARGET, "OPERATIONAL_ONLY", "aligned")
    (root / "authorization.json").write_text(
        json.dumps({
            "evidence_root": str(root.resolve()),
            "target": "common",
            "mode": "OPERATIONAL_ONLY",
            "contract_sha256": harness.V2_CONTRACT_SHA256,
            "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "allowed_cases": ["aligned"],
            "allowed_phases": [1, 2],
            "case_profile": {
                "prefix_bytes": profile["prefix_bytes"],
                "prefix_profile": profile.get("prefix_profile"),
                "wire_offset": profile["wire_offset"],
                "transfer_offset": profile["transfer_offset"],
                "overlap_bytes": profile["overlap_bytes"],
                "effective_caps": harness._case_effective_limits(
                    "aligned", "OPERATIONAL_ONLY", "common", profile,
                ),
                "approved_maxima": dict(harness.APPROVED_LIMITS),
            },
        }),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        evidence_root=root,
        phase_report=root / "aligned" / "phase-1.child.json",
        authorization_file=root / "authorization.json",
        target="common",
        mode="OPERATIONAL_ONLY",
        case="aligned",
        phase=1,
        phase1_pid=0,
        recovered_phase1=False,
    )

    assert harness._validate_child_authorization(args)["target"] == "common"
    args.phase_report = tmp_path / "outside.child.json"
    with pytest.raises(RuntimeError, match="CHILD_PATH_SCOPE_INVALID"):
        harness._validate_child_authorization(args)


def test_recovered_phase2_child_requires_observed_phase1_exit(tmp_path, monkeypatch) -> None:
    token = "b" * 64
    monkeypatch.setenv("S6_V2_PROOF_AUTH", token)
    root = tmp_path / "s6-v2-real-proof-recovery"
    case_root = root / "aligned"
    case_root.mkdir(parents=True)
    profile = harness._case_budget(harness.COMMON_TARGET, "OPERATIONAL_ONLY", "aligned")
    (root / "authorization.json").write_text(json.dumps({
        "evidence_root": str(root.resolve()), "target": "common",
        "mode": "OPERATIONAL_ONLY", "contract_sha256": harness.V2_CONTRACT_SHA256,
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "allowed_cases": ["aligned"], "allowed_phases": [2], "recovered_phase1": True,
        "case_profile": {
            "prefix_bytes": profile["prefix_bytes"],
            "prefix_profile": profile.get("prefix_profile"),
            "wire_offset": profile["wire_offset"],
            "transfer_offset": profile["transfer_offset"],
            "overlap_bytes": profile["overlap_bytes"],
            "effective_caps": harness._case_effective_limits(
                "aligned", "OPERATIONAL_ONLY", "common", profile,
            ),
            "approved_maxima": dict(harness.APPROVED_LIMITS),
        },
    }), encoding="utf-8")
    (case_root / "phase-1.json").write_text(json.dumps({
        "phase": 1, "process_id": None, "process_exit_confirmed": True,
        "target_name": "common", "mode": "OPERATIONAL_ONLY", "case": "aligned",
        "sqlite_state": "FAILED_RETRYABLE",
    }), encoding="utf-8")
    args = SimpleNamespace(
        evidence_root=root, phase_report=case_root / "phase-2.child.json",
        authorization_file=root / "authorization.json", target="common",
        mode="OPERATIONAL_ONLY", case="aligned", phase=2, phase1_pid=0,
        recovered_phase1=True,
    )

    assert harness._validate_child_authorization(args)["allowed_phases"] == [2]
    args.recovered_phase1 = False
    with pytest.raises(RuntimeError, match="CHILD_AUTHORIZATION_SCOPE_MISMATCH"):
        harness._validate_child_authorization(args)


def test_dryrun_creates_only_proof_sqlite_and_leaves_v2_disabled(tmp_path) -> None:
    import telegram_courses.downloads as downloads_module

    exit_code, evidence_root = harness.dry_run("common", "OPERATIONAL_ONLY", tmp_path)
    report = json.loads((evidence_root / "s6-v2-dryrun-report.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["real_telegram_calls"] == 0
    assert report["original_sqlite_access"] == "NO"
    assert report["historical_part_access"] == "NO"
    assert report["v2_effective"] is False
    assert Path(report["proof_sqlite"]).is_file()
    assert downloads_module.V2_EFFECTIVE is False


def test_python_entrypoint_refuses_execute_without_native_launcher_flag(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["s6_v2_proof_harness.py", "--target", "common", "--mode", "OPERATIONAL_ONLY"],
    )
    assert harness.main() == 5
    output = capsys.readouterr().out
    assert "STOP=RuntimeError" in output
    assert "USE_NATIVE_LAUNCHER_CONFIRMATION" not in output


def test_child_rejects_missing_native_token_before_async_entry(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.delenv("S6_V2_PROOF_AUTH", raising=False)
    monkeypatch.setattr(
        harness.asyncio, "run",
        lambda *args, **kwargs: pytest.fail("async event loop must not start without native token"),
    )
    args = SimpleNamespace(
        target="common", mode="OPERATIONAL_ONLY", case="aligned", phase=1,
        evidence_root=tmp_path, phase_report=tmp_path / "phase-1.json", phase1_pid=0,
        recovered_phase1=False,
    )

    assert harness._child_main(args) == 5
    assert "NATIVE_CONFIRMATION_TOKEN_REQUIRED" in capsys.readouterr().out


def test_real_execute_scope_is_common_operational_with_immutable_case_profiles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "a" * 64)
    monkeypatch.setattr(harness, "_verify_ratified_contract", lambda: None)

    with pytest.raises(RuntimeError, match="REAL_PROOF_SCOPE_NOT_AUTHORIZED"):
        harness.execute("common", "TRUSTED_REFERENCE", tmp_path, case_name="aligned")
    assert harness._case_budget(
        harness.CONTROLLED_TARGET, "TRUSTED_REFERENCE", "aligned", "8MiB"
    )["prefix_bytes"] == 8 * 1024 * 1024
    budget = harness._case_budget(
        harness.COMMON_TARGET, "OPERATIONAL_ONLY", "unaligned-prepared",
    )
    assert budget["prefix_bytes"] == 1_048_699
    assert budget["wire_offset"] == 1_048_576
    assert budget["overlap_bytes"] == 123
    assert budget["transfer_offset"] == 1_310_720
    assert budget["aggregate_getfile_cap"] == 95
    assert budget["aggregate_getfilehashes_cap"] == 92
    assert budget["aggregate_payload_reservation_cap"] == 24_903_680
    assert harness._case_effective_limits("unaligned-prepared") == {
        "getfile_calls": 95, "getfilehashes_calls": 92, "reserved_bytes": 24_903_680,
    }
    assert harness._case_effective_limits("aligned") == {
        "getfile_calls": 94, "getfilehashes_calls": 92, "reserved_bytes": 24_641_536,
    }
    with pytest.raises(RuntimeError, match="AUTHORIZED_PROOF_CASE_MISSING"):
        harness._case_budget(harness.COMMON_TARGET, "OPERATIONAL_ONLY", "other")


def test_native_launcher_requires_sync_confirmation_before_child_spawn() -> None:
    launcher = (harness.REPOSITORY_ROOT / "tools/manual_proofs/Invoke-S6V2Proof.ps1").read_text(
        encoding="utf-8"
    )
    confirmation = launcher.index("$confirmation = Read-Host")
    token_creation = launcher.index("$random.GetBytes($authorizationBytes)")
    child_dispatch = launcher.index("& $pythonPath @arguments '--case' $Case")

    assert confirmation < token_creation < child_dispatch
    assert "EXECUTE S6 V2 PROOF common OPERATIONAL_ONLY $Case" in launcher
    assert "$Case -ceq 'aligned'" in launcher
    assert "aligned; PREFIX_BYTES=1048576; REMOTE_ALIGNED_OFFSET=1048576; CHUNK_BYTES=262144; OVERLAP=0 / NOT_APPLICABLE_ALIGNED" in launcher
    assert "unaligned-prepared; PREFIX_BYTES=1048699; REMOTE_ALIGNED_OFFSET=1048576; CHUNK_BYTES=262144; OVERLAP=123" in launcher
    assert "$getfileEffectiveCap = 94" in launcher
    assert "$getfileEffectiveCap = 95" in launcher
    assert "$reservedBytesEffectiveCap = 24641536" in launcher
    assert "$reservedBytesEffectiveCap = 24903680" in launcher
    assert "requires a fresh isolated proof root; resume is disabled" in launcher
    assert "$preflightOutput = @(& $pythonPath $harnessPath '--secure-preflight-status-only')" in launcher
    policy_query = launcher.index("'--timeout-policy-status-only'")
    confirmation = launcher.index("$confirmation = Read-Host")
    assert policy_query < confirmation
    assert "PROCESS_TIMEOUT_EFFECTIVE_SECONDS=$policyProcessTimeout" in launcher
    assert "AGGREGATE_DEADLINE_EFFECTIVE_SECONDS=$policyAggregateDeadline" in launcher
    assert "'--expected-timeout-policy-sha256' $timeoutPolicyHash" in launcher
    assert "contract_match" in launcher
    assert "--native-launcher-confirmed" in launcher
    assert "Start-Job" not in launcher
    assert "Start-ThreadJob" not in launcher
    assert "Task.Run" not in launcher


def test_effective_timeout_policy_is_scenario_scoped_and_contract_checked(monkeypatch) -> None:
    controlled = harness._effective_timeout_policy("controlled", "TRUSTED_REFERENCE")
    assert controlled["process_timeout_effective_seconds"] == 4500
    assert controlled["aggregate_deadline_effective_seconds"] == 4800
    assert controlled["semantic_inactivity_timeout_seconds"] == 180
    assert controlled["progress_heartbeat_seconds"] == 15
    assert controlled["cancellation_grace_max_seconds"] == 30
    assert controlled["grace_inside_hard_deadline"] is True
    assert controlled["contract_match"] is True
    common = harness._effective_timeout_policy("common", "OPERATIONAL_ONLY")
    assert common["process_timeout_effective_seconds"] == 3600
    assert common["aggregate_deadline_effective_seconds"] == 900
    assert common["contract_match"] is True
    with pytest.raises(RuntimeError, match="TIMEOUT_POLICY_SCENARIO_NOT_AUTHORIZED"):
        harness._effective_timeout_policy("controlled", "OPERATIONAL_ONLY")
    monkeypatch.setattr(harness, "PROOF_TRUSTED_REFERENCE_AGGREGATE_DEADLINE_SECONDS", 900)
    assert harness._effective_timeout_policy("controlled", "TRUSTED_REFERENCE")["contract_match"] is False


@pytest.mark.parametrize(
    ("target", "mode", "process_timeout", "aggregate_deadline"),
    [
        ("controlled", "TRUSTED_REFERENCE", 4500, 4800),
        ("common", "OPERATIONAL_ONLY", 3600, 900),
    ],
)
def test_timeout_policy_status_cli_emits_effective_values(monkeypatch, capsys, target, mode,
                                                          process_timeout, aggregate_deadline) -> None:
    monkeypatch.setattr(sys, "argv", [
        "s6_v2_proof_harness.py", "--timeout-policy-status-only", "--target", target, "--mode", mode,
    ])
    assert harness.main() == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["target"] == target
    assert emitted["mode"] == mode
    assert emitted["process_timeout_effective_seconds"] == process_timeout
    assert emitted["aggregate_deadline_effective_seconds"] == aggregate_deadline
    assert emitted["contract_match"] is True
    assert len(emitted["policy_sha256"]) == 64


def test_timeout_policy_status_cli_fails_closed_when_policy_or_scenario_is_invalid(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["s6_v2_proof_harness.py", "--timeout-policy-status-only"])
    assert harness.main() == 5
    assert capsys.readouterr().out == "STOP=RuntimeError\n"
    monkeypatch.setattr(sys, "argv", [
        "s6_v2_proof_harness.py", "--timeout-policy-status-only", "--target", "controlled",
        "--mode", "OPERATIONAL_ONLY",
    ])
    assert harness.main() == 5
    assert capsys.readouterr().out == "STOP=RuntimeError\n"
    with pytest.raises(RuntimeError, match="TIMEOUT_POLICY_SCENARIO_NOT_AUTHORIZED"):
        harness._effective_timeout_policy("controlled", "OPERATIONAL_ONLY")


def test_execution_fails_closed_if_timeout_configuration_changes_after_confirmation(monkeypatch, tmp_path) -> None:
    policy = harness._effective_timeout_policy("controlled", "TRUSTED_REFERENCE")
    monkeypatch.setattr(harness, "PROOF_TRUSTED_REFERENCE_AGGREGATE_DEADLINE_SECONDS", 900)
    monkeypatch.setattr(sys, "argv", [
        "s6_v2_proof_harness.py", "--target", "controlled", "--mode", "TRUSTED_REFERENCE",
        "--evidence-parent", str(tmp_path), "--native-launcher-confirmed",
        "--expected-timeout-policy-sha256", policy["policy_sha256"],
    ])
    assert harness.main() == 5


def test_execution_fails_closed_when_effective_policy_diverges_from_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(harness, "PROOF_TRUSTED_REFERENCE_AGGREGATE_DEADLINE_SECONDS", 900)
    changed_policy = harness._effective_timeout_policy("controlled", "TRUSTED_REFERENCE")
    monkeypatch.setattr(sys, "argv", [
        "s6_v2_proof_harness.py", "--target", "controlled", "--mode", "TRUSTED_REFERENCE",
        "--evidence-parent", str(tmp_path), "--native-launcher-confirmed",
        "--expected-timeout-policy-sha256", changed_policy["policy_sha256"],
    ])
    assert harness.main() == 5


def test_proof_gateway_fails_closed_before_identity_preflight(tmp_path) -> None:
    class NeverCalledGateway:
        async def get_file_hashes(self, *args, **kwargs):
            raise AssertionError("remote hash call must not happen before identity preflight")

    ledger = harness.ProofLedger(tmp_path / "proof-budget.sqlite3", getfile_cap=1, hash_cap=1,
                                 payload_cap=harness.CHUNK_BYTES)
    gateway = harness.ProofGateway(NeverCalledGateway(), ledger, phase=1)

    request = gateway.get_file_hashes(0, 1)
    with pytest.raises(RuntimeError, match="REMOTE_IDENTITY_PREFLIGHT_REQUIRED"):
        request.send(None)
    assert ledger.snapshot()["getfilehashes_calls"] == 0


def test_remote_identity_mismatch_prevents_getfile_streaming(tmp_path) -> None:
    class MismatchedIdentityGateway:
        def __init__(self):
            self.stream_calls = 0

        async def validate_media_identity(self, *_args, **_kwargs):
            return False

        async def stream_media(self, *_args, **_kwargs):
            self.stream_calls += 1
            raise AssertionError("GetFile streaming must not start after identity mismatch")

    inner = MismatchedIdentityGateway()
    ledger = harness.ProofLedger(
        tmp_path / "identity-mismatch.sqlite3", getfile_cap=1, hash_cap=0,
        payload_cap=harness.CHUNK_BYTES,
    )
    gateway = harness.ProofGateway(inner, ledger, phase=1)

    validation = gateway.validate_media_identity(
        harness.CONTROLLED_TARGET["channel_id"],
        harness.CONTROLLED_TARGET["message_id"],
        harness.CONTROLLED_TARGET["media_ordinal"],
        telegram_media_id=harness.CONTROLLED_TARGET["media_id"],
        expected_bytes=harness.CONTROLLED_TARGET["expected_bytes"],
    )
    with pytest.raises(StopIteration) as result:
        validation.send(None)
    assert result.value.value is False

    async def no_reservation(*_args, **_kwargs):
        raise AssertionError("no budget reservation may occur before identity passes")

    stream = gateway.stream_media(
        harness.CONTROLLED_TARGET["channel_id"],
        harness.CONTROLLED_TARGET["message_id"],
        harness.CONTROLLED_TARGET["media_ordinal"],
        telegram_media_id=harness.CONTROLLED_TARGET["media_id"],
        expected_bytes=harness.CONTROLLED_TARGET["expected_bytes"],
        reserve_chunk=no_reservation,
    )
    with pytest.raises(RuntimeError, match="REMOTE_IDENTITY_PREFLIGHT_REQUIRED"):
        stream.__anext__().send(None)
    assert inner.stream_calls == 0
    assert gateway.getfile_calls == 0
    assert ledger.snapshot()["getfile_calls"] == 0


def test_unaligned_preparation_uses_controlled_application_stream_and_reconciles_wire(tmp_path) -> None:
    prefix_bytes = 1_048_699
    chunks = [bytes([index]) * harness.CHUNK_BYTES for index in range(5)]

    class Lease:
        def received(self, _count):
            pass

        def release(self):
            pass

        def charge_uncertain(self):
            pass

    class SyntheticGateway:
        async def stream_media(self, *args, reserve_chunk, **kwargs):
            for block in chunks:
                lease = await reserve_chunk(len(block))
                lease.received(len(block))
                yield block

    async def grant(_size):
        return Lease()

    ledger = harness.ProofLedger(
        tmp_path / "unaligned-preparation.sqlite3", getfile_cap=5, hash_cap=0,
        payload_cap=5 * harness.CHUNK_BYTES,
    )
    gateway = harness.ProofGateway(
        SyntheticGateway(), ledger, phase=1, phase_getfile_cap=5,
        interrupt_after=prefix_bytes, prefix_bytes=prefix_bytes,
    )
    gateway.identity_preflight_passed = True

    from telegram_courses.downloads import DownloadGatewayError

    async def consume():
        delivered = bytearray()
        with pytest.raises(DownloadGatewayError, match="CONTROLLED_INTERRUPT"):
            async for block in gateway.stream_media(0, 598, 0, reserve_chunk=grant, offset=0):
                delivered.extend(block)
        return bytes(delivered)

    delivered = asyncio.run(consume())
    receipt = gateway.preparation_receipt
    assert len(delivered) == prefix_bytes
    assert receipt["wire_requests"][4] == {
        "offset": 1_048_576, "wire_bytes_received": 262_144,
        "delivered_bytes": 123, "preparation_discarded": 262_021,
    }
    assert receipt["wire_bytes_received"] == 1_310_720
    assert receipt["bytes_delivered"] == receipt["bytes_persisted"] == prefix_bytes
    assert receipt["preparation_discarded"] == 262_021
    assert receipt["wire_bytes_received"] == (
        receipt["bytes_delivered"] + receipt["preparation_discarded"]
    )
    assert ledger.snapshot() == {
        "getfile_calls": 5, "getfilehashes_calls": 0,
        "payload_reserved": 1_310_720, "payload_received": 1_310_720,
        "uncertain_bytes": 0,
    }


def _valid_unaligned_preparation_receipt(tmp_path: Path) -> tuple[dict, dict, str]:
    budget = harness._case_budget(
        harness.COMMON_TARGET, "OPERATIONAL_ONLY", "unaligned-prepared",
    )
    downloads = tmp_path / "case" / "downloads"
    downloads.mkdir(parents=True)
    partial = downloads / "proof.part"
    contents = b"p" * int(budget["prefix_bytes"])
    partial.write_bytes(contents)
    rows = [
        {"offset": index * harness.CHUNK_BYTES, "wire_bytes_received": harness.CHUNK_BYTES,
         "delivered_bytes": harness.CHUNK_BYTES, "preparation_discarded": 0}
        for index in range(4)
    ]
    rows.append({
        "offset": 1_048_576, "wire_bytes_received": 262_144,
        "delivered_bytes": 123, "preparation_discarded": 262_021,
    })
    digest = hashlib.sha256(contents).hexdigest()
    receipt = {
        "process_id": 41001, "wire_request_offset": 0,
        "wire_bytes_received": 1_310_720, "bytes_delivered": 1_048_699,
        "bytes_persisted": 1_048_699, "preparation_discarded": 262_021,
        "wire_requests": rows, "prefix_bytes": 1_048_699, "prefix_sha256": digest,
        "sqlite_checkpoint_bytes": 1_048_699, "sqlite_state": "FAILED_RETRYABLE",
        "stop_condition": "CONTROLLED_INTERRUPT",
        "partial_path": str(partial.resolve()), "downloads_root": str(downloads.resolve()),
        "paths_safe": True,
        "wire_reconciliation": {
            "wire_bytes_received": 1_310_720, "bytes_delivered": 1_048_699,
            "preparation_discarded": 262_021, "reconciled": True,
        },
    }
    return receipt, budget, digest


def test_unaligned_preparation_receipt_validates_checkpoint_and_wire_equation(tmp_path) -> None:
    receipt, budget, digest = _valid_unaligned_preparation_receipt(tmp_path)
    assert harness._preparation_receipt_valid(
        receipt, case=budget, prefix_sha256=digest, process_id=41001,
    )


@pytest.mark.parametrize("field,value", [
    ("prefix_bytes", 1_048_576),
    ("prefix_sha256", "0" * 64),
    ("sqlite_checkpoint_bytes", 1_048_698),
    ("wire_bytes_received", 1_310_719),
    ("wire_request_offset", 1),
    ("preparation_discarded", 262_020),
    ("stop_condition", "OTHER"),
    ("paths_safe", False),
])
def test_unaligned_preparation_receipt_rejects_mismatched_evidence(tmp_path, field, value) -> None:
    receipt, budget, digest = _valid_unaligned_preparation_receipt(tmp_path)
    receipt[field] = value
    assert not harness._preparation_receipt_valid(
        receipt, case=budget, prefix_sha256=digest, process_id=41001,
    )


def _exercise_unaligned_prefix_and_overlap(
    prefix: bytes, expected_overlap: bytes, ledger_path: Path,
) -> tuple:
    class Lease:
        def received(self, _count):
            pass

        def release(self):
            pass

        def charge_uncertain(self):
            pass

    class SyntheticGateway:
        def __init__(self):
            self.continuation_calls = 0

        async def stream_media(self, *args, reserve_chunk, offset=0, **kwargs):
            if offset == 0:
                data = prefix + b"b" * (5 * harness.CHUNK_BYTES - len(prefix))
            else:
                self.continuation_calls += 1
                data = b"c" * harness.CHUNK_BYTES
            for start in range(0, len(data), harness.CHUNK_BYTES):
                block = data[start:start + harness.CHUNK_BYTES]
                lease = await reserve_chunk(len(block))
                lease.received(len(block))
                yield block

    async def grant(_size):
        return Lease()

    synthetic = SyntheticGateway()
    ledger = harness.ProofLedger(
        ledger_path, getfile_cap=8, hash_cap=0, payload_cap=8 * harness.CHUNK_BYTES,
    )
    gateway = harness.ProofGateway(
        synthetic, ledger, phase=2, phase_getfile_cap=8, phase_hash_cap=0,
        expected_prefix_sha256=hashlib.sha256(prefix).hexdigest(),
        prefix_bytes=len(prefix), expected_overlap_bytes=expected_overlap,
    )
    gateway.identity_preflight_passed = True

    async def consume():
        async for _ in gateway.stream_media(0, 598, 0, reserve_chunk=grant, offset=0):
            pass
        async for _ in gateway.stream_media(
            0, 598, 0, reserve_chunk=grant, offset=1_310_720,
        ):
            pass

    return gateway, synthetic, ledger, consume


def test_unaligned_prefix_reread_and_overlap_observation_pass(tmp_path) -> None:
    prefix = b"a" * 1_048_699
    gateway, synthetic, ledger, consume = _exercise_unaligned_prefix_and_overlap(
        prefix, prefix[1_048_576:], tmp_path / "overlap-pass.sqlite3",
    )

    asyncio.run(consume())
    assert gateway.verified_prefix_bytes == 1_048_699
    assert gateway.verified_prefix_sha256 == hashlib.sha256(prefix).hexdigest()
    assert gateway.overlap_observation == {
        "remote_request_offset": 1_048_576, "wire_bytes_received": 262_144,
        "overlap_bytes_compared": 123, "overlap_match": True,
        "reused_suffix_bytes": 262_021, "next_remote_request_offset": 1_310_720,
        "next_offset_observed": True, "status": "PASS",
    }
    assert synthetic.continuation_calls == 1
    assert ledger.snapshot()["uncertain_bytes"] == 0


def test_unaligned_overlap_mismatch_blocks_continuation_before_remote_request(tmp_path) -> None:
    prefix = b"a" * 1_048_699
    gateway, synthetic, _ledger, consume = _exercise_unaligned_prefix_and_overlap(
        prefix, b"z" * 123, tmp_path / "overlap-fail.sqlite3",
    )

    from telegram_courses.downloads import DownloadGatewayError

    with pytest.raises(DownloadGatewayError, match="OVERLAP_RECONCILIATION_REQUIRED"):
        asyncio.run(consume())
    assert gateway.verified_prefix_bytes is None
    assert gateway.prefix_reread_verified is False
    assert gateway.overlap_observation is None
    assert synthetic.continuation_calls == 0


def test_proof_gateway_phase_caps_fail_before_ledger_reservation(tmp_path) -> None:
    class OneChunkGateway:
        async def validate_media_identity(self, *args, **kwargs):
            return True

        async def get_file_hashes(self, *args, **kwargs):
            raise AssertionError("phase cap must reject before remote hash call")

        async def stream_media(self, *args, reserve_chunk, **kwargs):
            lease = await reserve_chunk(harness.CHUNK_BYTES)
            if lease is not None:
                lease.release()
            yield b"x"

    ledger = harness.ProofLedger(tmp_path / "proof-budget.sqlite3", getfile_cap=1, hash_cap=1,
                                 payload_cap=harness.CHUNK_BYTES)
    gateway = harness.ProofGateway(
        OneChunkGateway(), ledger, phase=1, phase_getfile_cap=0, phase_hash_cap=0,
    )
    gateway.identity_preflight_passed = True

    class DummyLease:
        def release(self):
            pass

    async def grant(_size):
        return DummyLease()

    stream = gateway.stream_media(0, 1, 0, reserve_chunk=grant).__aiter__()
    advance = stream.asend(None)
    with pytest.raises(RuntimeError, match="PHASE_GETFILE_BUDGET_EXHAUSTED"):
        advance.send(None)
    assert ledger.snapshot()["getfile_calls"] == 0


def test_hash_failure_after_admission_remains_in_proof_ledger(tmp_path) -> None:
    class HashFailureGateway:
        async def get_file_hashes(self, *args, **kwargs):
            raise RuntimeError("synthetic hash transport failure")

    ledger = harness.ProofLedger(
        tmp_path / "proof-budget.sqlite3", getfile_cap=1, hash_cap=1,
        payload_cap=harness.CHUNK_BYTES,
    )
    gateway = harness.ProofGateway(HashFailureGateway(), ledger, phase=2, execution_id="hash-fail")
    gateway.identity_preflight_passed = True
    application_request_counter = 0
    request = gateway.get_file_hashes(0, 1)
    with pytest.raises(RuntimeError, match="synthetic hash transport failure"):
        request.send(None)

    assert application_request_counter == 0
    assert ledger.snapshot()["getfilehashes_calls"] == 1


def test_absent_phase1_ledger_requires_independently_new_empty_root(tmp_path) -> None:
    case_root = tmp_path / "aligned"
    (case_root / "downloads").mkdir(parents=True)
    ledger = case_root / "budget.sqlite3"

    assert harness._phase1_root_is_new_and_empty(case_root, ledger)
    (case_root / "preexisting.json").write_text("{}", encoding="utf-8")
    assert not harness._phase1_root_is_new_and_empty(case_root, ledger)


@pytest.mark.parametrize(
    ("ledger_before", "phase1_after", "expected"),
    [
        (None, {"getfile_calls": 4}, False),
        ({"getfile_calls": 5}, {"getfile_calls": 4}, False),
        ({"getfile_calls": 4}, {"getfile_calls": 4}, True),
    ],
)
def test_phase2_requires_snapshot_equal_to_phase1_after(ledger_before, phase1_after, expected) -> None:
    assert harness._phase2_ledger_before_matches(
        phase=2, ledger_before=ledger_before, phase1_ledger_after=phase1_after,
    ) is expected


def test_attempt_identity_normalizes_both_supported_key_forms() -> None:
    normalized = harness._normalize_attempt_rows([
        {"id": "attempt-from-id"},
        {"attempt_id": "attempt-from-canonical-key"},
        {"id": "same-key", "attempt_id": "same-key"},
    ])
    assert [row["attempt_id"] for row in normalized] == [
        "attempt-from-id", "attempt-from-canonical-key", "same-key",
    ]


@pytest.mark.parametrize(
    "rows",
    [
        [{"status": "BLOCKED"}],
        [{"id": "duplicate"}, {"attempt_id": "duplicate"}],
        [{"id": "one", "attempt_id": "conflicting"}],
    ],
)
def test_attempt_identity_normalization_fails_closed(rows) -> None:
    assert harness._normalize_attempt_rows(rows) is None


def test_phase1_interrupts_immediately_after_exact_aligned_prefix(tmp_path) -> None:
    from telegram_courses.downloads import DownloadGatewayError

    class Lease:
        def received(self, _count):
            pass

        def release(self):
            pass

        def charge_uncertain(self):
            pass

    class ChunkingGateway:
        reservations = 0

        async def stream_media(self, *args, reserve_chunk, **kwargs):
            for _ in range(5):
                self.reservations += 1
                await reserve_chunk(harness.CHUNK_BYTES)
                yield b"x" * harness.CHUNK_BYTES

    async def grant(_size):
        return Lease()

    ledger = harness.ProofLedger(
        tmp_path / "proof-budget.sqlite3", getfile_cap=4, hash_cap=0,
        payload_cap=4 * harness.CHUNK_BYTES,
    )
    gateway = harness.ProofGateway(
        ChunkingGateway(), ledger, phase=1, phase_getfile_cap=4,
        interrupt_after=4 * harness.CHUNK_BYTES,
    )
    gateway.identity_preflight_passed = True
    stream = gateway.stream_media(0, 1, 0, reserve_chunk=grant).__aiter__()

    async def next_chunk():
        return await stream.__anext__()

    for _ in range(4):
        next_request = next_chunk()
        with pytest.raises(StopIteration) as delivered:
            next_request.send(None)
        assert delivered.value.value == b"x" * harness.CHUNK_BYTES
    fifth_request = next_chunk()
    with pytest.raises(DownloadGatewayError, match="CONTROLLED_INTERRUPT"):
        fifth_request.send(None)
    assert ledger.snapshot()["getfile_calls"] == 4
    assert gateway.gateway.reservations == 4


@pytest.mark.parametrize("prefix_case", ["mismatch-final-block", "short"])
def test_phase2_prefix_mismatch_or_short_never_emits_continuation(tmp_path, monkeypatch, prefix_case) -> None:
    from telegram_courses.downloads import DownloadGatewayError

    class Lease:
        def received(self, _count):
            pass

        def release(self):
            pass

        def charge_uncertain(self):
            pass

    expected = b"a" * harness.COMMON_PREFIX_ALIGNED
    remote = bytearray(expected)
    if prefix_case == "mismatch-final-block":
        remote[-1] = ord("b")
    else:
        remote = remote[:-harness.CHUNK_BYTES]

    class SyntheticGateway:
        def __init__(self):
            self.continuation_calls = 0
            self.continuation_bytes = 0
            self.continuation_blocks = 0

        async def stream_media(self, *args, reserve_chunk, offset=0, **kwargs):
            if offset == harness.COMMON_PREFIX_ALIGNED:
                self.continuation_calls += 1
            data = bytes(remote) if offset == 0 else b"c" * harness.CHUNK_BYTES
            for start in range(0, len(data), harness.CHUNK_BYTES):
                block = data[start:start + harness.CHUNK_BYTES]
                lease = await reserve_chunk(len(block))
                lease.received(len(block))
                if offset == harness.COMMON_PREFIX_ALIGNED:
                    self.continuation_bytes += len(block)
                    self.continuation_blocks += 1
                yield block

    async def grant(_size):
        return Lease()

    progress = tmp_path / "progress.jsonl"
    monkeypatch.setenv("S6_V2_PROGRESS_JSONL", str(progress))
    monkeypatch.setenv("S6_V2_PROGRESS_ROOT", str(tmp_path))
    monkeypatch.delenv("S6_V2_TEST_PROBE", raising=False)
    ledger = harness.ProofLedger(
        tmp_path / "prefix-ledger.sqlite3", getfile_cap=8, hash_cap=0,
        payload_cap=8 * harness.CHUNK_BYTES,
    )
    synthetic = SyntheticGateway()
    gateway = harness.ProofGateway(
        synthetic, ledger, phase=2, phase_getfile_cap=8, phase_hash_cap=0,
        expected_prefix_sha256=hashlib.sha256(expected).hexdigest(),
    )
    gateway.identity_preflight_passed = True

    snapshots = []

    async def exercise():
        prefix = gateway.stream_media(0, 598, 0, reserve_chunk=grant, offset=0)
        async for _ in prefix:
            pass
        before_gate = (
            synthetic.continuation_calls,
            synthetic.continuation_bytes,
            synthetic.continuation_blocks,
        )
        snapshots.append(before_gate)
        continuation = gateway.stream_media(
            0, 598, 0, reserve_chunk=grant, offset=harness.COMMON_PREFIX_ALIGNED,
        )
        async for _ in continuation:
            pass
        return before_gate

    with pytest.raises(DownloadGatewayError, match="PREFIX_RECONCILIATION_REQUIRED"):
        asyncio.run(exercise())
    after_denial = (
        synthetic.continuation_calls,
        synthetic.continuation_bytes,
        synthetic.continuation_blocks,
    )
    assert snapshots == [(0, 0, 0)]
    assert after_denial == (0, 0, 0)
    rows = [json.loads(line) for line in progress.read_text(encoding="utf-8").splitlines()]
    assert not any(row["stage"] in {
        "child.full_prefix_reread", "child.prefix_hash_reconciled", "child.continuation_started",
    } and row["outcome"] in {"completed", "matched", "started_transfer"} for row in rows)


def test_phase2_exact_prefix_comparison_is_recorded_only_at_continuation(tmp_path, monkeypatch) -> None:
    class Lease:
        def received(self, _count):
            pass

        def release(self):
            pass

        def charge_uncertain(self):
            pass

    prefix = b"z" * harness.COMMON_PREFIX_ALIGNED

    class SyntheticGateway:
        def __init__(self):
            self.continuation_calls = 0

        async def stream_media(self, *args, reserve_chunk, offset=0, **kwargs):
            if offset == harness.COMMON_PREFIX_ALIGNED:
                self.continuation_calls += 1
            data = prefix if offset == 0 else b"c" * harness.CHUNK_BYTES
            for start in range(0, len(data), harness.CHUNK_BYTES):
                block = data[start:start + harness.CHUNK_BYTES]
                lease = await reserve_chunk(len(block))
                lease.received(len(block))
                yield block

    async def grant(_size):
        return Lease()

    progress = tmp_path / "progress.jsonl"
    monkeypatch.setenv("S6_V2_PROGRESS_JSONL", str(progress))
    monkeypatch.setenv("S6_V2_PROGRESS_ROOT", str(tmp_path))
    ledger = harness.ProofLedger(
        tmp_path / "prefix-ledger.sqlite3", getfile_cap=8, hash_cap=0,
        payload_cap=8 * harness.CHUNK_BYTES,
    )
    synthetic = SyntheticGateway()
    gateway = harness.ProofGateway(
        synthetic, ledger, phase=2, phase_getfile_cap=8, phase_hash_cap=0,
        expected_prefix_sha256=hashlib.sha256(prefix).hexdigest(),
    )
    gateway.identity_preflight_passed = True

    async def exercise():
        async for _ in gateway.stream_media(0, 598, 0, reserve_chunk=grant, offset=0):
            pass
        assert gateway.pending_prefix_result == (
            harness.COMMON_PREFIX_ALIGNED, hashlib.sha256(prefix).hexdigest(),
        )
        assert gateway.prefix_reread_verified is False
        async for _ in gateway.stream_media(
            0, 598, 0, reserve_chunk=grant, offset=harness.COMMON_PREFIX_ALIGNED,
        ):
            break

    asyncio.run(exercise())
    rows = [json.loads(line) for line in progress.read_text(encoding="utf-8").splitlines()]
    assert gateway.prefix_reread_verified is True
    assert synthetic.continuation_calls == 1
    assert [
        row["stage"] for row in rows
        if row["outcome"] in {"completed", "matched", "started_transfer"}
        and row["stage"] != "child.transfer_progress"
    ] == [
        "child.full_prefix_reread", "child.prefix_hash_reconciled", "child.continuation_started",
    ]


def _run_synthetic_child(tmp_path, monkeypatch, *, phase: int, execution_id: str, child_body: str):
    root = tmp_path / f"s6-v2-real-proof-{execution_id}"
    case_root = root / "aligned"
    (case_root / "downloads").mkdir(parents=True)
    child_path = case_root / f"phase-{phase}.child.json"
    receipt_path = case_root / f"phase-{phase}.json"
    if phase == 2:
        progress_path = root / "execution-progress.jsonl"
        phase1_execution_id = f"{execution_id}-phase1"
        progress_path.write_text(json.dumps({
            "execution_id": phase1_execution_id, "phase": 1, "process_id": os.getpid(),
            "stage": "supervisor.sqlite_ledger_reconciled", "sequence": 1,
            "monotonic_ns": 1, "outcome": "completed", "counts": {},
        }) + "\n", encoding="utf-8")
        progress_info = progress_path.stat()
        (case_root / "phase-1.json").write_text(json.dumps({
            "phase": 1, "execution_id": phase1_execution_id,
            "progress_evidence_valid": True,
            "progress_log_identity": {"device": progress_info.st_dev, "inode": progress_info.st_ino},
        }), encoding="utf-8")
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "c" * 64)
    child_code = f"""
import json, os
from datetime import UTC, datetime
from pathlib import Path
from tools.manual_proofs.s6_v2_proof_harness import _atomic_write_json
path = Path({str(child_path)!r})
doc = {{
 'schema_version': 1, 'phase_id': {f'{execution_id}:{phase}'!r},
 'execution_id': {execution_id!r}, 'phase': {phase}, 'target_name': 'common',
 'mode': 'OPERATIONAL_ONLY', 'case': 'aligned', 'process_id': os.getpid(),
 'process_started_at_utc': datetime.now(UTC).isoformat(),
 'process_ended_at_utc': datetime.now(UTC).isoformat(), 'child_exit_code': 0,
 'status': {'PROCESS_INTERRUPTED' if phase == 1 else 'PROCESS_COMPLETED'!r},
 'stop_condition': {'CONTROLLED_INTERRUPT' if phase == 1 else None!r},
 'child_result': {{'phase': {phase}}}
}}
{child_body}
"""
    command = [getattr(sys, "_base_executable", sys.executable), "-c", child_code]
    receipt = harness._run_phase_child(
        command, evidence_root=root, case_name="aligned", phase=phase,
        target=harness.COMMON_TARGET, mode="OPERATIONAL_ONLY", execution_id=execution_id,
        child_report_path=child_path, supervisor_report_path=receipt_path,
        ledger_path=case_root / "budget.sqlite3", timeout_seconds=10,
    )
    return root, child_path, receipt_path, receipt


def test_phase_receipt_records_real_child_lifecycle_and_process_boundary(tmp_path, monkeypatch) -> None:
    _, child1, report1, phase1 = _run_synthetic_child(
        tmp_path, monkeypatch, phase=1, execution_id="exec-one",
        child_body="_atomic_write_json(path, doc, replace=False)",
    )
    time.sleep(0.05)
    _, child2, report2, phase2 = _run_synthetic_child(
        tmp_path, monkeypatch, phase=2, execution_id="exec-two",
        child_body="_atomic_write_json(path, doc, replace=False)",
    )

    assert child1.is_file() and child2.is_file()
    assert report1.is_file() and report2.is_file()
    assert phase1["process_id"] > 0 and phase2["process_id"] > 0
    assert phase1["process_id"] != phase2["process_id"]
    assert phase1["execution_id"] != phase2["execution_id"]
    assert phase1["process_exit_confirmed"] and phase2["process_exit_confirmed"]
    assert isinstance(phase1["exit_code"], int) and phase1["exit_code"] == 0
    assert phase1["status"] == "PROCESS_INTERRUPTED"
    assert phase2["status"] == "PROCESS_COMPLETED"


def test_phase1_refuses_preexisting_progress_log(tmp_path, monkeypatch) -> None:
    root = tmp_path / "fresh-proof-root"
    case_root = root / "aligned"
    (case_root / "downloads").mkdir(parents=True)
    progress_path = root / "execution-progress.jsonl"
    progress_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="PROGRESS_LOG_ALREADY_EXISTS"):
        harness._run_phase_child(
            [sys.executable, "-c", "raise SystemExit(0)"],
            evidence_root=root, case_name="aligned", phase=1,
            target=harness.COMMON_TARGET, mode="OPERATIONAL_ONLY", execution_id="preexisting-log",
            child_report_path=case_root / "phase-1.child.json",
            supervisor_report_path=case_root / "phase-1.json",
            ledger_path=case_root / "budget.sqlite3", timeout_seconds=1,
        )


def _install_synthetic_gateway_bootstrap(
    tmp_path, monkeypatch, *, fail_phase1=False, probe=False, loop_policy="selector",
    trusted_reference_path: Path | None = None, trusted_expected_bytes: int | None = None,
):
    bootstrap = tmp_path / "test-child-bootstrap"
    bootstrap.mkdir()
    event_log = tmp_path / "synthetic-gateway-events.jsonl"
    redirected_local_appdata = tmp_path / "synthetic-localappdata"
    redirected_local_appdata.mkdir(exist_ok=True)
    source = r'''
import asyncio, hashlib, json, os, socket, sqlite3, sys, threading, time, warnings
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from telegram_courses import config as config_module

def event(name, **fields):
    record = {"event": name, "pid": os.getpid(), **fields}
    with Path(os.environ["S6_V2_TEST_GATEWAY_LOG"]).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")

def probe(stage, boundary, outcome=None, error=None):
    if os.environ.get("S6_V2_TEST_PROBE") != "1":
        return
    try:
        allowed_root = Path(os.environ["S6_V2_TEST_ALLOWED_ROOT"]).resolve(strict=True)
        probe_path = Path(os.environ["S6_V2_TEST_PROBE_JSONL"])
        if not probe_path.resolve(strict=False).is_relative_to(allowed_root):
            return
        try:
            loop_name = type(asyncio.get_running_loop()).__name__
        except RuntimeError:
            loop_name = None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            policy_name = type(asyncio.get_event_loop_policy()).__name__
        record = {
            "execution_id": os.environ.get("S6_V2_TEST_PROBE_EXECUTION_ID", "bootstrap"),
            "pid": os.getpid(), "ppid": os.getppid(), "monotonic_ns": time.monotonic_ns(),
            "stage": stage, "boundary": boundary, "outcome": outcome,
            "exception_class": type(error).__name__ if error is not None else None,
            "thread_id": threading.get_ident(), "thread_name": threading.current_thread().name,
            "loop_type": loop_name, "policy_type": policy_name,
        }
        descriptor = os.open(os.environ["S6_V2_TEST_PROBE_JSONL"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8"))
        finally:
            os.close(descriptor)
    except Exception:
        return

event("synthetic_gateway_installed")
probe("B04_synthetic_stubs", "start")
if sys.platform == "win32" and os.environ.get("S6_V2_TEST_LOOP_POLICY") == "selector":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    event("test_selector_loop_policy_installed")
probe("B06_selected_loop_policy", "end", outcome=type(asyncio.get_event_loop_policy()).__name__)

def block_credential_loader():
    phase = int(sys.argv[sys.argv.index("--phase") + 1])
    event("synthetic_credentials_blocked", phase=phase)
    probe("B04_credentials_stub", "end", outcome="stub_only")
    return object()

config_module.load_telegram_credentials = block_credential_loader
event("credential_loader_stubbed")
from telegram_courses.auth import AuthState
from telegram_courses import telethon_gateway

allowed_root = Path(os.environ["S6_V2_TEST_ALLOWED_ROOT"]).resolve()
protected_root = Path(os.environ["LOCALAPPDATA"]).resolve()
original_connect = sqlite3.connect
def guarded_sqlite_connect(database, *args, **kwargs):
    raw = os.fsdecode(os.fspath(database))
    if raw not in {"", ":memory:"}:
        try:
            if raw.startswith("file:"):
                parsed = urlsplit(raw)
                if (
                    parsed.scheme != "file"
                    or parsed.netloc.casefold() not in {"", "localhost"}
                    or "#" in raw
                ):
                    raise ValueError("UNSAFE_SQLITE_FILE_URI")
                local_uri = urlunsplit(("file", "", parsed.path, "", ""))
                candidate = Path.from_uri(local_uri)
            else:
                candidate = Path(raw)
            resolved = candidate.resolve()
        except (OSError, RuntimeError, ValueError) as error:
            event("forbidden_sqlite_access", path=raw, reason=type(error).__name__)
            raise RuntimeError("TEST_BLOCKED_NONPROOF_SQLITE_ACCESS") from error
        if not resolved.is_relative_to(allowed_root):
            event("forbidden_sqlite_access", path=raw, resolved=str(resolved))
            raise RuntimeError("TEST_BLOCKED_NONPROOF_SQLITE_ACCESS")
    return original_connect(database, *args, **kwargs)
sqlite3.connect = guarded_sqlite_connect

original_socket_connect = socket.socket.connect
def guarded_socket_connect(sock, address):
    if isinstance(address, tuple) and address and address[0] in {"127.0.0.1", "::1", "localhost"}:
        return original_socket_connect(sock, address)
    event("network_attempt")
    raise RuntimeError("TEST_BLOCKED_NETWORK_ACCESS")

original_create_connection = socket.create_connection
def guarded_create_connection(address, *args, **kwargs):
    if isinstance(address, tuple) and address and address[0] in {"127.0.0.1", "::1", "localhost"}:
        return original_create_connection(address, *args, **kwargs)
    event("network_attempt")
    raise RuntimeError("TEST_BLOCKED_NETWORK_ACCESS")

socket.create_connection = guarded_create_connection
socket.socket.connect = guarded_socket_connect
original_connect_ex = socket.socket.connect_ex
def guarded_connect_ex(sock, address):
    if isinstance(address, tuple) and address and address[0] in {"127.0.0.1", "::1", "localhost"}:
        return original_connect_ex(sock, address)
    event("network_attempt")
    raise RuntimeError("TEST_BLOCKED_NETWORK_ACCESS")
socket.socket.connect_ex = guarded_connect_ex

original_path_open = Path.open
def guarded_path_open(self, *args, **kwargs):
    resolved = self.resolve(strict=False)
    if resolved.is_relative_to(protected_root):
        event("protected_path_attempt", operation="Path.open")
        probe("protected_path_attempt", "end", outcome="blocked")
        raise RuntimeError("TEST_BLOCKED_PROTECTED_PATH")
    if self.suffix == ".part" and not resolved.is_relative_to(allowed_root):
        event("forbidden_historical_part_access", path=str(resolved))
        raise RuntimeError("TEST_BLOCKED_HISTORICAL_PART_ACCESS")
    return original_path_open(self, *args, **kwargs)
Path.open = guarded_path_open

original_os_open = os.open
def guarded_os_open(path, flags, *args, **kwargs):
    try:
        resolved = Path(os.fsdecode(os.fspath(path))).resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError):
        resolved = None
    if resolved is not None and resolved.is_relative_to(protected_root):
        event("protected_path_attempt", operation="os.open")
        probe("protected_path_attempt", "end", outcome="blocked")
        raise RuntimeError("TEST_BLOCKED_PROTECTED_PATH")
    return original_os_open(path, flags, *args, **kwargs)
os.open = guarded_os_open

class SyntheticGateway:
    def __init__(self, *_args, **_kwargs):
        self.phase = int(sys.argv[sys.argv.index("--phase") + 1])
        event("gateway_created", phase=self.phase)

    async def restore(self):
        event("gateway_restored", phase=self.phase)
        return AuthState.AUTHENTICATED

    async def close(self):
        event("gateway_closed", phase=self.phase)

    async def validate_media_identity(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id, expected_bytes
    ):
        event("identity_check", phase=self.phase)
        return not (os.environ.get("S6_V2_TEST_FAIL_PHASE1") == "1" and self.phase == 1)

    async def stream_media(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id,
        expected_bytes, offset=0, reserve_chunk=None
    ):
        event("stream", phase=self.phase, offset=offset)
        for start in range(offset, expected_bytes, 256 * 1024):
            data = bytes((index % 251 for index in range(start, min(start + 256 * 1024, expected_bytes))))
            lease = await reserve_chunk(len(data))
            if lease is None:
                return
            lease.received(len(data))
            yield data

    async def get_file_hashes(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id,
        expected_bytes, offset=0
    ):
        from telegram_courses.downloads import RemoteFileHash
        digest = hashlib.sha256(bytes((index % 251 for index in range(expected_bytes)))).digest()
        event("remote_hash", phase=self.phase)
        return (RemoteFileHash(0, expected_bytes, digest),)

telethon_gateway.TelethonGateway = SyntheticGateway
if os.environ.get("S6_V2_TEST_TRUSTED_REFERENCE") == "1":
    from tools.manual_proofs import s6_v2_proof_harness as harness_module
    reference_path = Path(os.environ["S6_V2_TEST_REFERENCE_PATH"])
    harness_module.CONTROLLED_TARGET["expected_bytes"] = int(
        os.environ["S6_V2_TEST_REFERENCE_BYTES"]
    )
    harness_module.CANONICAL_TRUSTED_REFERENCE_PATH = reference_path
    def synthetic_write_reference_manifest(case_root):
        target = harness_module.CONTROLLED_TARGET
        size, digest = harness_module._hash_file(reference_path)
        manifest = {
            "schema_version": 1, "channel_id": target["channel_id"],
            "telegram_message_id": target["message_id"], "media_ordinal": 0,
            "telegram_media_id": target["media_id"], "expected_bytes": target["expected_bytes"],
            "provenance": "SYNTHETIC_TEST_FIXTURE", "reference_path": str(reference_path),
            "reference_size": size, "sha256": digest,
            "file_identity": harness_module._file_identity(reference_path),
        }
        manifest_path = Path(case_root) / "reference-manifest.v1.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest_path
    harness_module._write_reference_manifest = synthetic_write_reference_manifest
    def synthetic_reference_manifest(case_root):
        manifest_path = Path(case_root) / "reference-manifest.v1.json"
        manifest = harness_module._read_json_object(manifest_path)
        source = Path(manifest["reference_path"])
        identity = harness_module._file_identity(source)
        size, digest = harness_module._hash_file(source)
        if (identity != manifest["file_identity"] or size != manifest["expected_bytes"]
                or digest != manifest["sha256"]):
            raise RuntimeError("SYNTHETIC_REFERENCE_INVALID")
        return manifest, source
    harness_module._verify_reference_manifest = synthetic_reference_manifest
from telegram_courses import credentials as credentials_module
from telegram_courses import telethon_session as session_module

def protected_attempt(operation):
    def denied(*_args, **_kwargs):
        event("protected_path_attempt", operation=operation)
        probe("protected_path_attempt", "end", outcome="blocked")
        raise RuntimeError("TEST_BLOCKED_PROTECTED_PATH")
    return denied

for method in ("__init__", "load", "setup", "status"):
    setattr(credentials_module.CredentialVault, method, protected_attempt("CredentialVault." + method))
for class_name in ("_ProtectedSessionVault", "_ProtectedCredentialsVault"):
    vault_class = getattr(session_module, class_name)
    for method in ("__init__", "_load", "_save"):
        setattr(vault_class, method, protected_attempt(class_name + "." + method))
telethon_gateway._ProtectedSessionVault = protected_attempt("telethon_gateway._ProtectedSessionVault")
S6_TEST_BOOTSTRAP_READY = True
probe("B04_synthetic_stubs", "end", outcome="ready")
'''
    (bootstrap / "sitecustomize.py").write_text(source, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(bootstrap))
    monkeypatch.setenv("S6_V2_TEST_GATEWAY_LOG", str(event_log))
    monkeypatch.setenv("S6_V2_TEST_FAIL_PHASE1", "1" if fail_phase1 else "0")
    monkeypatch.setenv("S6_V2_TEST_ALLOWED_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv("LOCALAPPDATA", str(redirected_local_appdata.resolve()))
    monkeypatch.setenv("S6_V2_TEST_LOOP_POLICY", loop_policy)
    if probe:
        monkeypatch.setenv("S6_V2_TEST_PROBE", "1")
        monkeypatch.setenv("S6_V2_TEST_PROBE_JSONL", str(tmp_path / "s6-probe.jsonl"))
        monkeypatch.setenv("S6_V2_TEST_PROBE_STACK_PATH", str(tmp_path / "s6-probe-stacks.log"))
        monkeypatch.setenv("S6_V2_TEST_PROBE_STACK_SECONDS", "2")
        monkeypatch.setenv("S6_V2_TEST_PROBE_TIMEOUT_SECONDS", "8")
    if trusted_reference_path is not None:
        if trusted_expected_bytes is None:
            raise ValueError("trusted_expected_bytes is required with trusted_reference_path")
        monkeypatch.setenv("S6_V2_TEST_TRUSTED_REFERENCE", "1")
        monkeypatch.setenv("S6_V2_TEST_REFERENCE_PATH", str(trusted_reference_path.resolve()))
        monkeypatch.setenv("S6_V2_TEST_REFERENCE_BYTES", str(trusted_expected_bytes))
    return event_log


def _probe_sqlite_path_guard(tmp_path, monkeypatch, database: str) -> dict[str, object]:
    _install_synthetic_gateway_bootstrap(tmp_path, monkeypatch)
    probe = """
import json, sqlite3, sys, sitecustomize
calls = []
def original(database, *args, **kwargs):
    calls.append([database, list(args), kwargs])
    return "CONNECTED"
sitecustomize.original_connect = original
try:
    outcome = sqlite3.connect(sys.argv[1], "sentinel-arg", marker="sentinel-kwarg")
    result = {"outcome": outcome}
except Exception as error:
    result = {"error": str(error), "error_type": type(error).__name__}
result["calls"] = calls
print(json.dumps(result))
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe, database],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_probe_minimal_bootstrap_entrypoints_and_stall_cleanup(tmp_path, monkeypatch) -> None:
    event_log = _install_synthetic_gateway_bootstrap(
        tmp_path, monkeypatch, probe=True, loop_policy="selector"
    )
    redirected_root = Path(os.environ["LOCALAPPDATA"]).resolve()
    assert redirected_root == (tmp_path / "synthetic-localappdata").resolve()
    assert redirected_root.is_relative_to(tmp_path.resolve())
    script = tmp_path / "minimal_probe_entry.py"
    script.write_text(
        "import os, sitecustomize, sys\n"
        "sitecustomize.probe('B01_minimal_script_entry', 'start')\n"
        "sitecustomize.probe('B02_B03_minimal_imports', 'start')\n"
        "from telegram_courses import config, telethon_gateway\n"
        "sitecustomize.probe('B02_B03_minimal_imports', 'end', outcome='ready')\n"
        "from tools.manual_proofs import s6_v2_proof_harness as harness\n"
        "sitecustomize.probe('B07_minimal_harness_import', 'end', outcome='ready')\n"
        "print('MINIMAL_BOOTSTRAP_READY')\n",
        encoding="utf-8",
    )
    python = getattr(sys, "_base_executable", sys.executable)
    probe_path = tmp_path / "s6-probe.jsonl"
    for sequence, mode in enumerate(("A_direct_default", "B_direct_selector", "C_runpy_selector"), 1):
        current_policy = "default" if mode == "A_direct_default" else "selector"
        monkeypatch.setenv("S6_V2_TEST_LOOP_POLICY", current_policy)
        execution_id = f"minimal-{sequence}"
        monkeypatch.setenv("S6_V2_TEST_PROBE_EXECUTION_ID", execution_id)
        harness._probe_mark("B00_parent_spawn", "start", execution_id=execution_id)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(harness.REPOSITORY_ROOT), str(harness.REPOSITORY_ROOT / "src"), env["PYTHONPATH"]))
        if mode == "C_runpy_selector":
            command = [
                python, "-u", "-c",
                "import runpy,sys; script=sys.argv[1]; sys.argv=sys.argv[1:]; runpy.run_path(script, run_name='__main__')",
                str(script), "--probe-minimal",
            ]
        else:
            command = [python, "-u", str(script), "--probe-minimal"]
        completed = subprocess.run(
            command, cwd=harness.REPOSITORY_ROOT, env=env,
            capture_output=True, text=True, timeout=10, check=False,
        )
        harness._probe_mark(
            "B10_parent_child_termination", "end",
            outcome="exit_confirmed" if completed.returncode is not None else "exit_unconfirmed",
            execution_id=execution_id,
        )
        assert completed.returncode == 0, completed.stderr
        assert "MINIMAL_BOOTSTRAP_READY" in completed.stdout

    # Inject a stall to confirm traceback capture, a bounded kill/wait, and no orphan.
    stall_script = tmp_path / "stall_probe_entry.py"
    stall_script.write_text(
        "import time, sitecustomize\n"
        "from tools.manual_proofs import s6_v2_proof_harness as harness\n"
        "harness._probe_start_faulthandler()\n"
        "sitecustomize.probe('B08_injected_stall', 'start')\n"
        "time.sleep(20)\n",
        encoding="utf-8",
    )
    stall_id = "injected-stall"
    monkeypatch.setenv("S6_V2_TEST_PROBE_EXECUTION_ID", stall_id)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(harness.REPOSITORY_ROOT), str(harness.REPOSITORY_ROOT / "src"), env["PYTHONPATH"]))
    harness._probe_mark("B00_parent_spawn", "start", execution_id=stall_id)
    stall = subprocess.Popen(
        [python, "-u", str(stall_script)], cwd=harness.REPOSITORY_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    harness._probe_mark("B00_parent_spawn", "end", outcome="spawned", execution_id=stall_id)
    try:
        stdout, stderr = stall.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        harness._probe_mark("B10_parent_timeout", "start", outcome="terminate", execution_id=stall_id)
        stall.kill()
        stdout, stderr = stall.communicate(timeout=5)
        harness._probe_mark(
            "B10_parent_timeout", "end",
            outcome="exit_confirmed" if stall.returncode is not None else "exit_unconfirmed",
            execution_id=stall_id,
        )
    harness._probe_mark(
        "B10_parent_child_termination", "end",
        outcome="exit_confirmed" if stall.returncode is not None else "exit_unconfirmed",
        execution_id=stall_id,
    )
    assert stall.returncode is not None
    assert (tmp_path / "s6-probe-stacks.log").is_file()
    stack_text = (tmp_path / "s6-probe-stacks.log").read_text(encoding="utf-8")
    assert "stall_probe_entry.py" in stack_text, (stdout, stderr, stack_text)
    records = [json.loads(line) for line in probe_path.read_text(encoding="utf-8").splitlines()]
    minimal_records = [row for row in records if row["execution_id"].startswith("minimal-")]
    assert {row["execution_id"] for row in minimal_records} == {"minimal-1", "minimal-2", "minimal-3"}
    assert all("thread_id" in row and "policy_type" in row and "loop_type" in row for row in minimal_records)
    bootstrap_events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert not any(row["event"] == "protected_path_attempt" for row in bootstrap_events)


def test_probe_blocks_direct_credential_and_session_vault_access(tmp_path, monkeypatch) -> None:
    event_log = _install_synthetic_gateway_bootstrap(
        tmp_path, monkeypatch, probe=True, loop_policy="selector"
    )
    redirected_root = Path(os.environ["LOCALAPPDATA"]).resolve()
    assert redirected_root == (tmp_path / "synthetic-localappdata").resolve()
    assert redirected_root.is_relative_to(tmp_path.resolve())
    monkeypatch.setenv("S6_V2_TEST_PROBE_EXECUTION_ID", "protected-vault-attempts")
    script = r'''
import json, os
from pathlib import Path
from telegram_courses.credentials import CredentialVault
from telegram_courses.telethon_session import _ProtectedCredentialsVault, _ProtectedSessionVault
from telegram_courses import telethon_gateway

attempts = []
def check(name, operation):
    try:
        operation()
    except RuntimeError as error:
        assert str(error) == "TEST_BLOCKED_PROTECTED_PATH"
        attempts.append(name)
    else:
        raise AssertionError("protected access was not blocked: " + name)

check("CredentialVault.__init__", lambda: CredentialVault())
check("CredentialVault.load", lambda: CredentialVault.load(object.__new__(CredentialVault)))
check("CredentialVault.setup", lambda: CredentialVault.setup(object.__new__(CredentialVault), object()))
check("CredentialVault.status", lambda: CredentialVault.status(object.__new__(CredentialVault)))
for vault_type in (_ProtectedSessionVault, _ProtectedCredentialsVault):
    check(vault_type.__name__ + ".__init__", lambda cls=vault_type: cls())
    instance = object.__new__(vault_type)
    check(vault_type.__name__ + "._load", instance._load)
    check(vault_type.__name__ + "._save", lambda item=instance: item._save("synthetic"))
check("gateway._ProtectedSessionVault", lambda: telethon_gateway._ProtectedSessionVault())
protected_file = Path(os.environ["LOCALAPPDATA"]) / "direct-open-attempt.txt"
check("Path.open", lambda: protected_file.open("w", encoding="utf-8"))
check("os.open", lambda: os.open(protected_file, os.O_CREAT | os.O_WRONLY, 0o600))
assert not list(Path(os.environ["LOCALAPPDATA"]).rglob("*"))
print(json.dumps({"attempts": attempts, "protected_root_empty": True}))
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((
        str(harness.REPOSITORY_ROOT), str(harness.REPOSITORY_ROOT / "src"), env["PYTHONPATH"]
    ))
    result = subprocess.run(
        [getattr(sys, "_base_executable", sys.executable), "-u", "-c", script],
        cwd=harness.REPOSITORY_ROOT, env=env, capture_output=True, text=True,
        timeout=10, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "attempts": [
            "CredentialVault.__init__", "CredentialVault.load", "CredentialVault.setup",
            "CredentialVault.status",
            "_ProtectedSessionVault.__init__", "_ProtectedSessionVault._load",
            "_ProtectedSessionVault._save", "_ProtectedCredentialsVault.__init__",
            "_ProtectedCredentialsVault._load", "_ProtectedCredentialsVault._save",
            "gateway._ProtectedSessionVault", "Path.open", "os.open",
        ],
        "protected_root_empty": True,
    }
    rows = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    attempts = [row for row in rows if row["event"] == "protected_path_attempt"]
    assert len(attempts) == 13
    assert {row["operation"] for row in attempts} == {
        "CredentialVault.__init__", "CredentialVault.load", "CredentialVault.setup",
        "CredentialVault.status",
        "_ProtectedSessionVault.__init__", "_ProtectedSessionVault._load",
        "_ProtectedSessionVault._save", "_ProtectedCredentialsVault.__init__",
        "_ProtectedCredentialsVault._load", "_ProtectedCredentialsVault._save",
        "telethon_gateway._ProtectedSessionVault", "Path.open", "os.open",
    }
    assert all("path" not in row and "content" not in row for row in attempts)


@pytest.mark.parametrize("as_file_uri", [False, True])
def test_sqlite_guard_accepts_local_paths_and_preserves_connect_arguments(
    tmp_path, monkeypatch, as_file_uri,
) -> None:
    proof_root = tmp_path / "proof root with spaces"
    proof_root.mkdir()
    database_path = proof_root / "proof database.sqlite3"
    database = database_path.as_uri() + "?mode=ro&immutable=1" if as_file_uri else str(database_path)

    result = _probe_sqlite_path_guard(tmp_path, monkeypatch, database)

    assert result == {
        "outcome": "CONNECTED",
        "calls": [[database, ["sentinel-arg"], {"marker": "sentinel-kwarg"}]],
    }


@pytest.mark.parametrize(
    "database_kind",
    ["outside", "different-drive", "authority", "fragment", "traversal"],
)
def test_sqlite_guard_rejects_outside_or_unsafe_uris_without_connecting(
    tmp_path, monkeypatch, database_kind,
) -> None:
    allowed_root = tmp_path.resolve()
    if database_kind == "outside":
        database = str(tmp_path.parent / "outside.sqlite3")
    elif database_kind == "different-drive":
        other_drive = "Z" if allowed_root.drive[:1].upper() != "Z" else "Y"
        database = f"{other_drive}:\\proof-root\\outside.sqlite3"
    elif database_kind == "authority":
        database = "file://remote-host/C:/outside.sqlite3"
    elif database_kind == "fragment":
        database = allowed_root.joinpath("database.sqlite3").as_uri() + "#fragment"
    else:
        traversal_path = allowed_root / "inside" / ".." / ".." / "outside.sqlite3"
        database = "file:///" + traversal_path.as_posix()

    result = _probe_sqlite_path_guard(tmp_path, monkeypatch, database)

    assert result["error"] == "TEST_BLOCKED_NONPROOF_SQLITE_ACCESS"
    assert result["calls"] == []


def test_sqlite_guard_rejects_junction_resolving_outside_root(tmp_path, monkeypatch) -> None:
    allowed_root = tmp_path.resolve()
    outside_root = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_root.mkdir()
    junction = allowed_root / "outside-junction"
    junction_env = dict(os.environ)
    junction_env["S6_TEST_JUNCTION_PATH"] = str(junction)
    junction_env["S6_TEST_JUNCTION_TARGET"] = str(outside_root)
    created = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-Command",
            "New-Item -ItemType Junction -Path $env:S6_TEST_JUNCTION_PATH "
            "-Target $env:S6_TEST_JUNCTION_TARGET | Out-Null",
        ],
        capture_output=True,
        text=True,
        env=junction_env,
        timeout=10,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(
            "Windows directory junction creation is unavailable: "
            f"{created.stderr.strip() or created.stdout.strip()}"
        )

    result = _probe_sqlite_path_guard(
        tmp_path, monkeypatch, str(junction / "outside.sqlite3")
    )

    assert result["error"] == "TEST_BLOCKED_NONPROOF_SQLITE_ACCESS"
    assert result["calls"] == []


def test_resolve_completed_final_path_accepts_file_contained_under_downloads(tmp_path) -> None:
    case_root = tmp_path / "case"
    downloads = case_root / "downloads"
    downloads.mkdir(parents=True)
    final_path = downloads / "nested" / "proof.bin"
    final_path.parent.mkdir()
    final_path.write_bytes(b"proof")

    resolved = harness._resolve_completed_final_path(
        case_root, state="COMPLETED_V2", final_path=str(final_path.resolve())
    )

    assert resolved == final_path.resolve(strict=True)
    assert resolved.read_bytes() == b"proof"


@pytest.mark.parametrize(
    ("state", "final_path"),
    [
        ("FAILED_RETRYABLE", "C:\\case\\downloads\\proof.bin"),
        ("COMPLETED_V2", None),
        ("COMPLETED_V2", ""),
        ("COMPLETED_V2", "relative\\proof.bin"),
        ("COMPLETED_V2", "C:\\case\\downloads\\missing.bin"),
        ("COMPLETED_V2", "C:\\outside\\proof.bin"),
    ],
)
def test_resolve_completed_final_path_rejects_missing_or_uncontained_paths(
    tmp_path, state, final_path,
) -> None:
    case_root = tmp_path / "case"
    (case_root / "downloads").mkdir(parents=True)

    with pytest.raises(RuntimeError, match="COMPLETED_V2_REQUIRED"):
        harness._resolve_completed_final_path(
            case_root, state=state, final_path=final_path
        )


def test_resolve_completed_final_path_rejects_symlink_escape(tmp_path) -> None:
    case_root = tmp_path / "case"
    downloads = case_root / "downloads"
    downloads.mkdir(parents=True)
    outside_file = tmp_path / "outside.bin"
    sentinel = b"protected external sentinel\x00\xff"
    outside_file.write_bytes(sentinel)
    link = downloads / "escape.bin"
    created = False
    try:
        try:
            link.symlink_to(outside_file)
            created = True
        except OSError as error:
            pytest.skip(f"File symlink creation is unavailable: {error}")

        with pytest.raises(RuntimeError, match="COMPLETED_V2_REQUIRED"):
            harness._resolve_completed_final_path(
                case_root, state="COMPLETED_V2", final_path=str(link)
            )
        assert outside_file.read_bytes() == sentinel
    finally:
        if created and link.is_symlink() and link.resolve(strict=False) == outside_file.resolve():
            link.unlink()
        assert not link.exists() and not link.is_symlink()
        assert outside_file.read_bytes() == sentinel


def _create_interrupted_final_path_case(tmp_path, root_name: str = "aligned") -> tuple[Path, dict, Path]:
    case_root = tmp_path / root_name
    downloads = case_root / "downloads"
    downloads.mkdir(parents=True)
    database = case_root / "proof.sqlite3"
    target = harness.COMMON_TARGET
    planned = harness._expected_common_final_path(case_root, 1, target)
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE downloads(media_item_id,state,partial_path,final_path,expected_bytes,"
            "downloaded_bytes,sha256,failure_category,contract_version,evidence_version,owner_pid)"
        )
        db.execute(
            "CREATE TABLE media_items(id,channel_id,telegram_message_id,media_ordinal,"
            "telegram_media_id,kind,file_size_bytes)"
        )
        db.execute(
            "CREATE TABLE s6_v2_attempts(id,channel_id,telegram_message_id,media_ordinal,"
            "telegram_media_id,expected_bytes,selected_mode,schema_version,contract_version,"
            "evidence_version,status,remote_hash_class,evidence_class,requests,bytes_reserved,"
            "bytes_received,details_json,plan_id,invocation_id)"
        )
        db.execute(
            "CREATE TABLE s6_v2_evidence(media_item_id,attempt_id,channel_id,telegram_message_id,"
            "media_ordinal,telegram_media_id,expected_bytes,final_path,final_sha256,selected_mode,"
            "schema_version,evidence_class,remote_hash_class,contract_version,evidence_version,"
            "plan_id,invocation_id)"
        )
        db.execute(
            "INSERT INTO downloads VALUES(1,'FAILED_RETRYABLE',NULL,?,?,0,NULL,"
            "'CONTROLLED_INTERRUPT',NULL,NULL,NULL)", (planned, target["expected_bytes"]),
        )
        db.execute(
            "INSERT INTO media_items VALUES(1,?,?,?,?,?,?)",
            (target["channel_id"], target["message_id"], target["media_ordinal"],
             target["media_id"], target["media_kind"], target["expected_bytes"]),
        )
    return case_root, target, planned


def test_interrupted_planned_final_path_is_absent_and_existing_file_is_observed(tmp_path) -> None:
    case_root, _target, planned = _create_interrupted_final_path_case(tmp_path)

    observed = harness._observe_isolated_media_state(case_root)
    assert observed["available"] is True
    assert observed["final_path"] == observed["expected_planned_final_path"] == planned
    assert observed["final_path_status"] == "PLANNED_ABSENT"
    assert observed["final_exists"] is False and observed["final_bytes"] is None

    planned_file = Path(planned)
    planned_file.parent.mkdir(parents=True, exist_ok=True)
    planned_file.write_bytes(b"premature final")
    observed_existing = harness._observe_isolated_media_state(case_root)
    assert observed_existing["final_exists"] is True
    assert observed_existing["final_bytes"] == len(b"premature final")


def _seed_timeout_reconciliation_case(tmp_path, *, checkpoint_matches=True):
    case_root, target, planned = _create_interrupted_final_path_case(
        tmp_path, root_name="timeout-reconciliation"
    )
    partial = case_root / "downloads" / "proof-document.bin.part"
    payload = b"synthetic partial checkpoint"
    partial.write_bytes(payload)
    checkpoint = len(payload) if checkpoint_matches else len(payload) - 1
    with sqlite3.connect(case_root / "proof.sqlite3") as db:
        db.execute(
            "UPDATE downloads SET state='DOWNLOADING',partial_path=?,downloaded_bytes=?,"
            "failure_category=NULL,owner_pid=? WHERE media_item_id=1",
            (str(partial), checkpoint, os.getpid()),
        )
        db.execute(
            "INSERT INTO s6_v2_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("s6v2:timeout-invocation:1:test", target["channel_id"], target["message_id"],
             target["media_ordinal"], target["media_id"], target["expected_bytes"],
             "TRUSTED_REFERENCE", 1, 2, 1, "SELECTED", "REMOTE_HASH_UNAVAILABLE",
             "REFERENCE_MATCH", 3, 3 * harness.CHUNK_BYTES, checkpoint,
             json.dumps({"prior": "preserved"}), "timeout-plan", "timeout-invocation"),
        )
    return case_root, target, partial, planned


def test_confirmed_timeout_reconciliation_is_transactional_idempotent_and_never_completes(tmp_path) -> None:
    case_root, target, partial, _planned = _seed_timeout_reconciliation_case(tmp_path)
    observed = harness._observe_isolated_media_state(case_root)
    result = harness._reconcile_supervisor_timeout(
        case_root=case_root, target=target, mode="TRUSTED_REFERENCE",
        phase_id="timeout-execution:2:SUPERVISOR_TIMEOUT",
        media_state=observed, attempts_before=[], process_pid=os.getpid(),
    )
    assert result["status"] == "RECONCILED"
    assert result["completion_evidence_created"] is False
    assert result["result_claimed"] == "INCOMPLETE"
    reconciled = harness._observe_isolated_media_state(case_root)
    assert reconciled["sqlite_state"] == "FAILED_RETRYABLE"
    assert reconciled["failure_category"] == "SUPERVISOR_TIMEOUT"
    assert reconciled["partial_bytes"] == reconciled["sqlite_checkpoint_bytes"] == len(partial.read_bytes())
    assert reconciled["evidence_rows"] == 0 and reconciled["evidence"] is None
    assert reconciled["final_exists"] is False
    assert reconciled["attempts"][0]["status"] == "FAILED_RETRYABLE"
    assert reconciled["attempts"][0]["details"]["prior"] == "preserved"
    replay = harness._reconcile_supervisor_timeout(
        case_root=case_root, target=target, mode="TRUSTED_REFERENCE",
        phase_id="timeout-execution:2:SUPERVISOR_TIMEOUT",
        media_state=reconciled, attempts_before=[], process_pid=os.getpid(),
    )
    assert replay["status"] == "RECONCILED" and replay["idempotent_replay"] is True


def test_inconsistent_timeout_checkpoint_preserves_downloading_state(tmp_path) -> None:
    case_root, target, _partial, _planned = _seed_timeout_reconciliation_case(
        tmp_path, checkpoint_matches=False
    )
    observed = harness._observe_isolated_media_state(case_root)
    result = harness._reconcile_supervisor_timeout(
        case_root=case_root, target=target, mode="TRUSTED_REFERENCE",
        phase_id="bad-timeout:2:SUPERVISOR_TIMEOUT",
        media_state=observed, attempts_before=[], process_pid=os.getpid(),
    )
    assert result["status"] == "BLOCKED"
    unchanged = harness._observe_isolated_media_state(case_root)
    assert unchanged["sqlite_state"] == "DOWNLOADING"
    assert unchanged["attempts"][0]["status"] == "SELECTED"


def test_timeout_reconciliation_rejects_different_download_owner_pid(tmp_path) -> None:
    case_root, target, _partial, _planned = _seed_timeout_reconciliation_case(tmp_path)
    with sqlite3.connect(case_root / "proof.sqlite3") as db:
        db.execute("UPDATE downloads SET owner_pid=? WHERE media_item_id=1", (os.getpid() + 1,))
    observed = harness._observe_isolated_media_state(case_root)
    result = harness._reconcile_supervisor_timeout(
        case_root=case_root, target=target, mode="TRUSTED_REFERENCE",
        phase_id="wrong-owner:2:SUPERVISOR_TIMEOUT",
        media_state=observed, attempts_before=[], process_pid=os.getpid(),
    )
    assert result["status"] == "BLOCKED"
    assert harness._observe_isolated_media_state(case_root)["sqlite_state"] == "DOWNLOADING"


def test_cooperative_child_timeout_failure_state_is_verified_without_rewriting(tmp_path) -> None:
    case_root, target, _partial, _planned = _seed_timeout_reconciliation_case(tmp_path)
    with sqlite3.connect(case_root / "proof.sqlite3") as db:
        db.execute(
            "UPDATE downloads SET state='FAILED_RETRYABLE',failure_category='SUPERVISOR_TIMEOUT',"
            "owner_pid=NULL "
            "WHERE media_item_id=1"
        )
        db.execute(
            "UPDATE s6_v2_attempts SET status='FAILED_RETRYABLE',details_json=? WHERE id=?",
            (json.dumps({"failure_category": "SUPERVISOR_TIMEOUT"}), "s6v2:timeout-invocation:1:test"),
        )
    observed = harness._observe_isolated_media_state(case_root)
    result = harness._reconcile_supervisor_timeout(
        case_root=case_root, target=target, mode="TRUSTED_REFERENCE",
        phase_id="cooperative-timeout:2:SUPERVISOR_TIMEOUT",
        media_state=observed, attempts_before=[], process_pid=os.getpid(),
        child_report_pid=os.getpid(),
    )
    assert result["status"] == "RECONCILED"
    assert result["already_normalized_by_child"] is True
    after = harness._observe_isolated_media_state(case_root)
    assert after["sqlite_state"] == "FAILED_RETRYABLE"
    assert after["failure_category"] == "SUPERVISOR_TIMEOUT"
    assert after["evidence_rows"] == 0 and after["final_exists"] is False


def test_child_normalized_timeout_without_valid_pid_receipt_is_blocked(tmp_path) -> None:
    case_root, target, _partial, _planned = _seed_timeout_reconciliation_case(tmp_path)
    with sqlite3.connect(case_root / "proof.sqlite3") as db:
        db.execute(
            "UPDATE downloads SET state='FAILED_RETRYABLE',failure_category='SUPERVISOR_TIMEOUT',"
            "owner_pid=NULL WHERE media_item_id=1"
        )
        db.execute(
            "UPDATE s6_v2_attempts SET status='FAILED_RETRYABLE',details_json=? WHERE id=?",
            (json.dumps({"failure_category": "SUPERVISOR_TIMEOUT"}), "s6v2:timeout-invocation:1:test"),
        )
    observed = harness._observe_isolated_media_state(case_root)
    result = harness._reconcile_supervisor_timeout(
        case_root=case_root, target=target, mode="TRUSTED_REFERENCE",
        phase_id="no-child-report:2:SUPERVISOR_TIMEOUT",
        media_state=observed, attempts_before=[], process_pid=os.getpid(),
        child_report_pid=None,
    )
    assert result["status"] == "BLOCKED"


def test_child_cancel_marker_must_be_isolated_and_regular_file(tmp_path, monkeypatch) -> None:
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    case_root = evidence_root / "aligned"
    case_root.mkdir()
    marker = case_root / "supervisor.cancel"
    monkeypatch.setenv("S6_V2_PROGRESS_ROOT", str(evidence_root))
    monkeypatch.setenv("S6_V2_CANCEL_MARKER", str(marker))
    assert not harness._child_cancel_requested()
    marker.write_text("cancel", encoding="utf-8")
    assert harness._child_cancel_requested()
    monkeypatch.setenv("S6_V2_CANCEL_MARKER", str(tmp_path / "outside.cancel"))
    (tmp_path / "outside.cancel").write_text("cancel", encoding="utf-8")
    assert not harness._child_cancel_requested()


def test_supervisor_cancels_stalled_synthetic_getfile_and_fails_closed(tmp_path, monkeypatch) -> None:
    """Exercise the native child boundary after GetFile stops following a persisted chunk."""
    evidence_root = tmp_path / "stalled-getfile-proof"
    case_root = evidence_root / "aligned"
    (case_root / "downloads").mkdir(parents=True)
    monkeypatch.setattr(harness, "PROOF_CANCEL_GRACE_SECONDS", 1)
    monkeypatch.setattr(harness, "_deadline_policy", lambda _mode: (3, 6))
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "d" * 64)
    execution_id = "synthetic-stalled-getfile"
    child_report = case_root / "phase-1.child.json"
    supervisor_report = case_root / "phase-1.json"
    progress_path = evidence_root / "execution-progress.jsonl"
    child_code = f'''
import json, os, time
from pathlib import Path
path = Path({str(progress_path)!r})
def emit(sequence, stage, counts):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({{
            "execution_id": {execution_id!r}, "phase": 1,
            "process_id": os.getpid(), "sequence": sequence,
            "monotonic_ns": time.monotonic_ns(), "stage": stage,
            "outcome": "completed", "counts": counts,
        }}) + "\\n")
emit(1, "child.ready", {{}})
emit(2, "child.transfer_progress", {{
    "stream_confirmed_bytes": {harness.CHUNK_BYTES},
    "persisted_bytes": {harness.CHUNK_BYTES},
    "received_bytes": {harness.CHUNK_BYTES},
}})
# Simulate a GetFile await that remains stalled after one persisted chunk.
time.sleep(30)
'''
    receipt = harness._run_phase_child(
        [getattr(sys, "_base_executable", sys.executable), "-c", child_code],
        evidence_root=evidence_root, case_name="aligned", phase=1,
        target=harness.COMMON_TARGET, mode="OPERATIONAL_ONLY",
        execution_id=execution_id, child_report_path=child_report,
        supervisor_report_path=supervisor_report,
        ledger_path=case_root / "missing-ledger.sqlite3", timeout_seconds=2,
    )

    assert receipt["timeout_reason"] == "PHASE_PROCESS_TIMEOUT"
    assert receipt["stop_condition"] == "SUPERVISOR_TIMEOUT"
    assert receipt["process_exit_confirmed"] is True
    assert receipt["child_report_valid"] is False
    assert receipt["timeout_reconciliation"]["status"] == "BLOCKED"
    assert receipt["status"] != "PASS"
    assert not child_report.exists()
    assert (case_root / "supervisor.cancel").is_file()
    events = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines()]
    transfer = next(event for event in events if event["stage"] == "child.transfer_progress")
    assert transfer["counts"]["persisted_bytes"] == harness.CHUNK_BYTES


def test_interrupted_planned_final_path_rejects_non_symlink_escape(tmp_path) -> None:
    case_root, _target, _planned = _create_interrupted_final_path_case(tmp_path)
    outside = tmp_path / "outside-final.bin"
    outside.write_bytes(b"outside")
    database = case_root / "proof.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("UPDATE downloads SET final_path=? WHERE media_item_id=1", (str(outside),))
    observed_escape = harness._observe_isolated_media_state(case_root)
    assert observed_escape["final_path_status"] == "OUTSIDE_OR_UNSAFE"


@pytest.mark.parametrize("guard", ["observe", "resolve"])
@pytest.mark.parametrize("component", ["leaf", "ancestor"])
def test_path_guards_reject_deterministic_symlink_leaf_and_ancestor_before_read_or_hash(
    tmp_path, monkeypatch, guard, component,
) -> None:
    case_root, _target, planned = _create_interrupted_final_path_case(
        tmp_path, root_name=f"{guard}-{component}"
    )
    planned_file = Path(planned)
    planned_file.parent.mkdir(parents=True, exist_ok=True)
    if guard == "resolve":
        planned_file.write_bytes(b"contained final")

    symlink_target = planned_file if component == "leaf" else planned_file.parent

    def path_key(path: Path) -> str:
        return os.path.normcase(os.path.abspath(os.fspath(path)))

    original_is_symlink = Path.is_symlink

    def is_symlink_with_target(self: Path) -> bool:
        if path_key(self) == path_key(symlink_target):
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", is_symlink_with_target)

    unsafe_reads: list[str] = []
    original_open = Path.open

    def guarded_open(self: Path, *args, **kwargs):
        if path_key(self) == path_key(planned_file):
            unsafe_reads.append(path_key(self))
            raise AssertionError("guard attempted to read unsafe final path")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    unsafe_hashes: list[str] = []

    def guarded_hash(path: Path) -> tuple[int, str]:
        if path_key(path) == path_key(planned_file):
            unsafe_hashes.append(path_key(path))
            raise AssertionError("guard attempted to hash unsafe final path")
        raise AssertionError("unexpected hash while checking unsafe final path")

    monkeypatch.setattr(harness, "_hash_file", guarded_hash)

    if guard == "observe":
        observed = harness._observe_isolated_media_state(case_root)
        assert observed["final_path_status"] == "OUTSIDE_OR_UNSAFE"
    else:
        with pytest.raises(RuntimeError, match="COMPLETED_V2_REQUIRED"):
            harness._resolve_completed_final_path(
                case_root, state="COMPLETED_V2", final_path=str(planned_file)
            )

    assert unsafe_reads == []
    assert unsafe_hashes == []


def test_interrupted_planned_final_path_rejects_real_symlink_when_creation_is_available(
    tmp_path,
) -> None:
    case_root, _target, planned = _create_interrupted_final_path_case(tmp_path)
    planned_file = Path(planned)
    planned_file.parent.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside-final.bin"
    sentinel = b"protected interrupted sentinel\x00\xfe"
    outside.write_bytes(sentinel)
    created = False
    try:
        try:
            planned_file.symlink_to(outside)
            created = True
        except OSError as error:
            pytest.skip(f"File symlink creation is unavailable: {error}")
        observed_symlink = harness._observe_isolated_media_state(case_root)
        assert observed_symlink["final_path_status"] == "OUTSIDE_OR_UNSAFE"
        assert outside.read_bytes() == sentinel
    finally:
        if created and planned_file.is_symlink() and planned_file.resolve(strict=False) == outside.resolve():
            planned_file.unlink()
        assert not planned_file.exists() and not planned_file.is_symlink()
        assert outside.read_bytes() == sentinel


@pytest.mark.parametrize("counter_state", ["null", "missing"])
@pytest.mark.parametrize("ledger_available", [True, False])
def test_aggregate_persists_incomplete_report_when_child_counters_unavailable(
    tmp_path, monkeypatch, counter_state, ledger_available,
) -> None:
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "a" * 64)
    monkeypatch.setattr(harness, "_execute_token_valid", lambda: True)
    monkeypatch.setattr(harness, "_verify_ratified_contract", lambda: None)
    if counter_state == "null":
        failed_receipt = {
            "status": "PROCESS_FAILED",
            "requests_used": {
                "GetFile": None,
                "GetFileHashes": None,
                "identity_GetMessages": None,
                "GetMe": None,
            },
        }
    else:
        failed_receipt = {"status": "PROCESS_FAILED"}
    monkeypatch.setattr(harness, "_run_phase_child", lambda *_args, **_kwargs: failed_receipt)
    ledger = {
        "getfile_calls": 3,
        "getfilehashes_calls": 4,
        "payload_reserved": 0,
        "payload_received": 0,
        "uncertain_bytes": 0,
    }
    monkeypatch.setattr(
        harness,
        "_read_budget_snapshot",
        lambda _path: ledger if ledger_available else None,
    )

    exit_code, evidence_root = harness.execute(
        "common", "OPERATIONAL_ONLY", tmp_path, case_name="aligned"
    )

    aggregate = json.loads((evidence_root / "s6-v2-proof-report.json").read_text(encoding="utf-8"))
    counts = aggregate["budget"]["request_counts"]
    assert exit_code == 5
    assert aggregate["result"] == "INCOMPLETE"
    assert aggregate["stop_condition"] == "aligned_PHASE_1_PROCESS_FAILED"
    assert aggregate["budget"]["within_caps"] is False
    assert counts["within_caps"] is False
    assert counts["identity_GetMessages"] is None
    assert counts["GetMe"] is None
    assert counts["known_remote_calls"] is None
    assert counts["GetFile"] == (3 if ledger_available else None)
    assert counts["GetFileHashes"] == (4 if ledger_available else None)
    assert not (evidence_root / ".execution.lock").exists()


def test_aggregate_sums_complete_child_counters(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "b" * 64)
    monkeypatch.setattr(harness, "_execute_token_valid", lambda: True)
    monkeypatch.setattr(harness, "_verify_ratified_contract", lambda: None)
    receipts = [
        {
            "process_id": 101,
            "execution_id": "phase-one-execution",
            "process_started_at_utc": "2026-01-01T00:00:00+00:00",
            "process_ended_at_utc": "2026-01-01T00:00:01+00:00",
            "transfer_attempts": 1,
            "requests_used": {
                "GetFile": 2,
                "GetFileHashes": 3,
                "identity_GetMessages": 1,
                "GetMe": 0,
            },
        },
        {
            "process_id": 202,
            "execution_id": "phase-two-execution",
            "process_started_at_utc": "2026-01-01T00:00:02+00:00",
            "process_ended_at_utc": "2026-01-01T00:00:03+00:00",
            "transfer_attempts": 1,
            "requests_used": {
                "GetFile": 4,
                "GetFileHashes": 5,
                "identity_GetMessages": 2,
                "GetMe": 1,
            },
        },
    ]
    monkeypatch.setattr(harness, "_phase_receipt_is_acceptable", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        harness, "_run_phase_child", lambda *_args, **_kwargs: receipts.pop(0)
    )
    ledger = {
        "getfile_calls": 6,
        "getfilehashes_calls": 8,
        "payload_reserved": 0,
        "payload_received": 0,
        "uncertain_bytes": 0,
    }
    monkeypatch.setattr(harness, "_read_budget_snapshot", lambda _path: ledger)

    exit_code, evidence_root = harness.execute(
        "common", "OPERATIONAL_ONLY", tmp_path, case_name="aligned"
    )

    aggregate = json.loads((evidence_root / "s6-v2-proof-report.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert aggregate["result"] == "PASS"
    assert aggregate["budget"]["within_caps"] is True
    assert aggregate["budget"]["request_counts"] == {
        "GetFile": 6,
        "GetFileHashes": 8,
        "identity_GetMessages": 3,
        "GetMe": 1,
        "known_remote_calls": None,
        "counted_remote_calls_lower_bound": 26,
        "known_remote_calls_reason": "No total is available; lower bound omits per-stream metadata refetch calls",
        "telethon_connect_rpc_count": None,
        "total_api_requests": None,
        "total_api_requests_reason": "Telethon.connect performs internal sender RPCs outside this harness counter",
        "within_caps": True,
    }
    assert not (evidence_root / ".execution.lock").exists()


@pytest.mark.parametrize("case_name", ["aligned", "unaligned-prepared"])
def test_two_process_handoff_real_harness_lifecycle_offline(
    tmp_path_factory, monkeypatch, case_name: str,
) -> None:
    proof_root = tmp_path_factory.mktemp("s6")
    event_log = _install_synthetic_gateway_bootstrap(
        proof_root, monkeypatch, probe=True, loop_policy="default"
    )
    monkeypatch.setenv("S6_V2_TEST_PROBE_TIMEOUT_SECONDS", "60")
    monkeypatch.setattr(harness, "PROOF_AGGREGATE_DEADLINE_SECONDS", 90)
    monkeypatch.setattr(harness, "PROOF_CANCEL_GRACE_SECONDS", 2)
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "f" * 64)
    run_phase_child = harness._run_phase_child
    timeout_observations: dict[float, dict[str, float]] = {}
    phase1_handoff_checks: dict[str, bool] = {}
    original_timeout_reason = harness._supervisor_timeout_reason

    def observe_supervisor_timeout(**kwargs):
        observation = {
            "phase_timeout": kwargs["phase_timeout"],
            "spawned": kwargs["spawned"],
            "aggregate_started": kwargs["aggregate_started"],
        }
        prior = timeout_observations.setdefault(kwargs["spawned"], observation)
        assert prior == observation
        return original_timeout_reason(**kwargs)

    monkeypatch.setattr(harness, "_supervisor_timeout_reason", observe_supervisor_timeout)

    def run_with_test_timeout(command, **kwargs):
        # These bounded synthetic deadlines leave a two-second shutdown grace.
        receipt = run_phase_child(command, timeout_seconds=90, **kwargs)
        if kwargs.get("phase") == 1:
            # The phase-1 .part checkpoint is expected to be renamed after
            # phase 2 completes, so reconcile it at the handoff boundary.
            phase1_reconcile = {
                "phase": 1, "target": harness.COMMON_TARGET, "mode": "OPERATIONAL_ONLY",
                "media_state": receipt["media_state_observed"],
                "child_result": receipt["child_result"],
                "ledger_before": receipt["ledger_before"],
                "ledger_after": receipt["ledger_after"],
                "ledger_delta": receipt["ledger_delta"],
                "phase_attempt_ids": receipt["phase_attempt_ids"],
                "ledger_before_is_new_root_baseline": receipt["ledger_before_is_new_root_baseline"],
                "child_exit_code": receipt["child_exit_code"],
                "supervisor_exit_code": receipt["exit_code"],
            }
            phase1_handoff_checks["checkpoint_reconciles"] = harness._phase_state_reconciles(
                **phase1_reconcile
            )
            tampered_capacity = json.loads(json.dumps(receipt["media_state_observed"]))
            assert tampered_capacity.get("attempts"), {
                "status": receipt.get("status"),
                "stop_condition": receipt.get("stop_condition"),
                "child_output_stop": receipt.get("child_output_stop"),
                "child_report_error": receipt.get("child_report_error"),
                "phase_state_reconciled": receipt.get("phase_state_reconciled"),
                "media_state_keys": sorted(tampered_capacity),
            }
            tampered_capacity["attempts"][0]["bytes_reserved"] += harness.CHUNK_BYTES
            phase1_handoff_checks["tampered_capacity_rejected"] = not harness._phase_state_reconciles(
                **(phase1_reconcile | {"media_state": tampered_capacity})
            )
            other_blocked_reason = json.loads(json.dumps(receipt["media_state_observed"]))
            other_blocked_reason["attempts"][0]["details"]["reason"] = "OTHER_BLOCKED_REASON"
            phase1_handoff_checks["other_blocked_reason_rejected"] = not harness._phase_state_reconciles(
                **(phase1_reconcile | {"media_state": other_blocked_reason})
            )
            wrong_queue_key = json.loads(json.dumps(receipt["child_result"]))
            wrong_queue_key["queue_result"][0][0][1] += 1
            phase1_handoff_checks["wrong_queue_key_rejected"] = not harness._phase_state_reconciles(
                **(phase1_reconcile | {"child_result": wrong_queue_key})
            )
            final_exists_at_interrupt = json.loads(json.dumps(receipt["media_state_observed"]))
            final_exists_at_interrupt["final_exists"] = True
            final_exists_at_interrupt["final_bytes"] = 1
            phase1_handoff_checks["early_final_rejected"] = not harness._phase_state_reconciles(
                **(phase1_reconcile | {"media_state": final_exists_at_interrupt})
            )
            escaping_final_path = json.loads(json.dumps(receipt["media_state_observed"]))
            escaping_final_path["final_path"] = str(proof_root / "outside.bin")
            escaping_final_path["final_path_status"] = "OUTSIDE_OR_UNSAFE"
            phase1_handoff_checks["escaping_final_path_rejected"] = not harness._phase_state_reconciles(
                **(phase1_reconcile | {"media_state": escaping_final_path})
            )
            assert all(phase1_handoff_checks.values()), phase1_handoff_checks
        return receipt

    monkeypatch.setattr(harness, "_run_phase_child", run_with_test_timeout)
    exit_code, evidence_root = harness.execute(
        "common", "OPERATIONAL_ONLY", proof_root, case_name=case_name
    )

    case_root = evidence_root / case_name
    assert exit_code == 0
    phase1_path = case_root / "phase-1.json"
    assert phase1_path.is_file(), "phase 1 receipt is required before reading phase 2"
    first = json.loads(phase1_path.read_text(encoding="utf-8"))
    assert harness._phase_receipt_is_acceptable(first, 1, require_live_checkpoint=False), first
    aggregate_path = evidence_root / "s6-v2-proof-report.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    phase2_path = case_root / "phase-2.json"
    assert phase2_path.is_file(), "phase 2 receipt is required after admissible phase 1"
    second = json.loads(phase2_path.read_text(encoding="utf-8"))
    receipts = [first, second]
    children = [
        json.loads((case_root / f"phase-{phase}.child.json").read_text(encoding="utf-8"))
        for phase in (1, 2)
    ]

    assert aggregate["result"] == "PASS"
    assert aggregate["process_boundary"]["two_process_proof"] == "PASS"
    assert len(aggregate["phases"]) == 2
    first, second = receipts
    progress_rows = [
        json.loads(line)
        for line in (evidence_root / "execution-progress.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert first["progress_evidence_valid"] is True
    assert second["progress_evidence_valid"] is True
    assert first["progress_log_identity"] == second["progress_log_identity"]
    assert "child.full_prefix_reread" not in first["progress_observed_stages"]
    assert "child.continuation_started" not in first["progress_observed_stages"]
    assert "child.full_prefix_reread" in second["progress_observed_stages"]
    assert "child.continuation_started" in second["progress_observed_stages"]
    assert "child.planned_interruption" in first["progress_observed_stages"]
    assert "child.planned_interruption" not in second["progress_observed_stages"]
    assert {row["execution_id"] for row in progress_rows} >= {
        first["execution_id"], second["execution_id"],
    }
    for receipt in receipts:
        receipt_rows = [row for row in progress_rows if row["execution_id"] == receipt["execution_id"]]
        assert receipt_rows
        sqlite_created_outcome = "created" if receipt["phase"] == 1 else "validated"
        assert any(
            row["stage"] == "child.sqlite_created" and row["outcome"] == sqlite_created_outcome
            for row in receipt_rows
        )
        assert any(
            row["stage"] == "supervisor.sqlite_ledger_reconciled" and row["outcome"] == "completed"
            for row in receipt_rows
        )
    assert first["process_id"] > 0 and second["process_id"] > 0
    assert first["process_id"] != second["process_id"]
    assert first["execution_id"] != second["execution_id"]
    assert first["exit_code"] == first["child_exit_code"] == children[0]["child_exit_code"] == 0
    assert second["exit_code"] == second["child_exit_code"] == children[1]["child_exit_code"] == 0
    assert first["status"] == "PROCESS_INTERRUPTED"
    assert first["stop_condition"] == "CONTROLLED_INTERRUPT"
    assert first["process_ended_at_utc"] <= second["process_started_at_utc"]
    for receipt in receipts:
        assert receipt["progress_evidence_valid"] is True
        assert "supervisor.sqlite_ledger_reconciled" in receipt["progress_observed_stages"]
    profile = harness._case_budget(harness.COMMON_TARGET, "OPERATIONAL_ONLY", case_name)
    prefix_bytes = int(profile["prefix_bytes"])
    wire_offset = int(profile["wire_offset"])
    transfer_offset = int(profile["transfer_offset"])
    overlap_bytes = int(profile["overlap_bytes"])
    assert first["child_result"]["prefix_bytes"] == prefix_bytes
    assert first["child_result"]["prefix_sha256"] == hashlib.sha256(
        bytes((index % 251 for index in range(prefix_bytes)))
    ).hexdigest()
    preparation = first["child_result"]["preparation_receipt"]
    assert preparation["sqlite_checkpoint_bytes"] == prefix_bytes
    assert preparation["bytes_persisted"] == prefix_bytes
    assert preparation["wire_bytes_received"] == (
        preparation["bytes_delivered"] + preparation["preparation_discarded"]
    )
    assert first["ledger_delta"]["payload_received"] == preparation["wire_bytes_received"]
    assert first["ledger_delta"]["uncertain_bytes"] == 0
    if overlap_bytes:
        assert preparation["wire_requests"][4] == {
            "offset": wire_offset, "wire_bytes_received": harness.CHUNK_BYTES,
            "delivered_bytes": overlap_bytes,
            "preparation_discarded": harness.CHUNK_BYTES - overlap_bytes,
        }
        assert preparation["preparation_discarded"] == harness.CHUNK_BYTES - overlap_bytes
        assert second["full_prefix_reread_bytes"] == prefix_bytes
        assert second["overlap_verification"] == {
            "remote_request_offset": wire_offset,
            "wire_bytes_received": harness.CHUNK_BYTES,
            "overlap_bytes_compared": overlap_bytes,
            "overlap_match": True,
            "reused_suffix_bytes": harness.CHUNK_BYTES - overlap_bytes,
            "next_remote_request_offset": transfer_offset,
            "next_offset_observed": True,
            "status": "PASS",
        }
    else:
        assert preparation["preparation_discarded"] == 0
        assert second["full_prefix_reread_bytes"] == prefix_bytes
        assert second["overlap_verification"] == "NOT_APPLICABLE_ALIGNED"
    assert first["checkpoint_confirmed"] is True
    assert second["final_file_confirmed"] is True
    assert (first["timeout_requested_seconds"], second["timeout_requested_seconds"]) == (90, 90)
    assert len(timeout_observations) == 2
    observed_deadlines = list(timeout_observations.values())
    assert observed_deadlines[0]["aggregate_started"] == observed_deadlines[1]["aggregate_started"]
    for receipt, observation in zip(receipts, observed_deadlines, strict=True):
        actual_applied = min(
            60,
                max(
                    0.0,
                    90 - (observation["spawned"] - observation["aggregate_started"])
                    - harness.PROOF_CANCEL_GRACE_SECONDS,
                ),
        )
        assert observation["phase_timeout"] == actual_applied
        assert receipt["timeout_effective_seconds"] == observation["phase_timeout"]
        assert type(receipt["timeout_effective_seconds"]) is float
        assert math.isfinite(receipt["timeout_effective_seconds"])
        assert 0 < receipt["timeout_effective_seconds"] <= 60
        mismatched_receipt = dict(receipt)
        mismatched_receipt["timeout_effective_seconds"] += 0.25
        assert not (
            mismatched_receipt["timeout_effective_seconds"] == observation["phase_timeout"]
        )
    assert first["timeout_operational_default_seconds"] == 3600
    assert second["timeout_operational_default_seconds"] == 3600
    assert first["bytes_reserved"] == harness._ceil_chunks(prefix_bytes) * harness.CHUNK_BYTES
    assert first["media_state_observed"]["attempts"][0]["bytes_reserved"] == 45 * harness.CHUNK_BYTES
    first_attempt = first["media_state_observed"]["attempts"][0]
    second_attempt_id = second["phase_attempt_ids"][0]
    second_phase_attempts = [
        row for row in second["media_state_observed"]["attempts"]
        if row["attempt_id"] in second["phase_attempt_ids"]
    ]
    assert first["phase_attempt_ids"] == [first_attempt["attempt_id"]]
    assert second["prior_phase_attempt_ids"] == [first_attempt["attempt_id"]]
    assert first_attempt["attempt_id"] in {
        row["attempt_id"] for row in second["media_state_observed"]["attempts"]
    }
    assert second["phase_attempt_ids"] == [second_attempt_id]
    assert sum(row["requests"] for row in second_phase_attempts) == (
        second["requests_used"]["GetFile"]
        + second["requests_used"]["GetFileHashes"]
        + second["requests_used"]["identity_GetMessages"]
    )
    assert second["requests_used"]["identity_GetMessages"] == 2
    assert sum(row["bytes_received"] for row in second_phase_attempts) == second["ledger_delta"]["payload_received"]
    assert second["bytes_received"] == (
        second["ledger_after"]["payload_received"] - second["ledger_before"]["payload_received"]
    ) == harness.COMMON_TARGET["expected_bytes"]
    assert second["ledger_after"]["payload_received"] == (
        first["ledger_after"]["payload_received"] + second["bytes_received"]
    )
    assert first_attempt["bytes_received"] == preparation["bytes_delivered"]
    assert first["media_state_observed"]["final_path"] == first["media_state_observed"]["expected_planned_final_path"]
    assert first["media_state_observed"]["final_path"] is not None
    assert first["media_state_observed"]["final_exists"] is False
    assert first["media_state_observed"]["final_bytes"] is None
    assert second["ledger_before"] == first["ledger_after"]
    assert isinstance(children[0]["child_result"]["queue_result"], list)

    assert phase1_handoff_checks == {
        "checkpoint_reconciles": True,
        "tampered_capacity_rejected": True,
        "other_blocked_reason_rejected": True,
        "wrong_queue_key_rejected": True,
        "early_final_rejected": True,
        "escaping_final_path_rejected": True,
    }

    phase2_reconcile = {
        "phase": 2, "target": harness.COMMON_TARGET, "mode": "OPERATIONAL_ONLY",
        "media_state": second["media_state_observed"], "child_result": second["child_result"],
        "ledger_before": second["ledger_before"], "ledger_after": second["ledger_after"],
        "ledger_delta": second["ledger_delta"], "phase_attempt_ids": second["phase_attempt_ids"],
        "expected_ledger_before": first["ledger_after"],
        "child_exit_code": second["child_exit_code"], "supervisor_exit_code": second["exit_code"],
    }
    assert harness._phase_state_reconciles(**phase2_reconcile)
    retry_state = json.loads(json.dumps(second["media_state_observed"]))
    final_attempt = retry_state["attempts"][-1]
    earlier_attempt = json.loads(json.dumps(final_attempt))
    earlier_attempt.update({
        "attempt_id": "synthetic-earlier-retry",
        "invocation_id": "synthetic-earlier-invocation",
        "status": "FAILED_RETRYABLE",
        "requests": 1,
        "bytes_received": harness.CHUNK_BYTES,
    })
    final_attempt["requests"] = max(0, final_attempt["requests"] - 1)
    final_attempt["bytes_received"] -= harness.CHUNK_BYTES
    retry_state["attempts"].append(earlier_attempt)
    retry_reconcile = phase2_reconcile | {
        "media_state": retry_state,
        "phase_attempt_ids": ["synthetic-earlier-retry", *second["phase_attempt_ids"]],
    }
    assert harness._phase_state_reconciles(**retry_reconcile)
    divergent_before = dict(second["ledger_before"])
    divergent_before["getfile_calls"] += 1
    assert not harness._phase_state_reconciles(**(phase2_reconcile | {"ledger_before": divergent_before}))

    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert sum(event["event"] == "synthetic_gateway_installed" for event in events) == 2
    assert sum(event["event"] == "synthetic_credentials_blocked" for event in events) == 2
    assert sum(event["event"] == "gateway_created" for event in events) == 2
    assert not any(event["event"] in {
        "network_attempt", "forbidden_sqlite_access", "forbidden_historical_part_access"
    } for event in events)

    probe_rows = [
        json.loads(line) for line in (proof_root / "s6-probe.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    for receipt in receipts:
        child_rows = [row for row in probe_rows if row["pid"] == receipt["process_id"]]
        loop_created = [
            row for row in child_rows
            if row["stage"] == "B06_loop_setup" and row["boundary"] == "end"
        ]
        stage_complete = [
            row for row in child_rows
            if row["stage"] == "B06_loop_and_first_coroutine" and row["boundary"] == "end"
        ]
        assert len(loop_created) == 1 and loop_created[0]["outcome"] == "loop_created"
        assert len(stage_complete) == 1 and stage_complete[0]["outcome"] == "ok"
        assert stage_complete[0]["loop_type"] == loop_created[0]["loop_type"]
        assert "Selector" not in loop_created[0]["policy_type"]
    phase2_offsets = [event["offset"] for event in events if event["event"] == "stream" and event["phase"] == 2]
    assert 0 in phase2_offsets
    assert transfer_offset in phase2_offsets

    expected_bytes = harness.COMMON_TARGET["expected_bytes"]
    expected_payload = bytes(index % 251 for index in range(expected_bytes))
    final_path = Path(second["media_state_observed"]["final_path"]) if "final_path" in second["media_state_observed"] else None
    final_file = next((case_root / "downloads").rglob("*.bin"))
    assert final_path is None or final_path == final_file
    assert final_file.read_bytes() == expected_payload
    with sqlite3.connect(case_root / "proof.sqlite3") as db:
        state, downloaded = db.execute("SELECT state,downloaded_bytes FROM downloads").fetchone()
        evidence_count = db.execute("SELECT count(*) FROM s6_v2_evidence").fetchone()[0]
    assert state == "COMPLETED_V2" and downloaded == expected_bytes and evidence_count == 1

    ledger = harness._read_budget_snapshot(case_root / "budget.sqlite3")
    assert ledger == aggregate["budget"]["ledger"]
    assert ledger["getfile_calls"] <= aggregate["budget"]["limits"]["aggregate_getfile_cap"]
    assert ledger["payload_reserved"] <= aggregate["budget"]["limits"]["aggregate_payload_reservation_cap"]
    assert ledger["uncertain_bytes"] == 0
    assert aggregate["budget"]["within_caps"] is True
    assert aggregate["reference_integrity_post_verification"]["status"] == "NOT_APPLICABLE"
    assert all(item["v2_restored_false_after_call"] is True for item in aggregate["phases"])
    assert aggregate["v1_active"] is True and aggregate["v2_effective"] is False
    assert aggregate["real_telegram_calls"] == "RECORDED_PER_PHASE"
    assert aggregate["original_sqlite_access"] == "NO"
    assert aggregate["historical_part_access"] == "NO"
    assert aggregate_path.is_file()


def test_trusted_reference_two_process_synthetic_e2e(tmp_path_factory, monkeypatch) -> None:
    prefix_bytes = harness.CONTROLLED_PREFIX_OPTIONS["8MiB"]
    expected_bytes = prefix_bytes + harness.CHUNK_BYTES
    proof_root = tmp_path_factory.mktemp("s6")
    synthetic_target = dict(harness.CONTROLLED_TARGET, expected_bytes=expected_bytes)
    anticipated_evidence_root = proof_root / "s6v2" / f"s6t-{'0' * 32}"
    from telegram_courses.download_repository import DownloadCandidate
    from telegram_courses.downloads import destination_paths

    anticipated_final, anticipated_partial = destination_paths(
        anticipated_evidence_root / "aligned" / "downloads",
        DownloadCandidate(
            media_item_id=1,
            channel_id=synthetic_target["channel_id"],
            telegram_message_id=synthetic_target["message_id"],
            media_ordinal=synthetic_target["media_ordinal"],
            telegram_media_id=synthetic_target["media_id"],
            expected_bytes=expected_bytes,
            original_filename="proof-document.bin",
            lineage=(("lesson", "S6 V2 proof item"),),
        ),
    )
    assert len(str(anticipated_final)) <= 240
    assert len(str(anticipated_partial)) <= 240
    reference = proof_root / "synthetic-reference.bin"
    with reference.open("wb") as stream:
        for start in range(0, expected_bytes, harness.CHUNK_BYTES):
            block = bytes((index % 251 for index in range(start, min(start + harness.CHUNK_BYTES, expected_bytes))))
            stream.write(block)

    monkeypatch.setattr(harness, "CONTROLLED_TARGET", synthetic_target)
    monkeypatch.setattr(harness, "CANONICAL_TRUSTED_REFERENCE_PATH", reference)
    event_log = _install_synthetic_gateway_bootstrap(
        proof_root, monkeypatch, probe=True, loop_policy="default",
        trusted_reference_path=reference, trusted_expected_bytes=expected_bytes,
    )
    monkeypatch.setenv("S6_V2_TEST_PROBE_TIMEOUT_SECONDS", "60")
    monkeypatch.setattr(harness, "PROOF_AGGREGATE_DEADLINE_SECONDS", 60)
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "9" * 64)

    def write_synthetic_reference_manifest(case_root):
        size, digest = harness._hash_file(reference)
        manifest = {
            "schema_version": 1, "channel_id": synthetic_target["channel_id"],
            "telegram_message_id": synthetic_target["message_id"], "media_ordinal": 0,
            "telegram_media_id": synthetic_target["media_id"], "expected_bytes": expected_bytes,
            "provenance": "SYNTHETIC_TEST_FIXTURE", "reference_path": str(reference),
            "reference_size": size, "sha256": digest,
            "file_identity": harness._file_identity(reference),
        }
        path = case_root / "reference-manifest.v1.json"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return path

    def verify_synthetic_reference(case_root):
        manifest = json.loads((case_root / "reference-manifest.v1.json").read_text(encoding="utf-8"))
        source = Path(manifest["reference_path"])
        if (harness._file_identity(source) != manifest["file_identity"]
                or harness._hash_file(source) != (expected_bytes, manifest["sha256"])):
            raise RuntimeError("SYNTHETIC_REFERENCE_INVALID")
        return manifest, source

    monkeypatch.setattr(harness, "_write_reference_manifest", write_synthetic_reference_manifest)
    monkeypatch.setattr(harness, "_verify_reference_manifest", verify_synthetic_reference)
    real_run_phase_child = harness._run_phase_child
    module_child_runner = (
        "import argparse, sys, sitecustomize; from pathlib import Path; "
        "from tools.manual_proofs import s6_v2_proof_harness as h; "
        "p=argparse.ArgumentParser(); p.add_argument('--child', action='store_true'); "
        "p.add_argument('--target'); p.add_argument('--mode'); p.add_argument('--case'); "
        "p.add_argument('--phase', type=int); p.add_argument('--evidence-root', type=Path); "
        "p.add_argument('--phase-report', type=Path); p.add_argument('--phase1-pid', type=int); "
        "p.add_argument('--execution-id'); p.add_argument('--authorization-file', type=Path); "
        "p.add_argument('--prefix-profile'); p.add_argument('--recovered-phase1', action='store_true'); "
        "raise SystemExit(h._child_main(p.parse_args()))"
    )

    def run_trusted_child(command, **kwargs):
        evidence_root_arg = command[command.index("--evidence-root") + 1]
        evidence_root_for_child = Path(evidence_root_arg).resolve()
        monkeypatch.setenv("S6_V2_TEST_ALLOWED_ROOT", str(evidence_root_for_child))
        monkeypatch.setenv(
            "S6_V2_TEST_PROBE_JSONL", str(evidence_root_for_child / "s6-probe.jsonl")
        )
        wrapped = [command[0], "-c", module_child_runner, *command[2:]]
        return real_run_phase_child(wrapped, **kwargs)

    monkeypatch.setattr(harness, "_run_phase_child", run_trusted_child)
    import tempfile

    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(proof_root))
    exit_code, evidence_root = harness.execute(
        "controlled", "TRUSTED_REFERENCE", proof_root, case_name="aligned", prefix_profile="8MiB",
    )
    phase1_path = evidence_root / "aligned" / "phase-1.json"
    assert phase1_path.is_file(), "phase 1 receipt is required before reading phase 2"
    first_receipt = json.loads(phase1_path.read_text(encoding="utf-8"))
    assert harness._phase_receipt_is_acceptable(
        first_receipt, 1, require_live_checkpoint=False
    ), first_receipt
    report = json.loads((evidence_root / "s6-v2-proof-report.json").read_text(encoding="utf-8"))
    phase2_path = evidence_root / "aligned" / "phase-2.json"
    assert phase2_path.is_file(), "phase 2 receipt is required after admissible phase 1"
    second_receipt = json.loads(phase2_path.read_text(encoding="utf-8"))
    receipts = [first_receipt, second_receipt]
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    probe_path = evidence_root / "s6-probe.jsonl"
    assert probe_path.is_file(), "the trusted child probe must publish evidence inside its allowed root"
    probe_rows = [json.loads(line) for line in probe_path.read_text(encoding="utf-8").splitlines()]
    assert probe_rows, "an empty probe file does not prove that the probe activated"
    planner_rows = [row for row in probe_rows if row.get("stage") == "planner"]
    assert {row.get("boundary") for row in planner_rows} >= {"begin", "end"}
    assert {row.get("pid") for row in planner_rows} == {
        first_receipt["process_id"], second_receipt["process_id"],
    }

    assert exit_code == 0, report
    assert report["result"] == "TRUSTED_REFERENCE_MATCH"
    assert report["process_boundary"]["two_process_proof"] == "PASS"
    assert report["phases"][1]["child_result"]["queue_result"][0][1] == "COMPLETED_V2"
    assert receipts[1]["trusted_reference_result"]["status"] == "TRUSTED_REFERENCE_MATCH"
    assert report["supervisor_reference_comparison"]["status"] == "TRUSTED_REFERENCE_MATCH"
    assert [receipt["phase"] for receipt in receipts] == [1, 2]
    assert receipts[0]["process_id"] != receipts[1]["process_id"]
    assert sum(event["event"] == "gateway_created" for event in events) == 2
    assert not any(event["event"] == "network_attempt" for event in events)


@pytest.mark.parametrize("entry_mode", ["A_direct_default", "B_direct_selector", "C_runpy_selector"])
def test_probe_full_synthetic_handoff_entrypoint_variants(tmp_path, monkeypatch, entry_mode) -> None:
    loop_policy = "default" if entry_mode == "A_direct_default" else "selector"
    event_log = _install_synthetic_gateway_bootstrap(
        tmp_path, monkeypatch, probe=True, loop_policy=loop_policy
    )
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "c" * 64)
    run_phase_child = harness._run_phase_child
    bootstrap_runner = (
        "import runpy, sitecustomize, sys; "
        "assert getattr(sitecustomize, 'S6_TEST_BOOTSTRAP_READY', False); "
        "script = sys.argv[1]; sys.argv = sys.argv[1:]; "
        "runpy.run_path(script, run_name='__main__')"
    )

    def run_probe_command(command, **kwargs):
        if entry_mode == "C_runpy_selector":
            wrapped = [command[0], "-u", "-c", bootstrap_runner, *command[1:]]
        else:
            wrapped = [command[0], "-u", *command[1:]]
        return run_phase_child(wrapped, **kwargs)

    monkeypatch.setattr(harness, "_run_phase_child", run_probe_command)
    exit_code, evidence_root = harness.execute(
        "common", "OPERATIONAL_ONLY", tmp_path, case_name="aligned"
    )
    aggregate_path = evidence_root / "s6-v2-proof-report.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    probe_path = tmp_path / "s6-probe.jsonl"
    rows = [json.loads(line) for line in probe_path.read_text(encoding="utf-8").splitlines()]
    event_rows = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    stages = {row["stage"] for row in rows}

    assert exit_code in {0, 5}
    assert aggregate["result"] in {"PASS", "INCOMPLETE"}
    assert aggregate_path.is_file()
    assert {"B00_parent_spawn", "B10_parent_child_termination"}.issubset(stages)
    assert all(row.get("execution_id") and row.get("pid") and row.get("ppid") for row in rows)
    assert all("thread_id" in row and "policy_type" in row and "loop_type" in row for row in rows)
    assert not any(row["event"] in {
        "network_attempt", "forbidden_sqlite_access", "forbidden_historical_part_access",
        "protected_path_attempt",
    } for row in event_rows)
    assert all(phase["process_exit_confirmed"] is True for phase in aggregate["phases"])
    stack_path = tmp_path / "s6-probe-stacks.log"
    assert stack_path.is_file()
    print(f"PROBE_MODE={entry_mode} EXIT={exit_code} RESULT={aggregate['result']} STAGES={sorted(stages)}")


def test_negative_phase1_evidence_prevents_phase2_child_start(tmp_path, monkeypatch) -> None:
    event_log = _install_synthetic_gateway_bootstrap(tmp_path, monkeypatch, fail_phase1=True)
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "1" * 64)
    run_phase_child = harness._run_phase_child
    bootstrap_runner = (
        "import runpy, sitecustomize, sys; "
        "assert getattr(sitecustomize, 'S6_TEST_BOOTSTRAP_READY', False); "
        "script = sys.argv[1]; sys.argv = sys.argv[1:]; "
        "runpy.run_path(script, run_name='__main__')"
    )

    def run_with_test_timeout(command, **kwargs):
        wrapped_command = [command[0], "-c", bootstrap_runner, *command[1:]]
        return run_phase_child(wrapped_command, timeout_seconds=15, **kwargs)

    monkeypatch.setattr(harness, "_run_phase_child", run_with_test_timeout)
    exit_code, evidence_root = harness.execute(
        "common", "OPERATIONAL_ONLY", tmp_path, case_name="aligned"
    )

    aggregate = json.loads((evidence_root / "s6-v2-proof-report.json").read_text(encoding="utf-8"))
    case_root = evidence_root / "aligned"
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert exit_code != 0
    assert aggregate["result"] == "INCOMPLETE"
    assert len(aggregate["phases"]) == 1
    assert (case_root / "phase-1.child.json").is_file()
    assert (case_root / "phase-1.json").is_file()
    assert not (case_root / "phase-2.child.json").exists()
    assert not (case_root / "phase-2.json").exists()
    assert {event["phase"] for event in events if event["event"] == "gateway_created"} == {1}
    assert sum(event["event"] == "synthetic_credentials_blocked" for event in events) == 1
    assert not any(event["event"] in {
        "network_attempt", "forbidden_sqlite_access", "forbidden_historical_part_access"
    } for event in events)


def test_native_python_subprocess_runs_asyncio_cycle_offline() -> None:
    python = getattr(sys, "_base_executable", sys.executable)
    result = subprocess.run(
        [
            python,
            "-c",
            "import asyncio; assert asyncio.run(asyncio.sleep(0)) is None",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_child_failure_before_stage_result_emits_failed_phase_json(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("S6_V2_PROOF_AUTH", "d" * 64)
    monkeypatch.setattr(harness, "_verify_ratified_contract", lambda: None)
    monkeypatch.setattr(harness, "_validate_child_authorization", lambda _args: {})

    def fail_async(coro):
        coro.close()
        raise RuntimeError("F06_SECRET_SENTINEL")

    monkeypatch.setattr(harness.asyncio, "run", fail_async)
    path = tmp_path / "phase-1.child.json"
    args = SimpleNamespace(
        target="common", mode="OPERATIONAL_ONLY", case="aligned", phase=1,
        evidence_root=tmp_path, phase_report=path, authorization_file=tmp_path / "authorization.json",
        phase1_pid=0, recovered_phase1=False, execution_id="failure-exec",
    )

    assert harness._child_main(args) == 5
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["status"] == "PROCESS_FAILED"
    assert report["child_exit_code"] == 5
    assert report["child_error_type"] == "RuntimeError"
    assert report["child_error"] == "RuntimeError"
    assert report["child_error_stage"] is None
    assert "F06_SECRET_SENTINEL" not in path.read_text(encoding="utf-8")
    assert report["process_id"] == os.getpid()
    output = capsys.readouterr().out
    assert "STOP=RuntimeError" in output
    assert "F06_SECRET_SENTINEL" not in output


def test_child_domain_failure_emits_only_allowlisted_code_and_stage(tmp_path, monkeypatch) -> None:
    from telegram_courses.downloads import DownloadError

    monkeypatch.setenv("S6_V2_PROOF_AUTH", "e" * 64)
    monkeypatch.setattr(harness, "_verify_ratified_contract", lambda: None)
    monkeypatch.setattr(harness, "_validate_child_authorization", lambda _args: {})

    def fail_async(coro):
        coro.close()
        error = DownloadError("REMOTE_HASH_UNAVAILABLE", failure_phase="REMOTE_HASH")
        error.args = ("credential=synthetic-secret",)
        raise error

    monkeypatch.setattr(harness.asyncio, "run", fail_async)
    path = tmp_path / "phase-1.child.json"
    args = SimpleNamespace(
        target="common", mode="OPERATIONAL_ONLY", case="aligned", phase=1,
        evidence_root=tmp_path, phase_report=path, authorization_file=tmp_path / "authorization.json",
        phase1_pid=0, recovered_phase1=False, execution_id="domain-failure-exec",
    )

    assert harness._child_main(args) == 5
    report_text = path.read_text(encoding="utf-8")
    report = json.loads(report_text)
    assert report["status"] == "PROCESS_FAILED"
    assert report["stop_condition"] == "REMOTE_HASH_UNAVAILABLE"
    assert report["child_error_type"] == "REMOTE_HASH_UNAVAILABLE"
    assert report["child_error_stage"] == "REMOTE_HASH"
    assert "synthetic-secret" not in report_text


def test_download_error_category_with_secret_is_reduced_to_other_without_leaking() -> None:
    from telegram_courses.downloads import DownloadError

    error = DownloadError("REMOTE_HASH_UNAVAILABLE credential=synthetic-secret")
    assert harness._safe_exception_class(error) == "OTHER"
    assert harness._safe_stop_condition(error) == "OTHER"
    assert "synthetic-secret" not in harness._safe_stop_condition(error)


@pytest.mark.parametrize(
    ("child_body", "return_code", "expected_status"),
    [
        ("path.write_text('{partial', encoding='utf-8')", 0, "EVIDENCE_INCOMPLETE"),
        ("os._exit(9)", 9, "EVIDENCE_INCOMPLETE"),
    ],
)
def test_corrupt_or_missing_child_json_fails_closed(
    tmp_path, monkeypatch, child_body, return_code, expected_status,
) -> None:
    _, child_path, report_path, receipt = _run_synthetic_child(
        tmp_path, monkeypatch, phase=2, execution_id=f"bad-{return_code}-{len(child_body)}",
        child_body=child_body,
    )
    assert receipt["status"] == expected_status
    assert receipt["process_exit_confirmed"] is True
    assert receipt["exit_code"] == return_code
    assert receipt["child_report_valid"] is False
    assert receipt["child_exit_code"] is None
    assert receipt["child_result"] is None
    assert report_path.is_file()
    if return_code == 0:
        assert receipt["child_report_error"] is not None
    else:
        assert not child_path.exists()


def test_child_declared_and_observed_exit_mismatch_is_explicit(tmp_path, monkeypatch) -> None:
    _, child_path, report_path, receipt = _run_synthetic_child(
        tmp_path,
        monkeypatch,
        phase=1,
        execution_id="declared-observed-mismatch",
        child_body="_atomic_write_json(path, doc, replace=False)\nos._exit(9)",
    )

    assert child_path.is_file()
    assert report_path.is_file()
    assert receipt["child_exit_code"] == 0
    assert receipt["exit_code"] == 9
    assert receipt["status"] == "EVIDENCE_INCOMPLETE"
    assert receipt["stop_condition"] == "CHILD_EXIT_CODE_MISMATCH:declared=0:observed=9"
    assert receipt["child_report_valid"] is False
    assert receipt["child_result"] is None


def test_child_report_pid_mismatch_keeps_declared_exit_null_and_fails_closed(
    tmp_path, monkeypatch,
) -> None:
    _, child_path, report_path, receipt = _run_synthetic_child(
        tmp_path,
        monkeypatch,
        phase=1,
        execution_id="child-pid-mismatch",
        child_body="doc['process_id'] = os.getpid() + 1\n"
                   "_atomic_write_json(path, doc, replace=False)",
    )

    assert child_path.is_file()
    assert report_path.is_file()
    assert receipt["status"] == "EVIDENCE_INCOMPLETE"
    assert receipt["child_report_valid"] is False
    assert receipt["child_exit_code"] is None
    assert receipt["child_result"] is None


def test_atomic_json_replace_failure_preserves_last_complete_report(tmp_path, monkeypatch) -> None:
    path = tmp_path / "phase.json"
    original = {"status": "EVIDENCE_INCOMPLETE", "version": 1}
    harness._atomic_write_json(path, original, replace=False)
    monkeypatch.setattr(harness.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace failed")))

    with pytest.raises(OSError, match="replace failed"):
        harness._atomic_write_json(path, {"status": "PROCESS_COMPLETED", "version": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == original
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_json_normalizes_nested_tuples_and_rejects_lossy_values(tmp_path) -> None:
    path = tmp_path / "normalized.json"
    harness._atomic_write_json(path, {"outcomes": ((1, "FAILED"), (2, "OK"))}, replace=False)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "outcomes": [[1, "FAILED"], [2, "OK"]]
    }

    with pytest.raises(TypeError, match="JSON_OBJECT_KEYS_MUST_BE_STRINGS"):
        harness._atomic_write_json(tmp_path / "bad-key.json", {1: "lossy"})
    with pytest.raises(TypeError, match="UNSUPPORTED_JSON_VALUE:bytes"):
        harness._atomic_write_json(tmp_path / "bad-value.json", {"value": b"lossy"})
    with pytest.raises(ValueError):
        harness._atomic_write_json(tmp_path / "non-finite.json", {"value": float("nan")})


def test_missing_phase_evidence_never_reconciles_to_two_process_pass() -> None:
    incomplete = {
        "phase_id": "execution:1", "execution_id": "execution", "phase": 1,
        "process_id": 123, "process_exit_confirmed": True, "exit_code": 0,
        "child_report_valid": False, "child_result": None,
        "status": "EVIDENCE_INCOMPLETE", "stop_condition": "CHILD_REPORT_MISSING",
    }
    assert not harness._phase_receipt_is_acceptable(incomplete, 1)


def _acceptable_phase1_receipt_for_timeout_validation() -> dict:
    target = harness.COMMON_TARGET
    digest = "a" * 64
    return {
        "phase_id": "timeout-test:1", "execution_id": "timeout-test", "phase": 1,
        "process_id": 123, "process_exit_confirmed": True,
        "process_handle_pid_matches_child_pid": True, "exit_code": 0,
        "child_report_valid": True, "child_exit_code": 0, "child_result": {},
        "process_started_at_utc": "2026-10-18T00:00:00+00:00",
        "process_ended_at_utc": "2026-10-18T00:00:01+00:00",
        "phase_state_reconciled": True, "progress_evidence_valid": True,
        "target_name": "common", "mode": "OPERATIONAL_ONLY", "case": "aligned",
        "identity": {
            "channel_id": target["channel_id"], "message_id": target["message_id"],
            "media_ordinal": target["media_ordinal"], "media_id": target["media_id"],
            "media_kind": target["media_kind"], "expected_bytes": target["expected_bytes"],
        },
        "transfer_attempts": 1,
        "requests_used": {
            "GetFile": 1, "GetFileHashes": 0, "identity_GetMessages": 1,
            "GetMe": 0, "restore_calls": 1,
        },
        "ledger_delta": {
            "getfile_calls": 1, "getfilehashes_calls": 0,
            "payload_reserved": harness.CHUNK_BYTES,
            "payload_received": harness.CHUNK_BYTES, "uncertain_bytes": 0,
        },
        "bytes_received": harness.CHUNK_BYTES,
        "uncertain_bytes": 0,
        "preparation_receipt": {
            "partial_path": None, "wire_bytes_received": harness.CHUNK_BYTES,
        },
        "timeout_requested_seconds": 3600,
        "timeout_effective_seconds": 900,
        "timeout_operational_default_seconds": 3600,
        "ledger_before_is_new_root_baseline": True,
        "ledger_before_matches_phase1_after": True,
        "ledger_after": {}, "status": "PROCESS_INTERRUPTED",
        "stop_condition": "CONTROLLED_INTERRUPT", "checkpoint_confirmed": True,
        "sqlite_state": "FAILED_RETRYABLE", "prefix_bytes": harness.COMMON_PREFIX_ALIGNED,
        "prefix_sha256": digest, "media_state_observed": {"partial_sha256": digest},
        "remote_identity_preflight": "PASS",
    }


@pytest.mark.parametrize(
    "effective",
    [899.9471857000001, 900.25, 900.0, 900, 1.0, 1],
)
def test_phase_receipt_accepts_positive_finite_effective_timeout(effective, monkeypatch) -> None:
    monkeypatch.setattr(harness, "_preparation_receipt_valid", lambda *_args, **_kwargs: True)
    receipt = _acceptable_phase1_receipt_for_timeout_validation()
    receipt["timeout_effective_seconds"] = effective

    assert harness._phase_receipt_is_acceptable(receipt, 1)


@pytest.mark.parametrize(
    "effective",
    [
        True, False, math.nan, math.inf, -math.inf, 0, 0.0, -1, -0.25,
        3600.01, None, "900", [], {},
        pytest.param(10**10000, id="huge-positive-int"),
    ],
)
def test_phase_receipt_rejects_invalid_effective_timeout(effective, monkeypatch) -> None:
    monkeypatch.setattr(harness, "_preparation_receipt_valid", lambda *_args, **_kwargs: True)
    receipt = _acceptable_phase1_receipt_for_timeout_validation()
    receipt["timeout_effective_seconds"] = effective

    assert not harness._phase_receipt_is_acceptable(receipt, 1)


@pytest.mark.parametrize("requested", [True, 3600.0, 0, -1, None])
def test_phase_receipt_requires_positive_integer_requested_timeout(requested, monkeypatch) -> None:
    monkeypatch.setattr(harness, "_preparation_receipt_valid", lambda *_args, **_kwargs: True)
    receipt = _acceptable_phase1_receipt_for_timeout_validation()
    receipt["timeout_requested_seconds"] = requested

    assert not harness._phase_receipt_is_acceptable(receipt, 1)


@pytest.mark.parametrize("value", [1, None])
def test_phase_receipt_rejects_uncertain_or_unreconciled_bytes(value, monkeypatch) -> None:
    monkeypatch.setattr(harness, "_preparation_receipt_valid", lambda *_args, **_kwargs: True)
    receipt = _acceptable_phase1_receipt_for_timeout_validation()
    receipt["uncertain_bytes"] = value

    assert not harness._phase_receipt_is_acceptable(receipt, 1)


def test_phase_receipt_rejects_budget_exceeding_case_cap(monkeypatch) -> None:
    monkeypatch.setattr(harness, "_preparation_receipt_valid", lambda *_args, **_kwargs: True)
    receipt = _acceptable_phase1_receipt_for_timeout_validation()
    receipt["requests_used"]["GetFile"] = 95
    receipt["ledger_delta"]["getfile_calls"] = 95
    receipt["ledger_delta"]["payload_reserved"] = 95 * harness.CHUNK_BYTES
    receipt["ledger_delta"]["payload_received"] = 95 * harness.CHUNK_BYTES
    receipt["bytes_received"] = 95 * harness.CHUNK_BYTES
    receipt["preparation_receipt"]["wire_bytes_received"] = 95 * harness.CHUNK_BYTES

    assert not harness._phase_receipt_is_acceptable(receipt, 1)


def _build_recoverable_checkpoint(tmp_path, monkeypatch, *, process_id=41001):
    repo = tmp_path / "repo"
    reports = repo / "docs" / "reports"
    root = reports / "s6-v2-real-proof-recovery-contract"
    case_root = root / "aligned"
    downloads = case_root / "downloads"
    downloads.mkdir(parents=True)
    monkeypatch.setattr(harness, "REPOSITORY_ROOT", repo)
    target = harness.target_for("common")
    budget = harness.proof_budget(
        target["expected_bytes"], harness.COMMON_PREFIX_ALIGNED, "OPERATIONAL_ONLY"
    )
    case_profile = harness._case_budget(target, "OPERATIONAL_ONLY", "aligned")
    token = "e" * 64
    (root / "authorization.json").write_text(json.dumps({
        "evidence_root": str(root.resolve()), "target": "common",
        "mode": "OPERATIONAL_ONLY", "contract_sha256": harness.V2_CONTRACT_SHA256,
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "allowed_cases": ["aligned"], "allowed_phases": [1, 2],
        "case_profile": {
            "prefix_bytes": case_profile["prefix_bytes"],
            "prefix_profile": case_profile.get("prefix_profile"),
            "wire_offset": case_profile["wire_offset"],
            "transfer_offset": case_profile["transfer_offset"],
            "overlap_bytes": case_profile["overlap_bytes"],
            "effective_caps": harness._case_effective_limits(
                "aligned", "OPERATIONAL_ONLY", "common", case_profile,
            ),
            "approved_maxima": dict(
                harness.TRUSTED_REFERENCE_APPROVED_MAXIMA
                if case_profile.get("prefix_profile") else harness.APPROVED_LIMITS
            ),
        },
        "recovered_phase1": False,
    }), encoding="utf-8")
    monkeypatch.setenv("S6_V2_PROOF_AUTH", token)
    partial = downloads / "proof.bin.part"
    partial.write_bytes(b"p" * harness.COMMON_PREFIX_ALIGNED)
    digest = hashlib.sha256(partial.read_bytes()).hexdigest()
    wire_requests = [
        {"offset": index * harness.CHUNK_BYTES, "wire_bytes_received": harness.CHUNK_BYTES,
         "delivered_bytes": harness.CHUNK_BYTES, "preparation_discarded": 0}
        for index in range(4)
    ]
    preparation_receipt = {
        "process_id": process_id, "wire_request_offset": 0,
        "wire_bytes_received": harness.COMMON_PREFIX_ALIGNED,
        "bytes_delivered": harness.COMMON_PREFIX_ALIGNED,
        "bytes_persisted": harness.COMMON_PREFIX_ALIGNED, "preparation_discarded": 0,
        "wire_requests": wire_requests, "prefix_bytes": harness.COMMON_PREFIX_ALIGNED,
        "prefix_sha256": digest, "sqlite_checkpoint_bytes": harness.COMMON_PREFIX_ALIGNED,
        "sqlite_state": "FAILED_RETRYABLE", "stop_condition": "CONTROLLED_INTERRUPT",
        "partial_path": str(partial.resolve()), "downloads_root": str(downloads.resolve()),
        "paths_safe": True,
        "wire_reconciliation": {
            "wire_bytes_received": harness.COMMON_PREFIX_ALIGNED,
            "bytes_delivered": harness.COMMON_PREFIX_ALIGNED,
            "preparation_discarded": 0, "reconciled": True,
        },
    }
    phase1 = {
        "schema_version": 1, "phase_id": "phase-one:1", "execution_id": "phase-one",
        "phase": 1, "target_name": "common", "mode": "OPERATIONAL_ONLY", "case": "aligned",
        "process_id": process_id, "status": "PROCESS_INTERRUPTED",
        "stop_condition": "CONTROLLED_INTERRUPT", "exit_code": 0, "child_exit_code": 0,
        "process_exit_confirmed": True, "child_report_valid": True,
        "transfer_attempts": harness.PHASE1_TRANSFER_ATTEMPT_CAP,
        "checkpoint_confirmed": True, "prefix_bytes": harness.COMMON_PREFIX_ALIGNED,
        "prefix_sha256": digest, "sqlite_state": "FAILED_RETRYABLE",
        "sqlite_checkpoint_bytes": harness.COMMON_PREFIX_ALIGNED,
        "preparation_receipt": preparation_receipt,
    }
    (case_root / "phase-1.json").write_text(json.dumps(phase1), encoding="utf-8")
    with sqlite3.connect(case_root / "proof.sqlite3") as db:
        db.execute("CREATE TABLE downloads(media_item_id,state,partial_path,expected_bytes,downloaded_bytes,failure_category,owner_pid)")
        db.execute("CREATE TABLE s6_v2_attempts(channel_id,telegram_message_id,media_ordinal,telegram_media_id,expected_bytes,selected_mode,status,remote_hash_class,details_json,requests,bytes_received)")
        db.execute("INSERT INTO downloads VALUES(1,'FAILED_RETRYABLE',?,?,?,'CONTROLLED_INTERRUPT',NULL)", (
            str(partial), target["expected_bytes"], harness.COMMON_PREFIX_ALIGNED,
        ))
        db.execute("INSERT INTO s6_v2_attempts VALUES(?,?,?,?,?,?,'BLOCKED','REMOTE_HASH_UNAVAILABLE','{}',?,?)", (
            target["channel_id"], target["message_id"], target["media_ordinal"],
            target["media_id"], target["expected_bytes"], "OPERATIONAL_ONLY",
            int(budget["phase1_getfile_cap"]) + 1, harness.COMMON_PREFIX_ALIGNED,
        ))
    ledger = harness.ProofLedger(
        case_root / "budget.sqlite3", getfile_cap=int(budget["aggregate_getfile_cap"]),
        hash_cap=int(budget["aggregate_getfilehashes_cap"]),
        payload_cap=int(budget["aggregate_payload_reservation_cap"]),
    )
    for index in range(int(budget["phase1_getfile_cap"])):
        reservation_id = f"recovery-seed-{index}"
        ledger.reserve_getfile(harness.CHUNK_BYTES, reservation_id)
        ledger.settle_getfile(reservation_id, harness.CHUNK_BYTES)
    return root, phase1


def test_resume_requires_and_preserves_real_phase1_receipt(tmp_path, monkeypatch) -> None:
    root, phase1 = _build_recoverable_checkpoint(tmp_path, monkeypatch)

    recovered = harness._recover_phase1_checkpoint(
        root, harness.target_for("common"), "OPERATIONAL_ONLY"
    )
    assert recovered["phase1"] == phase1
    assert (root / "aligned" / "phase-1.json").read_text(encoding="utf-8") == json.dumps(phase1)


def test_resume_refuses_legacy_phase1_without_real_pid(tmp_path, monkeypatch) -> None:
    root, _ = _build_recoverable_checkpoint(tmp_path, monkeypatch, process_id=None)

    with pytest.raises(RuntimeError, match="RECOVERY_PHASE1_RECEIPT_NOT_RESUMABLE"):
        harness._recover_phase1_checkpoint(
            root, harness.target_for("common"), "OPERATIONAL_ONLY"
        )


def test_download_error_subclasses_retain_only_allowlisted_code_and_stage() -> None:
    from telegram_courses.downloads import DownloadError

    class SpecializedDownloadError(DownloadError):
        def __init__(self, message: str) -> None:
            super().__init__("REMOTE_HASH_UNAVAILABLE", failure_phase="REMOTE_HASH")
            self.args = (message,)

    secret_path = r"C:\Users\sensitive\secret-session.db"
    error = SpecializedDownloadError(f"credential=do-not-log path={secret_path}")

    assert harness._safe_exception_class(error) == "REMOTE_HASH_UNAVAILABLE"
    assert harness._safe_stop_condition(error) == "REMOTE_HASH_UNAVAILABLE"
    assert harness._safe_exception_stage(error) == "REMOTE_HASH"
    assert secret_path not in harness._safe_stop_condition(error)
    path_error = DownloadError("PATH_TOO_LONG")
    assert harness._safe_exception_class(path_error) == "PATH_TOO_LONG"
    assert harness._safe_exception_stage(path_error) is None


def test_download_error_rejects_unallowlisted_code_and_stage_without_leaking_them() -> None:
    from telegram_courses.downloads import DownloadError

    error = DownloadError("C:\\sensitive\\token=secret", failure_phase="private-stage")
    assert harness._safe_exception_class(error) == "OTHER"
    assert harness._safe_stop_condition(error) == "OTHER"
    assert harness._safe_exception_stage(error) is None


def test_failed_null_child_result_is_valid_failure_envelope_but_never_phase_success() -> None:
    report = {
        "schema_version": 1, "phase_id": "failed-exec:1", "execution_id": "failed-exec",
        "phase": 1, "target_name": "common", "mode": "OPERATIONAL_ONLY",
        "case": "aligned", "prefix_profile": None, "process_id": 41001,
        "process_started_at_utc": "2026-10-20T12:00:00+00:00",
        "process_ended_at_utc": "2026-10-20T12:00:01+00:00",
        "child_exit_code": 5, "status": "PROCESS_FAILED", "stop_condition": "PATH_TOO_LONG",
        "child_result": None,
    }
    assert harness._child_report_envelope_valid(
        report, execution_id="failed-exec", phase=1, target_name="common",
        mode="OPERATIONAL_ONLY", case_name="aligned", prefix_profile=None,
        observed_process_id=41001,
    )
    failed_phase = {
        "case": "aligned", "target_name": "common", "mode": "OPERATIONAL_ONLY",
        "status": "PROCESS_FAILED", "exit_code": 5, "child_exit_code": 5,
        "child_report_valid": True, "child_result": None,
    }
    assert not harness._phase_receipt_is_acceptable(failed_phase, 1)

    for key, value in (("status", "PROCESS_COMPLETED"), ("child_exit_code", 0)):
        contradictory = dict(report)
        contradictory[key] = value
        assert not harness._child_report_envelope_valid(
            contradictory, execution_id="failed-exec", phase=1, target_name="common",
            mode="OPERATIONAL_ONLY", case_name="aligned", prefix_profile=None,
            observed_process_id=41001,
        )


def test_unknown_exception_subclass_is_reported_as_other_without_inspecting_message() -> None:
    class UnknownError(Exception):
        pass

    sensitive = "token=synthetic-secret"
    error = UnknownError(sensitive)

    assert harness._safe_exception_class(error) == "OTHER"
    assert harness._safe_stop_condition(error) == "OTHER"
    assert sensitive not in harness._safe_stop_condition(error)


@pytest.mark.parametrize("suffix", ["", ".part"])
def test_native_path_guard_rejects_paths_over_240_including_part_suffix(tmp_path, suffix) -> None:
    # Construct a path value only; this test never creates an overlong file.
    base = tmp_path / ("x" * 180) / ("y" * 90)
    candidate = Path(f"{base}{suffix}")
    assert len(str(candidate.absolute())) > harness.MAX_NATIVE_PATH_CHARS

    with pytest.raises(RuntimeError, match="NATIVE_PATH_LIMIT_EXCEEDED"):
        harness._guard_native_paths((candidate,))


def test_native_path_guard_accepts_final_below_limit_but_rejects_derived_part(tmp_path) -> None:
    parent = str(tmp_path.absolute())
    final_path = Path(parent + "\\" + "f" * (harness.MAX_NATIVE_PATH_CHARS - len(parent) - 1))
    part_path = Path(f"{final_path}.part")

    assert len(str(final_path.absolute())) == harness.MAX_NATIVE_PATH_CHARS
    harness._guard_native_paths((final_path,))
    assert len(str(part_path.absolute())) > harness.MAX_NATIVE_PATH_CHARS
    with pytest.raises(RuntimeError, match="NATIVE_PATH_LIMIT_EXCEEDED"):
        harness._guard_native_paths((part_path,))


def test_planner_rejects_overlong_destination_before_queue_and_plans_short_contained_path(
    tmp_path,
) -> None:
    from telegram_courses.downloads import DownloadError, destination_paths
    from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection

    database = tmp_path / "planner-path-fixture.sqlite3"
    asyncio.run(harness._seed_proof_catalog(database, harness.COMMON_TARGET))
    selection = DownloadSelection(harness.COMMON_TARGET["channel_id"])

    short_download_root = tmp_path / "short-downloads"
    short_plan = asyncio.run(DownloadPlanner(database, short_download_root).build(selection))
    assert len(short_plan.items) == 1
    short_item = short_plan.items[0]
    assert short_item.status == "PENDING"
    assert short_item.candidate is not None
    short_final, short_partial = destination_paths(short_download_root, short_item.candidate)
    assert short_final.is_relative_to(short_download_root.absolute())
    assert short_partial.is_relative_to(short_download_root.absolute())
    assert len(str(short_final)) <= 240
    assert len(str(short_partial)) <= 240

    # The real stage builds its plan before constructing DownloadQueue. This
    # synthetic long root therefore fails in the planner, before queue startup,
    # without creating the long path or a final/.part artifact.
    long_download_root = tmp_path / ("d" * 190)
    with pytest.raises(DownloadError) as error_info:
        asyncio.run(DownloadPlanner(database, long_download_root).build(selection))
    assert error_info.value.category == "PATH_TOO_LONG"
    assert not long_download_root.exists()


def test_failed_child_with_exit_5_and_null_result_never_satisfies_phase_acceptance(
    monkeypatch,
) -> None:
    monkeypatch.setattr(harness, "_preparation_receipt_valid", lambda *_args, **_kwargs: True)
    receipt = _acceptable_phase1_receipt_for_timeout_validation()
    receipt.update({
        "status": "PROCESS_FAILED",
        "child_status": "PROCESS_FAILED",
        "exit_code": 5,
        "child_exit_code": 5,
        "child_result": None,
        "stop_condition": "RuntimeError",
        "checkpoint_confirmed": False,
    })

    assert receipt["child_status"] == "PROCESS_FAILED"
    assert receipt["child_exit_code"] == 5
    assert receipt["child_result"] is None
    assert not harness._phase_receipt_is_acceptable(receipt, 1)


def _synthetic_child_report(**overrides) -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": 1,
        "phase_id": "synthetic-run:1",
        "execution_id": "synthetic-run",
        "phase": 1,
        "process_id": 43210,
        "target_name": "common",
        "mode": "OPERATIONAL_ONLY",
        "case": "aligned",
        "prefix_profile": None,
        "status": "PROCESS_FAILED",
        "child_exit_code": 5,
        "child_result": None,
        "stop_condition": "RuntimeError",
        "process_started_at_utc": "2026-10-20T00:00:00+00:00",
        "process_ended_at_utc": "2026-10-20T00:00:01+00:00",
    }
    report.update(overrides)
    return report


def test_child_report_envelope_accepts_process_failed_exit_5_with_null_result() -> None:
    report = _synthetic_child_report()

    assert harness._child_report_envelope_valid(
        report,
        execution_id="synthetic-run",
        phase=1,
        target_name="common",
        mode="OPERATIONAL_ONLY",
        case_name="aligned",
        prefix_profile=None,
        observed_process_id=43210,
    )


def test_child_report_envelope_validates_without_os_exit_code() -> None:
    report = _synthetic_child_report()

    assert harness._child_report_envelope_valid(
        report,
        execution_id="synthetic-run",
        phase=1,
        target_name="common",
        mode="OPERATIONAL_ONLY",
        case_name="aligned",
        prefix_profile=None,
        observed_process_id=43210,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"child_exit_code": 0},
        {"status": "PROCESS_COMPLETED"},
        {"phase": True},
        {"process_id": True},
        {"child_exit_code": True},
        {"phase_id": "another-run:1"},
    ],
)
def test_child_report_envelope_rejects_contradictory_or_wrongly_typed_failure(
    overrides,
) -> None:
    report = _synthetic_child_report(**overrides)

    assert not harness._child_report_envelope_valid(
        report,
        execution_id="synthetic-run",
        phase=1,
        target_name="common",
        mode="OPERATIONAL_ONLY",
        case_name="aligned",
        prefix_profile=None,
        observed_process_id=43210,
    )
