from __future__ import annotations

import asyncio
import hashlib

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

    async def restore(self):
        return AuthState.AUTHENTICATED

    async def stream_media(self, channel_id, message_id, ordinal, *, telegram_media_id, expected_bytes):
        assert (channel_id, message_id, ordinal) == (CHANNEL_ID, MESSAGE_ID, 0)
        assert telegram_media_id == "synthetic-media"
        assert expected_bytes == len(PAYLOAD)
        self.calls += 1
        for chunk in self.chunks:
            yield chunk

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
    assert version == 4


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
