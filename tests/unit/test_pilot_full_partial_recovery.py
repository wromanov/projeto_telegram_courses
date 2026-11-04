"""Offline tests for verified complete-part recovery; no Telegram/real product files."""
from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from pathlib import Path

import pytest
from tools import telegram_3_recover_full_partials as recovery

from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import RemoteFileHash

BLOCK = recovery.HASH_BLOCK
MEDIA = bytes(range(251)) * (BLOCK // 251 + 1) + b"tail"
MEDIA = MEDIA[:BLOCK + 37]


class FakeGateway:
    def __init__(self, payload=MEDIA, *, mode="valid"):
        self.payload = payload
        self.mode = mode
        self.calls = []

    async def validate_media_identity(self, *args, **kwargs):
        return True

    async def get_file_hashes(self, *args, offset=0, **kwargs):
        self.calls.append(offset)
        ranges = []
        for start in range(0, len(self.payload), BLOCK):
            chunk = self.payload[start:start + BLOCK]
            digest = hashlib.sha256(chunk).digest()
            if self.mode == "bad_hash" and start == BLOCK:
                digest = b"x" * 32
            ranges.append(RemoteFileHash(start, BLOCK, digest))
        if self.mode == "missing" and offset != 0:
            return ()
        if self.mode == "gap" and offset != 0:
            return (RemoteFileHash(offset + 1, BLOCK, b"x" * 32),)
        if self.mode == "no_progress" and offset != 0:
            return (ranges[0],)
        # Simulates server response beginning on an earlier hash boundary.
        return tuple(ranges[:1] if offset == 0 else ranges)


def target(tmp_path: Path, payload: bytes = MEDIA) -> recovery.Target:
    final = tmp_path / "lesson.mp4"
    partial = tmp_path / "lesson.mp4.part"
    partial.write_bytes(payload)
    return recovery.Target(
        db_id=1, message_id=10, media_id="dummy", size=len(payload),
        attempts=1, owner_pid=None, partial=partial, final=final,
    )


def test_all_hash_ranges_covered_with_eof_and_page_overlap(tmp_path: Path):
    item = target(tmp_path)
    gateway = FakeGateway()
    budget = recovery.RPCBudget(gateway, limit=10)
    proof = asyncio.run(recovery.verify_one(item, gateway, budget))
    assert proof.sha256 == hashlib.sha256(MEDIA).hexdigest()
    assert budget.calls == 2
    assert item.partial.read_bytes() == MEDIA
    assert not item.final.exists()


@pytest.mark.parametrize("mode", ("bad_hash", "missing", "gap", "no_progress"))
def test_recovery_hash_check_fails_closed(tmp_path: Path, mode):
    item = target(tmp_path)
    gateway = FakeGateway(mode=mode)
    budget = recovery.RPCBudget(gateway, limit=10)
    with pytest.raises(ValueError, match="HASH|REMOTE"):
        asyncio.run(recovery.verify_one(item, gateway, budget))
    assert item.partial.read_bytes() == MEDIA
    assert not item.final.exists()


def test_hash_rpc_budget_does_not_retry_or_download(tmp_path: Path):
    item = target(tmp_path)
    gateway = FakeGateway()
    with pytest.raises(RuntimeError, match="BUDGET"):
        asyncio.run(recovery.verify_one(item, gateway, recovery.RPCBudget(gateway, 1)))
    assert len(gateway.calls) == 1


def test_finalize_only_verified_full_partial_preserves_attempts(tmp_path: Path, monkeypatch):
    from tests.integration.test_download_flow import CHANNEL_ID, MESSAGE_ID, seed_lesson

    from telegram_courses.downloads import destination_paths

    data = tmp_path / "catalog.sqlite3"
    downloads = tmp_path / "downloads"
    monkeypatch.setattr(recovery, "DB", data)
    monkeypatch.setattr(recovery, "DOWNLOADS", downloads)

    async def seed():
        await seed_lesson(data)
        repository = DownloadRepository(data)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        assert candidate is not None
        final, partial = destination_paths(downloads, candidate)
        partial.parent.mkdir(parents=True, exist_ok=True)
        partial.write_bytes(b"synthetic lesson media")
        await repository.start(candidate, final, partial)
        await repository.checkpoint(candidate.media_item_id, len(b"synthetic lesson media"))
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE",
            downloaded_bytes=len(b"synthetic lesson media"), failure_category="REMOTE_HASH_RANGE_INVALID",
        )
        return candidate, final, partial

    candidate, final, partial = asyncio.run(seed())
    # Synthetic previously exited download process; no actual retry attempted.
    with sqlite3.connect(data) as db:
        db.execute("UPDATE downloads SET owner_pid=NULL WHERE media_item_id=?", (candidate.media_item_id,))
        db.commit()
    item = recovery.Target(
        db_id=candidate.media_item_id,
        message_id=candidate.telegram_message_id,
        media_id=candidate.telegram_media_id,
        size=candidate.expected_bytes,
        attempts=1,
        owner_pid=None,
        partial=partial,
        final=final,
    )
    proof = recovery.Verified(item, hashlib.sha256(partial.read_bytes()).hexdigest())
    recovery.finalize_one(proof)
    assert not partial.exists()
    assert final.read_bytes() == b"synthetic lesson media"
    with sqlite3.connect(data) as db:
        state, attempts, stored_hash = db.execute(
            "SELECT state,attempts,sha256 FROM downloads WHERE media_item_id=?",
            (candidate.media_item_id,),
        ).fetchone()
    assert state == "DOWNLOADED"
    assert attempts == 1
    assert stored_hash == proof.sha256


def test_finalize_rejects_unproved_modification(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(recovery, "DOWNLOADS", tmp_path)
    item = target(tmp_path)
    proof = recovery.Verified(item, hashlib.sha256(MEDIA).hexdigest())
    item.partial.write_bytes(MEDIA[:-1] + b"Z")
    with pytest.raises(ValueError, match="PARTIAL_CHANGED"):
        recovery.finalize_one(proof)
    assert not item.final.exists()
