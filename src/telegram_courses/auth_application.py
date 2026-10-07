"""Authentication workflow; all user input is supplied through prompt seams."""

from __future__ import annotations

from collections.abc import Callable

from telegram_courses.auth import AdapterError, AuthOutcome, AuthState
from telegram_courses.config import ConfigurationError, TelegramCredentials
from telegram_courses.telegram_gateway import TelegramGateway


class AuthenticationApplication:
    def __init__(
        self,
        gateway_factory: Callable[[TelegramCredentials], TelegramGateway],
        credentials: Callable[[], TelegramCredentials],
        phone_prompt: Callable[[], str],
        code_prompt: Callable[[], str],
        password_prompt: Callable[[], str],
        interactive_check: Callable[[], None] | None = None,
    ) -> None:
        self._gateway_factory = gateway_factory
        self._credentials = credentials
        self._phone_prompt = phone_prompt
        self._code_prompt = code_prompt
        self._password_prompt = password_prompt
        self._interactive_check = interactive_check

    async def authenticate(self) -> AuthOutcome:
        credentials = self._credentials()
        if not isinstance(credentials, TelegramCredentials):
            raise ConfigurationError from None
        gateway = self._gateway_factory(credentials)
        try:
            state = await gateway.restore()
            if state is AuthState.AUTHENTICATED:
                return AuthOutcome(state)
            if state not in {AuthState.AUTH_REQUIRED, AuthState.SESSION_INVALID}:
                raise AdapterError from None
            if self._interactive_check is not None:
                self._interactive_check()
            state = await gateway.begin(self._phone_prompt())
            if state is AuthState.CODE_REQUIRED:
                state = await gateway.submit_code(self._code_prompt())
            if state is AuthState.PASSWORD_REQUIRED:
                state = await gateway.submit_password(self._password_prompt())
            if state is not AuthState.AUTHENTICATED:
                raise AdapterError from None
            return AuthOutcome(state)
        finally:
            await gateway.close()
