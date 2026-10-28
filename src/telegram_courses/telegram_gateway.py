"""Application-facing boundary for Telegram authentication."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Awaitable, Callable, Protocol

from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import DiscoveryRequest, DiscoveryResult
from telegram_courses.downloads import RemoteFileHash
from telegram_courses.message_scanner import GatewayMessage


class TelegramGateway(Protocol):
    async def restore(self) -> AuthState: ...

    async def begin(self, phone: str) -> AuthState: ...

    async def submit_code(self, code: str) -> AuthState: ...

    async def submit_password(self, password: str) -> AuthState: ...

    async def discover_channels(self, request: DiscoveryRequest) -> DiscoveryResult: ...

    async def recover_selected_channel_peer(
        self, telegram_chat_id: int, *, max_dialogs: int = 100
    ) -> bool: ...

    def iter_channel_messages(
        self,
        telegram_chat_id: int,
        *,
        through_message_id: int | None,
        before_message_id: int | None,
        limit: int,
        min_message_id: int | None = None,
    ) -> AsyncIterator[GatewayMessage]: ...

    def iter_channel_metadata(
        self,
        telegram_chat_id: int,
        *,
        max_messages: int,
    ) -> AsyncIterator[GatewayMessage]: ...

    def stream_media(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        reserve_chunk: Callable[[int], Awaitable["ChunkReservation | None"]] | None = None,
        offset: int = 0,
    ) -> AsyncIterator[bytes]: ...

    async def get_file_hashes(
        self,
        channel_id: int,
        message_id: int,
        media_ordinal: int,
        *,
        telegram_media_id: str,
        expected_bytes: int,
        offset: int = 0,
    ) -> tuple[RemoteFileHash, ...]: ...

    async def validate_media_identity(
        self, channel_id: int, message_id: int, media_ordinal: int,
        *, telegram_media_id: str, expected_bytes: int,
    ) -> bool: ...

    async def close(self) -> None: ...


class ChunkReservation(Protocol):
    def received(self, byte_count: int) -> None: ...

    def release(self) -> None: ...

    def charge_uncertain(self) -> None: ...
