from __future__ import annotations

import asyncio
import ctypes
import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

import telegram_courses.download_repository as download_repository_module
import telegram_courses.downloads as downloads_module
import telegram_courses.sqlite_repository as sqlite_repository_module
from telegram_courses.auth import AdapterError, AuthState
from telegram_courses.download_repository import (
    DownloadCandidate,
    DownloadInProgress,
    DownloadRepository,
)
from telegram_courses.downloads import (
    DownloadError,
    SingleMediaDownloadApplication,
    destination_paths,
)
from telegram_courses.message_scanner import (
    GatewayMedia,
    GatewayMessage,
    ScanGatewayError,
    ScanRequest,
    ScanStatus,
)
from telegram_courses.s5_downloads import DownloadPlanner, DownloadSelection
from telegram_courses.scan_application import ScanApplication
from telegram_courses.sqlite_repository import SQLiteMessageRepository

CHAT = -1001234567890


def message(
    message_id: int,
    text: str | None = "synthetic",
    *,
    edit: str | None = None,
    media: tuple[GatewayMedia, ...] = (),
) -> GatewayMessage:
    return GatewayMessage(
        CHAT, message_id, "2026-10-25T12:00:00+00:00", edit, text, None, media
    )


class FakeGateway:
    def __init__(
        self,
        messages: list[GatewayMessage],
        *,
        failure: str | None = None,
        fail_after: int = 0,
    ) -> None:
        self.messages = messages
        self.failure = failure
        self.fail_after = fail_after

    async def restore(self) -> AuthState:
        return AuthState.AUTHENTICATED

    async def close(self) -> None:
        return None

    def iter_channel_messages(
        self,
        _channel_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        min_message_id: int | None = None,
        limit: int,
    ):
        async def iterate():
            filtered = sorted(
                self.messages,
                key=lambda item: item.telegram_message_id,
                reverse=True,
            )
            filtered = [
                item for item in filtered
                if (through_message_id is None or item.telegram_message_id <= through_message_id)
                and (before_message_id is None or item.telegram_message_id < before_message_id)
                and (min_message_id is None or item.telegram_message_id >= min_message_id)
            ][:limit]
            yielded = 0
            for item in filtered:
                if self.failure is not None and yielded >= self.fail_after:
                    raise ScanGatewayError(self.failure)
                yielded += 1
                yield item
            if self.failure is not None and yielded >= self.fail_after:
                raise ScanGatewayError(self.failure)

        return iterate()


def make_application(path: Path, gateway: FakeGateway) -> tuple[ScanApplication, SQLiteMessageRepository]:
    repository = SQLiteMessageRepository(path)
    application = ScanApplication(
        lambda _credentials: gateway,
        lambda: object(),  # FakeGateway does not use credentials.
        repository,
    )
    return application, repository


def sync_request(max_messages: int = 100, reconcile_window: int = 0) -> ScanRequest:
    return ScanRequest(
        max_messages=max_messages,
        timeout_seconds=3,
        mode="INCREMENTAL",
        reconcile_window=reconcile_window,
    )


def test_incremental_first_run_new_messages_edits_and_repeat(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway([message(3, "three"), message(2, "two"), message(1, "one")])
    application, repository = make_application(path, gateway)

    async def exercise() -> None:
        first = await application.scan(CHAT, sync_request(reconcile_window=2))
        assert first.status is ScanStatus.COMPLETE
        assert first.messages_inserted == 3
        assert first.has_confirmed_high_water and first.high_water_confirmed == 3

        second = await application.scan(CHAT, sync_request(reconcile_window=2))
        assert second.status is ScanStatus.COMPLETE
        assert second.messages_inserted == 0
        assert second.messages_updated == 0
        assert second.messages_unchanged == 2

        gateway.messages = [
            message(4, "four"), message(3, "three edited", edit="2026-10-25T13:00:00+00:00"),
            message(2, "two"), message(1, "one"),
        ]
        third = await application.scan(CHAT, sync_request(reconcile_window=2))
        assert third.status is ScanStatus.COMPLETE
        assert third.messages_inserted == 1
        assert third.messages_updated == 1
        assert third.messages_unchanged == 1
        assert third.high_water_confirmed == 4

        db = await repository._connect()
        try:
            rows = await (await db.execute(
                "SELECT telegram_message_id,text FROM messages WHERE channel_id=? "
                "ORDER BY telegram_message_id DESC",
                (CHAT,),
            )).fetchall()
            assert [tuple(row) for row in rows] == [
                (4, "four"), (3, "three edited"), (2, "two"), (1, "one")
            ]
        finally:
            await db.close()

    asyncio.run(exercise())


def test_partial_incremental_run_resumes_without_promoting_cursor(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway([message(4), message(3), message(2), message(1)])
    application, repository = make_application(path, gateway)

    async def exercise() -> None:
        first = await application.scan(CHAT, sync_request(2, 1))
        assert first.status is ScanStatus.PARTIAL
        assert not first.has_confirmed_high_water
        assert first.last_message_id == 3

        second = await application.scan(CHAT, sync_request(2, 1))
        assert second.status is ScanStatus.PARTIAL
        assert not second.has_confirmed_high_water
        assert second.last_message_id == 1

        third = await application.scan(CHAT, sync_request(2, 1))
        assert third.status is ScanStatus.COMPLETE
        assert third.has_confirmed_high_water
        assert third.high_water_confirmed == 4
        assert third.messages_inserted == 4

        db = await repository._connect()
        try:
            count = await (await db.execute(
                "SELECT COUNT(*) FROM messages WHERE channel_id=?", (CHAT,)
            )).fetchone()
            assert count[0] == 4
        finally:
            await db.close()

    asyncio.run(exercise())


def test_resumed_run_keeps_captured_head_when_new_posts_arrive(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway([message(10)])
    application, repository = make_application(path, gateway)

    async def exercise() -> None:
        baseline = await application.scan(CHAT, sync_request(reconcile_window=0))
        assert baseline.status is ScanStatus.COMPLETE
        assert baseline.high_water_confirmed == 10

        gateway.messages = [message(12), message(11)]
        gateway.failure = "NETWORK"
        gateway.fail_after = 1
        with pytest.raises(ScanGatewayError):
            await application.scan(CHAT, sync_request(reconcile_window=0))
        assert await repository.get_confirmed_high_water(CHAT) == (True, 10)

        db = await repository._connect()
        try:
            run = await (await db.execute(
                "SELECT id,watermark_message_id,sync_snapshot_head_message_id,status FROM scan_runs "
                "WHERE channel_id=? AND sync_mode='INCREMENTAL' "
                "ORDER BY started_at DESC LIMIT 1",
                (CHAT,),
            )).fetchone()
            assert run["watermark_message_id"] is None
            assert run["sync_snapshot_head_message_id"] == 12
            assert run["status"] == "FAILED"
            failed_run_id = run["id"]
            cursor = await (await db.execute(
                "SELECT last_message_id,watermark_message_id FROM sync_checkpoints WHERE scan_run_id=?",
                (failed_run_id,),
            )).fetchone()
            assert cursor[0] is None
            assert cursor[1] is None
        finally:
            await db.close()

        # Message 13 arrives after this run's head (12) was durably captured.
        # Resumption must finish the old snapshot before a later run sees 13.
        gateway.messages = [message(13), message(12), message(11), message(10)]
        gateway.failure = None
        resumed = await application.scan(CHAT, sync_request(reconcile_window=0))
        assert resumed.run_id == failed_run_id
        assert resumed.status is ScanStatus.COMPLETE
        assert resumed.high_water_confirmed == 12

        db = await repository._connect()
        try:
            confirmed_checkpoint = await (await db.execute(
                "SELECT watermark_message_id FROM sync_checkpoints WHERE scan_run_id=?",
                (failed_run_id,),
            )).fetchone()
            assert confirmed_checkpoint[0] == 12
            ids = await (await db.execute(
                "SELECT telegram_message_id FROM messages WHERE channel_id=? "
                "ORDER BY telegram_message_id DESC",
                (CHAT,),
            )).fetchall()
            assert [row[0] for row in ids] == [12, 11, 10]
        finally:
            await db.close()

        next_run = await application.scan(CHAT, sync_request(reconcile_window=0))
        assert next_run.status is ScanStatus.COMPLETE
        assert next_run.messages_inserted == 1
        assert next_run.high_water_confirmed == 13

    asyncio.run(exercise())


def test_windows_dead_pid_detection_uses_invalid_parameter_as_positive_evidence(
    monkeypatch,
) -> None:
    class FakeFunction:
        argtypes = None
        restype = None

        def __call__(self, *_args):
            return 0

    class FakeKernel32:
        OpenProcess = FakeFunction()
        GetExitCodeProcess = FakeFunction()
        CloseHandle = FakeFunction()

    kernel32 = FakeKernel32()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 87, raising=False)

    assert sqlite_repository_module._windows_process_is_alive(987654321) is False


@pytest.mark.parametrize(("error", "expected"), [(87, False), (5, True), (1234, None)])
def test_download_windows_pid_open_errors_are_tri_state(monkeypatch, error, expected) -> None:
    class FakeFunction:
        argtypes = None
        restype = None

        def __call__(self, *_args):
            return 0

    class FakeKernel32:
        OpenProcess = FakeFunction()
        GetExitCodeProcess = FakeFunction()
        CloseHandle = FakeFunction()

    monkeypatch.setattr(download_repository_module.os, "name", "nt")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: FakeKernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    assert download_repository_module._process_is_alive(987654321) is expected


@pytest.mark.parametrize(("exit_code", "expected"), [(259, True), (0, False)])
def test_download_windows_pid_exit_code_classifies_alive_and_dead(
    monkeypatch, exit_code, expected
) -> None:
    class FakeFunction:
        argtypes = None
        restype = None

        def __init__(self, result):
            self.result = result

        def __call__(self, *_args):
            return self.result(*_args) if callable(self.result) else self.result

    class FakeKernel32:
        OpenProcess = FakeFunction(1)
        CloseHandle = FakeFunction(1)

        @staticmethod
        def _set_exit_code(handle, output):
            output._obj.value = exit_code
            return 1

        GetExitCodeProcess = FakeFunction(_set_exit_code)

    monkeypatch.setattr(download_repository_module.os, "name", "nt")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: FakeKernel32, raising=False)
    assert download_repository_module._process_is_alive(987654321) is expected


def test_download_windows_failed_exit_query_is_unknown(monkeypatch) -> None:
    class FakeFunction:
        argtypes = None
        restype = None

        def __init__(self, result):
            self.result = result

        def __call__(self, *_args):
            return self.result

    class FakeKernel32:
        OpenProcess = FakeFunction(1)
        GetExitCodeProcess = FakeFunction(0)
        CloseHandle = FakeFunction(1)

    monkeypatch.setattr(download_repository_module.os, "name", "nt")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: FakeKernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    assert download_repository_module._process_is_alive(987654321) is None


def test_persist_batch_failure_rolls_back_and_resumes_without_advancing_high_water(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway([message(10)])
    application, repository = make_application(path, gateway)

    class FailBeforeCommit:
        def __init__(self, connection, armed: dict[str, bool]) -> None:
            self.connection = connection
            self.armed = armed
            self.message_write_seen = False

        def __getattr__(self, name):
            return getattr(self.connection, name)

        async def execute(self, sql, *args, **kwargs):
            if sql.lstrip().upper().startswith(("INSERT INTO MESSAGES", "UPDATE MESSAGES")):
                self.message_write_seen = True
            return await self.connection.execute(sql, *args, **kwargs)

        async def commit(self) -> None:
            if self.message_write_seen and self.armed["value"]:
                self.armed["value"] = False
                raise sqlite3.OperationalError("injected persist_batch commit failure")
            await self.connection.commit()

    async def exercise() -> None:
        baseline = await application.scan(CHAT, sync_request(reconcile_window=0))
        assert baseline.status is ScanStatus.COMPLETE
        assert baseline.high_water_confirmed == 10

        gateway.messages = [message(11)]
        original_connect = repository._connect
        armed = {"value": True}

        async def injected_connect():
            return FailBeforeCommit(await original_connect(), armed)

        monkeypatch.setattr(repository, "_connect", injected_connect)
        with pytest.raises(AdapterError):
            await application.scan(CHAT, sync_request(reconcile_window=0))

        # The batch transaction rolled back completely, while the failed run
        # remains available for retry and cannot replace the completed baseline.
        assert await repository.get_confirmed_high_water(CHAT) == (True, 10)
        db = await original_connect()
        try:
            row = await (await db.execute(
                "SELECT id,status,watermark_message_id,sync_snapshot_head_message_id FROM scan_runs "
                "WHERE channel_id=? AND sync_mode='INCREMENTAL' "
                "ORDER BY started_at DESC LIMIT 1",
                (CHAT,),
            )).fetchone()
            failed_run_id = row["id"]
            assert row["status"] == "FAILED"
            assert row["watermark_message_id"] is None
            assert row["sync_snapshot_head_message_id"] == 11
            checkpoint = await (await db.execute(
                "SELECT last_message_id FROM sync_checkpoints WHERE scan_run_id=?",
                (failed_run_id,),
            )).fetchone()
            assert checkpoint[0] is None
            message_count = await (await db.execute(
                "SELECT COUNT(*) FROM messages WHERE channel_id=? AND telegram_message_id=11",
                (CHAT,),
            )).fetchone()
            assert message_count[0] == 0
        finally:
            await db.close()

        monkeypatch.setattr(repository, "_connect", original_connect)
        retried = await application.scan(CHAT, sync_request(reconcile_window=0))
        assert retried.run_id == failed_run_id
        assert retried.status is ScanStatus.COMPLETE
        assert retried.messages_inserted == 1
        assert retried.high_water_confirmed == 11
        db = await repository._connect()
        try:
            rows = await (await db.execute(
                "SELECT COUNT(*), MIN(text), MAX(text) FROM messages "
                "WHERE channel_id=? AND telegram_message_id=11",
                (CHAT,),
            )).fetchone()
            assert tuple(rows) == (1, "synthetic", "synthetic")
        finally:
            await db.close()

    asyncio.run(exercise())


def test_complete_incremental_scan_does_not_regress_high_water_without_new_ids(
    tmp_path,
) -> None:
    path = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway([message(10)])
    application, repository = make_application(path, gateway)

    async def exercise() -> None:
        baseline = await application.scan(CHAT, sync_request(reconcile_window=0))
        assert baseline.status is ScanStatus.COMPLETE
        assert baseline.high_water_confirmed == 10

        gateway.messages = [message(9), message(8)]
        completed = await application.scan(CHAT, sync_request(reconcile_window=0))
        assert completed.status is ScanStatus.COMPLETE
        assert completed.high_water_confirmed == 10
        assert await repository.get_confirmed_high_water(CHAT) == (True, 10)

        db = await repository._connect()
        try:
            run = await (await db.execute(
                "SELECT watermark_message_id,sync_snapshot_head_message_id FROM scan_runs "
                "WHERE channel_id=? AND sync_mode='INCREMENTAL' AND status='COMPLETE' "
                "ORDER BY finished_at DESC LIMIT 1",
                (CHAT,),
            )).fetchone()
            assert run["watermark_message_id"] == 10
            assert run["sync_snapshot_head_message_id"] is None
            checkpoint = await (await db.execute(
                "SELECT watermark_message_id FROM sync_checkpoints WHERE scan_run_id=("
                "SELECT id FROM scan_runs WHERE channel_id=? AND sync_mode='INCREMENTAL' "
                "AND status='COMPLETE' ORDER BY finished_at DESC LIMIT 1)",
                (CHAT,),
            )).fetchone()
            assert checkpoint[0] == 10
        finally:
            await db.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("full_head", [90, None])
def test_full_complete_run_cannot_lower_incremental_high_water(tmp_path, full_head) -> None:
    path = tmp_path / f"full-head-{full_head}.sqlite3"
    repository = SQLiteMessageRepository(path)

    async def exercise() -> None:
        await repository.migrate()
        await repository.start_run(CHAT, 100, "complete-100")
        await repository.finish_run("complete-100", ScanStatus.COMPLETE, None)
        await repository.start_run(CHAT, full_head, "full-lower-head")
        await repository.finish_run("full-lower-head", ScanStatus.COMPLETE, None)
        assert await SQLiteMessageRepository(path).get_confirmed_high_water(CHAT) == (True, 100)

        baseline = await repository.start_sync_run(
            CHAT, "next-incremental", max_messages=10, reconcile_window=0
        )
        assert baseline["baseline_confirmed"] is True
        assert baseline["high_water_before"] == 100

        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE scan_runs SET finished_at='equal-time' "
                "WHERE id IN ('complete-100','full-lower-head')"
            )
            await db.commit()
        finally:
            await db.close()
        assert await SQLiteMessageRepository(path).get_confirmed_high_water(CHAT) == (True, 100)

    asyncio.run(exercise())


def test_only_complete_runs_contribute_to_high_water_and_empty_is_confirmed(tmp_path) -> None:
    path = tmp_path / "aggregate-watermark.sqlite3"
    repository = SQLiteMessageRepository(path)

    async def exercise() -> None:
        await repository.migrate()
        await repository.start_run(CHAT, 100, "complete-100")
        await repository.finish_run("complete-100", ScanStatus.COMPLETE, None)
        await repository.start_run(CHAT, 999, "partial-999")
        await repository.finish_run("partial-999", ScanStatus.PARTIAL, "LIMIT_REACHED")
        assert await repository.get_confirmed_high_water(CHAT) == (True, 100)

        other_chat = CHAT - 1
        await repository.start_run(other_chat, None, "empty-complete")
        await repository.finish_run("empty-complete", ScanStatus.COMPLETE, None)
        assert await repository.get_confirmed_high_water(other_chat) == (True, None)

    asyncio.run(exercise())


def test_recovery_requires_positive_dead_owner_evidence(tmp_path, monkeypatch) -> None:
    path = tmp_path / "catalog.sqlite3"
    application, repository = make_application(
        path, FakeGateway([message(2), message(1)])
    )

    async def exercise() -> None:
        partial = await application.scan(CHAT, sync_request(1, 0))
        assert partial.status is ScanStatus.PARTIAL
        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE scan_runs SET status='RUNNING', owner_pid=NULL WHERE id=?",
                (partial.run_id,),
            )
            await db.commit()
        finally:
            await db.close()

        assert await repository.mark_abandoned_sync_runs_interrupted() == 0
        db = await repository._connect()
        try:
            state = await (await db.execute(
                "SELECT status FROM scan_runs WHERE id=?", (partial.run_id,)
            )).fetchone()
            assert state[0] == "RUNNING"
        finally:
            await db.close()

        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE scan_runs SET owner_pid=987654321 WHERE id=?", (partial.run_id,)
            )
            await db.commit()
        finally:
            await db.close()

        assert await repository.mark_abandoned_sync_runs_interrupted() == 1
        db = await repository._connect()
        try:
            state = await (await db.execute(
                "SELECT status,stop_reason FROM scan_runs WHERE id=?", (partial.run_id,)
            )).fetchone()
            assert tuple(state) == ("INTERRUPTED", "PROCESS_RESTART")
        finally:
            await db.close()

    asyncio.run(exercise())


def test_absent_message_is_unverified_and_preserved(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    gateway = FakeGateway([message(3), message(2), message(1)])
    application, repository = make_application(path, gateway)

    async def exercise() -> None:
        await application.scan(CHAT, sync_request(reconcile_window=3))
        gateway.messages = [message(3), message(1)]
        result = await application.scan(CHAT, sync_request(reconcile_window=3))
        assert result.status is ScanStatus.COMPLETE
        assert result.messages_unverified == 1
        db = await repository._connect()
        try:
            rows = await (await db.execute(
                "SELECT telegram_message_id FROM messages WHERE channel_id=? "
                "ORDER BY telegram_message_id",
                (CHAT,),
            )).fetchall()
            assert [row[0] for row in rows] == [1, 2, 3]
        finally:
            await db.close()

    asyncio.run(exercise())


def test_access_failure_does_not_advance_confirmed_high_water(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    application, repository = make_application(
        path, FakeGateway([message(2), message(1)])
    )

    async def exercise() -> None:
        await application.scan(CHAT, sync_request(reconcile_window=1))
        failing, _ = make_application(
            path, FakeGateway([message(3)], failure="ACCESS_DENIED")
        )
        with pytest.raises(ScanGatewayError):
            await failing.scan(CHAT, sync_request(reconcile_window=1))
        assert await repository.get_confirmed_high_water(CHAT) == (True, 2)

    asyncio.run(exercise())


def test_legacy_complete_scan_remains_a_confirmed_baseline(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    try:
        from importlib.resources import files

        connection.executescript(
            files("telegram_courses").joinpath("migrations/001_initial.sql").read_text()
        )
        connection.execute(
            "INSERT INTO channels(telegram_chat_id,created_at,updated_at) VALUES(?,?,?)",
            (CHAT, "created", "updated"),
        )
        connection.execute(
            "INSERT INTO scan_runs(id,channel_id,status,started_at,finished_at,watermark_message_id) "
            "VALUES('legacy-complete',?,'COMPLETE','started','finished',42)",
            (CHAT,),
        )
        connection.execute(
            "INSERT INTO sync_checkpoints(scan_run_id,channel_id,watermark_message_id,status,updated_at) "
            "VALUES('legacy-complete',?,42,'COMPLETE','finished')",
            (CHAT,),
        )
        connection.commit()
    finally:
        connection.close()

    async def exercise() -> None:
        repository = SQLiteMessageRepository(path)
        await repository.migrate()
        await repository.migrate()
        assert await repository.get_confirmed_high_water(CHAT) == (True, 42)
        db = await repository._connect()
        try:
            version = await (await db.execute(
                "SELECT 1 FROM schema_migrations WHERE version=6"
            )).fetchone()
            assert version is not None
        finally:
            await db.close()

    asyncio.run(exercise())


def test_media_replacement_blocks_download_reuse_and_preserves_record(tmp_path) -> None:
    path = tmp_path / "catalog.sqlite3"
    old_media = GatewayMedia(0, "DOCUMENT", "media-old", "old.pdf", "application/pdf", 7)
    gateway = FakeGateway([message(5, "lesson", media=(old_media,))])
    application, repository = make_application(path, gateway)
    download_repository = DownloadRepository(path)

    async def exercise() -> None:
        await application.scan(CHAT, sync_request(reconcile_window=1))
        await download_repository.migrate()
        db = await repository._connect()
        try:
            media_item_id = (await (await db.execute(
                "SELECT id FROM media_items WHERE channel_id=? AND telegram_message_id=5",
                (CHAT,),
            )).fetchone())[0]
        finally:
            await db.close()
        old_candidate = DownloadCandidate(
            media_item_id, CHAT, 5, 0, "media-old", 7, "old.pdf", (("lesson", "Lesson"),)
        )
        final_path = tmp_path / "downloads" / "old.pdf"
        partial_path = tmp_path / "downloads" / "old.pdf.part"
        await download_repository.start(old_candidate, final_path, partial_path)

        new_media = GatewayMedia(0, "DOCUMENT", "media-new", "new.pdf", "application/pdf", 7)
        gateway.messages = [message(5, "lesson edited", edit="2026-10-25T13:00:00+00:00", media=(new_media,))]
        result = await application.scan(CHAT, sync_request(reconcile_window=1))
        assert result.messages_updated == 1

        db = await repository._connect()
        try:
            await db.execute(
                "INSERT INTO catalog_nodes(id,channel_id,parent_id,kind,title,source_message_id,created_at,updated_at,is_active) "
                "VALUES(1,?,NULL,'lesson','Lesson',5,'now','now',1)",
                (CHAT,),
            )
            await db.execute(
                "UPDATE media_items SET catalog_node_id=1 WHERE id=?", (media_item_id,)
            )
            await db.execute(
                "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,source_message_count,catalog_node_count,unresolved_count) "
                "VALUES('catalog-1',?,'generic','1','COMPLETE','now','now',1,1,0)",
                (CHAT,),
            )
            await db.commit()
            before = await (await db.execute(
                "SELECT state,final_path,partial_path,remote_identity_media_id,remote_identity_size "
                "FROM downloads WHERE media_item_id=?", (media_item_id,)
            )).fetchone()
        finally:
            await db.close()

        planner = DownloadPlanner(path, tmp_path / "downloads")
        plan = await planner.build(DownloadSelection(CHAT))
        assert len(plan.blocked) == 1
        assert plan.blocked[0].reason == "MEDIA_IDENTITY_CHANGED"

        new_candidate = DownloadCandidate(
            media_item_id, CHAT, 5, 0, "media-new", 7, "new.pdf", (("lesson", "Lesson"),)
        )
        with pytest.raises(ValueError, match="identity changed"):
            await download_repository.start(new_candidate, tmp_path / "new.pdf", tmp_path / "new.pdf.part")

        db = await repository._connect()
        try:
            after = await (await db.execute(
                "SELECT state,final_path,partial_path,remote_identity_media_id,remote_identity_size "
                "FROM downloads WHERE media_item_id=?", (media_item_id,)
            )).fetchone()
            assert tuple(after) == tuple(before)
            current = await (await db.execute(
                "SELECT telegram_media_id FROM media_items WHERE id=?", (media_item_id,)
            )).fetchone()
            assert current[0] == "media-new"
        finally:
            await db.close()

    asyncio.run(exercise())


def test_reobserved_missing_media_is_durable_and_blocks_without_file_mutation(tmp_path) -> None:
    path = tmp_path / "media-observation.sqlite3"
    root = tmp_path / "downloads"
    first = GatewayMedia(0, "DOCUMENT", "media-0", "first.pdf", "application/pdf", 4)
    second = GatewayMedia(1, "DOCUMENT", "media-a", "second.pdf", "application/pdf", 4)
    gateway = FakeGateway([message(5, "lesson", media=(first, second))])
    application, repository = make_application(path, gateway)
    downloads = DownloadRepository(path)

    class NeverGateway:
        calls = 0

        async def stream_media(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("NOT_OBSERVED media must block before transfer")
            yield b""

        async def get_file_hashes(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("NOT_OBSERVED media must block before hash request")

    async def exercise():
        await application.scan(CHAT, sync_request(reconcile_window=1))
        await downloads.migrate()
        db = await repository._connect()
        try:
            await db.execute(
                "INSERT INTO catalog_nodes(id,channel_id,parent_id,kind,title,source_message_id,created_at,updated_at,is_active) "
                "VALUES(1,?,NULL,'lesson','Lesson',5,'now','now',1)", (CHAT,),
            )
            await db.execute(
                "UPDATE media_items SET catalog_node_id=1 WHERE channel_id=? AND telegram_message_id=5",
                (CHAT,),
            )
            await db.execute(
                "INSERT INTO catalog_runs(id,channel_id,parser_key,grammar_version,status,started_at,finished_at,source_message_count,catalog_node_count,unresolved_count) "
                "VALUES('catalog-1',?,'generic','1','COMPLETE','now','now',1,1,0)", (CHAT,),
            )
            second_id = (await (await db.execute(
                "SELECT id FROM media_items WHERE channel_id=? AND telegram_message_id=5 AND media_ordinal=1",
                (CHAT,),
            )).fetchone())[0]
            await db.commit()
        finally:
            await db.close()

        candidate = await downloads.select_candidate(CHAT, 5, 1)
        assert candidate is not None
        final, partial = destination_paths(root, candidate)
        partial.parent.mkdir(parents=True, exist_ok=True)
        partial.write_bytes(b"part")
        await downloads.start(candidate, final, partial)
        await downloads.transition(
            candidate.media_item_id, "FAILED_RETRYABLE", downloaded_bytes=4,
            failure_category="TEST_RELEASE",
        )
        before = await downloads.get_record(candidate.media_item_id)
        before_bytes = partial.read_bytes()

        gateway.messages = [message(5, "lesson", media=(first,))]
        absent = await application.scan(CHAT, sync_request(reconcile_window=1))
        assert absent.messages_updated == 1
        assert absent.media_unverified == 1
        db = await repository._connect()
        try:
            state = await (await db.execute(
                "SELECT remote_observation_state FROM media_items WHERE id=?", (second_id,)
            )).fetchone()
        finally:
            await db.close()
        assert state[0] == "NOT_OBSERVED"

        plan = await DownloadPlanner(path, root).build(DownloadSelection(CHAT))
        blocked = next(item for item in plan.blocked if item.identity == (CHAT, 5, 1))
        assert blocked.reason == "MEDIA_NOT_OBSERVED"
        gateway_guard = NeverGateway()
        app = SingleMediaDownloadApplication(downloads, gateway_guard, root)
        with pytest.raises(DownloadError) as error:
            await app.download(CHAT, 5, 1)
        assert error.value.category == "MEDIA_NOT_OBSERVED"
        assert gateway_guard.calls == 0
        assert await downloads.get_record(candidate.media_item_id) == before
        assert partial.read_bytes() == before_bytes

        repeated = await application.scan(CHAT, sync_request(reconcile_window=1))
        assert repeated.messages_updated == 0
        assert repeated.media_unverified == 1

        gateway.messages = [message(5, "lesson", media=(first, second))]
        restored = await application.scan(CHAT, sync_request(reconcile_window=1))
        assert restored.messages_updated == 1
        assert restored.media_unverified == 0
        db = await repository._connect()
        try:
            state = await (await db.execute(
                "SELECT remote_observation_state FROM media_items WHERE id=?", (second_id,)
            )).fetchone()
        finally:
            await db.close()
        assert state[0] == "OBSERVED"

        replacement = GatewayMedia(1, "DOCUMENT", "media-b", "second.pdf", "application/pdf", 4)
        gateway.messages = [message(5, "lesson", media=(first, replacement))]
        changed = await application.scan(CHAT, sync_request(reconcile_window=1))
        assert changed.messages_updated == 1
        replacement_plan = await DownloadPlanner(path, root).build(DownloadSelection(CHAT))
        changed_item = next(item for item in replacement_plan.blocked if item.identity == (CHAT, 5, 1))
        assert changed_item.reason == "MEDIA_IDENTITY_CHANGED"
        assert partial.read_bytes() == before_bytes
        assert await downloads.get_record(candidate.media_item_id) == before

    asyncio.run(exercise())


class NoCallDownloadGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def stream_media(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("download identity validation must not call the gateway")
        yield b""

    async def get_file_hashes(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("download identity validation must not call the gateway")


async def prepare_download_identity_reuse_case(
    tmp_path: Path, *, replacement_media_id: str | None
) -> tuple[Path, Path, DownloadRepository, int, Path, bytes, FakeGateway]:
    path = tmp_path / "identity-reuse.sqlite3"
    root = tmp_path / "downloads"
    payload = b"identity"
    old_media = GatewayMedia(0, "DOCUMENT", "media-old", "same.pdf", "application/pdf", len(payload))
    scan_gateway = FakeGateway([message(5, "lesson", media=(old_media,))])
    application, repository = make_application(path, scan_gateway)
    download_repository = DownloadRepository(path)

    await application.scan(CHAT, sync_request(reconcile_window=1))
    await download_repository.migrate()
    db = await repository._connect()
    try:
        media_item_id = (await (await db.execute(
            "SELECT id FROM media_items WHERE channel_id=? AND telegram_message_id=5 AND media_ordinal=0",
            (CHAT,),
        )).fetchone())[0]
        await db.execute(
            "INSERT INTO catalog_nodes(channel_id,parent_id,kind,title,source_message_id,created_at,updated_at,is_active) "
            "VALUES(?,NULL,'lesson','Lesson',5,'now','now',1)",
            (CHAT,),
        )
        catalog_node_id = (await (await db.execute(
            "SELECT id FROM catalog_nodes WHERE channel_id=? AND source_message_id=5 AND kind='lesson'",
            (CHAT,),
        )).fetchone())[0]
        await db.execute(
            "UPDATE media_items SET catalog_node_id=? WHERE id=?",
            (catalog_node_id, media_item_id),
        )
        await db.commit()
    finally:
        await db.close()

    old_candidate = DownloadCandidate(
        media_item_id, CHAT, 5, 0, "media-old", len(payload), "same.pdf", (("lesson", "Lesson"),)
    )
    final_path, partial_path = destination_paths(root, old_candidate)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(payload)
    await download_repository.start(old_candidate, final_path, partial_path)
    digest = hashlib.sha256(payload).hexdigest()
    await download_repository.transition(
        media_item_id, "VALIDATED", downloaded_bytes=len(payload), sha256=digest
    )
    await download_repository.transition(
        media_item_id, "DOWNLOADED", downloaded_bytes=len(payload), sha256=digest
    )

    if replacement_media_id is not None:
        replacement = GatewayMedia(
            0, "DOCUMENT", replacement_media_id, "same.pdf", "application/pdf", len(payload)
        )
        scan_gateway.messages = [
            message(5, "lesson", edit="2026-10-25T13:00:00+00:00", media=(replacement,))
        ]
        result = await application.scan(CHAT, sync_request(reconcile_window=1))
        assert result.messages_updated == 1

    return path, root, download_repository, media_item_id, final_path, payload, scan_gateway


def test_individual_download_reuse_rejects_changed_identity_without_mutation(tmp_path) -> None:
    async def exercise() -> None:
        (
            path,
            root,
            download_repository,
            media_item_id,
            final_path,
            payload,
            _scan_gateway,
        ) = await prepare_download_identity_reuse_case(
            tmp_path, replacement_media_id="media-new"
        )
        db = await download_repository._connect()
        try:
            before = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,)
            )).fetchone())
        finally:
            await db.close()

        gateway = NoCallDownloadGateway()
        application = SingleMediaDownloadApplication(download_repository, gateway, root)
        with pytest.raises(DownloadError) as error:
            await application.download(CHAT, 5, 0)
        assert error.value.category == "RESUME_IDENTITY_MISMATCH"
        assert gateway.calls == 0
        assert final_path.read_bytes() == payload

        db = await download_repository._connect()
        try:
            after = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,)
            )).fetchone())
            current = await (await db.execute(
                "SELECT telegram_media_id, original_filename, file_size_bytes "
                "FROM media_items WHERE id=?", (media_item_id,)
            )).fetchone()
            assert current["telegram_media_id"] == "media-new"
            assert current["original_filename"] == "same.pdf"
            assert current["file_size_bytes"] == len(payload)
        finally:
            await db.close()
        assert after == before

    asyncio.run(exercise())


def test_individual_download_reuse_accepts_matching_identity_without_gateway(tmp_path) -> None:
    async def exercise() -> None:
        (
            _path,
            root,
            download_repository,
            media_item_id,
            final_path,
            payload,
            _scan_gateway,
        ) = await prepare_download_identity_reuse_case(
            tmp_path, replacement_media_id=None
        )
        db = await download_repository._connect()
        try:
            before = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,)
            )).fetchone())
        finally:
            await db.close()

        gateway = NoCallDownloadGateway()
        application = SingleMediaDownloadApplication(download_repository, gateway, root)
        outcome = await application.download(CHAT, 5, 0)
        assert outcome.result == "ALREADY_DOWNLOADED"
        assert outcome.final_path == final_path
        assert outcome.sha256 == hashlib.sha256(payload).hexdigest()
        assert gateway.calls == 0
        assert final_path.read_bytes() == payload

        db = await download_repository._connect()
        try:
            after = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,)
            )).fetchone())
        finally:
            await db.close()
        assert after == before

    asyncio.run(exercise())


def test_unknown_download_owner_blocks_start_and_reuse_without_mutation(tmp_path, monkeypatch) -> None:
    async def exercise() -> None:
        (
            _path,
            root,
            repository,
            media_item_id,
            final_path,
            payload,
            _scan_gateway,
        ) = await prepare_download_identity_reuse_case(tmp_path, replacement_media_id=None)
        candidate = await repository.select_candidate(CHAT, 5, 0)
        assert candidate is not None
        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE downloads SET state='DOWNLOADING',owner_pid=987654321 "
                "WHERE media_item_id=?", (media_item_id,),
            )
            await db.commit()
            before = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,),
            )).fetchone())
        finally:
            await db.close()

        monkeypatch.setattr(download_repository_module, "_process_is_alive", lambda _pid: None)
        monkeypatch.setattr(downloads_module, "_process_is_alive", lambda _pid: None)
        _, partial_path = destination_paths(root, candidate)
        with pytest.raises(DownloadInProgress):
            await repository.start(candidate, final_path, partial_path)

        gateway = NoCallDownloadGateway()
        with pytest.raises(DownloadError) as error:
            await SingleMediaDownloadApplication(repository, gateway, root).download(CHAT, 5, 0)
        assert error.value.category == "TRANSFER_IN_PROGRESS"
        assert gateway.calls == 0
        assert final_path.read_bytes() == payload
        db = await repository._connect()
        try:
            after = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,),
            )).fetchone())
        finally:
            await db.close()
        assert after == before

    asyncio.run(exercise())


def test_positive_dead_owner_evidence_allows_claim_and_failed_retryable_no_owner_resumes(
    tmp_path, monkeypatch
) -> None:
    async def exercise() -> None:
        (
            _path,
            root,
            repository,
            media_item_id,
            final_path,
            _payload,
            _scan_gateway,
        ) = await prepare_download_identity_reuse_case(tmp_path, replacement_media_id=None)
        candidate = await repository.select_candidate(CHAT, 5, 0)
        assert candidate is not None
        _, partial_path = destination_paths(root, candidate)
        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE downloads SET state='DOWNLOADING',owner_pid=987654321 "
                "WHERE media_item_id=?", (media_item_id,),
            )
            await db.commit()
        finally:
            await db.close()

        monkeypatch.setattr(download_repository_module, "_process_is_alive", lambda _pid: False)
        await repository.start(candidate, final_path, partial_path)
        claimed = await repository.get_record(media_item_id)
        assert claimed is not None and claimed.state == "DOWNLOADING"
        assert claimed.owner_pid == os.getpid()

        partial_path.write_bytes(b"part")
        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE downloads SET state='FAILED_RETRYABLE',owner_pid=NULL, "
                "final_path=?,partial_path=?,downloaded_bytes=4 WHERE media_item_id=?",
                (str(final_path), str(partial_path), media_item_id),
            )
            await db.commit()
        finally:
            await db.close()
        monkeypatch.setattr(
            download_repository_module,
            "_process_is_alive",
            lambda _pid: (_ for _ in ()).throw(AssertionError("explicit release needs no PID probe")),
        )
        await repository.start_resume(candidate, final_path, partial_path)
        resumed = await repository.get_record(media_item_id)
        assert resumed is not None and resumed.state == "DOWNLOADING"
        assert resumed.owner_pid == os.getpid()
        assert partial_path.read_bytes() == b"part"

    asyncio.run(exercise())


@pytest.mark.parametrize("owner_state", [True, None])
def test_failed_retryable_owner_without_partial_blocks_claim_and_gateway(
    tmp_path, monkeypatch, owner_state
) -> None:
    async def exercise() -> None:
        (
            _path,
            root,
            repository,
            media_item_id,
            final_path,
            _payload,
            _scan_gateway,
        ) = await prepare_download_identity_reuse_case(tmp_path, replacement_media_id=None)
        candidate = await repository.select_candidate(CHAT, 5, 0)
        assert candidate is not None
        _, partial_path = destination_paths(root, candidate)
        final_path.unlink()
        assert not partial_path.exists()

        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE downloads SET state='FAILED_RETRYABLE',owner_pid=987654321 "
                "WHERE media_item_id=?", (media_item_id,),
            )
            await db.commit()
            before = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,),
            )).fetchone())
        finally:
            await db.close()

        monkeypatch.setattr(
            download_repository_module, "_process_is_alive", lambda _pid: owner_state
        )
        monkeypatch.setattr(downloads_module, "_process_is_alive", lambda _pid: owner_state)
        with pytest.raises(DownloadInProgress):
            await repository.start(candidate, final_path, partial_path)

        gateway = NoCallDownloadGateway()
        with pytest.raises(DownloadError) as error:
            await SingleMediaDownloadApplication(repository, gateway, root).download(CHAT, 5, 0)
        assert error.value.category == "TRANSFER_IN_PROGRESS"
        assert gateway.calls == 0
        assert not final_path.exists()
        assert not partial_path.exists()
        db = await repository._connect()
        try:
            after = tuple(await (await db.execute(
                "SELECT * FROM downloads WHERE media_item_id=?", (media_item_id,),
            )).fetchone())
        finally:
            await db.close()
        assert after == before

    asyncio.run(exercise())


def test_failed_retryable_without_owner_can_claim_without_partial(tmp_path) -> None:
    async def exercise() -> None:
        (
            _path,
            root,
            repository,
            media_item_id,
            final_path,
            _payload,
            _scan_gateway,
        ) = await prepare_download_identity_reuse_case(tmp_path, replacement_media_id=None)
        candidate = await repository.select_candidate(CHAT, 5, 0)
        assert candidate is not None
        _, partial_path = destination_paths(root, candidate)
        final_path.unlink()
        assert not partial_path.exists()
        db = await repository._connect()
        try:
            await db.execute(
                "UPDATE downloads SET state='FAILED_RETRYABLE',owner_pid=NULL "
                "WHERE media_item_id=?", (media_item_id,),
            )
            await db.commit()
        finally:
            await db.close()

        await repository.start(candidate, final_path, partial_path)
        record = await repository.get_record(media_item_id)
        assert record is not None and record.state == "DOWNLOADING"
        assert record.owner_pid == os.getpid()
        assert not final_path.exists()
        assert not partial_path.exists()

    asyncio.run(exercise())
