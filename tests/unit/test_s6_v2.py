from __future__ import annotations

import asyncio
import hashlib
import json

import aiosqlite
import pytest

import telegram_courses.downloads as downloads
from telegram_courses.download_repository import DownloadRepository
from telegram_courses.downloads import (
    DownloadError,
    DownloadGatewayError,
    RemoteFileHash,
    SingleMediaDownloadApplication,
    destination_paths,
)
from telegram_courses.s5_downloads import (
    DownloadPlan,
    DownloadPlanner,
    DownloadQueue,
    DownloadSelection,
    PlanItem,
)
from telegram_courses.s6_integrity import assess_remote_hashes, load_reference

CHANNEL_ID = -100123
MESSAGE_ID = 47
PAYLOAD = b"synthetic s6 v2 bytes"
MEDIA_ID = "media-v2-test"


async def seed_database(path, *, expected_bytes: int = len(PAYLOAD)) -> DownloadRepository:
    repository = DownloadRepository(path)
    await repository.migrate()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (CHANNEL_ID, "channel", "now", "now"),
        )
        await db.execute(
            "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
            "VALUES(?,?,?,?,?)",
            (CHANNEL_ID, MESSAGE_ID, "2026-10-17T00:00:00Z", "now", "now"),
        )
        await db.execute(
            "INSERT INTO catalog_nodes(channel_id,kind,title,source_message_id,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (CHANNEL_ID, "lesson", "Lesson", MESSAGE_ID, "now", "now"),
        )
        lesson_id = (await (await db.execute("SELECT id FROM catalog_nodes")).fetchone())[0]
        await db.execute(
            "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,"
            "telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (CHANNEL_ID, MESSAGE_ID, 0, lesson_id, "DOCUMENT", MEDIA_ID, "lesson.bin", expected_bytes, "now", "now"),
        )
        await db.commit()
    return repository


class FakeV2Gateway:
    def __init__(self, payload: bytes = PAYLOAD) -> None:
        self.payload = payload
        self.identity_calls = 0
        self.stream_calls: list[int] = []
        self.hash_calls = 0

    async def validate_media_identity(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id, expected_bytes
    ):
        self.identity_calls += 1
        assert (channel_id, message_id, media_ordinal) == (CHANNEL_ID, MESSAGE_ID, 0)
        assert telegram_media_id == MEDIA_ID
        assert expected_bytes == len(self.payload)
        return True

    async def stream_media(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id,
        expected_bytes, offset=0, reserve_chunk=None,
    ):
        assert (channel_id, message_id, media_ordinal) == (CHANNEL_ID, MESSAGE_ID, 0)
        assert telegram_media_id == MEDIA_ID
        assert expected_bytes == len(self.payload)
        self.stream_calls.append(offset)
        block = self.payload[offset:]
        if block:
            lease = await reserve_chunk(256 * 1024)
            assert lease is not None
            lease.received(len(block))
            yield block

    async def get_file_hashes(
        self, channel_id, message_id, media_ordinal, *, telegram_media_id,
        expected_bytes, offset=0,
    ):
        self.hash_calls += 1
        assert offset == 0
        return (RemoteFileHash(0, expected_bytes, hashlib.sha256(self.payload).digest()),)


def test_s6_hash_classification_preserves_remote_semantics(tmp_path) -> None:
    local = tmp_path / "payload.bin"
    local.write_bytes(PAYLOAD)
    full = (RemoteFileHash(0, len(PAYLOAD), hashlib.sha256(PAYLOAD).digest()),)
    assert assess_remote_hashes(local, len(PAYLOAD), full).primary == "REMOTE_HASH_FULL"
    assert assess_remote_hashes(local, len(PAYLOAD), full[:0]).primary == "REMOTE_HASH_ABSENT"
    partial = (RemoteFileHash(0, 3, hashlib.sha256(PAYLOAD[:3]).digest()),)
    assert assess_remote_hashes(local, len(PAYLOAD), partial).primary == "REMOTE_HASH_PARTIAL"
    eof = (RemoteFileHash(0, len(PAYLOAD) + 1, hashlib.sha256(PAYLOAD).digest()),)
    eof_result = assess_remote_hashes(local, len(PAYLOAD), eof)
    assert eof_result.primary == "REMOTE_HASH_UNVERIFIABLE_EOF"
    assert any(event["class"] == "REMOTE_HASH_PARTIAL" for event in eof_result.events)
    invalid = (RemoteFileHash(0, len(PAYLOAD), b"short"),)
    assert assess_remote_hashes(local, len(PAYLOAD), invalid).primary == "REMOTE_HASH_INVALID_RESPONSE"
    divergent = (RemoteFileHash(0, len(PAYLOAD), hashlib.sha256(b"other").digest()),)
    assert assess_remote_hashes(local, len(PAYLOAD), divergent).primary == "REMOTE_HASH_DIVERGENT"


@pytest.mark.parametrize(
    ("later_range", "expected_class"),
    [
        (
            RemoteFileHash(2, 2, hashlib.sha256(b"xx").digest()),
            "REMOTE_HASH_DIVERGENT",
        ),
        (
            RemoteFileHash(-1, 2, hashlib.sha256(b"cd").digest()),
            "REMOTE_HASH_INVALID_RESPONSE",
        ),
    ],
)
def test_remote_hash_unavailability_preserves_prior_evidence(
    tmp_path, later_range, expected_class
) -> None:
    local = tmp_path / "payload.bin"
    local.write_bytes(b"abcd")
    assessment = assess_remote_hashes(
        local,
        4,
        (
            RemoteFileHash(0, 2, hashlib.sha256(b"ab").digest()),
            later_range,
        ),
        unavailable=True,
    )
    event_classes = [event["class"] for event in assessment.events]
    assert assessment.primary == expected_class
    assert assessment.blocking is True
    assert assessment.verified_ranges == ((0, 2),)
    assert "REMOTE_HASH_RANGE_MATCH" in event_classes
    assert expected_class in event_classes
    assert "REMOTE_HASH_UNAVAILABLE" in event_classes


def test_trusted_reference_requires_registered_provenance(tmp_path) -> None:
    reference = tmp_path / "reference.bin"
    reference.write_bytes(PAYLOAD)
    manifest = tmp_path / "reference.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "telegram_message_id": MESSAGE_ID,
        "media_ordinal": 0,
        "telegram_media_id": MEDIA_ID,
        "expected_bytes": len(PAYLOAD),
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "reference_path": str(reference),
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="reference provenance is unverified"):
        load_reference(
            manifest,
            channel_id=CHANNEL_ID,
            telegram_message_id=MESSAGE_ID,
            media_ordinal=0,
            telegram_media_id=MEDIA_ID,
            expected_bytes=len(PAYLOAD),
        )


def test_v2_selection_rejects_candidate_vs_current_media_mismatch(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        assert candidate is not None
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "UPDATE media_items SET telegram_media_id=? WHERE id=?",
                ("replacement-media", candidate.media_item_id),
            )
            await db.commit()
        with pytest.raises(ValueError, match="current remote media identity changed"):
            await repository.record_v2_selection(
                candidate,
                selected_mode="OPERATIONAL_ONLY",
                invocation_id="candidate-current-mismatch",
            )
        async with aiosqlite.connect(database) as db:
            attempts = await (await db.execute(
                "SELECT COUNT(*) FROM s6_v2_attempts WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone()
            downloads = await (await db.execute(
                "SELECT COUNT(*) FROM downloads WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone()
        return attempts[0], downloads[0]

    attempts, downloads = asyncio.run(exercise())
    assert attempts == 0
    assert downloads == 0


def test_v2_selection_rejects_divergent_download_snapshot_without_mutation(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        assert candidate is not None
        final = tmp_path / "existing.bin"
        partial = tmp_path / "existing.bin.part"
        await repository.start(candidate, final, partial)
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "UPDATE downloads SET remote_identity_media_id=? WHERE media_item_id=?",
                ("snapshot-media", candidate.media_item_id),
            )
            await db.commit()
            before = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone())
        with pytest.raises(ValueError, match="download remote media identity changed"):
            await repository.record_v2_selection(
                candidate,
                selected_mode="OPERATIONAL_ONLY",
                invocation_id="snapshot-mismatch",
            )
        async with aiosqlite.connect(database) as db:
            after = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone())
            attempts = await (await db.execute(
                "SELECT COUNT(*) FROM s6_v2_attempts WHERE media_item_id=?",
                (candidate.media_item_id,),
            )).fetchone()
        return before, after, attempts[0]

    before, after, attempts = asyncio.run(exercise())
    assert after == before
    assert attempts == 0


def test_v2_is_inactive_before_database_or_gateway_use(tmp_path) -> None:
    class NeverGateway:
        calls = 0

    async def exercise() -> None:
        database = tmp_path / "must-not-be-created.sqlite3"
        app = SingleMediaDownloadApplication(DownloadRepository(database), NeverGateway(), tmp_path / "files")
        with pytest.raises(DownloadError, match="v2 inactive"):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY")
        assert not database.exists()

    asyncio.run(exercise())


def test_operational_only_rereads_full_prefix_and_persists_completed_v2(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "files"
    gateway = FakeV2Gateway()

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(PAYLOAD[:7])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=7,
            failure_category="TEST_RESTART",
        )
        app = SingleMediaDownloadApplication(repository, gateway, root)
        outcome = await app.download(
            CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY",
            plan_id="plan-v2-test", invocation_id="invoke-v2-test",
        )
        return repository, candidate, outcome

    repository, candidate, outcome = asyncio.run(exercise())
    assert outcome.result == "COMPLETED_V2"
    assert outcome.evidence_class == "OPERATIONAL_ONLY"
    assert outcome.guarantee == "UNVERIFIED_ORIGIN"
    assert gateway.stream_calls == [0]
    assert gateway.identity_calls >= 2
    assert outcome.final_path.read_bytes() == PAYLOAD

    async def inspect():
        record = await repository.get_record(candidate.media_item_id)
        evidence = await repository.get_v2_evidence(candidate.media_item_id)
        async with aiosqlite.connect(database) as db:
            attempt = await (await db.execute(
                "SELECT selected_mode,plan_id,invocation_id,status,requests,bytes_reserved,bytes_received "
                "FROM s6_v2_attempts WHERE media_item_id=? ORDER BY rowid DESC LIMIT 1",
                (candidate.media_item_id,),
            )).fetchone()
        return record, evidence, attempt

    record, evidence, attempt = asyncio.run(inspect())
    assert record.state == "COMPLETED_V2"
    assert record.contract_version == 2 and record.evidence_version == 1
    assert evidence["telegram_media_id"] == MEDIA_ID
    assert evidence["expected_bytes"] == len(PAYLOAD)
    assert evidence["final_sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert evidence["remote_hash_class"] == "REMOTE_HASH_FULL"
    assert tuple(attempt[:4]) == ("OPERATIONAL_ONLY", "plan-v2-test", "invoke-v2-test", "COMPLETED")
    assert attempt[4] >= 1
    assert attempt[5] == downloads.CHUNK_BYTES
    assert attempt[6] == len(PAYLOAD)

    async def legacy_read():
        v1 = SingleMediaDownloadApplication(repository, gateway, root)
        with pytest.raises(DownloadError, match="unknown legacy"):
            await v1.download(CHANNEL_ID, MESSAGE_ID, 0)
        v2 = await v1.download(CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY")
        return v2

    existing = asyncio.run(legacy_read())
    assert existing.result == "ALREADY_COMPLETED_V2"


def test_operational_only_rereads_chunk_aligned_prefix_before_boundary_transfer(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    chunk_bytes = downloads.CHUNK_BYTES
    payload = b"p" * chunk_bytes + b"boundary-tail"
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "files"

    class ChunkedGateway(FakeV2Gateway):
        async def stream_media(
            self, channel_id, message_id, media_ordinal, *, telegram_media_id,
            expected_bytes, offset=0, reserve_chunk=None,
        ):
            assert (channel_id, message_id, media_ordinal) == (CHANNEL_ID, MESSAGE_ID, 0)
            assert telegram_media_id == MEDIA_ID
            assert expected_bytes == len(payload)
            self.stream_calls.append(offset)
            for start in range(offset, len(payload), chunk_bytes):
                block = payload[start : start + chunk_bytes]
                lease = await reserve_chunk(chunk_bytes)
                assert lease is not None
                lease.received(len(block))
                yield block

    gateway = ChunkedGateway(payload)

    async def exercise():
        repository = await seed_database(database)
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "UPDATE media_items SET file_size_bytes=? WHERE telegram_media_id=?",
                (len(payload), MEDIA_ID),
            )
            await db.commit()
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(payload[:chunk_bytes])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=chunk_bytes,
            failure_category="TEST_RESTART",
        )
        app = SingleMediaDownloadApplication(repository, gateway, root)
        outcome = await app.download(
            CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY",
            plan_id="aligned-prefix-plan", invocation_id="aligned-prefix-invocation",
        )
        return partial, outcome

    partial, outcome = asyncio.run(exercise())
    assert outcome.result == "COMPLETED_V2"
    assert outcome.final_path.read_bytes() == payload
    assert gateway.stream_calls == [0, chunk_bytes]
    assert not partial.exists()


def test_trusted_reference_requires_exact_manifest_and_byte_match(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    reference = tmp_path / "trusted.bin"
    reference.write_bytes(PAYLOAD)
    manifest = tmp_path / "trusted.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "telegram_message_id": MESSAGE_ID,
        "media_ordinal": 0,
        "telegram_media_id": MEDIA_ID,
        "expected_bytes": len(PAYLOAD),
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "reference_path": str(reference),
        "provenance": "captured before Telegram upload; user supplied",
    }), encoding="utf-8")
    gateway = FakeV2Gateway()

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        assert candidate is not None
        app = SingleMediaDownloadApplication(repository, gateway, root)
        return await app.download(
            CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="TRUSTED_REFERENCE",
            reference_manifest_path=manifest, plan_id="one-item-plan",
            invocation_id="trusted-invocation",
        )

    outcome = asyncio.run(exercise())
    assert outcome.result == "COMPLETED_V2"
    assert outcome.evidence_class == "REFERENCE_MATCH"
    assert outcome.remote_hash_class == "REMOTE_HASH_FULL"
    assert outcome.final_path.read_bytes() == reference.read_bytes()


@pytest.mark.parametrize("prefix_size_kind", ["one", "chunk_minus_one", "chunk_plus_123", "end_minus_one", "aligned", "end"])
def test_trusted_reference_resume_keeps_physical_cursor_and_aligned_wire_offset(
    tmp_path, monkeypatch, prefix_size_kind
) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    chunk_bytes = downloads.CHUNK_BYTES
    payload = bytes(index % 251 for index in range(2 * chunk_bytes + 17))
    prefix_size = {
        "one": 1,
        "chunk_minus_one": chunk_bytes - 1,
        "chunk_plus_123": chunk_bytes + 123,
        "end_minus_one": len(payload) - 1,
        "aligned": chunk_bytes,
        "end": len(payload),
    }[prefix_size_kind]
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    reference = tmp_path / "trusted.bin"
    reference.write_bytes(payload)
    manifest = tmp_path / "trusted.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "telegram_message_id": MESSAGE_ID,
        "media_ordinal": 0,
        "telegram_media_id": MEDIA_ID,
        "expected_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "reference_path": str(reference),
        "provenance": "synthetic fixture",
    }), encoding="utf-8")

    class ChunkedGateway(FakeV2Gateway):
        async def stream_media(
            self, channel_id, message_id, media_ordinal, *, telegram_media_id,
            expected_bytes, offset=0, reserve_chunk=None,
        ):
            assert expected_bytes == len(payload)
            self.stream_calls.append(offset)
            for start in range(offset, len(payload), chunk_bytes):
                block = payload[start : start + chunk_bytes]
                lease = await reserve_chunk(chunk_bytes)
                assert lease is not None
                lease.received(len(block))
                yield block

    gateway = ChunkedGateway(payload)

    async def exercise():
        repository = await seed_database(database, expected_bytes=len(payload))
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(payload[:prefix_size])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=prefix_size,
            failure_category="TEST_RESTART",
        )
        app = SingleMediaDownloadApplication(repository, gateway, root)
        outcome = await app.download(
            CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="TRUSTED_REFERENCE",
            reference_manifest_path=manifest,
        )
        return partial, outcome

    partial, outcome = asyncio.run(exercise())
    assert outcome.result == "COMPLETED_V2"
    assert outcome.evidence_class == "REFERENCE_MATCH"
    assert outcome.final_path.read_bytes() == payload
    assert not partial.exists()
    wire_offset = (prefix_size // chunk_bytes) * chunk_bytes
    if prefix_size < len(payload):
        assert gateway.stream_calls == [wire_offset]
    else:
        assert gateway.stream_calls == []


def test_trusted_reference_overlap_mismatch_preserves_prefix_without_append(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    chunk_bytes = downloads.CHUNK_BYTES
    payload = b"a" * (chunk_bytes + 512)
    conflicting_payload = payload[: chunk_bytes + 12] + b"X" + payload[chunk_bytes + 13 :]
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    reference = tmp_path / "trusted.bin"
    reference.write_bytes(payload)
    manifest = tmp_path / "trusted.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "channel_id": CHANNEL_ID,
        "telegram_message_id": MESSAGE_ID, "media_ordinal": 0,
        "telegram_media_id": MEDIA_ID, "expected_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "reference_path": str(reference),
        "provenance": "synthetic fixture",
    }), encoding="utf-8")
    gateway = FakeV2Gateway(conflicting_payload)

    async def exercise():
        repository = await seed_database(database, expected_bytes=len(payload))
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        prefix = payload[: chunk_bytes + 123]
        partial.write_bytes(prefix)
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=len(prefix),
            failure_category="TEST_RESTART",
        )
        app = SingleMediaDownloadApplication(repository, gateway, root)
        with pytest.raises(DownloadError) as error:
            await app.download(
                CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="TRUSTED_REFERENCE",
                reference_manifest_path=manifest,
            )
        return error.value.category, partial

    category, partial = asyncio.run(exercise())
    assert category == "PREFIX_CONFLICT"
    assert partial.read_bytes() == payload[: chunk_bytes + 123]


def test_trusted_reference_resume_budget_block_preserves_prefix(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    reference = tmp_path / "trusted.bin"
    reference.write_bytes(PAYLOAD)
    manifest = tmp_path / "trusted.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "channel_id": CHANNEL_ID,
        "telegram_message_id": MESSAGE_ID, "media_ordinal": 0,
        "telegram_media_id": MEDIA_ID, "expected_bytes": len(PAYLOAD),
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(), "reference_path": str(reference),
        "provenance": "synthetic fixture",
    }), encoding="utf-8")

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(PAYLOAD[:7])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=7,
            failure_category="TEST_RESTART",
        )
        app = SingleMediaDownloadApplication(repository, FakeV2Gateway(), root)
        async def no_budget(_amount):
            return None
        app.operation_reserver = no_budget
        with pytest.raises(DownloadError, match="budget"):
            await app.download(
                CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="TRUSTED_REFERENCE",
                reference_manifest_path=manifest,
            )
        return partial

    partial = asyncio.run(exercise())
    assert partial.read_bytes() == PAYLOAD[:7]


def test_trusted_reference_resume_cancellation_preserves_prefix(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    reference = tmp_path / "trusted.bin"
    reference.write_bytes(PAYLOAD)
    manifest = tmp_path / "trusted.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "channel_id": CHANNEL_ID,
        "telegram_message_id": MESSAGE_ID, "media_ordinal": 0,
        "telegram_media_id": MEDIA_ID, "expected_bytes": len(PAYLOAD),
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(), "reference_path": str(reference),
        "provenance": "synthetic fixture",
    }), encoding="utf-8")

    class CancelledGateway(FakeV2Gateway):
        async def stream_media(self, *args, **kwargs):
            self.stream_calls.append(kwargs.get("offset", 0))
            raise asyncio.CancelledError
            yield b""  # Keep this method an async generator.

    gateway = CancelledGateway()

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(PAYLOAD[:7])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=7,
            failure_category="TEST_RESTART",
        )
        app = SingleMediaDownloadApplication(repository, gateway, root)
        with pytest.raises(asyncio.CancelledError):
            await app.download(
                CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="TRUSTED_REFERENCE",
                reference_manifest_path=manifest,
            )
        return partial, final

    partial, final = asyncio.run(exercise())
    assert gateway.stream_calls == [0]
    assert partial.read_bytes() == PAYLOAD[:7]
    assert not final.exists()


def test_trusted_reference_byte_mismatch_preserves_partial_without_validation(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    reference = tmp_path / "trusted.bin"
    reference.write_bytes(PAYLOAD)
    manifest = tmp_path / "trusted.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "channel_id": CHANNEL_ID,
        "telegram_message_id": MESSAGE_ID,
        "media_ordinal": 0,
        "telegram_media_id": MEDIA_ID,
        "expected_bytes": len(PAYLOAD),
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "reference_path": str(reference),
        "provenance": "captured before Telegram upload; user supplied",
    }), encoding="utf-8")
    different_payload = b"X" + PAYLOAD[1:]
    gateway = FakeV2Gateway(different_payload)

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        app = SingleMediaDownloadApplication(repository, gateway, root)
        with pytest.raises(DownloadError) as error:
            await app.download(
                CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="TRUSTED_REFERENCE",
                reference_manifest_path=manifest, plan_id="mismatch-plan",
                invocation_id="mismatch-invocation",
            )
        record = await repository.get_record(candidate.media_item_id)
        attempt = await repository.get_latest_v2_attempt(candidate.media_item_id)
        final, partial = destination_paths(root, candidate)
        return error.value.category, record, attempt, final, partial

    category, record, attempt, final, partial = asyncio.run(exercise())
    assert category == "REFERENCE_MISMATCH"
    assert record.state == "FAILED_RETRYABLE"
    assert record.state not in {"VALIDATED", "FINALIZATION_PENDING", "COMPLETED_V2"}
    assert attempt["status"] == "BLOCKED"
    assert not final.exists()
    assert partial.read_bytes() == different_payload


@pytest.mark.parametrize("manifest_kind", ["absent", "divergent_sha256"])
def test_trusted_reference_rejects_missing_or_divergent_manifest(
    tmp_path, monkeypatch, manifest_kind
) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    reference = tmp_path / "trusted.bin"
    reference.write_bytes(PAYLOAD)
    manifest = tmp_path / "trusted.json"
    if manifest_kind == "divergent_sha256":
        manifest.write_text(json.dumps({
            "schema_version": 1,
            "channel_id": CHANNEL_ID,
            "telegram_message_id": MESSAGE_ID,
            "media_ordinal": 0,
            "telegram_media_id": MEDIA_ID,
            "expected_bytes": len(PAYLOAD),
            "sha256": hashlib.sha256(b"different").hexdigest(),
            "reference_path": str(reference),
            "provenance": "captured before Telegram upload; user supplied",
        }), encoding="utf-8")
    gateway = FakeV2Gateway()

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        app = SingleMediaDownloadApplication(repository, gateway, root)
        selected_manifest = None if manifest_kind == "absent" else manifest
        with pytest.raises(DownloadError) as error:
            await app.download(
                CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="TRUSTED_REFERENCE",
                reference_manifest_path=selected_manifest,
            )
        return repository, candidate, error.value.category

    repository, candidate, category = asyncio.run(exercise())
    assert category == ("REFERENCE_ABSENT" if manifest_kind == "absent" else "REFERENCE_INVALID")
    assert gateway.identity_calls == 0
    assert gateway.stream_calls == []
    assert gateway.hash_calls == 0

    async def check_blocked_attempt():
        return await repository.get_latest_v2_attempt(candidate.media_item_id)

    attempt = asyncio.run(check_blocked_attempt())
    assert attempt["status"] == "BLOCKED"


def test_v2_recovers_after_rename_before_completion_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "files"
    gateway = FakeV2Gateway()

    class SimulatedProcessInterruption(BaseException):
        pass

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        app = SingleMediaDownloadApplication(repository, gateway, root)
        complete_v2 = repository.complete_v2

        async def interrupt_after_rename(*args, **kwargs):
            raise SimulatedProcessInterruption

        repository.complete_v2 = interrupt_after_rename
        with pytest.raises(SimulatedProcessInterruption):
            await app.download(
                CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY",
                invocation_id="interrupted-invocation",
            )
        final, _partial = destination_paths(root, candidate)
        assert final.read_bytes() == PAYLOAD
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "UPDATE downloads SET owner_pid=? WHERE media_item_id=?",
                (2147483647, candidate.media_item_id),
            )
            await db.commit()
        repository.complete_v2 = complete_v2
        outcome = await app.download(
            CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY",
            invocation_id="recovery-invocation",
        )
        record = await repository.get_record(candidate.media_item_id)
        return outcome, record

    outcome, record = asyncio.run(exercise())
    assert outcome.result == "RECOVERED_V2"
    assert record.state == "COMPLETED_V2"
    assert gateway.stream_calls == [0]


def test_budget_block_happens_before_any_gateway_call(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "files"
    gateway = FakeV2Gateway()

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        item = PlanItem((CHANNEL_ID, MESSAGE_ID, 0), candidate, "PENDING", estimated_payload_bytes=len(PAYLOAD))
        plan = DownloadPlan("plan-budget", DownloadSelection(CHANNEL_ID), "channel", True, 1, (item,))
        app = SingleMediaDownloadApplication(repository, gateway, root)
        queue = DownloadQueue(
            repository, app, workers=1, attempts_per_media=3,
            free_space=lambda _path: 10**12, max_transfer_bytes=len(PAYLOAD),
            integrity_mode="OPERATIONAL_ONLY",
        )
        result = await queue.run(plan)
        return result

    result = asyncio.run(exercise())
    assert result.outcomes[0][1:] == ("BLOCKED", "BUDGET_BLOCK")
    assert gateway.identity_calls == 0
    assert gateway.stream_calls == []
    assert gateway.hash_calls == 0


def test_remote_hash_unavailable_retries_within_s5_then_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"

    class UnavailableHashGateway(FakeV2Gateway):
        async def get_file_hashes(self, *args, **kwargs):
            self.hash_calls += 1
            raise DownloadGatewayError("GATEWAY_FAILURE")

    gateway = UnavailableHashGateway()

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        item = PlanItem(
            (CHANNEL_ID, MESSAGE_ID, 0), candidate, "PENDING",
            estimated_payload_bytes=len(PAYLOAD),
        )
        plan = DownloadPlan("plan-hash-unavailable", DownloadSelection(CHANNEL_ID), "channel", True, 1, (item,))
        app = SingleMediaDownloadApplication(repository, gateway, root)
        queue = DownloadQueue(
            repository, app, workers=1, attempts_per_media=3,
            free_space=lambda _path: 10**12,
            max_transfer_bytes=3 * 256 * 1024,
            integrity_mode="OPERATIONAL_ONLY",
        )
        result = await queue.run(plan)
        attempt = await repository.get_latest_v2_attempt(candidate.media_item_id)
        return result, attempt

    result, attempt = asyncio.run(exercise())
    assert result.attempts == 3
    assert result.outcomes[0][1:] == ("BLOCKED", "REMOTE_HASH_UNAVAILABLE")
    assert gateway.hash_calls == 3
    assert attempt["status"] == "BLOCKED"
    assert attempt["remote_hash_class"] == "REMOTE_HASH_UNAVAILABLE"
    assert attempt["requests"] >= 3
    assert attempt["bytes_reserved"] == downloads.CHUNK_BYTES
    assert attempt["bytes_received"] == len(PAYLOAD)
    failure_details = json.loads(attempt["details_json"])
    assert failure_details["remote_hash_events"] == [
        {"class": "REMOTE_HASH_UNAVAILABLE"}
    ]


def test_later_malformed_hash_page_does_not_hide_prior_divergence(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"

    class DivergentThenMalformedGateway(FakeV2Gateway):
        async def get_file_hashes(
            self, channel_id, message_id, media_ordinal, *, telegram_media_id,
            expected_bytes, offset=0,
        ):
            self.hash_calls += 1
            assert (channel_id, message_id, media_ordinal) == (CHANNEL_ID, MESSAGE_ID, 0)
            assert telegram_media_id == MEDIA_ID
            assert expected_bytes == len(PAYLOAD)
            if offset == 0:
                return (RemoteFileHash(0, 4, hashlib.sha256(b"nope").digest()),)
            return (object(),)

    gateway = DivergentThenMalformedGateway()

    async def exercise():
        repository = await seed_database(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        assert candidate is not None
        app = SingleMediaDownloadApplication(repository, gateway, root)
        with pytest.raises(DownloadError) as error:
            await app.download(
                CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY",
                invocation_id="divergent-then-malformed",
            )
        attempt = await repository.get_latest_v2_attempt(candidate.media_item_id)
        return error.value, attempt

    error, attempt = asyncio.run(exercise())
    assert error.category == "BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE"
    assert gateway.hash_calls == 2
    assert attempt["status"] == "BLOCKED"
    assert attempt["requests"] >= 4
    assert attempt["bytes_reserved"] == downloads.CHUNK_BYTES
    assert attempt["bytes_received"] == len(PAYLOAD)
    assert attempt["remote_hash_class"] == "BLOCKED_CONTRADICTORY_REMOTE_EVIDENCE"
    recorded_classes = {
        event["class"] for event in json.loads(attempt["details_json"])["remote_hash_events"]
    }
    assert "REMOTE_HASH_DIVERGENT" in recorded_classes
    assert "REMOTE_HASH_INVALID_RESPONSE" in recorded_classes


def test_default_v1_queue_blocks_completed_v2_operational_only_without_gateway_calls(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(downloads, "V2_EFFECTIVE", True)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    v2_gateway = FakeV2Gateway()

    class NeverGateway:
        calls = 0

        async def stream_media(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("V1 queue must not contact the gateway for a V2-only record")

        async def validate_media_identity(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("V1 queue must not contact the gateway for a V2-only record")

        async def get_file_hashes(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("V1 queue must not contact the gateway for a V2-only record")

    v1_gateway = NeverGateway()

    async def exercise():
        repository = await seed_database(database)
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,"
                "started_at,finished_at,source_message_count,catalog_node_count,unresolved_count) "
                "VALUES('test-catalog-run',?,'test-parser','test-v1','COMPLETE','now','now',1,1,0)",
                (CHANNEL_ID,),
            )
            await db.commit()
        v2_app = SingleMediaDownloadApplication(repository, v2_gateway, root)
        created = await v2_app.download(
            CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY",
            plan_id="v2-only-plan", invocation_id="v2-only-invocation",
        )
        planner = DownloadPlanner(database, root)
        plan = await planner.build(DownloadSelection(CHANNEL_ID))
        v1_app = SingleMediaDownloadApplication(repository, v1_gateway, root)
        queue = DownloadQueue(repository, v1_app, workers=1)
        result = await queue.run(plan)
        return created, plan, result

    created, plan, result = asyncio.run(exercise())
    assert created.result == "COMPLETED_V2"
    assert plan.eligible[0].status == "COMPLETED_V2"
    assert result.failed == 1
    assert result.outcomes[0][1] == "BLOCKED"
    assert result.outcomes[0][2] is not None
    assert v1_gateway.calls == 0


def test_additive_migration_leaves_v1_downloaded_rows_unchanged(tmp_path) -> None:
    database = tmp_path / "legacy.sqlite3"
    final_path = tmp_path / "historical-a.bin"
    historical_bytes = b"A" * len(PAYLOAD)
    final_path.write_bytes(historical_bytes)
    historical_sha256 = hashlib.sha256(historical_bytes).hexdigest()

    async def exercise():
        from importlib.resources import files
        async with aiosqlite.connect(database) as db:
            for version, migration_name in (
                (1, "001_initial.sql"),
                (2, "002_catalog.sql"),
                (3, "003_catalog_unresolved.sql"),
                (4, "004_downloads.sql"),
                (5, "005_s6_integrity_v2.sql"),
            ):
                migration_sql = files("telegram_courses").joinpath(
                    f"migrations/{migration_name}"
                ).read_text(encoding="utf-8")
                for statement in migration_sql.split(";"):
                    if statement.strip():
                        await db.execute(statement)
                await db.execute(
                    "INSERT INTO schema_migrations(version,applied_at) VALUES(?, 'now')",
                    (version,),
                )
            await db.execute(
                "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(?,?,?,?)",
                (CHANNEL_ID, "channel", "now", "now"),
            )
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) VALUES(?,?,?,?,?)",
                (CHANNEL_ID, MESSAGE_ID, "2026-10-17T00:00:00Z", "now", "now"),
            )
            await db.execute(
                "INSERT INTO catalog_nodes(channel_id,kind,title,source_message_id,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (CHANNEL_ID, "lesson", "Lesson", MESSAGE_ID, "now", "now"),
            )
            lesson_id = (await (await db.execute("SELECT id FROM catalog_nodes")).fetchone())[0]
            await db.execute(
                "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (CHANNEL_ID, MESSAGE_ID, 0, lesson_id, "DOCUMENT", "media-b", "lesson.bin", len(historical_bytes), "now", "now"),
            )
            media_item_id = (await (await db.execute("SELECT id FROM media_items")).fetchone())[0]
            await db.execute(
                "INSERT INTO downloads(media_item_id,state,final_path,expected_bytes,downloaded_bytes,attempts,created_at,updated_at,sha256) VALUES(?,'DOWNLOADED',?,?,?,1,'now','now',?)",
                (media_item_id, str(final_path), len(historical_bytes), len(historical_bytes), historical_sha256),
            )
            await db.execute(
                "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,source_message_count,catalog_node_count,unresolved_count) VALUES('legacy-catalog',?,'generic','generic-v1','COMPLETE','now','now',1,1,0)",
                (CHANNEL_ID,),
            )
            await db.commit()
        async with aiosqlite.connect(database) as db:
            legacy = tuple(await (await db.execute(
                "SELECT state,final_path,expected_bytes,downloaded_bytes,sha256 FROM downloads WHERE media_item_id=?",
                (media_item_id,),
            )).fetchone())
            migration_006 = files("telegram_courses").joinpath(
                "migrations/006_s7_incremental_sync.sql"
            ).read_text(encoding="utf-8")
            await db.execute("BEGIN IMMEDIATE")
            for statement in migration_006.split(";"):
                if statement.strip():
                    await db.execute(statement)
            await db.execute(
                "INSERT INTO schema_migrations(version,applied_at) VALUES(6,'now')"
            )
            await db.commit()
        pre_007_plan = await DownloadPlanner(database, tmp_path / "downloads").build(
            DownloadSelection(CHANNEL_ID)
        )
        assert pre_007_plan.blocked[0].reason == "SCHEMA_MIGRATION_REQUIRED"
        repository = DownloadRepository(database)
        await repository.migrate()
        after = await repository.get_record(media_item_id)
        async with aiosqlite.connect(database) as db:
            versions = await (await db.execute("SELECT version FROM schema_migrations ORDER BY version")).fetchall()
            evidence_count = await (await db.execute("SELECT COUNT(*) FROM s6_v2_evidence")).fetchone()
            snapshot = await (await db.execute(
                "SELECT remote_identity_media_id,remote_identity_kind,remote_identity_size,remote_identity_provenance "
                "FROM downloads WHERE media_item_id=?", (media_item_id,),
            )).fetchone()
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        assert candidate is not None
        partial_path = final_path.with_suffix(".part")
        record_before_resume = await repository.get_record(media_item_id)
        with pytest.raises(ValueError, match="RESUME_IDENTITY_MISMATCH"):
            await repository.start_resume(candidate, final_path, partial_path)
        assert await repository.get_record(media_item_id) == record_before_resume == after
        assert final_path.read_bytes() == historical_bytes
        assert not partial_path.exists()
        plan = await DownloadPlanner(database, tmp_path / "downloads").build(
            DownloadSelection(CHANNEL_ID)
        )
        with pytest.raises(ValueError, match="RESUME_IDENTITY_MISMATCH"):
            await repository.start(candidate, final_path, final_path.with_suffix(".part"))

        class NeverGateway:
            calls = 0

            async def stream_media(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("legacy identity must block before gateway")
                yield b""

            async def get_file_hashes(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("legacy identity must block before gateway")

        gateway = NeverGateway()
        with pytest.raises(DownloadError) as error:
            await SingleMediaDownloadApplication(
                repository, gateway, tmp_path / "downloads"
            ).download(CHANNEL_ID, MESSAGE_ID, 0)
        assert error.value.category == "RESUME_IDENTITY_MISMATCH"
        return legacy, after, versions, evidence_count[0], snapshot, plan, gateway.calls

    legacy, after, versions, evidence_count, snapshot, plan, gateway_calls = asyncio.run(exercise())
    assert legacy[0] == after.state == "DOWNLOADED"
    assert legacy[1] == after.final_path == str(final_path)
    assert legacy[2] == after.expected_bytes == len(historical_bytes)
    assert legacy[3] == after.downloaded_bytes == len(historical_bytes)
    assert legacy[4] == after.sha256 == historical_sha256
    assert snapshot == ("media-b", "DOCUMENT", len(historical_bytes), "UNKNOWN_LEGACY")
    assert plan.blocked[0].reason == "IDENTITY_SNAPSHOT_UNVERIFIED"
    assert final_path.read_bytes() == historical_bytes
    assert [version[0] for version in versions] == [1, 2, 3, 4, 5, 6, 7]
    assert evidence_count == 0
    assert gateway_calls == 0
