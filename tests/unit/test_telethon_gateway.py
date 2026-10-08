from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from telethon import errors

from telegram_courses.auth import (
    AdapterError,
    AuthRejected,
    AuthState,
    ExpiredCode,
    InvalidCode,
    InvalidPassword,
    InvalidSession,
    NetworkError,
    RateLimited,
)
from telegram_courses.config import TelegramCredentials
from telegram_courses.telethon_gateway import TelethonGateway
from telegram_courses.telethon_session import StorageError


class FakeSession:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def save(self) -> str:
        return self.value


class FakeVault:
    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.saved: list[str] = []

    def _load(self) -> str | None:
        return self.value

    def _save(self, value: str) -> None:
        self.saved.append(value)
        self.value = value


class FakeClient:
    def __init__(self, session: FakeSession, **kwargs: object) -> None:
        self.session = session
        self.kwargs = kwargs
        self.me: object | None = None
        self.calls: list[tuple[object, ...]] = []
        self.connect_error: Exception | None = None
        self.me_error: Exception | None = None
        self.disconnect_error: Exception | None = None
        self.code_error: Exception | None = None
        self.code_hash: str | None = "synthetic-hash"
        self.closed = 0

    async def connect(self) -> None:
        self.calls.append(("connect",))
        if self.connect_error:
            raise self.connect_error

    async def disconnect(self) -> None:
        self.closed += 1
        if self.disconnect_error:
            raise self.disconnect_error

    async def get_me(self) -> object | None:
        self.calls.append(("get_me",))
        if self.me_error:
            raise self.me_error
        return self.me

    async def send_code_request(self, phone: str) -> object:
        self.calls.append(("send_code_request", phone))
        if self.code_error:
            raise self.code_error
        return SimpleNamespace(phone_code_hash=self.code_hash)

    async def sign_in(self, *args: object, **kwargs: object) -> object:
        self.calls.append(("sign_in", *args, kwargs))
        if self.code_error:
            raise self.code_error
        self.session.value = "synthetic-new-session"
        self.me = object()
        return object()


def gateway(vault: FakeVault) -> tuple[TelethonGateway, list[FakeClient]]:
    clients: list[FakeClient] = []

    def factory(session: FakeSession, *_args: object, **kwargs: object) -> FakeClient:
        client = FakeClient(session, **kwargs)
        if session.value == "synthetic-authorized-session":
            client.me = object()
        clients.append(client)
        return client

    return TelethonGateway(
        TelegramCredentials(42, "synthetic-api-hash"),
        client_factory=factory,
        session_factory=FakeSession,
        vault=vault,
    ), clients


def test_restore_missing_and_invalid_session_then_replace_only_on_success() -> None:
    vault = FakeVault("synthetic-old-session")
    adapter, clients = gateway(vault)
    assert asyncio.run(adapter.restore()) is AuthState.SESSION_INVALID
    assert asyncio.run(adapter.begin("synthetic-phone")) is AuthState.CODE_REQUIRED
    assert vault.value == "synthetic-old-session"
    assert asyncio.run(adapter.submit_code("synthetic-otp")) is AuthState.AUTHENTICATED
    assert vault.value == "synthetic-new-session"
    assert len(vault.saved) == 1
    settings = clients[-1].kwargs
    assert settings["flood_sleep_threshold"] == 0
    assert settings["request_retries"] == settings["connection_retries"] == 1
    assert settings["raise_last_call_error"] is True
    assert settings["auto_reconnect"] is False
    submitted = next(call for call in clients[-1].calls if call[0] == "sign_in")
    assert submitted[3] == {"phone_code_hash": "synthetic-hash"}
    asyncio.run(adapter.close())
    asyncio.run(adapter.close())
    assert clients[-1].closed == 1


def test_restore_reuses_authorized_session_and_no_session_is_required() -> None:
    adapter, clients = gateway(FakeVault(None))
    assert asyncio.run(adapter.restore()) is AuthState.AUTH_REQUIRED
    assert clients[0].session.value == ""
    asyncio.run(adapter.close())

    adapter, clients = gateway(FakeVault("synthetic-authorized-session"))
    assert asyncio.run(adapter.restore()) is AuthState.AUTHENTICATED
    assert clients[0].calls == [("connect",), ("get_me",)]
    asyncio.run(adapter.close())


def test_invalid_and_expired_codes_are_translated_without_replay() -> None:
    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    asyncio.run(adapter.begin("synthetic-phone"))
    clients[-1].code_error = errors.PhoneCodeInvalidError(request=None)
    with pytest.raises(InvalidCode):
        asyncio.run(adapter.submit_code("synthetic-code"))
    assert sum(call[0] == "sign_in" for call in clients[-1].calls) == 1

    error_adapter, clients = gateway(FakeVault())
    asyncio.run(error_adapter.restore())
    asyncio.run(error_adapter.begin("synthetic-phone"))
    clients[-1].code_error = errors.PhoneCodeExpiredError(request=None)
    with pytest.raises(ExpiredCode):
        asyncio.run(error_adapter.submit_code("synthetic-code"))
    assert sum(call[0] == "sign_in" for call in clients[-1].calls) == 1


def test_missing_phone_code_hash_is_controlled_before_otp_submission() -> None:
    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    original_factory = adapter._client_factory

    def missing_hash_factory(*args: object, **kwargs: object) -> FakeClient:
        client = original_factory(*args, **kwargs)
        client.code_hash = None
        return client

    adapter._client_factory = missing_hash_factory
    with pytest.raises(AdapterError) as caught:
        asyncio.run(adapter.begin("synthetic-phone"))
    assert "synthetic-hash" not in str(caught.value)
    assert not any(call[0] == "sign_in" for call in clients[-1].calls)


def test_floodwait_has_duration_and_unknown_error_is_suppressed() -> None:
    error = errors.FloodWaitError(request=None, capture=23)
    with pytest.raises(RateLimited) as caught:
        TelethonGateway._translate(error)
    assert caught.value.retry_after_seconds == 23
    assert str(caught.value) == "authentication rate limited"

    with pytest.raises(NetworkError):
        TelethonGateway._translate(TimeoutError("synthetic transport canary"))
    with pytest.raises(NetworkError) as incomplete_read:
        TelethonGateway._translate(
            asyncio.IncompleteReadError(partial=b"synthetic-transport", expected=8)
        )
    assert "synthetic-transport" not in str(incomplete_read.value)
    with pytest.raises(InvalidSession):
        TelethonGateway._translate(errors.AuthKeyUnregisteredError(request=None))
    with pytest.raises(InvalidSession):
        TelethonGateway._translate(errors.AuthKeyInvalidError(request=None))
    with pytest.raises(AuthRejected):
        TelethonGateway._translate(errors.PhoneNumberInvalidError(request=None))
    with pytest.raises(AuthRejected):
        TelethonGateway._translate(errors.PhoneNumberUnoccupiedError(request=None))
    secret_error = RuntimeError("synthetic raw adapter canary")
    with pytest.raises(AdapterError) as unknown:
        TelethonGateway._translate(secret_error)
    assert "synthetic raw adapter canary" not in str(unknown.value)
    assert unknown.value.__cause__ is None


def test_incomplete_read_during_connect_is_sanitized_network_diagnostic(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter, clients = gateway(FakeVault())
    original_factory = adapter._client_factory

    def failing_connect_factory(*args: object, **kwargs: object) -> FakeClient:
        client = original_factory(*args, **kwargs)
        client.connect_error = asyncio.IncompleteReadError(
            partial=b"synthetic-api-hash", expected=8
        )
        return client

    adapter._client_factory = failing_connect_factory
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(NetworkError) as caught:
            asyncio.run(adapter.restore())
    assert type(caught.value) is NetworkError
    assert caught.value.__cause__ is None
    assert "FAILURE_STAGE=CONNECT" in caplog.text
    assert "SANITIZED_EXCEPTION_CLASS=IncompleteReadError" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=NETWORK" in caplog.text
    assert "synthetic-api-hash" not in caplog.text
    assert len(clients[0].calls) == 1
    asyncio.run(adapter.close())


def test_incomplete_read_during_code_request_is_network_error_without_replay(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    original_factory = adapter._client_factory

    def failing_code_factory(*args: object, **kwargs: object) -> FakeClient:
        client = original_factory(*args, **kwargs)
        client.code_error = asyncio.IncompleteReadError(
            partial=b"synthetic-otp", expected=8
        )
        return client

    adapter._client_factory = failing_code_factory
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(NetworkError) as caught:
            asyncio.run(adapter.begin("synthetic-phone"))
    assert type(caught.value) is NetworkError
    assert caught.value.__cause__ is None
    assert "FAILURE_STAGE=REQUEST_CODE" in caplog.text
    assert "SANITIZED_EXCEPTION_CLASS=IncompleteReadError" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=NETWORK" in caplog.text
    assert "synthetic-phone" not in caplog.text
    assert "synthetic-otp" not in caplog.text
    assert sum(call[0] == "send_code_request" for call in clients[-1].calls) == 1
    assert clients[-1].kwargs["request_retries"] == 1
    assert clients[-1].kwargs["connection_retries"] == 1
    assert clients[-1].kwargs["auto_reconnect"] is False
    asyncio.run(adapter.close())


def test_auth_rejection_remains_authentication_category_in_safe_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    original_factory = adapter._client_factory

    def rejected_code_factory(*args: object, **kwargs: object) -> FakeClient:
        client = original_factory(*args, **kwargs)
        client.code_error = errors.PhoneNumberInvalidError(request=None)
        return client

    adapter._client_factory = rejected_code_factory
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(AuthRejected):
            asyncio.run(adapter.begin("synthetic-phone"))
    assert "FAILURE_STAGE=REQUEST_CODE" in caplog.text
    assert "SANITIZED_EXCEPTION_CLASS=PhoneNumberInvalidError" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=AUTHENTICATION" in caplog.text
    assert "synthetic-phone" not in caplog.text
    asyncio.run(adapter.close())


def test_failure_telemetry_tracks_otp_2fa_confirmation_persistence_and_disconnect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    asyncio.run(adapter.begin("synthetic-phone"))
    clients[-1].code_error = errors.PhoneCodeInvalidError(request=None)
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(InvalidCode):
            asyncio.run(adapter.submit_code("synthetic-otp"))
    assert "FAILURE_STAGE=OTP_SUBMISSION" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=AUTHENTICATION" in caplog.text
    asyncio.run(adapter.close())

    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    asyncio.run(adapter.begin("synthetic-phone"))
    clients[-1].code_error = errors.SessionPasswordNeededError(request=None)
    assert asyncio.run(adapter.submit_code("synthetic-otp")) is AuthState.PASSWORD_REQUIRED
    clients[-1].code_error = errors.PasswordHashInvalidError(request=None)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(InvalidPassword):
            asyncio.run(adapter.submit_password("synthetic-2fa"))
    assert "FAILURE_STAGE=2FA_SUBMISSION" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=AUTHENTICATION" in caplog.text
    assert "synthetic-2fa" not in caplog.text
    asyncio.run(adapter.close())

    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    asyncio.run(adapter.begin("synthetic-phone"))
    clients[-1].me_error = asyncio.IncompleteReadError(partial=b"", expected=8)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(NetworkError):
            asyncio.run(adapter.submit_code("synthetic-otp"))
    assert "FAILURE_STAGE=AUTHORIZATION_CONFIRMATION" in caplog.text
    asyncio.run(adapter.close())

    class FailingVault(FakeVault):
        def _save(self, value: str) -> None:
            raise StorageError("synthetic-storage-canary")

    adapter, _clients = gateway(FailingVault())
    asyncio.run(adapter.restore())
    asyncio.run(adapter.begin("synthetic-phone"))
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(AdapterError):
            asyncio.run(adapter.submit_code("synthetic-otp"))
    assert "FAILURE_STAGE=SESSION_PERSISTENCE" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=ADAPTER" in caplog.text
    assert "synthetic-storage-canary" not in caplog.text
    asyncio.run(adapter.close())

    adapter, clients = gateway(FakeVault())
    asyncio.run(adapter.restore())
    clients[-1].disconnect_error = RuntimeError("synthetic-disconnect-canary")
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(AdapterError):
            asyncio.run(adapter.close())
    assert "FAILURE_STAGE=DISCONNECT" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=ADAPTER" in caplog.text
    assert "synthetic-disconnect-canary" not in caplog.text


def test_client_creation_failure_has_safe_diagnostic_and_boundary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def failing_factory(*_args: object, **_kwargs: object) -> FakeClient:
        raise RuntimeError("synthetic-client-canary")

    adapter = TelethonGateway(
        TelegramCredentials(42, "synthetic-api-hash"),
        client_factory=failing_factory,
        session_factory=FakeSession,
        vault=FakeVault(),
    )
    with caplog.at_level(logging.WARNING, logger="telegram_courses.telethon_gateway"):
        with pytest.raises(AdapterError) as caught:
            asyncio.run(adapter.restore())
    assert type(caught.value) is AdapterError
    assert "FAILURE_STAGE=CLIENT_CREATION" in caplog.text
    assert "SANITIZED_EXCEPTION_CLASS=RuntimeError" in caplog.text
    assert "PROJECT_ERROR_CATEGORY=ADAPTER" in caplog.text
    assert "synthetic-client-canary" not in caplog.text
    assert "synthetic-api-hash" not in caplog.text


def test_2fa_challenge_and_password_submission() -> None:
    async def exercise() -> None:
        adapter, clients = gateway(FakeVault())
        await adapter.restore()
        await adapter.begin("synthetic-phone")
        clients[-1].code_error = errors.SessionPasswordNeededError(request=None)
        assert await adapter.submit_code("synthetic-code") is AuthState.PASSWORD_REQUIRED
        clients[-1].code_error = None
        assert await adapter.submit_password("synthetic-password") is AuthState.AUTHENTICATED
        assert clients[-1].calls[-2] == ("sign_in", {"password": "synthetic-password"})
        await adapter.close()

    asyncio.run(exercise())


def test_invalid_2fa_password_is_not_retried_or_saved() -> None:
    async def exercise() -> None:
        vault = FakeVault()
        adapter, clients = gateway(vault)
        await adapter.restore()
        await adapter.begin("synthetic-phone")
        clients[-1].code_error = errors.SessionPasswordNeededError(request=None)
        assert await adapter.submit_code("synthetic-code") is AuthState.PASSWORD_REQUIRED
        clients[-1].code_error = errors.PasswordHashInvalidError(request=None)
        with pytest.raises(InvalidPassword):
            await adapter.submit_password("synthetic-wrong-password")
        submissions = [call for call in clients[-1].calls if call[0] == "sign_in"]
        assert len(submissions) == 2
        assert len(vault.saved) == 0
        await adapter.close()

    asyncio.run(exercise())


def test_failed_protected_save_is_controlled_and_not_reported_as_success() -> None:
    class FailingVault(FakeVault):
        def _save(self, value: str) -> None:
            raise StorageError("synthetic-storage-canary")

    async def exercise() -> None:
        adapter, clients = gateway(FailingVault())
        await adapter.restore()
        await adapter.begin("synthetic-phone")
        with pytest.raises(AdapterError) as caught:
            await adapter.submit_code("synthetic-code")
        assert "synthetic-storage-canary" not in str(caught.value)
        assert clients[-1].me is not None
        await adapter.close()

    asyncio.run(exercise())
