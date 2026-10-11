"""Application-facing boundary for Telegram authentication."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import DiscoveryRequest, DiscoveryResult
from telegram_courses.message_scanner import GatewayMessage


class TelegramGateway(Protocol):
    async def restore(self) -> AuthState: ...

    async def begin(self, phone: str) -> AuthState: ...

    async def submit_code(self, code: str) -> AuthState: ...

    async def submit_password(self, password: str) -> AuthState: ...

    async def discover_channels(self, request: DiscoveryRequest) -> DiscoveryResult: ...

    def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
    ) -> AsyncIterator[GatewayMessage]: ...

    def stream_media(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
    ) -> AsyncIterator[bytes]: ...

    async def close(self) -> None: ...
