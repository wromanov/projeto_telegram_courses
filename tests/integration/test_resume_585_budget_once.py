"""Synthetic 585-equivalent aligned partial recovery, no live Telegram or product DB."""
from __future__ import annotations

import asyncio
import hashlib
import sqlite3

import pytest
from tests.integration import test_download_flow as flow

from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import (
    DownloadError,
    DownloadGatewayError,
    RemoteFileHash,
    SingleMediaDownloadApplication,
    destination_paths,
)

CHUNK = 262144
HASH = 131072
SIZE = 6199635
PREFIX = 6029312
WIRE_LIMIT = 6291456
DATA = (bytes(range(251)) * ((SIZE // 251) + 1))[:SIZE]


class FakeTelegram:
    def __init__(self, *, bad_prefix=False, fail_reservation=False,
                 batch_size=1, bad_tail=False, corrupt_tail=False):
        self.calls = []
        self.stream_calls = []
        self.bad_prefix = bad_prefix
        self.fail_reservation = fail_reservation
        self.batch_size = batch_size
        self.bad_tail = bad_tail
        self.corrupt_tail = corrupt_tail
        self.reserved = 0
        self.received = 0

    async def validate_media_identity(self, *args, **kwargs):
        return True

    async def get_file_hashes(self, _channel, _message, _ordinal, *,
                              telegram_media_id, expected_bytes, offset=0):
        assert telegram_media_id == "synthetic-media"
        assert expected_bytes == SIZE
        assert offset % HASH == 0 and offset < SIZE
        self.calls.append(offset)
        result = []
        for start in range(offset, min(SIZE, offset + self.batch_size * HASH), HASH):
            actual = DATA[start:start + HASH]
            digest = hashlib.sha256(actual).digest()
            if (self.bad_prefix and start == HASH) or (self.bad_tail and start >= PREFIX):
                digest = b"x" * 32
            result.append(RemoteFileHash(start, HASH, digest))
        return tuple(result)

    async def stream_media(self, _channel, _message, _ordinal, *,
                           telegram_media_id, expected_bytes, offset=0,
                           reserve_chunk=None):
        assert telegram_media_id == "synthetic-media"
        assert expected_bytes == SIZE
        assert offset % CHUNK == 0
        self.stream_calls.append(offset)
        if not callable(reserve_chunk):
            raise AssertionError("BOUNDED_CHUNK_RESERVER_REQUIRED")
        part = DATA[offset:]
        if self.corrupt_tail:
            part = part[:-1] + bytes([part[-1] ^ 1])
        if not part:
            return
        class Lease:
            def __init__(inner, owner, size):
                inner.owner = owner
                inner.size = size
            def received(inner, count):
                inner.owner.received += count
            def charge_uncertain(inner):
                pass
        if self.fail_reservation:
            raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
        if self.reserved + CHUNK > WIRE_LIMIT:
            raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
        self.reserved += CHUNK
        lease = Lease(self, CHUNK)
        lease.received(len(part))
        yield part


async def setup_partial(database, root):
    await flow.seed_lesson(database)
    repo = DownloadRepository(database)
    candidate = await repo.select_candidate(flow.CHANNEL_ID, flow.MESSAGE_ID, 0)
    assert candidate is not None and candidate.expected_bytes == SIZE
    final, partial = destination_paths(root, candidate)
    final.parent.mkdir(parents=True, exist_ok=True)
    await repo.start(candidate, final, partial)
    partial.write_bytes(DATA[:PREFIX])
    await repo.checkpoint(candidate.media_item_id, PREFIX)
    await repo.transition(candidate.media_item_id, "FAILED_RETRYABLE",
                          downloaded_bytes=PREFIX,
                          failure_category="TRANSFER_BUDGET_EXHAUSTED")
    return repo, candidate, final, partial


@pytest.mark.parametrize("mode", ("success", "invalid_prefix", "budget_denied"))
def test_exact_one_extra_attempt_never_redownloads_prefix(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(flow, "PAYLOAD", DATA)
    db = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    gateway = FakeTelegram(
        bad_prefix=mode == "invalid_prefix",
        fail_reservation=mode == "budget_denied",
    )

    async def exercise():
        repo, candidate, final, partial = await setup_partial(db, root)
        app = SingleMediaDownloadApplication(
            repo, gateway, root, require_full_remote_hash=True,
        )
        if mode == "success":
            outcome = await app.download(flow.CHANNEL_ID, flow.MESSAGE_ID, 0)
            assert outcome.remote_hash_class == "REMOTE_HASH_FULL"
            assert outcome.result == "DOWNLOADED"
        else:
            with pytest.raises(DownloadError):
                await app.download(flow.CHANNEL_ID, flow.MESSAGE_ID, 0)
        record = await repo.get_record(candidate.media_item_id)
        return record, final, partial

    record, final, partial = asyncio.run(exercise())
    assert record is not None
    if mode == "success":
        assert record.state == "DOWNLOADED"
        assert record.downloaded_bytes == SIZE
        assert record.sha256 == hashlib.sha256(DATA).hexdigest()
        assert final.read_bytes() == DATA
        assert not partial.exists()
        assert gateway.stream_calls == [PREFIX]
        assert gateway.reserved == CHUNK
        assert gateway.received == SIZE - PREFIX
        assert len(gateway.calls) == 46 + 48
    else:
        assert record.state == "FAILED_RETRYABLE"
        assert not final.exists()
        assert partial.read_bytes() == DATA[:PREFIX]
        if mode == "invalid_prefix":
            assert gateway.stream_calls == []
        else:
            assert gateway.stream_calls == [PREFIX]
    with sqlite3.connect(db) as c:
        attempts = c.execute("SELECT attempts FROM downloads").fetchone()[0]
        assert attempts == 2


@pytest.mark.parametrize("batch_size", (46, 48, 10))
def test_batched_hashes_produce_verified_prefix_and_full_recovery(
    tmp_path, monkeypatch, batch_size,
):
    monkeypatch.setattr(flow, "PAYLOAD", DATA)
    gateway = FakeTelegram(batch_size=batch_size)
    proofs = []

    async def exercise():
        repo, candidate, final, partial = await setup_partial(
            tmp_path / "catalog.sqlite3", tmp_path / "downloads",
        )
        original = hashlib.sha256(partial.read_bytes()).hexdigest()
        app = SingleMediaDownloadApplication(
            repo, gateway, tmp_path / "downloads", require_full_remote_hash=True,
            allow_prefix_terminal_eof=True,
            prefix_proof_observer=proofs.append,
        )
        outcome = await app.download(flow.CHANNEL_ID, flow.MESSAGE_ID, 0)
        return await repo.get_record(candidate.media_item_id), final, original, outcome

    record, final, original, outcome = asyncio.run(exercise())
    assert outcome.result == "DOWNLOADED"
    assert outcome.remote_hash_class == outcome.guarantee == "REMOTE_HASH_FULL"
    assert record.state == "DOWNLOADED" and record.downloaded_bytes == SIZE
    assert record.sha256 == hashlib.sha256(DATA).hexdigest()
    assert final.read_bytes() == DATA
    assert hashlib.sha256(final.read_bytes()[:PREFIX]).hexdigest() == original
    assert gateway.stream_calls == [PREFIX]
    assert gateway.received == SIZE - PREFIX and gateway.reserved == CHUNK
    assert len(proofs) == 1
    proof = proofs[0]
    assert proof.local_prefix_sha256 == original
    assert proof.verification_payload_bytes == 0
    assert len(proof.remote_ranges) == 46
    assert all(item.offset + item.limit <= PREFIX for item in proof.remote_ranges)


@pytest.mark.parametrize("failure", ("bad_tail_digest", "corrupt_tail"))
def test_later_bad_digest_or_corrupt_tail_blocks_finalization(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(flow, "PAYLOAD", DATA)
    gateway = FakeTelegram(
        batch_size=48, bad_tail=failure == "bad_tail_digest",
        corrupt_tail=failure == "corrupt_tail",
    )
    proofs = []

    async def exercise():
        root = tmp_path / "downloads"
        repo, candidate, final, partial = await setup_partial(tmp_path / "db.sqlite3", root)
        app = SingleMediaDownloadApplication(
            repo, gateway, root, require_full_remote_hash=True,
            allow_prefix_terminal_eof=True,
            prefix_proof_observer=proofs.append,
        )
        with pytest.raises(DownloadError, match="continuation integrity mismatch"):
            await app.download(flow.CHANNEL_ID, flow.MESSAGE_ID, 0)
        return await repo.get_record(candidate.media_item_id), final, partial

    record, final, partial = asyncio.run(exercise())
    assert record.state == "FAILED_RETRYABLE" and not final.exists()
    assert partial.read_bytes()[:PREFIX] == DATA[:PREFIX]
    assert len(proofs) == 1 and len(proofs[0].remote_ranges) == 46
