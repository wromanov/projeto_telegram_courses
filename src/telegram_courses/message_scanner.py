"""Project-owned message scan models and orchestration."""

from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Callable, Protocol

from telegram_courses.auth import AuthState


@dataclass(frozen=True)
class GatewayMedia:
    media_ordinal: int
    kind: str
    telegram_media_id: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None


@dataclass(frozen=True)
class GatewayMessage:
    telegram_chat_id: int
    telegram_message_id: int
    date_utc: str
    edit_date_utc: str | None
    text: str | None
    grouped_id: int | None
    media: tuple[GatewayMedia, ...] = ()


class ScanStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ScanGatewayError(Exception):
    """Sanitized gateway failure; carries retry timing without raw TL data."""

    def __init__(
        self, category: str, *, retry_after_seconds: int | None = None
    ) -> None:
        if category not in {
            "AUTH_REQUIRED", "SESSION_INVALID", "ACCESS_DENIED", "NETWORK",
            "RATE_LIMITED", "ADAPTER_FAILURE", "CHANNEL_UNRESOLVED",
        }:
            raise ValueError("invalid scan error category")
        self.category = category
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"message scan {category.lower().replace('_', ' ')}")


@dataclass(frozen=True)
class ScanRequest:
    max_messages: int
    timeout_seconds: float
    resume_run_id: str | None = None
    mode: str = "FULL"
    reconcile_window: int = 0

    def __post_init__(self) -> None:
        if type(self.max_messages) is not int or self.max_messages <= 0:
            raise ValueError("max_messages must be a positive integer")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")
        if self.mode not in {"FULL", "INCREMENTAL"}:
            raise ValueError("invalid scan mode")
        if type(self.reconcile_window) is not int or self.reconcile_window < 0:
            raise ValueError("reconcile_window must be a non-negative integer")
        if self.mode == "FULL" and self.reconcile_window != 0:
            raise ValueError("full scans do not accept a reconcile window")


class ScanDeadline:
    """One monotonic budget shared by the scan and its cleanup."""

    def __init__(
        self, timeout_seconds: float, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._clock = clock
        self.expires_at = clock() + timeout_seconds
        self.cleanup_starts_at = self.expires_at - min(timeout_seconds * 0.2, 5.0)
        self.finalization_starts_at = self.expires_at - min(
            timeout_seconds * 0.05, 2.0
        )

    def remaining(
        self, *, cleanup: bool = False, finalization: bool = False
    ) -> float:
        if finalization:
            limit = self.expires_at
        elif cleanup:
            limit = self.finalization_starts_at
        else:
            limit = self.cleanup_starts_at
        return max(0.0, limit - self._clock())

    def check(self) -> None:
        if self.remaining() <= 0:
            raise TimeoutError

    async def wait(
        self, awaitable: Any, *, cleanup: bool = False, finalization: bool = False
    ) -> Any:
        remaining = self.remaining(cleanup=cleanup, finalization=finalization)
        if remaining <= 0:
            if inspect.iscoroutine(awaitable):
                awaitable.close()
            raise TimeoutError
        result = await asyncio.wait_for(awaitable, timeout=remaining)
        if self.remaining(cleanup=cleanup, finalization=finalization) <= 0:
            raise TimeoutError
        return result


@dataclass(frozen=True)
class ScanOutcome:
    run_id: str
    status: ScanStatus
    stop_reason: str | None
    messages_seen: int
    messages_inserted: int
    messages_updated: int
    media_seen: int
    last_message_id: int | None
    messages_unchanged: int = 0
    messages_unverified: int | None = 0
    media_unverified: int = 0
    high_water_confirmed: int | None = None
    has_confirmed_high_water: bool = False


class MessageGateway(Protocol):
    async def restore(self) -> AuthState: ...

    def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
        min_message_id: int | None = None,
    ) -> AsyncIterator[GatewayMessage]: ...


class ScanRepository(Protocol):
    async def start_run(
        self, telegram_chat_id: int, watermark: int | None, run_id: str
    ) -> int | None: ...

    async def set_watermark(self, run_id: str, watermark: int | None) -> None: ...

    async def set_sync_snapshot_head(self, run_id: str, head_message_id: int) -> None: ...

    async def resume_run(
        self, run_id: str, telegram_chat_id: int
    ) -> tuple[int | None, int | None]: ...

    async def persist_batch(
        self, run_id: str, messages: tuple[GatewayMessage, ...]
    ) -> tuple[int, int]: ...

    async def finish_run(
        self, run_id: str, status: ScanStatus, reason: str | None
    ) -> None: ...

    async def get_confirmed_high_water(
        self, telegram_chat_id: int
    ) -> tuple[bool, int | None]: ...

    async def find_resumable_sync_run(self, telegram_chat_id: int) -> str | None: ...

    async def start_sync_run(
        self,
        telegram_chat_id: int,
        run_id: str,
        *,
        max_messages: int,
        reconcile_window: int,
    ) -> dict[str, int | str | None | bool]: ...

    async def resume_sync_run(
        self, run_id: str, telegram_chat_id: int
    ) -> dict[str, int | str | None | bool]: ...

    async def get_sync_run_summary(
        self, run_id: str
    ) -> dict[str, int | str | None | bool]: ...


class MessageScanner:
    def __init__(self, gateway: MessageGateway, repository: ScanRepository) -> None:
        self._gateway = gateway
        self._repository = repository

    async def scan(
        self,
        telegram_chat_id: int,
        request: ScanRequest,
        *,
        deadline: ScanDeadline | None = None,
    ) -> ScanOutcome:
        if type(telegram_chat_id) is not int or telegram_chat_id == 0:
            raise ValueError("invalid telegram_chat_id")
        deadline = deadline or ScanDeadline(request.timeout_seconds)
        if request.mode == "INCREMENTAL":
            return await self._incremental_scan(
                telegram_chat_id, request, deadline=deadline
            )
        run_id = request.resume_run_id or uuid.uuid4().hex
        if request.resume_run_id:
            watermark, cursor = await deadline.wait(
                self._repository.resume_run(run_id, telegram_chat_id)
            )
        else:
            watermark = None
            cursor = await deadline.wait(
                self._repository.start_run(telegram_chat_id, None, run_id)
            )
        seen = inserted = updated = media_seen = 0
        reason: str | None = None
        batch: list[GatewayMessage] = []
        previous_id = watermark + 1 if watermark is not None else None
        durable_cursor = cursor
        iterator: AsyncIterator[GatewayMessage] | None = None
        status = ScanStatus.FAILED
        primary_error: BaseException | None = None

        async def commit(*, cleanup: bool = False) -> None:
            nonlocal inserted, updated, media_seen, durable_cursor
            if batch:
                try:
                    new_count, update_count = await deadline.wait(
                        self._repository.persist_batch(run_id, tuple(batch)),
                        cleanup=cleanup,
                    )
                except TimeoutError:
                    batch.clear()
                    raise
                inserted += new_count
                updated += update_count
                media_seen += sum(len(item.media) for item in batch)
                durable_cursor = min(item.telegram_message_id for item in batch)
                batch.clear()

        exhausted = True
        try:
            state = await deadline.wait(self._gateway.restore())
            if state is not AuthState.AUTHENTICATED:
                category = (
                    "SESSION_INVALID"
                    if state is AuthState.SESSION_INVALID
                    else "AUTH_REQUIRED"
                )
                raise ScanGatewayError(category)
            iterator = self._gateway.iter_channel_messages(
                telegram_chat_id,
                through_message_id=watermark,
                before_message_id=cursor,
                limit=request.max_messages,
            ).__aiter__()
            while True:
                try:
                    message = await deadline.wait(iterator.__anext__())
                except StopAsyncIteration:
                    exhausted = True
                    break
                if (
                    message.telegram_chat_id != telegram_chat_id
                    or message.telegram_message_id <= 0
                ):
                    raise ValueError("invalid gateway message identity")
                if watermark is None:
                    watermark = message.telegram_message_id
                    await deadline.wait(
                        self._repository.set_watermark(run_id, watermark)
                    )
                if (
                    message.telegram_message_id > watermark
                    or (
                        previous_id is not None
                        and message.telegram_message_id >= previous_id
                    )
                ):
                    raise ValueError("invalid gateway message sequence")
                previous_id = message.telegram_message_id
                batch.append(normalize_message(message))
                seen += 1
                if len(batch) >= 100:
                    await commit()
                if seen >= request.max_messages:
                    reason = "MESSAGE_LIMIT"
                    exhausted = False
                    break
            await commit()
            status = (
                ScanStatus.COMPLETE
                if exhausted and reason is None
                else ScanStatus.PARTIAL
            )
        except TimeoutError:
            reason = "TIMEOUT"
            exhausted = False
            if batch:
                await commit(cleanup=True)
            status = (
                ScanStatus.PARTIAL
                if durable_cursor is not None
                else ScanStatus.FAILED
            )
        except asyncio.CancelledError as error:
            primary_error = error
            if batch:
                await commit(cleanup=True)
            await deadline.wait(
                self._repository.finish_run(
                    run_id, ScanStatus.PARTIAL, "CANCELLED"
                ),
                finalization=True,
            )
            raise
        except ScanGatewayError as error:
            primary_error = error
            status = ScanStatus.PARTIAL if durable_cursor is not None else ScanStatus.FAILED
            await deadline.wait(
                self._repository.finish_run(run_id, status, error.category),
                finalization=True,
            )
            raise
        except Exception as error:
            primary_error = error
            await deadline.wait(
                self._repository.finish_run(
                    run_id, ScanStatus.FAILED, "SCAN_FAILURE"
                ),
                finalization=True,
            )
            raise
        finally:
            if iterator is not None:
                close = getattr(iterator, "aclose", None)
                if close is not None:
                    try:
                        await deadline.wait(close(), cleanup=True)
                    except BaseException:
                        if primary_error is None:
                            status = ScanStatus.FAILED
                            reason = "CLEANUP_FAILURE"
        if status is ScanStatus.PARTIAL and durable_cursor is None:
            status = ScanStatus.FAILED
        cursor = durable_cursor
        await deadline.wait(
            self._repository.finish_run(run_id, status, reason), finalization=True
        )
        return ScanOutcome(
            run_id, status, reason, seen, inserted, updated, media_seen, cursor
        )

    async def _incremental_scan(
        self,
        telegram_chat_id: int,
        request: ScanRequest,
        *,
        deadline: ScanDeadline,
    ) -> ScanOutcome:
        """Run a bounded incremental sync with a separate committed baseline."""
        resume_id = request.resume_run_id
        if resume_id is None:
            resume_id = await deadline.wait(
                self._repository.find_resumable_sync_run(telegram_chat_id)
            )
        if resume_id is not None:
            run_id = resume_id
            state = await deadline.wait(
                self._repository.resume_sync_run(run_id, telegram_chat_id)
            )
            if (
                state["max_messages"] != request.max_messages
                or state["reconcile_window"] != request.reconcile_window
            ):
                await deadline.wait(
                    self._repository.finish_run(
                        run_id, ScanStatus.PARTIAL, "RESUME_SCOPE_MISMATCH"
                    ),
                    finalization=True,
                )
                raise ValueError("resume scope differs from the stored sync run")
        else:
            run_id = uuid.uuid4().hex
            state = await deadline.wait(
                self._repository.start_sync_run(
                    telegram_chat_id,
                    run_id,
                    max_messages=request.max_messages,
                    reconcile_window=request.reconcile_window,
                )
            )
        watermark = state["snapshot_head"]
        cursor = state["cursor"]
        floor = state["reconcile_floor"]
        seen = inserted = updated = media_seen = 0
        durable_cursor = cursor
        reason: str | None = None
        status = ScanStatus.FAILED
        iterator: AsyncIterator[GatewayMessage] | None = None
        primary_error: BaseException | None = None
        batch: list[GatewayMessage] = []

        async def commit(*, cleanup: bool = False) -> None:
            nonlocal inserted, updated, media_seen, durable_cursor
            if not batch:
                return
            try:
                new_count, update_count = await deadline.wait(
                    self._repository.persist_batch(run_id, tuple(batch)),
                    cleanup=cleanup,
                )
            except TimeoutError:
                batch.clear()
                raise
            inserted += new_count
            updated += update_count
            media_seen += sum(len(item.media) for item in batch)
            durable_cursor = min(item.telegram_message_id for item in batch)
            batch.clear()

        try:
            auth_state = await deadline.wait(self._gateway.restore())
            if auth_state is not AuthState.AUTHENTICATED:
                category = (
                    "SESSION_INVALID"
                    if auth_state is AuthState.SESSION_INVALID
                    else "AUTH_REQUIRED"
                )
                raise ScanGatewayError(category)
            iterator = self._gateway.iter_channel_messages(
                telegram_chat_id,
                # A new run captures the current Telegram head. The preceding
                # completed high-water is stored separately and must never cap
                # discovery of newer IDs. A resumed run reuses only its own
                # persisted head snapshot.
                through_message_id=watermark if resume_id is not None else None,
                before_message_id=cursor,
                min_message_id=floor,
                limit=request.max_messages,
            ).__aiter__()
            previous_id = watermark + 1 if watermark is not None else None
            exhausted = True
            while True:
                try:
                    message = await deadline.wait(iterator.__anext__())
                except StopAsyncIteration:
                    break
                if (
                    message.telegram_chat_id != telegram_chat_id
                    or message.telegram_message_id <= 0
                ):
                    raise ValueError("invalid gateway message identity")
                if watermark is None:
                    watermark = message.telegram_message_id
                    await deadline.wait(
                        self._repository.set_sync_snapshot_head(run_id, watermark)
                    )
                if message.telegram_message_id > watermark:
                    raise ValueError("invalid gateway message sequence")
                if floor is not None and message.telegram_message_id < floor:
                    break
                if previous_id is not None and message.telegram_message_id >= previous_id:
                    raise ValueError("invalid gateway message sequence")
                previous_id = message.telegram_message_id
                batch.append(normalize_message(message))
                seen += 1
                if len(batch) >= 100:
                    await commit()
                if seen >= request.max_messages:
                    reason = "MESSAGE_LIMIT"
                    exhausted = False
                    break
            await commit()
            status = (
                ScanStatus.COMPLETE
                if exhausted and reason is None
                else ScanStatus.PARTIAL
            )
        except TimeoutError:
            reason = "TIMEOUT"
            if batch:
                await commit(cleanup=True)
            status = (
                ScanStatus.PARTIAL
                if durable_cursor is not None
                else ScanStatus.FAILED
            )
        except asyncio.CancelledError as error:
            primary_error = error
            if batch:
                await commit(cleanup=True)
            await deadline.wait(
                self._repository.finish_run(run_id, ScanStatus.PARTIAL, "CANCELLED"),
                finalization=True,
            )
            raise
        except ScanGatewayError as error:
            primary_error = error
            status = ScanStatus.PARTIAL if durable_cursor is not None else ScanStatus.FAILED
            await deadline.wait(
                self._repository.finish_run(run_id, status, error.category),
                finalization=True,
            )
            raise
        except Exception as error:
            primary_error = error
            await deadline.wait(
                self._repository.finish_run(run_id, ScanStatus.FAILED, "SCAN_FAILURE"),
                finalization=True,
            )
            raise
        finally:
            if iterator is not None:
                close = getattr(iterator, "aclose", None)
                if close is not None:
                    try:
                        await deadline.wait(close(), cleanup=True)
                    except BaseException:
                        if primary_error is None:
                            status = ScanStatus.FAILED
                            reason = "CLEANUP_FAILURE"
        if status is ScanStatus.PARTIAL and durable_cursor is None:
            status = ScanStatus.FAILED
        await deadline.wait(
            self._repository.finish_run(run_id, status, reason), finalization=True
        )
        summary = await deadline.wait(self._repository.get_sync_run_summary(run_id))
        return ScanOutcome(
            run_id=run_id,
            status=ScanStatus(str(summary["status"])),
            stop_reason=summary["stop_reason"],
            messages_seen=int(summary["messages_seen"]),
            messages_inserted=int(summary["messages_new"]),
            messages_updated=int(summary["messages_updated"]),
            media_seen=int(summary["media_seen"]),
            last_message_id=durable_cursor,
            messages_unchanged=int(summary["messages_unchanged"]),
            messages_unverified=summary["messages_unverified"],
            media_unverified=int(summary["media_unverified"]),
            high_water_confirmed=summary["high_water_confirmed"],
            has_confirmed_high_water=bool(summary["has_confirmed_high_water"]),
        )


def normalize_message(message: GatewayMessage) -> GatewayMessage:
    if type(message.telegram_chat_id) is not int or type(message.telegram_message_id) is not int:
        raise ValueError("invalid message identity")
    if message.telegram_chat_id == 0 or message.telegram_message_id <= 0:
        raise ValueError("invalid message identity")
    date = _utc_iso(message.date_utc)
    edit_date = _utc_iso(message.edit_date_utc) if message.edit_date_utc else None
    text = message.text if isinstance(message.text, str) and message.text != "" else None
    media: list[GatewayMedia] = []
    for ordinal, item in enumerate(message.media):
        if item.media_ordinal != ordinal or not item.kind:
            raise ValueError("invalid media metadata")
        media.append(item)
    return GatewayMessage(
        message.telegram_chat_id,
        message.telegram_message_id,
        date,
        edit_date,
        text,
        message.grouped_id,
        tuple(media),
    )


def _utc_iso(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("message dates must include timezone")
    return parsed.astimezone(UTC).isoformat()
