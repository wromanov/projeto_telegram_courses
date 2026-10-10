from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from telegram_courses.auth import AuthState
from telegram_courses.message_scanner import (
    GatewayMedia,
    GatewayMessage,
    MessageScanner,
    ScanDeadline,
    ScanRequest,
    ScanStatus,
    normalize_message,
)

CHAT = -1001234567890


def message(message_id: int, text: str | None = "synthetic") -> GatewayMessage:
    return GatewayMessage(
        CHAT,
        message_id,
        "2026-10-09T12:00:00+00:00",
        None,
        text,
        None,
        (GatewayMedia(0, "DOCUMENT", "synthetic-media", "lesson.pdf", "application/pdf", 42),),
    )


class FakeGateway:
    def __init__(self, messages: list[GatewayMessage]) -> None:
        self.messages = messages
        self.messages_read = 0

    async def restore(self) -> AuthState:
        return AuthState.AUTHENTICATED

    async def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
    ) -> AsyncIterator[GatewayMessage]:
        yielded = 0
        for item in sorted(self.messages, key=lambda value: value.telegram_message_id, reverse=True):
            if through_message_id is not None and item.telegram_message_id > through_message_id:
                continue
            if before_message_id is not None and item.telegram_message_id >= before_message_id:
                continue
            if item.telegram_chat_id != telegram_chat_id:
                continue
            if yielded >= limit:
                break
            yielded += 1
            self.messages_read += 1
            yield item


class MemoryRepository:
    def __init__(self) -> None:
        self.runs: dict[str, tuple[int | None, int | None, str]] = {}
        self.rows: dict[tuple[int, int], GatewayMessage] = {}
        self.finished: list[tuple[str, ScanStatus, str | None]] = []

    async def start_run(self, chat_id: int, watermark: int | None, run_id: str):
        self.runs[run_id] = (watermark, None, "RUNNING")
        return None

    async def set_watermark(self, run_id: str, watermark: int | None) -> None:
        _, cursor, status = self.runs[run_id]
        self.runs[run_id] = (watermark, cursor, status)

    async def resume_run(self, run_id: str, chat_id: int):
        watermark, cursor, status = self.runs[run_id]
        assert status in {"PARTIAL", "INTERRUPTED"}
        self.runs[run_id] = (watermark, cursor, "RUNNING")
        return watermark, cursor

    async def persist_batch(self, run_id: str, messages: tuple[GatewayMessage, ...]):
        inserted = updated = 0
        for item in messages:
            key = (item.telegram_chat_id, item.telegram_message_id)
            if key not in self.rows:
                inserted += 1
            elif self.rows[key] != item:
                updated += 1
            self.rows[key] = item
        run_watermark, _, status = self.runs[run_id]
        self.runs[run_id] = (
            run_watermark,
            min(x.telegram_message_id for x in messages),
            status,
        )
        return inserted, updated

    async def finish_run(self, run_id: str, status: ScanStatus, reason: str | None):
        watermark, cursor, _ = self.runs[run_id]
        self.runs[run_id] = (watermark, cursor, status.value)
        self.finished.append((run_id, status, reason))


def test_normalization_keeps_full_text_and_maps_empty_to_null() -> None:
    assert normalize_message(message(3)).text == "synthetic"
    assert normalize_message(message(4, "")).text is None
    assert normalize_message(message(5, None)).text is None


def test_scanner_iterates_descending_and_persists_complete_scan() -> None:
    repository = MemoryRepository()
    scanner = MessageScanner(FakeGateway([message(9), message(5), message(1)]), repository)
    outcome = asyncio.run(scanner.scan(CHAT, ScanRequest(10, 2)))
    assert outcome.status is ScanStatus.COMPLETE
    assert outcome.messages_seen == 3
    assert outcome.last_message_id == 1
    assert len(repository.rows) == 3


def test_message_limit_is_partial_and_resume_uses_confirmed_cursor() -> None:
    repository = MemoryRepository()
    gateway = FakeGateway([message(9), message(5), message(1)])
    scanner = MessageScanner(gateway, repository)
    first = asyncio.run(scanner.scan(CHAT, ScanRequest(2, 2)))
    assert first.status is ScanStatus.PARTIAL
    assert first.last_message_id == 5
    resumed = asyncio.run(scanner.scan(CHAT, ScanRequest(5, 2, first.run_id)))
    assert resumed.status is ScanStatus.COMPLETE
    assert resumed.messages_seen == 1
    assert len(repository.rows) == 3


def test_total_read_cap_includes_first_message_used_as_watermark() -> None:
    repository = MemoryRepository()
    gateway = FakeGateway([message(index) for index in range(20, 0, -1)])
    outcome = asyncio.run(
        MessageScanner(gateway, repository).scan(CHAT, ScanRequest(10, 2))
    )
    assert gateway.messages_read == 10
    assert outcome.messages_seen == 10
    assert repository.runs[outcome.run_id][0] == 20
    assert repository.runs[outcome.run_id][1] == 11
    assert len(repository.rows) == 10


def test_gateway_cannot_be_asked_for_watermark_separately() -> None:
    class NoSeparateWatermark(FakeGateway):
        async def latest_message_id(self, *_args):
            raise AssertionError("separate watermark reads are forbidden")

    gateway = NoSeparateWatermark([message(7)])
    outcome = asyncio.run(
        MessageScanner(gateway, MemoryRepository()).scan(CHAT, ScanRequest(10, 2))
    )
    assert outcome.messages_seen == 1
    assert gateway.messages_read == 1


@pytest.mark.parametrize("phase", ["restore", "resolve", "iterate"])
def test_deadline_covers_restore_resolution_and_iteration(phase: str) -> None:
    now = [0.0]
    deadline = ScanDeadline(1, clock=lambda: now[0])

    class SlowGateway(FakeGateway):
        closed = False

        async def restore(self):
            if phase == "restore":
                now[0] = 0.81
            return AuthState.AUTHENTICATED

        async def iter_channel_messages(self, *args, **kwargs):
            try:
                if phase == "iterate":
                    yield message(9)
                if phase == "resolve":
                    now[0] = 0.81
                    yield message(9)
                if phase == "iterate":
                    now[0] = 0.81
                    yield message(8)
                async for item in super().iter_channel_messages(*args, **kwargs):
                    yield item
            finally:
                self.closed = True

    repository = MemoryRepository()
    gateway = SlowGateway([message(9), message(8)])
    outcome = asyncio.run(
        MessageScanner(gateway, repository).scan(
            CHAT, ScanRequest(10, 1), deadline=deadline
        )
    )
    assert outcome.stop_reason == "TIMEOUT"
    expected_status = ScanStatus.PARTIAL if phase == "iterate" else ScanStatus.FAILED
    assert outcome.status is expected_status
    assert repository.finished[-1][1] is expected_status
    assert gateway.closed is (phase != "restore")
    if phase == "iterate":
        assert outcome.last_message_id == 9
        assert set(repository.rows) == {(CHAT, 9)}


def test_deadline_uses_injected_monotonic_clock_between_phases() -> None:
    now = [10.0]
    deadline = ScanDeadline(2, clock=lambda: now[0])
    assert deadline.remaining() == pytest.approx(1.6)
    now[0] = 11.9
    assert deadline.remaining() == pytest.approx(0.0)
    with pytest.raises(TimeoutError):
        deadline.check()


def test_cancel_closes_iterator_and_keeps_only_durable_checkpoint() -> None:
    class BlockingGateway(FakeGateway):
        closed = False

        async def iter_channel_messages(self, *args, **kwargs):
            try:
                yield message(9)
                await asyncio.Event().wait()
                yield message(8)
            finally:
                self.closed = True

    async def exercise() -> None:
        gateway = BlockingGateway([message(9), message(8)])
        repository = MemoryRepository()
        task = asyncio.create_task(
            MessageScanner(gateway, repository).scan(CHAT, ScanRequest(10, 2))
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert gateway.closed
        run_id, status, reason = repository.finished[-1]
        assert status is ScanStatus.PARTIAL
        assert reason == "CANCELLED"
        assert repository.runs[run_id][1] == 9
        assert set(repository.rows) == {(CHAT, 9)}

    asyncio.run(exercise())


def test_gateway_failure_keeps_checkpoint_unadvanced() -> None:
    class BrokenGateway(FakeGateway):
        async def iter_channel_messages(self, *args, **kwargs):
            yield message(9)
            raise RuntimeError("synthetic failure")

    repository = MemoryRepository()
    scanner = MessageScanner(BrokenGateway([message(9)]), repository)
    with pytest.raises(RuntimeError):
        asyncio.run(scanner.scan(CHAT, ScanRequest(10, 2)))
    assert repository.rows == {}
    run_id, status, _ = repository.finished[-1]
    assert repository.runs[run_id][1] is None
    assert status is ScanStatus.FAILED


def test_scan_request_rejects_non_positive_limits() -> None:
    with pytest.raises(ValueError):
        ScanRequest(0, 1)
    with pytest.raises(ValueError):
        ScanRequest(1, 0)
