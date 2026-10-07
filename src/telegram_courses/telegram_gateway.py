"""Application-facing boundary for Telegram authentication."""

from __future__ import annotations

from typing import Protocol

from telegram_courses.auth import AuthState


class TelegramGateway(Protocol):
    async def restore(self) -> AuthState: ...

    async def begin(self, phone: str) -> AuthState: ...

    async def submit_code(self, code: str) -> AuthState: ...

    async def submit_password(self, password: str) -> AuthState: ...

    async def close(self) -> None: ...
