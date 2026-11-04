"""Proof tests for the opt-in terminal Telegram hash geometry; no network."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from telegram_courses.download_repository import DownloadCandidate, DownloadRepository
from telegram_courses.downloads import (
    DownloadError,
    RemoteFileHash,
    SingleMediaDownloadApplication,
    _validate_remote_ranges,
)

BLOCK = 128 * 1024
PAYLOAD = bytes(range(251)) * (BLOCK // 251 + 1) + b"tail"
PAYLOAD = PAYLOAD[:BLOCK + 37]


def candidate_for(payload: bytes) -> DownloadCandidate:
    return DownloadCandidate(
        1, -1001, 20, 0, "synthetic", len(payload), "synthetic.mp4",
        (("lesson", "Synthetic"),),
    )


def server_ranges(payload: bytes) -> tuple[RemoteFileHash, ...]:
    result = []
    for offset in range(0, len(payload), BLOCK):
        real = payload[offset:offset + BLOCK]
        result.append(RemoteFileHash(
            offset, BLOCK,
            hashlib.sha256(real).digest(),
        ))
    return tuple(result)


class FakeHashGateway:
    def __init__(self, ranges):
        self.ranges = ranges
        self.calls = 0

    async def get_file_hashes(self, *args, offset=0, **kwargs):
        self.calls += 1
        return tuple(self.ranges) if offset == 0 else ()


def test_strict_remote_hash_matches_only_actual_eof_tail(tmp_path: Path):
    media = tmp_path / "video.part"
    media.write_bytes(PAYLOAD)
    ranges = server_ranges(PAYLOAD)
    assert len(ranges) == 2
    assert ranges[-1].offset + ranges[-1].limit > len(PAYLOAD)
    assert _validate_remote_ranges(media, len(PAYLOAD), ranges, allow_terminal_eof=True)
    assert not _validate_remote_ranges(media, len(PAYLOAD), ranges)
    assert media.read_bytes() == PAYLOAD


@pytest.mark.parametrize("case", [
    "zero_pad", "mutate", "gap", "overlap", "reorder", "extra_range",
    "wrong_limit", "unaligned", "missing_tail", "wrong_length", "invalid_digest",
])
def test_strict_remote_eof_fail_closed(tmp_path: Path, case: str):
    media = tmp_path / "video.part"
    media.write_bytes(PAYLOAD)
    original = list(server_ranges(PAYLOAD))
    tail = PAYLOAD[BLOCK:]
    if case == "zero_pad":
        original[-1] = RemoteFileHash(
            BLOCK, BLOCK, hashlib.sha256(tail + bytes(BLOCK - len(tail))).digest(),
        )
    elif case == "mutate":
        changed = bytearray(PAYLOAD)
        changed[-1] ^= 1
        media.write_bytes(changed)
    elif case == "gap":
        original[0] = RemoteFileHash(0, BLOCK - 1, hashlib.sha256(PAYLOAD[:BLOCK - 1]).digest())
    elif case == "overlap":
        original[-1] = RemoteFileHash(
            BLOCK - 1, BLOCK, hashlib.sha256(PAYLOAD[BLOCK - 1:]).digest(),
        )
    elif case == "reorder":
        original.reverse()
    elif case == "extra_range":
        original.append(original[-1])
    elif case == "wrong_limit":
        original[-1] = RemoteFileHash(
            BLOCK, BLOCK + 1, hashlib.sha256(tail).digest(),
        )
    elif case == "unaligned":
        original[-1] = RemoteFileHash(
            BLOCK - 1, BLOCK, hashlib.sha256(PAYLOAD[BLOCK - 1:]).digest(),
        )
    elif case == "missing_tail":
        original.pop()
    elif case == "wrong_length":
        original[-1] = RemoteFileHash(BLOCK, BLOCK, b"x")
    elif case == "invalid_digest":
        original[-1] = RemoteFileHash(BLOCK, BLOCK, b"z" * 32)
    assert not _validate_remote_ranges(
        media, len(PAYLOAD), tuple(original), allow_terminal_eof=True
    )


def test_optin_fetch_accepts_terminal_overrun_but_default_blocks(tmp_path: Path):
    remote = FakeHashGateway(server_ranges(PAYLOAD))
    app = SingleMediaDownloadApplication(
        DownloadRepository(tmp_path / "unused.sqlite3"), remote, tmp_path,
        require_full_remote_hash=True,
    )
    candidate = candidate_for(PAYLOAD)

    async def check():
        hashes = await app._remote_hashes(
            candidate, len(PAYLOAD), allow_terminal_eof=True
        )
        assert hashes == server_ranges(PAYLOAD)
        with pytest.raises(DownloadError, match="remote hash range invalid"):
            await app._remote_hashes(candidate, len(PAYLOAD))
    asyncio.run(check())
    assert remote.calls == 2


@pytest.mark.parametrize("bad", ["gap", "extra_range", "wrong_limit", "bad_digest"])
def test_optin_fetch_rejects_malformed_response(tmp_path: Path, bad):
    ranges = list(server_ranges(PAYLOAD))
    if bad == "gap":
        ranges[1] = RemoteFileHash(BLOCK + 1, BLOCK, ranges[1].sha256)
    elif bad == "extra_range":
        ranges.append(ranges[-1])
    elif bad == "wrong_limit":
        ranges[-1] = RemoteFileHash(BLOCK, BLOCK + 1, ranges[-1].sha256)
    elif bad == "bad_digest":
        ranges[-1] = RemoteFileHash(BLOCK, BLOCK, b"short")
    remote = FakeHashGateway(ranges)
    app = SingleMediaDownloadApplication(
        DownloadRepository(tmp_path / "unused.sqlite3"), remote, tmp_path,
        require_full_remote_hash=True,
    )
    async def check():
        with pytest.raises(DownloadError):
            await app._remote_hashes(
                candidate_for(PAYLOAD), len(PAYLOAD), allow_terminal_eof=True
            )
    asyncio.run(check())


BATCH_PAYLOAD = (bytes(range(251)) * ((4 * BLOCK + 37) // 251 + 1))[:4 * BLOCK + 37]
PREFIX = 2 * BLOCK


def prefix_app(tmp_path: Path, ranges, *, strict=True, pilot=False):
    gateway = FakeHashGateway(ranges)
    return SingleMediaDownloadApplication(
        DownloadRepository(tmp_path / "unused.sqlite3"), gateway, tmp_path,
        require_full_remote_hash=strict,
        allow_prefix_terminal_eof=pilot,
    )


def test_prefix_batch_checks_local_bytes_and_reports_only_verified_ranges(tmp_path: Path):
    part = tmp_path / "media.part"
    part.write_bytes(BATCH_PAYLOAD[:PREFIX])
    all_ranges = server_ranges(BATCH_PAYLOAD)
    app = prefix_app(tmp_path, all_ranges, pilot=True)
    digest, verification_bytes, proof = asyncio.run(
        app._verify_prefix(candidate_for(BATCH_PAYLOAD), part, PREFIX)
    )
    assert digest == hashlib.sha256(BATCH_PAYLOAD[:PREFIX]).hexdigest()
    assert verification_bytes == 0
    assert proof.remote_ranges == all_ranges[:2]
    with pytest.raises(DownloadError, match="remote hash range invalid"):
        asyncio.run(prefix_app(tmp_path, all_ranges, strict=False)._verify_prefix(
            candidate_for(BATCH_PAYLOAD), part, PREFIX,
        ))


@pytest.mark.parametrize("case", [
    "empty", "incomplete", "reverse", "duplicate", "gap", "overlap", "negative",
    "zero_size", "bad_type", "short_digest", "bad_digest_type", "nonterminal_eof",
    "misaligned_eof", "oversize_eof", "short_terminal_size", "bad_local_digest",
    "misaligned_middle", "short_middle_size", "bad_later_digest", "local_mutation",
])
def test_prefix_batch_rejects_malformed_or_unverified_evidence(tmp_path: Path, case: str):
    part = tmp_path / "media.part"
    part.write_bytes(BATCH_PAYLOAD[:PREFIX])
    ranges = list(server_ranges(BATCH_PAYLOAD))
    if case == "empty":
        ranges = []
    elif case == "incomplete":
        ranges = ranges[:1]
    elif case == "reverse":
        ranges.reverse()
    elif case == "duplicate":
        ranges.insert(2, ranges[1])
    elif case == "gap":
        ranges[2] = replace(ranges[2], offset=2 * BLOCK + 1)
    elif case == "overlap":
        ranges[2] = replace(ranges[2], offset=2 * BLOCK - 1)
    elif case == "negative":
        ranges[0] = replace(ranges[0], offset=-1)
    elif case == "zero_size":
        ranges[2] = replace(ranges[2], limit=0)
    elif case == "bad_type":
        ranges[2] = replace(ranges[2], offset=True)
    elif case == "short_digest":
        ranges[0] = replace(ranges[0], sha256=b"short")
    elif case == "bad_digest_type":
        ranges[2] = replace(ranges[2], sha256=bytearray(32))
    elif case == "nonterminal_eof":
        ranges.append(RemoteFileHash(5 * BLOCK, BLOCK, b"x" * 32))
    elif case == "misaligned_eof":
        ranges[3] = replace(ranges[3], limit=BLOCK - 1)
        ranges[4] = replace(ranges[4], offset=4 * BLOCK - 1)
    elif case == "oversize_eof":
        ranges[-1] = replace(ranges[-1], limit=2 * BLOCK)
    elif case == "short_terminal_size":
        ranges[-1] = replace(ranges[-1], limit=BLOCK - 1)
    elif case == "misaligned_middle":
        ranges[2] = replace(ranges[2], offset=2 * BLOCK + 1)
    elif case == "short_middle_size":
        ranges[2] = replace(ranges[2], limit=BLOCK - 1)
    elif case == "bad_local_digest":
        ranges[0] = replace(ranges[0], sha256=b"x" * 32)
    elif case == "bad_later_digest":
        ranges[2] = replace(ranges[2], sha256=b"short")
    elif case == "local_mutation":
        part.write_bytes(b"x" + BATCH_PAYLOAD[1:PREFIX])
    with pytest.raises(DownloadError):
        asyncio.run(prefix_app(tmp_path, ranges, pilot=True)._verify_prefix(
            candidate_for(BATCH_PAYLOAD), part, PREFIX,
        ))


def test_prefix_crossing_terminal_range_is_rejected(tmp_path: Path):
    physical = 4 * BLOCK + 1
    part = tmp_path / "media.part"
    part.write_bytes(BATCH_PAYLOAD[:physical])
    with pytest.raises(DownloadError, match="remote hash range invalid"):
        asyncio.run(prefix_app(tmp_path, server_ranges(BATCH_PAYLOAD), pilot=True)._verify_prefix(
            candidate_for(BATCH_PAYLOAD), part, physical,
        ))


def test_pilot_unaligned_prefix_proves_only_ranges_verified_with_remote_complement(
    tmp_path: Path,
):
    payload = BATCH_PAYLOAD[:4 * BLOCK]
    physical = 2 * BLOCK + 1
    part = tmp_path / "media.part"
    part.write_bytes(payload[:physical])
    gateway = FakeHashGateway(server_ranges(payload))

    async def stream_media(*_args, offset=0, **_kwargs):
        yield payload[offset:offset + 2 * BLOCK]

    gateway.stream_media = stream_media
    app = SingleMediaDownloadApplication(
        DownloadRepository(tmp_path / "unused.sqlite3"), gateway, tmp_path,
        require_full_remote_hash=True, allow_prefix_terminal_eof=True,
    )
    digest, _, proof = asyncio.run(
        app._verify_prefix(candidate_for(payload), part, physical)
    )
    assert digest == hashlib.sha256(payload[:physical]).hexdigest()
    assert tuple(item.offset for item in proof.remote_ranges) == (
        0, BLOCK, 2 * BLOCK,
    )
    assert proof.remote_ranges[-1].offset + proof.remote_ranges[-1].limit == 3 * BLOCK
    assert proof.remote_ranges[-1].offset + proof.remote_ranges[-1].limit < len(payload)


def test_strict_nonpilot_resume_keeps_terminal_overrun_fail_closed(tmp_path: Path):
    part = tmp_path / "media.part"
    part.write_bytes(BATCH_PAYLOAD[:PREFIX])
    with pytest.raises(DownloadError, match="remote hash range invalid"):
        asyncio.run(prefix_app(
            tmp_path, server_ranges(BATCH_PAYLOAD), strict=True, pilot=False,
        )._verify_prefix(candidate_for(BATCH_PAYLOAD), part, PREFIX))


@pytest.mark.skipif(os.name != "nt", reason="S9 private-run validation is Windows-specific")
def test_s9_persists_real_prefix_observation_and_rejects_incomplete_coverage(tmp_path: Path):
    from tests.unit.test_s9_operational_reconciliation import _run_with_manifest

    from telegram_courses.s9_operational_ledger import S9OperationalLedger
    from telegram_courses.s9_operational_reconciliation import (
        OperationalReconciliationError,
        persist_s6_prefix_proof,
    )

    context, (manifest, _, _) = _run_with_manifest(tmp_path)
    ledger = S9OperationalLedger(context.ledger_path)
    ledger.update_execution(
        gate="G8", status="RUNNING", elapsed_ms=0, deadline_ns=context.deadline_ns,
        process_state="RUNNING", result="UNKNOWN",
    )
    candidate = replace(candidate_for(BATCH_PAYLOAD), channel_id=int(manifest["channel_id"]))
    alias = ledger.register_media(
        f"{candidate.channel_id}:{candidate.telegram_message_id}:{candidate.media_ordinal}",
        profile="F", expected_bytes=len(BATCH_PAYLOAD),
    )
    ledger.begin_attempt(alias)
    ledger.record_interruption(alias, part_bytes=PREFIX, expected_bytes=len(BATCH_PAYLOAD))
    ledger.begin_attempt(alias, recovery=True)
    part = tmp_path / "media.part"
    part.write_bytes(BATCH_PAYLOAD[:PREFIX])
    _, _, proof = asyncio.run(prefix_app(
        tmp_path, server_ranges(BATCH_PAYLOAD), strict=True, pilot=True,
    )._verify_prefix(
        candidate, part, PREFIX,
    ))
    with pytest.raises(OperationalReconciliationError, match="PREFIX_PROOF_COVERAGE_INCOMPLETE"):
        persist_s6_prefix_proof(
            context.run_directory, ledger, replace(proof, remote_ranges=proof.remote_ranges[:1]),
            measurement_source="SYNTHETIC_TEST",
        )
    path, _ = persist_s6_prefix_proof(
        context.run_directory, ledger, proof, measurement_source="SYNTHETIC_TEST",
    )
    payload = json.loads(path.read_text("utf-8"))
    assert payload["remote_hash_coverage_bytes"] == PREFIX
    assert len(payload["remote_hash_ranges"]) == 2
