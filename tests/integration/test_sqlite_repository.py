from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from telegram_courses.auth import AuthState
from telegram_courses.config import TelegramCredentials
from telegram_courses.message_scanner import GatewayMedia, GatewayMessage, ScanStatus
from telegram_courses.scan_application import ScanApplication
from telegram_courses.sqlite_repository import SQLiteMessageRepository

CHAT = -1001234567890


def message(message_id: int, text: str | None, media: tuple[GatewayMedia, ...] = ()):
    return GatewayMessage(CHAT, message_id, "2026-10-09T12:00:00+00:00", None, text, None, media)


def test_migration_idempotence_wal_foreign_keys_and_reopen(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    repository = SQLiteMessageRepository(path)
    async def exercise() -> None:
        await repository.migrate()
        await repository.migrate()
        await repository.start_run(CHAT, 20, "run-1")
        await repository.persist_batch("run-1", (message(20, None),))
        await repository.finish_run("run-1", ScanStatus.COMPLETE, None)
        db = await repository._connect()
        try:
            assert (await (await db.execute("PRAGMA foreign_keys")).fetchone())[0] == 1
            assert (await (await db.execute("PRAGMA journal_mode")).fetchone())[0].lower() == "wal"
            assert (await (await db.execute("SELECT text FROM messages WHERE channel_id=?", (CHAT,))).fetchone())[0] is None
            assert (await (await db.execute("SELECT last_message_id FROM sync_checkpoints WHERE scan_run_id='run-1'")).fetchone())[0] == 20
            versions = await (await db.execute("SELECT version FROM schema_migrations")).fetchall()
            assert [row[0] for row in versions] == [1]
        finally:
            await db.close()

    asyncio.run(exercise())


def test_idempotency_edited_message_and_media_replacement(tmp_path) -> None:
    repository = SQLiteMessageRepository(tmp_path / "catalog.sqlite3")
    async def exercise() -> None:
        await repository.migrate()
        await repository.start_run(CHAT, 10, "run-1")
        doc = GatewayMedia(0, "DOCUMENT", "m-1", "one.pdf", "application/pdf", 12)
        assert await repository.persist_batch("run-1", (message(10, "first", (doc,)),)) == (1, 0)
        assert await repository.persist_batch("run-1", (message(10, "first", (doc,)),)) == (0, 0)
        db = await aiosqlite.connect(repository.database_path)
        media_id = (await (await db.execute("SELECT id FROM media_items")).fetchone())[0]
        await db.close()
        edited = GatewayMedia(0, "PHOTO", "m-2")
        assert await repository.persist_batch("run-1", (message(10, "edited", (edited,)),)) == (0, 1)
        db = await aiosqlite.connect(repository.database_path)
        try:
            assert (await (await db.execute("SELECT text FROM messages WHERE telegram_message_id=10")).fetchone())[0] == "edited"
            assert (await (await db.execute("SELECT kind FROM media_items WHERE telegram_message_id=10")).fetchone())[0] == "PHOTO"
            assert (await (await db.execute("SELECT id FROM media_items WHERE telegram_message_id=10")).fetchone())[0] == media_id
            assert (await (await db.execute("SELECT COUNT(*) FROM messages WHERE telegram_message_id=10")).fetchone())[0] == 1
        finally:
            await db.close()

    asyncio.run(exercise())


def test_failed_batch_rolls_back_messages_and_checkpoint(tmp_path) -> None:
    repository = SQLiteMessageRepository(tmp_path / "catalog.sqlite3")
    async def exercise() -> None:
        await repository.migrate()
        await repository.start_run(CHAT, 10, "run-1")
        bad_media = GatewayMedia(0, "DOCUMENT", "m-1", file_size_bytes=-1)
        with pytest.raises(aiosqlite.IntegrityError):
            await repository.persist_batch("run-1", (message(10, "synthetic", (bad_media,)),))
        db = await aiosqlite.connect(repository.database_path)
        try:
            assert (await (await db.execute("SELECT COUNT(*) FROM messages")).fetchone())[0] == 0
            assert (await (await db.execute("SELECT last_message_id FROM sync_checkpoints WHERE scan_run_id='run-1'")).fetchone())[0] is None
        finally:
            await db.close()

    asyncio.run(exercise())


def test_integrated_fake_gateway_to_sqlite_checkpoint(tmp_path) -> None:
    first = message(10, "synthetic full text", (GatewayMedia(0, "DOCUMENT", "media-10"),))
    second = message(3, None)

    class FakeGateway:
        closed = False

        async def restore(self):
            db = await repository._connect()
            try:
                run = await (await db.execute(
                    "SELECT status, watermark_message_id FROM scan_runs"
                )).fetchone()
                assert tuple(run) == ("RUNNING", None)
            finally:
                await db.close()
            return AuthState.AUTHENTICATED

        async def iter_channel_messages(
            self, telegram_chat_id: int, *, through_message_id: int | None,
            before_message_id: int | None, limit: int,
        ):
            for item in (first, second):
                yield item

        async def close(self):
            self.closed = True

    gateway = FakeGateway()
    repository = SQLiteMessageRepository(tmp_path / "integrated.sqlite3")
    application = ScanApplication(
        lambda _credentials: gateway,
        lambda: TelegramCredentials(7, "synthetic-hash"),
        repository,
    )

    async def exercise():
        from telegram_courses.message_scanner import ScanRequest

        return await application.scan(CHAT, ScanRequest(10, 2))

    outcome = asyncio.run(exercise())
    assert outcome.status is ScanStatus.COMPLETE
    assert gateway.closed

    async def verify() -> None:
        db = await repository._connect()
        try:
            rows = await (await db.execute(
                "SELECT telegram_message_id, text FROM messages ORDER BY telegram_message_id DESC"
            )).fetchall()
            assert [tuple(row) for row in rows] == [(10, "synthetic full text"), (3, None)]
            checkpoint = await (await db.execute(
                "SELECT watermark_message_id, last_message_id, status FROM sync_checkpoints"
            )).fetchone()
            assert tuple(checkpoint) == (10, 3, "COMPLETE")
            assert (await (await db.execute("SELECT COUNT(*) FROM downloads")).fetchone())[0] == 0
        finally:
            await db.close()

    asyncio.run(verify())


def test_partial_run_resumes_from_durable_cursor_after_reopen(tmp_path) -> None:
    repository = SQLiteMessageRepository(tmp_path / "recovery.sqlite3")

    async def exercise() -> None:
        await repository.migrate()
        await repository.start_run(CHAT, 20, "run-recovery")
        await repository.persist_batch("run-recovery", (message(20, "first"),))
        await repository.mark_abandoned_runs_interrupted()
        watermark, cursor = await repository.resume_run("run-recovery", CHAT)
        assert (watermark, cursor) == (20, 20)
        await repository.persist_batch("run-recovery", (message(12, "second"),))
        await repository.finish_run("run-recovery", ScanStatus.COMPLETE, None)
        db = await repository._connect()
        try:
            ids = await (await db.execute(
                "SELECT telegram_message_id FROM messages ORDER BY telegram_message_id DESC"
            )).fetchall()
            assert [row[0] for row in ids] == [20, 12]
            state = await (await db.execute(
                "SELECT status, last_message_id FROM sync_checkpoints WHERE scan_run_id='run-recovery'"
            )).fetchone()
            assert tuple(state) == ("COMPLETE", 12)
        finally:
            await db.close()

    asyncio.run(exercise())


def test_application_deadline_includes_migration_before_credentials_or_gateway() -> None:
    clock = [10.0]
    calls = []

    class SlowMigrationRepository:
        async def migrate(self):
            clock[0] += 2.0

    application = ScanApplication(
        lambda _credentials: calls.append("gateway"),
        lambda: calls.append("credentials"),
        SlowMigrationRepository(),
        clock=lambda: clock[0],
    )

    async def exercise():
        from telegram_courses.message_scanner import ScanRequest

        with pytest.raises(TimeoutError):
            await application.scan(CHAT, ScanRequest(10, 1))

    asyncio.run(exercise())
    assert calls == []


def test_gateway_cleanup_is_bounded_by_the_same_total_deadline() -> None:
    class FastRepository:
        finished = []

        async def migrate(self):
            pass

        async def start_run(self, _chat_id, _watermark, _run_id):
            return None

        async def persist_batch(self, _run_id, _messages, *, watermark=None):
            return (0, 0)

        async def finish_run(self, run_id, status, reason):
            self.finished.append((run_id, status, reason))

    class SlowCleanupGateway:
        closed = False

        async def restore(self):
            return AuthState.AUTHENTICATED

        async def iter_channel_messages(self, *_args, **_kwargs):
            if False:
                yield message(1, None)

        async def close(self):
            try:
                await asyncio.sleep(2)
            finally:
                self.closed = True

    gateway = SlowCleanupGateway()
    repository = FastRepository()
    application = ScanApplication(
        lambda _credentials: gateway,
        lambda: TelegramCredentials(7, "synthetic-hash"),
        repository,
    )

    async def exercise():
        from telegram_courses.message_scanner import ScanRequest

        with pytest.raises(TimeoutError):
            await application.scan(CHAT, ScanRequest(10, 1))

    asyncio.run(exercise())
    assert gateway.closed
    assert repository.finished[-1][1:] == (ScanStatus.FAILED, "CLEANUP_FAILURE")


def test_application_closes_gateway_after_restore_timeout() -> None:
    clock = [0.0]

    class FastRepository:
        async def migrate(self):
            pass

        async def start_run(self, _chat_id, _watermark, _run_id):
            return None

        async def persist_batch(self, _run_id, _messages, *, watermark=None):
            return (0, 0)

        async def finish_run(self, *_args):
            pass

    class SlowRestoreGateway:
        closed = False

        async def restore(self):
            clock[0] = 0.81

        async def iter_channel_messages(self, *_args, **_kwargs):
            if False:
                yield message(1, None)

        async def close(self):
            self.closed = True

    gateway = SlowRestoreGateway()
    application = ScanApplication(
        lambda _credentials: gateway,
        lambda: TelegramCredentials(7, "synthetic-hash"),
        FastRepository(),
        clock=lambda: clock[0],
    )

    async def exercise():
        from telegram_courses.message_scanner import ScanRequest

        outcome = await application.scan(CHAT, ScanRequest(10, 1))
        assert outcome.status is ScanStatus.FAILED
        assert outcome.stop_reason == "TIMEOUT"

    asyncio.run(exercise())
    assert gateway.closed
