"""Project-owned models and workflow for local Telegram channel selection."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from telegram_courses.auth import (
    AuthenticationError,
    AuthRejected,
    AuthState,
    InvalidSession,
    NetworkError,
    RateLimited,
)
from telegram_courses.config import TelegramCredentials

_CALIBRATION_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from telegram_courses.telegram_gateway import TelegramGateway


class ChannelKind(str, Enum):
    BROADCAST_CHANNEL = "BROADCAST_CHANNEL"
    MEGAGROUP = "MEGAGROUP"


class DiscoveryStopReason(str, Enum):
    RAW_DIALOG_LIMIT = "RAW_DIALOG_LIMIT"
    PAGE_LIMIT = "PAGE_LIMIT"
    TIME_BUDGET = "TIME_BUDGET"


class DiscoveryErrorCategory(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_INVALID = "SESSION_INVALID"
    ACCESS_DENIED = "ACCESS_DENIED"
    NETWORK = "NETWORK"
    RATE_LIMITED = "RATE_LIMITED"
    ADAPTER_FAILURE = "ADAPTER_FAILURE"
    INVALID_SELECTION = "INVALID_SELECTION"
    CLEANUP_FAILED = "CLEANUP_FAILED"


_ERROR_MESSAGES = {
    DiscoveryErrorCategory.AUTH_REQUIRED: "run authentication before discovery",
    DiscoveryErrorCategory.SESSION_INVALID: "stored session is invalid; run authentication",
    DiscoveryErrorCategory.ACCESS_DENIED: "channel discovery access denied",
    DiscoveryErrorCategory.NETWORK: "channel discovery network unavailable",
    DiscoveryErrorCategory.RATE_LIMITED: "channel discovery rate limited",
    DiscoveryErrorCategory.ADAPTER_FAILURE: "channel discovery service failure",
    DiscoveryErrorCategory.INVALID_SELECTION: "invalid channel selection",
    DiscoveryErrorCategory.CLEANUP_FAILED: "channel discovery cleanup failed",
}


class ChannelDiscoveryError(Exception):
    """Safe, project-owned discovery error; never carries raw Telethon data."""

    def __init__(
        self,
        category: DiscoveryErrorCategory,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        if not isinstance(category, DiscoveryErrorCategory):
            raise TypeError("invalid discovery error category")
        if category is DiscoveryErrorCategory.RATE_LIMITED:
            if type(retry_after_seconds) is not int or retry_after_seconds < 0:
                raise ValueError("invalid retry duration")
        elif retry_after_seconds is not None:
            raise ValueError("retry duration is only valid for rate limits")
        self.category = category
        self.retry_after_seconds = retry_after_seconds
        super().__init__(_ERROR_MESSAGES[category])

    def __str__(self) -> str:
        return _ERROR_MESSAGES[self.category]


@dataclass(frozen=True, slots=True)
class DiscoveryLimits:
    page_size: int = 100
    max_raw_dialogs: int = 1000
    max_pages: int = 20
    operation_timeout_seconds: float = 120.0
    cleanup_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        integer_limits = (
            ("page_size", self.page_size, 1, 100),
            ("max_raw_dialogs", self.max_raw_dialogs, 1, 1000),
            ("max_pages", self.max_pages, 1, 20),
        )
        for name, value, minimum, maximum in integer_limits:
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"invalid {name}")
        time_limits = (
            ("operation_timeout_seconds", self.operation_timeout_seconds, 120.0),
            ("cleanup_timeout_seconds", self.cleanup_timeout_seconds, 10.0),
        )
        for name, value, maximum in time_limits:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 < value <= maximum
            ):
                raise ValueError(f"invalid {name}")


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    limits: DiscoveryLimits = field(default_factory=DiscoveryLimits)
    started_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if not isinstance(self.limits, DiscoveryLimits):
            raise ValueError("invalid discovery limits")
        if (
            isinstance(self.started_at, bool)
            or not isinstance(self.started_at, (int, float))
            or not math.isfinite(self.started_at)
            or self.started_at < 0
        ):
            raise ValueError("invalid discovery start time")

    @property
    def deadline(self) -> float:
        return self.started_at + self.limits.operation_timeout_seconds


@dataclass(frozen=True, slots=True)
class ChannelSummary:
    telegram_chat_id: int
    title: str
    username: str | None
    kind: ChannelKind

    def __post_init__(self) -> None:
        if (
            type(self.telegram_chat_id) is not int
            or self.telegram_chat_id > -1_000_000_000_000
        ):
            raise ValueError("invalid telegram chat id")
        if not isinstance(self.title, str):
            raise ValueError("invalid channel title")
        if self.username is not None and not isinstance(self.username, str):
            raise ValueError("invalid channel username")
        if not isinstance(self.kind, ChannelKind):
            raise ValueError("invalid channel kind")


@dataclass(frozen=True, slots=True)
class DiscoveryStats:
    pages_requested: int
    pages_received: int
    raw_dialogs_received: int
    unique_candidates: int
    elapsed_seconds: float
    limits: DiscoveryLimits


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    channels: tuple[ChannelSummary, ...]
    complete: bool
    stop_reason: DiscoveryStopReason | None
    stats: DiscoveryStats

    def __post_init__(self) -> None:
        if type(self.complete) is not bool:
            raise ValueError("invalid discovery completion state")
        if self.complete != (self.stop_reason is None):
            raise ValueError("inconsistent discovery completion state")
        if not isinstance(self.channels, tuple) or not all(
            isinstance(channel, ChannelSummary) for channel in self.channels
        ):
            raise ValueError("invalid discovery channels")
        if not isinstance(self.stats, DiscoveryStats):
            raise ValueError("invalid discovery stats")


@dataclass(frozen=True, slots=True)
class SelectedChannel:
    telegram_chat_id: int

    def __post_init__(self) -> None:
        if (
            type(self.telegram_chat_id) is not int
            or self.telegram_chat_id > -1_000_000_000_000
        ):
            raise ValueError("invalid telegram chat id")


class DiscoveryOutcomeState(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_INVALID = "SESSION_INVALID"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    INCOMPLETE_EMPTY = "INCOMPLETE_EMPTY"


@dataclass(frozen=True, slots=True)
class DiscoveryOutcome:
    state: DiscoveryOutcomeState
    result: DiscoveryResult | None = None

    def __post_init__(self) -> None:
        result_required = self.state in {
            DiscoveryOutcomeState.COMPLETE,
            DiscoveryOutcomeState.PARTIAL,
            DiscoveryOutcomeState.EMPTY,
            DiscoveryOutcomeState.INCOMPLETE_EMPTY,
        }
        if result_required != (self.result is not None):
            raise ValueError("inconsistent discovery outcome")
        if self.result is not None:
            complete_state = self.state in {
                DiscoveryOutcomeState.COMPLETE,
                DiscoveryOutcomeState.EMPTY,
            }
            empty_state = self.state in {
                DiscoveryOutcomeState.EMPTY,
                DiscoveryOutcomeState.INCOMPLETE_EMPTY,
            }
            if self.result.complete != complete_state:
                raise ValueError("inconsistent discovery outcome state")
            if bool(self.result.channels) == empty_state:
                raise ValueError("inconsistent empty discovery outcome")


def select_channel(
    snapshot: DiscoveryResult, telegram_chat_id: int
) -> SelectedChannel:
    if type(telegram_chat_id) is not int:
        raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)
    for channel in snapshot.channels:
        if channel.telegram_chat_id == telegram_chat_id:
            return SelectedChannel(telegram_chat_id)
    raise ChannelDiscoveryError(DiscoveryErrorCategory.INVALID_SELECTION)


class ChannelDiscoveryApplication:
    """Coordinates existing auth restore, bounded discovery, and cleanup."""

    def __init__(
        self,
        gateway_factory: Callable[[TelegramCredentials], TelegramGateway],
        credentials: Callable[[], TelegramCredentials],
        *,
        limits: DiscoveryLimits | None = None,
    ) -> None:
        self._gateway_factory = gateway_factory
        self._credentials = credentials
        self._limits = limits or DiscoveryLimits()

    async def discover(self) -> DiscoveryOutcome:
        credentials = self._credentials()
        if not isinstance(credentials, TelegramCredentials):
            raise ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)
        request = DiscoveryRequest(self._limits)
        gateway = self._gateway_factory(credentials)
        primary_error: BaseException | None = None
        outcome: DiscoveryOutcome | None = None
        failure_category = "NONE"
        restore_elapsed = 0.0
        discovery_elapsed = 0.0
        cleanup_elapsed = 0.0
        cleanup_status = "NOT_RUN"
        try:
            remaining = request.deadline - time.monotonic()
            if remaining <= 0:
                failure_category = DiscoveryErrorCategory.NETWORK.value
                raise ChannelDiscoveryError(DiscoveryErrorCategory.NETWORK)
            restore_started = time.monotonic()
            try:
                state = await asyncio.wait_for(gateway.restore(), remaining)
            except TimeoutError:
                failure_category = DiscoveryErrorCategory.NETWORK.value
                raise ChannelDiscoveryError(DiscoveryErrorCategory.NETWORK) from None
            finally:
                restore_elapsed = max(0.0, time.monotonic() - restore_started)
            if state is AuthState.AUTH_REQUIRED:
                outcome = DiscoveryOutcome(DiscoveryOutcomeState.AUTH_REQUIRED)
            elif state is AuthState.SESSION_INVALID:
                outcome = DiscoveryOutcome(DiscoveryOutcomeState.SESSION_INVALID)
            elif state is not AuthState.AUTHENTICATED:
                failure_category = DiscoveryErrorCategory.ADAPTER_FAILURE.value
                raise ChannelDiscoveryError(DiscoveryErrorCategory.ADAPTER_FAILURE)
            else:
                discovery_started = time.monotonic()
                try:
                    result = await gateway.discover_channels(request)
                finally:
                    discovery_elapsed = max(
                        0.0, time.monotonic() - discovery_started
                    )
                if not result.channels:
                    state = (
                        DiscoveryOutcomeState.EMPTY
                        if result.complete
                        else DiscoveryOutcomeState.INCOMPLETE_EMPTY
                    )
                else:
                    state = (
                        DiscoveryOutcomeState.COMPLETE
                        if result.complete
                        else DiscoveryOutcomeState.PARTIAL
                    )
                outcome = DiscoveryOutcome(state, result)
        except BaseException as error:
            primary_error = error
            if isinstance(error, ChannelDiscoveryError):
                failure_category = error.category.value
            elif isinstance(error, asyncio.CancelledError):
                failure_category = "CANCELLED"
            else:
                failure_category = DiscoveryErrorCategory.ADAPTER_FAILURE.value
            if isinstance(error, RateLimited):
                failure_category = DiscoveryErrorCategory.RATE_LIMITED.value
                raise ChannelDiscoveryError(
                    DiscoveryErrorCategory.RATE_LIMITED,
                    retry_after_seconds=error.retry_after_seconds,
                ) from None
            if isinstance(error, NetworkError):
                failure_category = DiscoveryErrorCategory.NETWORK.value
                raise ChannelDiscoveryError(DiscoveryErrorCategory.NETWORK) from None
            if isinstance(error, InvalidSession):
                failure_category = DiscoveryErrorCategory.SESSION_INVALID.value
                raise ChannelDiscoveryError(
                    DiscoveryErrorCategory.SESSION_INVALID
                ) from None
            if isinstance(error, AuthRejected):
                failure_category = DiscoveryErrorCategory.ACCESS_DENIED.value
                raise ChannelDiscoveryError(
                    DiscoveryErrorCategory.ACCESS_DENIED
                ) from None
            if isinstance(error, AuthenticationError):
                failure_category = DiscoveryErrorCategory.ADAPTER_FAILURE.value
                raise ChannelDiscoveryError(
                    DiscoveryErrorCategory.ADAPTER_FAILURE
                ) from None
            raise
        finally:
            cleanup_started = time.monotonic()
            try:
                await self._close(gateway, self._limits.cleanup_timeout_seconds)
                cleanup_status = "COMPLETE"
            except ChannelDiscoveryError:
                cleanup_status = "FAILED"
                if primary_error is None:
                    failure_category = DiscoveryErrorCategory.CLEANUP_FAILED.value
                if primary_error is None:
                    raise
            except asyncio.CancelledError:
                cleanup_status = "CANCELLED"
                raise
            except BaseException:
                cleanup_status = "FAILED"
                if primary_error is None:
                    failure_category = DiscoveryErrorCategory.CLEANUP_FAILED.value
                if primary_error is None:
                    raise
            finally:
                cleanup_elapsed = max(0.0, time.monotonic() - cleanup_started)
                result = outcome.result if outcome is not None else None
                stats = result.stats if result is not None else None
                _CALIBRATION_LOGGER.warning(
                    "S1D_CALIBRATION OPERATION_SECONDS=%.6f "
                    "RESTORE_SECONDS=%.6f "
                    "DISCOVERY_SECONDS=%.6f CLEANUP_SECONDS=%.6f "
                    "CLEANUP_STATUS=%s PAGES_REQUESTED=%s PAGES_RECEIVED=%s "
                    "RAW_DIALOGS_PROCESSED=%s PAGE_SIZE_LIMIT=%d "
                    "RAW_DIALOG_LIMIT=%d PAGE_LIMIT=%d OPERATION_BUDGET_SECONDS=%.3f "
                    "CLEANUP_BUDGET_SECONDS=%.3f RESULT=%s OUTCOME_STATE=%s "
                    "STOP_REASON=%s FAILURE_CATEGORY=%s",
                    max(0.0, cleanup_started - request.started_at),
                    restore_elapsed,
                    discovery_elapsed,
                    cleanup_elapsed,
                    cleanup_status,
                    stats.pages_requested if stats is not None else "NA",
                    stats.pages_received if stats is not None else "NA",
                    stats.raw_dialogs_received if stats is not None else "NA",
                    self._limits.page_size,
                    self._limits.max_raw_dialogs,
                    self._limits.max_pages,
                    self._limits.operation_timeout_seconds,
                    self._limits.cleanup_timeout_seconds,
                    (
                        "COMPLETE"
                        if result is not None and result.complete
                        else "PARTIAL"
                        if result is not None
                        else "ERROR"
                        if outcome is None
                        else "NOT_STARTED"
                    ),
                    outcome.state.value if outcome is not None else "ERROR",
                    (
                        result.stop_reason.value
                        if result is not None and result.stop_reason is not None
                        else "NONE"
                        if result is not None
                        else "NA"
                    ),
                    failure_category,
                )
        assert outcome is not None
        return outcome

    @staticmethod
    async def _close(gateway: TelegramGateway, timeout: float) -> None:
        close_task = asyncio.create_task(gateway.close())
        try:
            await asyncio.wait_for(asyncio.shield(close_task), timeout)
        except asyncio.CancelledError:
            try:
                await asyncio.wait_for(asyncio.shield(close_task), timeout)
            except BaseException:
                close_task.cancel()
            raise
        except TimeoutError:
            close_task.cancel()
            await asyncio.gather(close_task, return_exceptions=True)
            raise ChannelDiscoveryError(
                DiscoveryErrorCategory.CLEANUP_FAILED
            ) from None
        except Exception:
            raise ChannelDiscoveryError(
                DiscoveryErrorCategory.CLEANUP_FAILED
            ) from None
