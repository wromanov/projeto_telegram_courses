from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from telegram_courses.download_repository import DownloadCandidate
from telegram_courses.downloads import DownloadError
from telegram_courses.s5_downloads import (
    DownloadPlan,
    DownloadQueue,
    DownloadSelection,
    PlanItem,
)


def pending_plan(size: int = 4) -> DownloadPlan:
    candidate = DownloadCandidate(
        media_item_id=1,
        channel_id=-1001,
        telegram_message_id=10,
        media_ordinal=0,
        telegram_media_id="synthetic",
        expected_bytes=size,
        original_filename="item.bin",
        lineage=(("course", "Course"), ("lesson", "Lesson")),
    )
    identity = (-1001, 10, 0)
    item = PlanItem(identity, candidate, "PENDING")
    return DownloadPlan("plan", DownloadSelection(-1001), "Course", True, 1, (item,))


class FakeApplication:
    def __init__(self, action=None):
        self.action = action
        self.calls = 0
        self.active = 0
        self.maximum_active = 0
        self.requested_bytes = []
        self.received_bytes = []
        self.progress_callback = None
        self.chunk_callback = None
        self.chunk_reserver = None
        self.download_root = Path("downloads")

    async def download(self, *_identity):
        self.calls += 1
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            if self.chunk_reserver is not None:
                reservation = await self.chunk_reserver(4)
                if reservation is None:
                    raise DownloadError("TRANSFER_BUDGET_EXHAUSTED")
                self.requested_bytes.append(4)
                self.received_bytes.append(4)
                reservation.received(4)
                # Model the asynchronous boundary between reservation and the
                # gateway response so worker concurrency is exercised.
                await asyncio.sleep(0)
            if self.chunk_callback is not None:
                self.chunk_callback(4)
            if self.action is not None:
                return await self.action(self.calls)
            return SimpleNamespace(result="DOWNLOADED", transferred_bytes=4)
        finally:
            self.active -= 1


def multi_item_plan(count: int, size: int = 4) -> DownloadPlan:
    items = []
    for index in range(count):
        candidate = DownloadCandidate(
            media_item_id=index + 1, channel_id=-1001,
            telegram_message_id=10 + index, media_ordinal=0,
            telegram_media_id=f"synthetic-{index}", expected_bytes=size,
            original_filename=f"item-{index}.bin", lineage=(("lesson", f"Lesson {index}"),),
        )
        identity = (-1001, 10 + index, 0)
        items.append(PlanItem(identity, candidate, "PENDING"))
    return DownloadPlan("plan", DownloadSelection(-1001), "Course", True, count, tuple(items))


def test_queue_retries_transient_error_with_bounded_attempt_count() -> None:
    async def action(call):
        if call < 3:
            raise DownloadError("NETWORK")
        return SimpleNamespace(result="DOWNLOADED", transferred_bytes=4)

    app = FakeApplication(action)
    queue = DownloadQueue(
        repository=object(), application=app,
        free_space=lambda _path: 10**12,
    )
    result = asyncio.run(queue.run(pending_plan()))
    assert app.calls == 3
    assert result.attempts == 3
    assert result.failed == 0


def test_queue_does_not_retry_terminal_failure() -> None:
    async def action(_call):
        raise DownloadError("ACCESS_DENIED")

    app = FakeApplication(action)
    result = asyncio.run(DownloadQueue(
        repository=object(), application=app,
        free_space=lambda _path: 10**12,
    ).run(pending_plan()))
    assert app.calls == 1
    assert result.failed == 1
    assert result.outcomes[0][2] == "ACCESS_DENIED"


def test_queue_honors_floodwait_and_preserves_shared_cooldown() -> None:
    class FakeClock:
        now = 0.0

        async def sleep(self, duration: float) -> None:
            self.now += duration

        def time(self) -> float:
            return self.now

    async def action(call):
        if call == 1:
            raise DownloadError("RATE_LIMITED", retry_after_seconds=7)
        return SimpleNamespace(result="DOWNLOADED", transferred_bytes=4)

    clock = FakeClock()
    app = FakeApplication(action)
    queue = DownloadQueue(
        repository=object(), application=app,
        free_space=lambda _path: 10**12,
        sleep=clock.sleep,
        clock=clock.time,
    )
    result = asyncio.run(queue.run(pending_plan()))
    assert app.calls == 2
    assert clock.now == 7
    assert result.attempts == 2


def test_queue_stops_when_floodwait_exceeds_per_media_budget() -> None:
    async def action(_call):
        raise DownloadError("RATE_LIMITED", retry_after_seconds=121)

    clock_values = iter([0.0, 0.0, 0.0, 0.0, 0.0])
    app = FakeApplication(action)
    result = asyncio.run(DownloadQueue(
        repository=object(), application=app,
        free_space=lambda _path: 10**12,
        clock=lambda: next(clock_values, 0.0),
    ).run(pending_plan()))
    assert app.calls == 1
    assert result.failed == 1
    assert result.outcomes[0][2] == "RATE_LIMITED"


def test_queue_progress_reports_aggregate_counts_and_bytes() -> None:
    reports = []
    app = FakeApplication()
    app.progress_callback = lambda current, total: None
    result = asyncio.run(DownloadQueue(
        repository=object(), application=app,
        free_space=lambda _path: 10**12,
        progress_callback=reports.append,
    ).run(pending_plan()))
    assert result.failed == 0
    assert reports[0]["pending"] == 1
    assert reports[-1]["completed"] == 1
    assert reports[-1]["bytes_transferred"] == 4
    assert reports[-1]["bytes_expected"] == 4


def test_configured_limits_reject_before_workers_or_attempts() -> None:
    async def exercise():
        for kwargs, expected in (
            ({"max_media_items": 1}, "MEDIA_LIMIT_EXCEEDED"),
            ({"max_transfer_bytes": 3}, "TRANSFER_BUDGET_EXCEEDED"),
        ):
            app = FakeApplication()
            queue = DownloadQueue(
                repository=object(), application=app,
                free_space=lambda _path: 10**12, **kwargs,
            )
            try:
                await queue.run(multi_item_plan(2) if "max_media_items" in kwargs else pending_plan())
            except DownloadError as error:
                assert error.category == expected
            else:
                raise AssertionError("configured limit should reject the plan")
            assert app.calls == 0
    asyncio.run(exercise())


def test_shared_byte_budget_admits_only_operations_that_fit() -> None:
    async def action(_call):
        await asyncio.sleep(0)
        return SimpleNamespace(result="DOWNLOADED", transferred_bytes=4)

    async def exercise():
        app = FakeApplication(action)
        queue = DownloadQueue(
            repository=object(), application=app, workers=2,
            max_media_items=2, max_transfer_bytes=8, free_space=lambda _path: 10**12,
        )
        result = await queue.run(multi_item_plan(2))
        assert app.calls == app.maximum_active == 2
        assert result.transferred_bytes == 8
        assert sum(status == "COMPLETED" for _, status, _ in result.outcomes) == 2
    asyncio.run(exercise())


def test_byte_budget_rejects_plan_with_excluded_unknown_size() -> None:
    plan = pending_plan()
    unknown = PlanItem((-1001, 11, 0), None, "EXCLUDED", "UNKNOWN_SIZE")
    plan = DownloadPlan(
        plan.plan_id, plan.selection, plan.scope_title, plan.catalog_complete,
        plan.lesson_count, (*plan.items, unknown),
    )
    app = FakeApplication()
    async def exercise():
        try:
            await DownloadQueue(
                repository=object(), application=app, max_transfer_bytes=10,
                free_space=lambda _path: 10**12,
            ).run(plan)
        except DownloadError as error:
            assert error.category == "UNKNOWN_SIZE"
        else:
            raise AssertionError("byte-capped plan with unknown size must fail closed")

    asyncio.run(exercise())
    assert app.calls == 0


def test_failed_attempt_bytes_are_charged_before_retry_admission() -> None:
    async def action(_call):
        raise DownloadError("NETWORK")

    async def exercise():
        app = FakeApplication(action)
        queue = DownloadQueue(
            repository=object(), application=app, workers=1,
            max_transfer_bytes=7, free_space=lambda _path: 10**12,
        )
        result = await queue.run(pending_plan())
        assert app.calls == 2
        assert result.attempts == 2
        assert app.requested_bytes == [4]
        assert app.received_bytes == [4]
        assert result.transferred_bytes == 4
        assert result.outcomes[0][1:] == ("BLOCKED", "TRANSFER_BUDGET_EXHAUSTED")
    asyncio.run(exercise())


def test_unbudgeted_failed_attempt_keeps_received_chunk_bytes() -> None:
    async def action(_call):
        raise DownloadError("NETWORK")

    app = FakeApplication(action)
    result = asyncio.run(DownloadQueue(
        repository=object(), application=app, workers=1,
        free_space=lambda _path: 10**12,
    ).run(pending_plan()))
    assert result.failed == 1
    assert app.calls == result.attempts == 3
    assert result.transferred_bytes == 12


def test_exact_budget_is_reserved_before_payload_and_fully_consumed() -> None:
    app = FakeApplication()
    result = asyncio.run(DownloadQueue(
        repository=object(), application=app, max_transfer_bytes=4,
        free_space=lambda _path: 10**12,
    ).run(pending_plan()))
    assert app.requested_bytes == [4]
    assert app.received_bytes == [4]
    assert result.transferred_bytes == 4
    assert result.failed == 0


def test_declared_size_above_budget_is_rejected_during_preflight() -> None:
    app = FakeApplication()
    try:
        asyncio.run(DownloadQueue(
            repository=object(), application=app, max_transfer_bytes=7,
            free_space=lambda _path: 10**12,
        ).run(pending_plan(size=8)))
    except DownloadError as error:
        assert error.category == "TRANSFER_BUDGET_EXCEEDED"
    else:
        raise AssertionError("preflight must reject declared bytes above the budget")
    assert app.calls == 0
    assert app.requested_bytes == app.received_bytes == []


def test_next_stream_request_is_not_started_without_a_full_reservation() -> None:
    class TwoChunkApplication(FakeApplication):
        async def download(self, *_identity):
            self.calls += 1
            self.reservation_requests = []
            self.reservations = []
            first = await self.chunk_reserver(4)
            self.reservation_requests.append(4)
            assert first is not None
            self.reservations.append(first)
            self.requested_bytes.append(4)
            self.received_bytes.append(4)
            first.received(4)
            second = await self.chunk_reserver(4)
            self.reservation_requests.append(4)
            if second is None:
                raise DownloadError("TRANSFER_BUDGET_EXHAUSTED")
            self.reservations.append(second)
            self.requested_bytes.append(4)
            self.received_bytes.append(4)
            second.received(4)
            return SimpleNamespace(result="DOWNLOADED", transferred_bytes=8)

    app = TwoChunkApplication()
    result = asyncio.run(DownloadQueue(
        repository=object(), application=app, max_transfer_bytes=7,
        free_space=lambda _path: 10**12,
    ).run(pending_plan(size=7)))
    assert app.calls == 1
    assert app.reservation_requests == [4, 4]
    assert len(app.reservations) == 1
    assert app.reservations[0].amount == 4
    assert app.requested_bytes == [4]
    assert app.received_bytes == [4]
    assert result.transferred_bytes == 4
    assert result.attempts == 1
    assert result.outcomes[0][1:] == ("BLOCKED", "TRANSFER_BUDGET_EXHAUSTED")


def test_cancelled_inflight_request_is_charged_conservatively() -> None:
    class CancellingApplication(FakeApplication):
        async def download(self, *_identity):
            reservation = await self.chunk_reserver(4)
            assert reservation is not None
            reservation.charge_uncertain()
            raise asyncio.CancelledError

    result = asyncio.run(DownloadQueue(
        repository=object(), application=CancellingApplication(), max_transfer_bytes=4,
        free_space=lambda _path: 10**12,
    ).run(pending_plan()))
    assert result.cancelled is True
    assert result.transferred_bytes == 0
    assert result.outcomes[0][1:] == ("CANCELLED", "CANCELLED")


def test_simultaneous_chunk_reservations_do_not_overcommit_budget() -> None:
    async def exercise():
        app = FakeApplication()
        queue = DownloadQueue(
            repository=object(), application=app, workers=2,
            max_transfer_bytes=8, free_space=lambda _path: 10**12,
        )
        result = await queue.run(multi_item_plan(2))
        assert app.maximum_active == 2
        assert result.transferred_bytes == 8
        assert sum(status == "COMPLETED" for _, status, _ in result.outcomes) == 2
    asyncio.run(exercise())
