from __future__ import annotations

import asyncio
import hashlib
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

import aiosqlite

from telegram_courses.download_repository import DownloadCandidate
from telegram_courses.downloads import DownloadError, SingleMediaDownloadApplication
from telegram_courses.s5_downloads import (
    DownloadPlan,
    DownloadQueue,
    DownloadSelection,
    PlanItem,
)


def _plan(count: int = 1, size: int = 8) -> DownloadPlan:
    items = []
    for index in range(count):
        identity = (-1001, 10 + index, 0)
        candidate = DownloadCandidate(
            media_item_id=index + 1, channel_id=identity[0],
            telegram_message_id=identity[1], media_ordinal=0,
            telegram_media_id=f"synthetic-{index}", expected_bytes=size,
            original_filename=f"item-{index}.bin", lineage=(("lesson", "Synthetic"),),
        )
        items.append(PlanItem(identity, candidate, "PENDING"))
    return DownloadPlan("s8-plan", DownloadSelection(-1001), "Synthetic", True, 1, tuple(items))


class _QueueApp:
    def __init__(self, action=None) -> None:
        self.action = action
        self.calls = 0
        self.active = 0
        self.maximum_active = 0
        self.download_root = Path("synthetic-downloads")
        self.progress_callback = None
        self.chunk_callback = None
        self.chunk_reserver = None
        self.operation_reserver = None
        self.pre_append_check = None

    async def download(self, *_identity):
        self.calls += 1
        self.active += 1
        self.maximum_active = max(self.active, self.maximum_active)
        try:
            if self.action is not None:
                return await self.action(self.calls)
            return SimpleNamespace(result="DOWNLOADED", transferred_bytes=8)
        finally:
            self.active -= 1


def test_s8_queue_uses_full_jitter_and_finite_attempts() -> None:
    async def exercise():
        windows = []
        sleeps = []

        async def action(call):
            if call < 3:
                raise DownloadError("NETWORK")
            return SimpleNamespace(result="DOWNLOADED", transferred_bytes=8)

        async def sleep(delay):
            sleeps.append(delay)

        app = _QueueApp(action)
        queue = DownloadQueue(
            object(), app, workers=1, attempts_per_media=3,
            free_space=lambda _path: 2**40,
            random_uniform=lambda low, high: windows.append((low, high)) or high / 2,
            sleep=sleep,
        )
        result = await queue.run(_plan())
        return app, result, windows, sleeps

    app, result, windows, sleeps = asyncio.run(exercise())
    assert app.calls == result.attempts == 3
    assert windows == [(0.0, 1.0), (0.0, 2.0)]
    assert sleeps == [0.5, 1.0]
    assert result.failed == 0


def test_s8_queue_stops_at_configured_attempt_limit_and_terminal_error() -> None:
    async def exercise():
        transient = _QueueApp(lambda _call: _fail("NETWORK"))
        terminal = _QueueApp(lambda _call: _fail("ACCESS_DENIED"))
        options = dict(free_space=lambda _path: 2**40, sleep=_no_sleep)
        transient_result = await DownloadQueue(
            object(), transient, attempts_per_media=2, **options
        ).run(_plan())
        terminal_result = await DownloadQueue(
            object(), terminal, attempts_per_media=3, **options
        ).run(_plan())
        return transient, transient_result, terminal, terminal_result

    transient, transient_result, terminal, terminal_result = asyncio.run(exercise())
    assert transient.calls == transient_result.attempts == 2
    assert transient_result.failed == 1
    assert terminal.calls == terminal_result.attempts == 1
    assert terminal_result.outcomes[0][2] == "ACCESS_DENIED"


async def _fail(category: str):
    raise DownloadError(category)


async def _no_sleep(_delay: float) -> None:
    return None


def test_s8_queue_enforces_worker_limit_and_floodwait_budget() -> None:
    async def exercise():
        active = 0
        maximum_active = 0

        async def slow_success(_call):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(active, maximum_active)
            try:
                await asyncio.sleep(0)
                return SimpleNamespace(result="DOWNLOADED", transferred_bytes=8)
            finally:
                active -= 1

        app = _QueueApp(slow_success)
        result = await DownloadQueue(
            object(), app, workers=2, free_space=lambda _path: 2**40,
            sleep=_no_sleep,
        ).run(_plan(5))
        assert maximum_active <= 2
        assert app.calls == 5 and result.failed == 0

        clock = [0.0]
        sleeps = []

        async def advance(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        async def flood(_call):
            raise DownloadError("RATE_LIMITED", retry_after_seconds=70)

        flood_app = _QueueApp(flood)
        flood_result = await DownloadQueue(
            object(), flood_app, attempts_per_media=3,
            free_space=lambda _path: 2**40, sleep=advance,
            clock=lambda: clock[0],
        ).run(_plan())
        return app, result, flood_app, flood_result, sleeps, clock[0]

    app, result, flood_app, flood_result, sleeps, elapsed = asyncio.run(exercise())
    assert app.calls == 5 and result.failed == 0
    assert flood_app.calls <= 2
    assert elapsed <= 120
    assert sum(sleeps) <= 120
    assert flood_result.failed == 1


def test_s8_single_download_disk_gate_precedes_claim_and_stream(tmp_path) -> None:
    class Repository:
        starts = 0

        async def get_record(self, _media_item_id):
            return None

        async def migrate(self):
            return None

        async def select_candidate(self, *_identity):
            return _plan().items[0].candidate

        async def assert_candidate_identity(self, _candidate):
            return None

        async def start(self, *_args):
            self.starts += 1

    class Gateway:
        streams = 0

        async def stream_media(self, *_args, **_kwargs):
            self.streams += 1
            yield b"should-not-stream"

    async def exercise():
        repository, gateway = Repository(), Gateway()
        app = SingleMediaDownloadApplication(
            repository, gateway, tmp_path / "downloads",
            free_space=lambda _path: 0,
        )
        try:
            await app.download(-1001, 10, 0)
        except DownloadError as error:
            return error.category, repository, gateway
        raise AssertionError("insufficient disk should block before transfer")

    category, repository, gateway = asyncio.run(exercise())
    assert category == "INSUFFICIENT_DISK_SPACE"
    assert repository.starts == 0
    assert gateway.streams == 0
    assert not (tmp_path / "downloads").exists()


def test_s8_synthetic_stream_memory_measurement(tmp_path, record_property) -> None:
    """Measure a real S4 download path; no NFR-02 threshold is asserted here."""
    size = 16 * 1024 * 1024
    chunk_bytes = 256 * 1024
    payload = b"s" * size

    class StreamingGateway:
        yielded = 0

        async def stream_media(
            self, _channel, _message, _ordinal, *, expected_bytes, offset=0,
            reserve_chunk=None, **_kwargs,
        ):
            assert expected_bytes == size
            for start in range(offset, size, chunk_bytes):
                chunk = payload[start : min(start + chunk_bytes, size)]
                if reserve_chunk is not None:
                    reservation = await reserve_chunk(len(chunk))
                    assert reservation is not None
                    reservation.received(len(chunk))
                self.yielded += len(chunk)
                yield chunk

        async def get_file_hashes(
            self, _channel, _message, _ordinal, *, expected_bytes, offset=0,
        ):
            from telegram_courses.downloads import RemoteFileHash

            assert expected_bytes == size
            return (RemoteFileHash(0, size, hashlib.sha256(payload).digest()),)

    async def seed(database: Path) -> None:
        from telegram_courses.download_repository import DownloadRepository

        repository = DownloadRepository(database)
        await repository.migrate()
        async with aiosqlite.connect(database) as db:
            await db.execute(
                "INSERT INTO channels(telegram_chat_id,title,created_at,updated_at) "
                "VALUES(-1001,'Synthetic','now','now')"
            )
            await db.execute(
                "INSERT INTO messages(channel_id,telegram_message_id,message_date_utc,created_at,updated_at) "
                "VALUES(-1001,10,'2026-01-01T00:00:00+00:00','now','now')"
            )
            await db.execute(
                "INSERT INTO catalog_nodes(channel_id,kind,title,source_message_id,created_at,updated_at) "
                "VALUES(-1001,'lesson','Synthetic lesson',10,'now','now')"
            )
            lesson_id = (await (await db.execute(
                "SELECT id FROM catalog_nodes"
            )).fetchone())[0]
            await db.execute(
                "INSERT INTO media_items(channel_id,telegram_message_id,media_ordinal,"
                "catalog_node_id,kind,telegram_media_id,original_filename,file_size_bytes,created_at,updated_at) "
                "VALUES(-1001,10,0,?,'DOCUMENT','synthetic-memory','large.bin',?,'now','now')",
                (lesson_id, size),
            )
            await db.commit()

    async def exercise(database: Path, gateway: StreamingGateway):
        from telegram_courses.download_repository import DownloadRepository

        await seed(database)
        repository = DownloadRepository(database)
        app = SingleMediaDownloadApplication(
            repository, gateway, tmp_path / "streamed",
            chunk_bytes=chunk_bytes, free_space=lambda _path: 2**40,
        )
        return await app.download(-1001, 10, 0)

    database = tmp_path / "memory.sqlite3"
    gateway = StreamingGateway()
    tracemalloc.start()
    try:
        outcome = asyncio.run(exercise(database, gateway))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert outcome.result == "DOWNLOADED"
    assert outcome.final_path.stat().st_size == size
    assert gateway.yielded == size
    record_property("s8_memory_size_bytes", size)
    record_property("s8_memory_method", "tracemalloc around SingleMediaDownloadApplication streaming flow")
    record_property("s8_memory_peak_bytes", peak)
    record_property("s8_memory_limit", "NFR-02 threshold not supplied; measurement only")
    record_property("s8_memory_sha256", hashlib.sha256(payload).hexdigest())
