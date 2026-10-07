from __future__ import annotations

from telegram_courses import cli
from telegram_courses.auth import AuthState, InvalidCode
from telegram_courses.config import TelegramCredentials


class FakeGateway:
    def __init__(self) -> None:
        self.closed = False

    async def restore(self) -> AuthState:
        return AuthState.AUTH_REQUIRED

    async def begin(self, phone: str) -> AuthState:
        assert phone == "synthetic-phone"
        return AuthState.CODE_REQUIRED

    async def submit_code(self, code: str) -> AuthState:
        assert code == "synthetic-otp"
        return AuthState.AUTHENTICATED

    async def submit_password(self, password: str) -> AuthState:
        raise AssertionError

    async def close(self) -> None:
        self.closed = True


def test_auth_succeeds_with_fake_gateway_and_synthetic_credentials(monkeypatch, capsys) -> None:
    fake = FakeGateway()
    monkeypatch.setattr(
        cli, "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )
    code = "synthetic-otp"
    assert cli.main(
        ["auth"], gateway_factory=lambda _credentials: fake,
        phone_prompt=lambda: "synthetic-phone", code_prompt=lambda: code,
        password_prompt=lambda: "synthetic-password",
    ) == 0
    output = capsys.readouterr()
    assert output.out == "authentication successful\n"
    assert output.err == ""
    assert code not in output.out + output.err
    assert fake.closed


def test_auth_failure_is_generic_and_secret_arguments_are_rejected(monkeypatch, capsys) -> None:
    class BrokenGateway(FakeGateway):
        async def submit_code(self, code: str) -> AuthState:
            raise InvalidCode

    monkeypatch.setattr(
        cli, "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )
    assert cli.main(
        ["auth"], gateway_factory=lambda _credentials: BrokenGateway(),
        phone_prompt=lambda: "synthetic-phone", code_prompt=lambda: "secret-canary",
        password_prompt=lambda: "synthetic-password",
    ) == 3
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err == "invalid authentication code\n"
    assert "secret-canary" not in result.err
    assert cli.main(["auth", "--code", "secret-canary"]) == 2


def test_authenticated_session_reuse_does_not_require_interactive_stdin(
    monkeypatch, capsys
) -> None:
    class ReusedGateway(FakeGateway):
        async def restore(self) -> AuthState:
            return AuthState.AUTHENTICATED

    monkeypatch.setattr(
        cli, "load_telegram_credentials",
        lambda: TelegramCredentials(7, "synthetic-api-hash"),
    )
    monkeypatch.setattr(cli.sys, "stdin", type("Input", (), {"isatty": lambda self: False})())
    assert cli.main(
        ["auth"], gateway_factory=lambda _credentials: ReusedGateway()
    ) == 0
    output = capsys.readouterr()
    assert output.out == "authentication successful\n"
    assert output.err == ""
