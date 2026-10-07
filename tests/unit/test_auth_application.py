from __future__ import annotations

import asyncio

import pytest

from telegram_courses.auth import AuthState, InvalidCode
from telegram_courses.auth_application import AuthenticationApplication
from telegram_courses.config import TelegramCredentials


class Gateway:
    def __init__(self, states: list[AuthState]) -> None:
        self.states = iter(states)
        self.calls: list[tuple[object, ...]] = []
        self.closed = 0

    async def restore(self) -> AuthState:
        self.calls.append(("restore",))
        return next(self.states)

    async def begin(self, phone: str) -> AuthState:
        self.calls.append(("begin", phone))
        return next(self.states)

    async def submit_code(self, code: str) -> AuthState:
        self.calls.append(("code", code))
        return next(self.states)

    async def submit_password(self, password: str) -> AuthState:
        self.calls.append(("password", password))
        return next(self.states)

    async def close(self) -> None:
        self.closed += 1


def app(gateway: Gateway, prompts: list[str]) -> AuthenticationApplication:
    def prompt() -> str:
        return prompts.pop(0)

    return AuthenticationApplication(
        lambda _credentials: gateway,
        lambda: TelegramCredentials(1, "synthetic-hash"),
        prompt, prompt, prompt,
    )


@pytest.mark.parametrize("state", [AuthState.AUTH_REQUIRED, AuthState.SESSION_INVALID])
def test_otp_and_2fa_flow_and_cleanup(state: AuthState) -> None:
    gateway = Gateway([state, AuthState.CODE_REQUIRED,
                       AuthState.PASSWORD_REQUIRED, AuthState.AUTHENTICATED])
    outcome = asyncio.run(app(gateway, ["synthetic-phone", "synthetic-code", "synthetic-password"]).authenticate())
    assert outcome.state is AuthState.AUTHENTICATED
    assert gateway.calls == [
        ("restore",), ("begin", "synthetic-phone"),
        ("code", "synthetic-code"), ("password", "synthetic-password"),
    ]
    assert gateway.closed == 1


def test_authenticated_restore_does_not_prompt() -> None:
    gateway = Gateway([AuthState.AUTHENTICATED])
    result = asyncio.run(app(gateway, []).authenticate())
    assert result.state is AuthState.AUTHENTICATED
    assert gateway.calls == [("restore",)]
    assert gateway.closed == 1


def test_failure_still_closes_gateway() -> None:
    class FailingGateway(Gateway):
        async def submit_code(self, code: str) -> AuthState:
            raise InvalidCode

    gateway = FailingGateway([AuthState.AUTH_REQUIRED, AuthState.CODE_REQUIRED])
    with pytest.raises(InvalidCode):
        asyncio.run(app(gateway, ["synthetic-phone", "synthetic-code"]).authenticate())
    assert gateway.closed == 1
