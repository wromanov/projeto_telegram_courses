"""Application integration for authenticated, selected-channel scans."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from telegram_courses.auth import AdapterError
from telegram_courses.config import ConfigurationError, TelegramCredentials
from telegram_courses.message_scanner import (
    MessageScanner,
    ScanDeadline,
    ScanGatewayError,
    ScanOutcome,
    ScanRequest,
    ScanStatus,
)
from telegram_courses.sqlite_repository import SQLiteMessageRepository
from telegram_courses.telegram_gateway import TelegramGateway


class ScanApplication:
    def __init__(
        self,
        gateway_factory: Callable[[TelegramCredentials], TelegramGateway],
        credentials: Callable[[], TelegramCredentials],
        repository: SQLiteMessageRepository,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._gateway_factory = gateway_factory
        self._credentials = credentials
        self._repository = repository
        self._clock = clock

    async def scan(self, telegram_chat_id: int, request: ScanRequest) -> ScanOutcome:
        deadline = ScanDeadline(request.timeout_seconds, clock=self._clock)
        gateway: TelegramGateway | None = None
        primary_error: BaseException | None = None
        outcome: ScanOutcome | None = None
        try:
            await deadline.wait(self._repository.migrate())
            deadline.check()
            credentials = self._credentials()
            deadline.check()
            gateway = self._gateway_factory(credentials)
            deadline.check()
            outcome = await MessageScanner(gateway, self._repository).scan(
                telegram_chat_id, request, deadline=deadline
            )
        except (ScanGatewayError, ConfigurationError, TimeoutError) as error:
            primary_error = error
            raise
        except asyncio.CancelledError as error:
            primary_error = error
            raise
        except Exception as error:
            primary_error = error
            raise AdapterError from None
        finally:
            if gateway is not None:
                try:
                    await deadline.wait(gateway.close(), cleanup=True)
                except BaseException:
                    if outcome is not None:
                        try:
                            await deadline.wait(
                                self._repository.finish_run(
                                    outcome.run_id,
                                    ScanStatus.FAILED,
                                    "CLEANUP_FAILURE",
                                ),
                                finalization=True,
                            )
                        except BaseException:
                            pass
                    if primary_error is None:
                        raise
        assert outcome is not None
        return outcome
