from __future__ import annotations

import asyncio
import hashlib
import sys

import aiosqlite
import pytest

from telegram_courses.auth import AuthState
from telegram_courses.cli import main
from telegram_courses.config import TelegramCredentials
from telegram_courses.download_repository import (
    DownloadInProgress,
    DownloadRepository,
)
from telegram_courses.downloads import (
    DownloadError,
    DownloadGatewayError,
    SingleMediaDownloadApplication,
)

PAYLOAD = b"synthetic lesson media"
CHANNEL_ID = -100100
MESSAGE_ID = 73


class FakeGateway:
    def __init__(self, chunks=None):
        self.chunks = chunks if chunks is not None else (PAYLOAD[:7], PAYLOAD[7:])
        self.calls = 0
        self.hash_calls = 0

    async def restore(self):
        return AuthState.AUTHENTICATED

    async def stream_media(self, channel_id, message_id, ordinal, *, telegram_media_id, expected_bytes, offset=0, reserve_chunk=None):
        assert (channel_id, message_id, ordinal) == (CHANNEL_ID, MESSAGE_ID, 0)
        assert telegram_media_id == "synthetic-media"
        assert expected_bytes == len(PAYLOAD)
        assert callable(reserve_chunk)
        self.calls += 1
        payload = b"".join(self.chunks)[offset:]
        if payload:
            yield payload

    async def get_file_hashes(self, channel_id, message_id, ordinal, *, telegram_media_id, expected_bytes, offset=0):
        from telegram_courses.downloads import RemoteFileHash

        self.hash_calls += 1
        if self.hash_calls == 1:
            size = getattr(self, "prefix_size", expected_bytes)
        else:
            size = expected_bytes
        return (RemoteFileHash(0, size, hashlib.sha256(PAYLOAD[:size]).digest()),) if size else ()

    async def close(self):
        pass


async def seed_lesson(path) -> None:
    repository = DownloadRepository(path)
    await repository.migrate()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) VALUES(?,?,?,?)",
            (CHANNEL_ID, "Synthetic channel", "now", "now"),
        )
        await db.execute(
            "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) VALUES(?,?,?,?,?)",
            (CHANNEL_ID, MESSAGE_ID, "2026-01-01T00:00:00+00:00", "now", "now"),
        )
        await db.execute(
            "INSERT INTO catalog_nodes(channel_id,kind,title,source_message_id,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (CHANNEL_ID, "lesson", "Synthetic lesson", MESSAGE_ID, "now", "now"),
        )
        lesson_id = (await (await db.execute("SELECT id FROM catalog_nodes")).fetchone())[0]
        await db.execute(
            "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,catalog_node_id,kind,telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (CHANNEL_ID, MESSAGE_ID, 0, lesson_id, "DOCUMENT", "synthetic-media", "lesson.bin", len(PAYLOAD), "now", "now"),
        )
        await db.commit()


def test_offline_download_rerun_is_deduplicated(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    gateway = FakeGateway()

    async def exercise():
        await seed_lesson(database)
        app = SingleMediaDownloadApplication(DownloadRepository(database), gateway, root)
        first = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        second = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return first, second

    first, second = asyncio.run(exercise())
    assert first.result == "DOWNLOADED"
    assert first.final_path.read_bytes() == PAYLOAD
    assert first.sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert second.result == "ALREADY_DOWNLOADED"
    assert gateway.calls == 1

    async def verify():
        async with aiosqlite.connect(database) as db:
            rows = await (await db.execute("SELECT state,downloaded_bytes,sha256 FROM downloads")).fetchall()
            version = await (await db.execute("SELECT MAX(version) FROM schema_migrations")).fetchone()
            return rows, version[0]

    rows, version = asyncio.run(verify())
    assert rows == [("DOWNLOADED", len(PAYLOAD), hashlib.sha256(PAYLOAD).hexdigest())]
    assert version == 7


def test_reconciles_rename_before_sqlite_completion_without_stream(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    gateway = FakeGateway()

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        from telegram_courses.downloads import destination_paths

        final, partial = destination_paths(root, candidate)
        final.parent.mkdir(parents=True)
        final.write_bytes(PAYLOAD)
        await repository.start(candidate, final, partial)
        await repository.transition(candidate.media_item_id, "VALIDATED", downloaded_bytes=len(PAYLOAD), sha256=hashlib.sha256(PAYLOAD).hexdigest())
        await repository.transition(candidate.media_item_id, "FINALIZATION_PENDING", downloaded_bytes=len(PAYLOAD))
        app = SingleMediaDownloadApplication(repository, gateway, root)
        outcome = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return outcome

    outcome = asyncio.run(exercise())
    assert outcome.result == "RECOVERED"
    assert gateway.calls == 0


def test_rejects_ineligible_media_before_stream(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway()

    async def exercise():
        await seed_lesson(database)
        async with aiosqlite.connect(database) as db:
            await db.execute("UPDATE catalog_nodes SET kind='unclassified'")
            await db.commit()
        app = SingleMediaDownloadApplication(DownloadRepository(database), gateway, tmp_path / "downloads")
        with pytest.raises(DownloadError, match="media not eligible"):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0)

    asyncio.run(exercise())
    assert gateway.calls == 0


def test_wrong_size_is_failed_and_never_finalized(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway(chunks=(PAYLOAD[:-1],))

    async def exercise():
        await seed_lesson(database)
        app = SingleMediaDownloadApplication(DownloadRepository(database), gateway, tmp_path / "downloads")
        with pytest.raises(DownloadError, match="size mismatch"):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0)

    asyncio.run(exercise())
    assert list((tmp_path / "downloads").rglob("*.part"))
    assert not [path for path in (tmp_path / "downloads").rglob("*") if path.is_file() and not path.name.endswith(".part")]


def test_cli_repeat_avoids_gateway_construction_after_local_dedup(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    gateway = FakeGateway()
    asyncio.run(seed_lesson(database))
    args = [
        "download", "--channel-id", str(CHANNEL_ID), "--telegram-message-id",
        str(MESSAGE_ID), "--media-ordinal", "0", "--database", str(database),
        "--download-dir", str(root),
    ]
    def credentials():
        return TelegramCredentials(123, "synthetic-api-hash")
    assert main(args, download_gateway_factory=lambda _credentials: gateway, credentials_loader=credentials) == 0

    def fail_if_constructed(_credentials):
        raise AssertionError("deduplicated run must not construct a Telegram gateway")

    assert main(args, download_gateway_factory=fail_if_constructed, credentials_loader=credentials) == 0
    assert gateway.calls == 1


def test_sqlite_owner_lease_rejects_second_active_transfer(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final = tmp_path / "downloads" / "lesson.bin"
        partial = final.with_name(final.name + ".part")
        await repository.start(candidate, final, partial)
        with pytest.raises(DownloadInProgress):
            await repository.start(candidate, final, partial)

    asyncio.run(exercise())


def test_failure_after_rename_is_reconciled_without_second_stream(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    gateway = FakeGateway()

    class FailDownloadedCommitOnce(DownloadRepository):
        def __init__(self, database_path):
            super().__init__(database_path)
            self.fail_commit = True

        async def transition(self, media_item_id, state, **kwargs):
            if state == "DOWNLOADED" and self.fail_commit:
                self.fail_commit = False
                raise OSError("synthetic database failure")
            await super().transition(media_item_id, state, **kwargs)

    async def exercise():
        await seed_lesson(database)
        repository = FailDownloadedCommitOnce(database)
        app = SingleMediaDownloadApplication(repository, gateway, root)
        with pytest.raises(DownloadError, match="state commit pending"):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        second = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return second

    outcome = asyncio.run(exercise())
    assert outcome.result == "RECOVERED"
    assert gateway.calls == 1


@pytest.mark.parametrize("checkpoint", (2, len(PAYLOAD) + 5))
def test_resume_validates_prefix_compares_overlap_and_appends_without_rewrite(tmp_path, checkpoint) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    gateway = FakeGateway(chunks=(PAYLOAD,))
    gateway.prefix_size = 9

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        from telegram_courses.downloads import destination_paths

        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(PAYLOAD[:9])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=checkpoint,
            failure_category="NETWORK",
        )
        app = SingleMediaDownloadApplication(repository, gateway, root)
        result = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return result, partial, final, await repository.get_record(candidate.media_item_id)

    result, partial, final, record = asyncio.run(exercise())
    assert result.result == "DOWNLOADED"
    assert result.transferred_bytes == len(PAYLOAD)
    assert final.read_bytes() == PAYLOAD
    assert not partial.exists()
    assert record.state == "DOWNLOADED"
    assert record.downloaded_bytes == len(PAYLOAD)
    assert gateway.hash_calls == 2
    assert gateway.calls == 1


def test_unaligned_operational_resume_reuses_boundary_suffix_then_appends(tmp_path, monkeypatch) -> None:
    import telegram_courses.downloads as downloads_module

    payload = bytes((index % 251 for index in range(1_572_987)))
    monkeypatch.setattr(sys.modules[__name__], "PAYLOAD", payload)
    monkeypatch.setattr(downloads_module, "V2_EFFECTIVE", True)
    prefix_bytes = 1_048_699
    wire_offset = 1_048_576
    transfer_offset = 1_310_720

    class SyntheticGateway:
        def __init__(self):
            self.offsets = []

        async def restore(self):
            return AuthState.AUTHENTICATED

        async def validate_media_identity(self, *_args, **_kwargs):
            return True

        async def get_file_hashes(
            self, *_args, expected_bytes, offset=0, **_kwargs,
        ):
            from telegram_courses.downloads import RemoteFileHash

            ranges = []
            for start in range(0, expected_bytes, 256 * 1024):
                block = payload[start:min(start + 256 * 1024, expected_bytes)]
                ranges.append(RemoteFileHash(start, len(block), hashlib.sha256(block).digest()))
            return tuple(item for item in ranges if item.offset >= offset)

        async def stream_media(
            self, *_args, expected_bytes, offset=0, reserve_chunk=None, **_kwargs,
        ):
            assert expected_bytes == len(payload)
            assert callable(reserve_chunk)
            self.offsets.append(offset)
            for start in range(offset, expected_bytes, 256 * 1024):
                block = payload[start:min(start + 256 * 1024, expected_bytes)]
                reservation = await reserve_chunk(len(block))
                if reservation is None:
                    raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
                reservation.received(len(block))
                yield block

        async def close(self):
            pass

    gateway = SyntheticGateway()
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        from telegram_courses.downloads import destination_paths

        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(payload[:prefix_bytes])
        await repository.start(candidate, final, partial)
        await repository.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=prefix_bytes,
            failure_category="NETWORK",
        )
        app = SingleMediaDownloadApplication(repository, gateway, root)
        result = await app.download(
            CHANNEL_ID, MESSAGE_ID, 0, integrity_mode="OPERATIONAL_ONLY",
        )
        record = await repository.get_record(candidate.media_item_id)
        return result, record, partial, final

    result, record, partial, final = asyncio.run(exercise())
    expected_digest = hashlib.sha256(payload).hexdigest()
    assert result.result == "COMPLETED_V2"
    assert result.sha256 == expected_digest
    assert final.read_bytes() == payload
    assert hashlib.sha256(final.read_bytes()).hexdigest() == expected_digest
    assert not partial.exists()
    assert record.state == "COMPLETED_V2"
    assert record.downloaded_bytes == len(payload)
    assert gateway.offsets[-2:] == [0, transfer_offset]
    assert wire_offset == 1_048_576


def test_resume_overlap_mismatch_preserves_partial_and_never_finalizes(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    corrupted_stream = b"X" * 9 + PAYLOAD[9:]
    gateway = FakeGateway(chunks=(corrupted_stream,))
    gateway.prefix_size = 9

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        from telegram_courses.downloads import destination_paths

        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        original = PAYLOAD[:9]
        partial.write_bytes(original)
        await repository.start(candidate, final, partial)
        await repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=9, failure_category="NETWORK")
        app = SingleMediaDownloadApplication(repository, gateway, root)
        with pytest.raises(DownloadError, match="overlap mismatch"):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return partial, final

    partial, final = asyncio.run(exercise())
    assert partial.read_bytes() == PAYLOAD[:9]
    assert not final.exists()


def test_gateway_interruption_persists_failure_and_keeps_only_partial(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"

    class InterruptedGateway(FakeGateway):
        async def stream_media(self, *args, **kwargs):
            self.calls += 1
            yield PAYLOAD[:4]
            raise DownloadGatewayError("NETWORK")

    gateway = InterruptedGateway()

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        app = SingleMediaDownloadApplication(repository, gateway, tmp_path / "downloads")
        with pytest.raises(DownloadError, match="network"):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        record = await repository.get_record(candidate.media_item_id)
        return record

    record = asyncio.run(exercise())
    assert record.state == "FAILED_RETRYABLE"
    assert record.downloaded_bytes == 4
    assert record.failure_category == "NETWORK"
    assert list((tmp_path / "downloads").rglob("*.part"))
    assert not [path for path in (tmp_path / "downloads").rglob("*") if path.is_file() and not path.name.endswith(".part")]


def test_hash_divergence_is_not_deduplicated_or_overwritten(tmp_path) -> None:
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    gateway = FakeGateway()

    async def exercise():
        await seed_lesson(database)
        app = SingleMediaDownloadApplication(DownloadRepository(database), gateway, root)
        first = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        first.final_path.write_bytes(b"foreign divergent content")
        with pytest.raises(DownloadError, match="downloaded file mismatch"):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return first.final_path.read_bytes()

    assert asyncio.run(exercise()) == b"foreign divergent content"
    assert gateway.calls == 1


class BoundaryGateway:
    def __init__(self, payload, limits, *, corruption=None, short_stream=False, fail_stream=False):
        self.payload = payload
        self.limits = limits
        self.corruption = corruption
        self.short_stream = short_stream
        self.fail_stream = fail_stream
        self.offsets = []
        self.received = 0
        self.hash_calls = 0

    async def get_file_hashes(self, *_args, offset=0, **_kwargs):
        from telegram_courses.downloads import RemoteFileHash

        self.hash_calls += 1
        ranges = []
        start = 0
        for size in self.limits:
            ranges.append(RemoteFileHash(
                start, size, hashlib.sha256(self.payload[start:start + size]).digest(),
            ))
            start += size
        return tuple(item for item in ranges if item.offset >= offset)

    async def stream_media(self, *_args, offset=0, reserve_chunk=None, **_kwargs):
        assert callable(reserve_chunk)
        assert offset % (256 * 1024) == 0
        self.offsets.append(offset)
        data = self.corruption if self.corruption is not None else self.payload
        end = 131073 if self.short_stream else len(data)
        for start in range(offset, end, 64 * 1024):
            reservation = await reserve_chunk(256 * 1024)
            if reservation is None:
                raise DownloadGatewayError("TRANSFER_BUDGET_EXHAUSTED")
            if self.fail_stream:
                reservation.charge_uncertain()
                raise DownloadGatewayError("NETWORK")
            chunk = data[start:min(start + 64 * 1024, end)]
            reservation.received(len(chunk))
            self.received += len(chunk)
            yield chunk


@pytest.mark.parametrize("prefix", (0, 400001, 131072, 262144, 1, 131071, 131073, 262143, 262145, 400000))
@pytest.mark.parametrize("limits", ((131072, 131072, 137857), (70000, 90000, 120000, 120001)))
def test_resume_prefix_boundary_matrix(tmp_path, monkeypatch, prefix, limits) -> None:
    import telegram_courses.downloads as downloads_module

    payload = bytes(range(251)) * 1593 + b"tail"  # 399847 bytes
    payload = payload + b"x" * (400001 - len(payload))
    monkeypatch.setattr(sys.modules[__name__], "PAYLOAD", payload)
    gateway = BoundaryGateway(payload, limits)
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = downloads_module.destination_paths(root, candidate)
        if prefix:
            partial.parent.mkdir(parents=True)
            partial.write_bytes(payload[:prefix])
            await repository.start(candidate, final, partial)
            await repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=prefix, failure_category="NETWORK")
        counted = []
        app = SingleMediaDownloadApplication(repository, gateway, root, chunk_callback=counted.append)
        outcome = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return outcome, counted

    outcome, counted = asyncio.run(exercise())
    assert outcome.result == "DOWNLOADED"
    assert outcome.final_path.read_bytes() == payload
    assert sum(counted) == gateway.received
    assert gateway.offsets[-1] == (prefix // (256 * 1024)) * (256 * 1024)
    assert gateway.hash_calls == (2 if prefix else 0)
    crossing = any(sum(limits[:i]) < prefix < sum(limits[:i + 1]) for i in range(len(limits)))
    assert len(gateway.offsets) == (2 if crossing else 1)
    assert outcome.transferred_bytes == gateway.received


@pytest.mark.parametrize("failure", ("corrupt", "short", "hash", "gap", "overlap", "unaligned", "budget", "network"))
def test_prefix_proof_failure_preserves_partial(tmp_path, monkeypatch, failure) -> None:
    import telegram_courses.downloads as downloads_module

    payload = bytes(range(251)) * 1593 + b"x" * (400001 - 251 * 1593)
    monkeypatch.setattr(sys.modules[__name__], "PAYLOAD", payload)
    prefix = 131073
    original = bytearray(payload[:prefix])
    if failure == "corrupt":
        original[17] ^= 1
    gateway = BoundaryGateway(payload, (131072, 131072, len(payload) - 262144), short_stream=failure == "short", fail_stream=failure == "network")
    if failure in {"hash", "gap", "overlap", "unaligned"}:
        original_hashes = gateway.get_file_hashes

        async def bad_hashes(*args, **kwargs):
            from telegram_courses.downloads import RemoteFileHash

            ranges = list(await original_hashes(*args, **kwargs))
            if failure == "hash":
                ranges[1] = RemoteFileHash(ranges[1].offset, ranges[1].limit, b"z" * 32)
            elif failure == "gap":
                ranges[1] = RemoteFileHash(131073, 131071, ranges[1].sha256)
            elif failure == "overlap":
                ranges[1] = RemoteFileHash(131071, 131073, ranges[1].sha256)
            else:
                ranges[0] = RemoteFileHash(1, 131071, ranges[0].sha256)
            return tuple(ranges)

        gateway.get_file_hashes = bad_hashes
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = downloads_module.destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(original)
        await repository.start(candidate, final, partial)
        await repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=prefix - 1, failure_category="NETWORK")
        app = SingleMediaDownloadApplication(repository, gateway, root)
        if failure == "budget":
            async def deny(_amount):
                return None
            app.chunk_reserver = deny
        with pytest.raises(DownloadError):
            await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return partial, final, await repository.get_record(candidate.media_item_id)

    partial, final, record = asyncio.run(exercise())
    assert partial.read_bytes() == original
    assert not final.exists()
    assert record.state == "FAILED_RETRYABLE"


@pytest.mark.parametrize("with_cap", (False, True))
def test_prefix_complement_counts_verification_and_continuation_once(tmp_path, monkeypatch, with_cap) -> None:
    import telegram_courses.downloads as downloads_module

    payload = bytes(range(251)) * 1593 + b"x" * (400001 - 251 * 1593)
    monkeypatch.setattr(sys.modules[__name__], "PAYLOAD", payload)
    prefix = 131073
    gateway = BoundaryGateway(payload, (131072, 131072, len(payload) - 262144))
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    charged = []

    class Reservation:
        def __init__(self, amount):
            self.amount = amount

        def received(self, size):
            assert 0 < size <= self.amount
            charged.append(size)

        def release(self):
            pass

        def charge_uncertain(self):
            charged.append(self.amount)

    async def reserve(amount):
        if sum(charged) + amount > 2 * len(payload) + 256 * 1024:
            return None
        return Reservation(amount)

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = downloads_module.destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(payload[:prefix])
        await repository.start(candidate, final, partial)
        await repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=prefix, failure_category="NETWORK")
        counted = []
        app = SingleMediaDownloadApplication(repository, gateway, root, chunk_callback=counted.append)
        if with_cap:
            app.chunk_reserver = reserve
        outcome = await app.download(CHANNEL_ID, MESSAGE_ID, 0)
        return outcome, counted

    outcome, counted = asyncio.run(exercise())
    verification_bytes = 262144
    continuation_bytes = len(payload)
    assert gateway.offsets == [0, 0]
    assert gateway.received == verification_bytes + continuation_bytes
    assert sum(counted) == outcome.transferred_bytes == gateway.received
    if with_cap:
        assert sum(charged) == gateway.received


def test_failed_prefix_proof_can_restart_without_rewriting_partial(tmp_path, monkeypatch) -> None:
    import telegram_courses.downloads as downloads_module

    payload = bytes(range(251)) * 1593 + b"x" * (400001 - 251 * 1593)
    monkeypatch.setattr(sys.modules[__name__], "PAYLOAD", payload)
    prefix = 131073
    database = tmp_path / "catalog.sqlite3"
    root = tmp_path / "downloads"
    limits = (131072, 131072, len(payload) - 262144)

    async def exercise():
        await seed_lesson(database)
        repository = DownloadRepository(database)
        candidate = await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0)
        final, partial = downloads_module.destination_paths(root, candidate)
        partial.parent.mkdir(parents=True)
        partial.write_bytes(payload[:prefix])
        await repository.start(candidate, final, partial)
        await repository.transition(candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=prefix, failure_category="NETWORK")
        first = SingleMediaDownloadApplication(repository, BoundaryGateway(payload, limits, short_stream=True), root)
        with pytest.raises(DownloadError, match="remote hashes incomplete"):
            await first.download(CHANNEL_ID, MESSAGE_ID, 0)
        assert partial.read_bytes() == payload[:prefix]
        second = SingleMediaDownloadApplication(DownloadRepository(database), BoundaryGateway(payload, limits), root)
        outcome = await second.download(CHANNEL_ID, MESSAGE_ID, 0)
        return outcome, partial

    outcome, partial = asyncio.run(exercise())
    assert outcome.final_path.read_bytes() == payload
    assert not partial.exists()


@pytest.mark.parametrize("update", [
    "UPDATE media_items SET file_size_bytes=NULL",
    "UPDATE media_items SET kind='PHOTO'",
])
def test_unknown_size_and_non_document_are_ineligible(tmp_path, update) -> None:
    database = tmp_path / "catalog.sqlite3"

    async def exercise():
        await seed_lesson(database)
        async with aiosqlite.connect(database) as db:
            await db.execute(update)
            await db.commit()
        repository = DownloadRepository(database)
        assert await repository.select_candidate(CHANNEL_ID, MESSAGE_ID, 0) is None

    asyncio.run(exercise())
