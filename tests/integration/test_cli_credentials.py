from __future__ import annotations

from telegram_courses import cli
from telegram_courses.auth import AuthState
from telegram_courses.channel_discovery import (
    DiscoveryLimits,
    DiscoveryResult,
    DiscoveryStats,
)
from telegram_courses.config import TelegramCredentials
from telegram_courses.credentials import CredentialVaultError

SYNTHETIC_HASH = "c" * 32


class _FakeVault:
    def __init__(self, *, available: bool = False) -> None:
        self.available = available
        self.saved: TelegramCredentials | None = None

    def setup(self, credentials: TelegramCredentials) -> None:
        self.saved = credentials

    def status(self) -> bool:
        return self.available


def test_credentials_setup_hides_hash_and_status_prints_no_values(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli.sys, "stdin", type("Input", (), {"isatty": lambda self: True})()
    )
    vault = _FakeVault()

    assert cli.main(
        ["credentials", "setup"],
        api_id_prompt=lambda: "71234",
        api_hash_prompt=lambda: SYNTHETIC_HASH,
        credential_vault_factory=lambda: vault,
    ) == 0
    setup_output = capsys.readouterr()
    assert setup_output.out == "credentials setup successful\n"
    assert setup_output.err == ""
    assert SYNTHETIC_HASH not in setup_output.out + setup_output.err
    assert "71234" not in setup_output.out + setup_output.err
    assert vault.saved == TelegramCredentials(71234, SYNTHETIC_HASH)

    vault.available = True
    assert cli.main(
        ["credentials", "status"],
        credential_vault_factory=lambda: vault,
    ) == 0
    status_output = capsys.readouterr()
    assert status_output.out == (
        "credentials vault configured: yes\ncredentials available: yes\n"
    )
    assert SYNTHETIC_HASH not in status_output.out


def test_credentials_status_and_setup_failures_are_sanitized(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli.sys, "stdin", type("Input", (), {"isatty": lambda self: True})()
    )

    class BrokenVault(_FakeVault):
        def status(self) -> bool:
            raise CredentialVaultError(SYNTHETIC_HASH)

    assert cli.main(
        ["credentials", "status"],
        credential_vault_factory=BrokenVault,
    ) == 2
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err == "credentials vault error\n"
    assert SYNTHETIC_HASH not in result.err

    assert cli.main(
        ["credentials", "setup"],
        api_id_prompt=lambda: "not-an-id-secret-sentinel",
        api_hash_prompt=lambda: SYNTHETIC_HASH,
        credential_vault_factory=BrokenVault,
    ) == 2
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err == "configuration error\n"
    assert "not-an-id-secret-sentinel" not in result.err
    assert SYNTHETIC_HASH not in result.err


def test_auth_and_channels_resolve_complete_environment_pair(
    monkeypatch, capsys
) -> None:
    monkeypatch.setenv("TELEGRAM_API_ID", "71234")
    monkeypatch.setenv("TELEGRAM_API_HASH", SYNTHETIC_HASH)

    class AuthGateway:
        async def restore(self) -> AuthState:
            return AuthState.AUTHENTICATED

        async def close(self) -> None:
            return None

    auth_credentials: list[TelegramCredentials] = []

    def auth_gateway_factory(credentials: TelegramCredentials) -> AuthGateway:
        auth_credentials.append(credentials)
        return AuthGateway()

    assert cli.main(["auth"], gateway_factory=auth_gateway_factory) == 0
    output = capsys.readouterr()
    assert output.out == "authentication successful\n"
    assert SYNTHETIC_HASH not in output.out + output.err
    assert auth_credentials == [TelegramCredentials(71234, SYNTHETIC_HASH)]

    class DiscoveryGateway:
        async def restore(self) -> AuthState:
            return AuthState.AUTHENTICATED

        async def discover_channels(self, _request) -> DiscoveryResult:
            return DiscoveryResult(
                channels=(), complete=True, stop_reason=None,
                stats=DiscoveryStats(1, 1, 0, 0, 0.01, DiscoveryLimits()),
            )

        async def close(self) -> None:
            return None

    discovery_credentials: list[TelegramCredentials] = []

    def discovery_factory(credentials: TelegramCredentials) -> DiscoveryGateway:
        discovery_credentials.append(credentials)
        return DiscoveryGateway()

    assert cli.main(
        ["channels"],
        discovery_gateway_factory=discovery_factory,
        selection_prompt=lambda _message: "q",
    ) == 0
    output = capsys.readouterr()
    assert discovery_credentials == [TelegramCredentials(71234, SYNTHETIC_HASH)]
    assert SYNTHETIC_HASH not in output.out + output.err


def test_incomplete_environment_pair_fails_before_auth_or_channels(
    monkeypatch, capsys
) -> None:
    monkeypatch.setenv("TELEGRAM_API_ID", "71234")
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    called = False

    def gateway_factory(_credentials: TelegramCredentials) -> object:
        nonlocal called
        called = True
        raise AssertionError("gateway must not be created")

    assert cli.main(["auth"], gateway_factory=gateway_factory) == 2
    output = capsys.readouterr()
    assert output.err == "configuration error\n"
    assert not called
