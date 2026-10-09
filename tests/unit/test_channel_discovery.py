from __future__ import annotations

import asyncio

import pytest

from telegram_courses.auth import AuthState, NetworkError, RateLimited
from telegram_courses.channel_discovery import (
    ChannelDiscoveryApplication,
    ChannelDiscoveryError,
    ChannelKind,
    ChannelSummary,
    DiscoveryErrorCategory,
    DiscoveryLimits,
    DiscoveryOutcomeState,
    DiscoveryResult,
    DiscoveryStats,
    DiscoveryStopReason,
    SelectedChannel,
    select_channel,
)
from telegram_courses.config import TelegramCredentials


def summary(chat_id: int = -1_000_000_000_123) -> ChannelSummary:
    return ChannelSummary(chat_id, "Synthetic", None, ChannelKind.BROADCAST_CHANNEL)


def result(*, complete: bool = True) -> DiscoveryResult:
    limits = DiscoveryLimits()
    return DiscoveryResult(
        channels=(summary(),),
        complete=complete,
        stop_reason=None if complete else DiscoveryStopReason.PAGE_LIMIT,
        stats=DiscoveryStats(1, 1, 1, 1, 0.1, limits),
    )


class FakeGateway:
    def __init__(
        self,
        events: list[str],
        *,
        state: AuthState = AuthState.AUTHENTICATED,
        outcome: DiscoveryResult | None = None,
        discovery_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.state = state
        self.outcome = outcome or result()
        self.discovery_error = discovery_error
        self.close_error = close_error

    async def restore(self) -> AuthState:
        self.events.append("restore")
        return self.state

    async def discover_channels(self, request) -> DiscoveryResult:
        self.events.append("discover")
        assert request.limits.page_size == 100
        assert request.limits.max_raw_dialogs == 1000
        assert request.limits.max_pages == 20
        if self.discovery_error:
            raise self.discovery_error
        return self.outcome

    async def close(self) -> None:
        self.events.append("close")
        if self.close_error:
            raise self.close_error


def application(gateway: FakeGateway) -> ChannelDiscoveryApplication:
    return ChannelDiscoveryApplication(
        lambda _credentials: gateway,
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"page_size": True},
        {"page_size": 101},
        {"max_raw_dialogs": 0},
        {"max_pages": 21},
        {"operation_timeout_seconds": float("inf")},
        {"operation_timeout_seconds": True},
        {"cleanup_timeout_seconds": 11},
    ],
)
def test_limits_reject_invalid_or_over_budget_values(kwargs) -> None:
    with pytest.raises(ValueError):
        DiscoveryLimits(**kwargs)


def test_discovery_returns_snapshot_after_gateway_is_closed() -> None:
    events: list[str] = []
    gateway = FakeGateway(events, outcome=result(complete=False))
    outcome = asyncio.run(application(gateway).discover())

    assert outcome.state is DiscoveryOutcomeState.PARTIAL
    assert outcome.result is not None
    assert outcome.result.stop_reason is DiscoveryStopReason.PAGE_LIMIT
    assert events == ["restore", "discover", "close"]


@pytest.mark.parametrize(
    ("complete", "expected"),
    [
        (True, DiscoveryOutcomeState.EMPTY),
        (False, DiscoveryOutcomeState.INCOMPLETE_EMPTY),
    ],
)
def test_empty_discovery_states_are_explicit(complete, expected) -> None:
    limits = DiscoveryLimits()
    empty = DiscoveryResult(
        channels=(),
        complete=complete,
        stop_reason=None if complete else DiscoveryStopReason.PAGE_LIMIT,
        stats=DiscoveryStats(1, 1, 1, 0, 0.1, limits),
    )
    events: list[str] = []

    outcome = asyncio.run(
        application(FakeGateway(events, outcome=empty)).discover()
    )

    assert outcome.state is expected
    assert outcome.result == empty
    assert events == ["restore", "discover", "close"]


@pytest.mark.parametrize(
    ("auth_state", "expected"),
    [
        (AuthState.AUTH_REQUIRED, DiscoveryOutcomeState.AUTH_REQUIRED),
        (AuthState.SESSION_INVALID, DiscoveryOutcomeState.SESSION_INVALID),
    ],
)
def test_missing_or_invalid_session_never_starts_discovery(auth_state, expected) -> None:
    events: list[str] = []
    outcome = asyncio.run(
        application(FakeGateway(events, state=auth_state)).discover()
    )

    assert outcome.state is expected
    assert outcome.result is None
    assert events == ["restore", "close"]


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (NetworkError(), DiscoveryErrorCategory.NETWORK),
        (RateLimited(17), DiscoveryErrorCategory.RATE_LIMITED),
    ],
)
def test_auth_adapter_errors_map_to_discovery_errors(error, category) -> None:
    events: list[str] = []
    with pytest.raises(ChannelDiscoveryError) as caught:
        asyncio.run(
            application(FakeGateway(events, discovery_error=error)).discover()
        )

    assert caught.value.category is category
    assert events == ["restore", "discover", "close"]
    assert "synthetic" not in str(caught.value)


def test_cleanup_failure_is_controlled_and_hides_raw_error() -> None:
    events: list[str] = []
    with pytest.raises(ChannelDiscoveryError) as caught:
        asyncio.run(
            application(
                FakeGateway(events, close_error=RuntimeError("secret-canary"))
            ).discover()
        )
    assert caught.value.category is DiscoveryErrorCategory.CLEANUP_FAILED
    assert "secret-canary" not in str(caught.value)
    assert events == ["restore", "discover", "close"]


def test_cleanup_has_its_own_bounded_timeout() -> None:
    class HangingCloseGateway(FakeGateway):
        async def close(self) -> None:
            self.events.append("close")
            await asyncio.Event().wait()

    events: list[str] = []
    limits = DiscoveryLimits(cleanup_timeout_seconds=0.01)
    app = ChannelDiscoveryApplication(
        lambda _credentials: HangingCloseGateway(events),
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
        limits=limits,
    )
    with pytest.raises(ChannelDiscoveryError) as caught:
        asyncio.run(app.discover())
    assert caught.value.category is DiscoveryErrorCategory.CLEANUP_FAILED
    assert events == ["restore", "discover", "close"]


def test_restore_uses_operation_budget_and_cleans_up_on_timeout() -> None:
    class SlowRestoreGateway(FakeGateway):
        async def restore(self) -> AuthState:
            self.events.append("restore")
            await asyncio.sleep(0.1)
            return AuthState.AUTHENTICATED

    events: list[str] = []
    limits = DiscoveryLimits(operation_timeout_seconds=0.01)
    app = ChannelDiscoveryApplication(
        lambda _credentials: SlowRestoreGateway(events),
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
        limits=limits,
    )
    with pytest.raises(ChannelDiscoveryError) as caught:
        asyncio.run(app.discover())
    assert caught.value.category is DiscoveryErrorCategory.NETWORK
    assert events == ["restore", "close"]


def test_cancelled_discovery_still_closes_gateway() -> None:
    class BlockingGateway(FakeGateway):
        async def discover_channels(self, request) -> DiscoveryResult:
            self.events.append("discover")
            await asyncio.Event().wait()

    events: list[str] = []
    gateway = BlockingGateway(events)
    app = application(gateway)

    async def cancel_during_discovery() -> None:
        task = asyncio.create_task(app.discover())
        while "discover" not in events:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_during_discovery())
    assert events == ["restore", "discover", "close"]


def test_selection_is_local_and_requires_exact_present_canonical_id() -> None:
    snapshot = result()
    assert select_channel(snapshot, -1_000_000_000_123) == SelectedChannel(
        -1_000_000_000_123
    )
    for invalid in (True, 0, 123, -123, -1_000_000_000_124):
        with pytest.raises(ChannelDiscoveryError) as caught:
            select_channel(snapshot, invalid)
        assert caught.value.category is DiscoveryErrorCategory.INVALID_SELECTION


def test_channel_dto_has_no_message_or_telethon_payload_fields() -> None:
    names = set(ChannelSummary.__dataclass_fields__)
    assert names == {"telegram_chat_id", "title", "username", "kind"}
    assert not names.intersection(
        {"message", "last_message", "text", "media", "draft", "access_hash"}
    )
