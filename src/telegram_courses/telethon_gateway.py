"""Private Telethon adapter for the project authentication boundary."""

from __future__ import annotations

import logging
import socket
import ssl
from importlib import import_module
from typing import Any, Callable

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
from telegram_courses.config import ConfigurationError, TelegramCredentials

_session_storage = import_module("telegram_courses.telethon_session")
IntegrityError = _session_storage.IntegrityError
StorageError = _session_storage.StorageError
_ProtectedSessionVault = _session_storage._ProtectedSessionVault


class _PasswordChallenge(Exception):
    pass


def _client_logger() -> logging.Logger:
    logger = logging.Logger("telegram_courses.telethon_auth", logging.CRITICAL)
    logger.propagate = False
    logger.addHandler(logging.NullHandler())
    return logger


class TelethonGateway:
    """Owns all Telethon objects and session material for one auth attempt."""

    def __init__(
        self,
        credentials: TelegramCredentials,
        *,
        client_factory: Callable[..., Any] | None = None,
        session_factory: Callable[[str], Any] | None = None,
        vault: Any | None = None,
    ) -> None:
        if client_factory is None or session_factory is None:
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession
            except Exception:
                raise AdapterError from None
            client_factory = client_factory or TelegramClient
            session_factory = session_factory or StringSession
        self._credentials = credentials
        self._client_factory = client_factory
        self._session_factory = session_factory
        try:
            self._vault = vault or _ProtectedSessionVault()
        except (StorageError, IntegrityError):
            raise AdapterError from None
        self._client: Any | None = None
        self._phone: str | None = None
        self._phone_code_hash: str | None = None
        self._state: AuthState | None = None
        self._closed = False

    def _new_client(self, session: Any) -> Any:
        return self._client_factory(
            session,
            self._credentials.api_id,
            self._credentials.api_hash,
            flood_sleep_threshold=0,
            request_retries=1,
            connection_retries=1,
            raise_last_call_error=True,
            auto_reconnect=False,
            base_logger=_client_logger(),
        )

    async def _disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                raise AdapterError from None

    async def _replace_with_empty(self) -> None:
        await self._disconnect()
        self._client = self._new_client(self._session_factory(""))
        await self._client.connect()

    @staticmethod
    def _translate(error: Exception) -> None:
        try:
            from telethon import errors
        except Exception:
            raise AdapterError from None
        if isinstance(error, errors.FloodWaitError):
            seconds = getattr(error, "seconds", None)
            if type(seconds) is not int or seconds < 0:
                raise AdapterError from None
            raise RateLimited(seconds) from None
        if isinstance(error, (errors.PhoneCodeExpiredError, errors.PhoneCodeHashEmptyError)):
            raise ExpiredCode from None
        if isinstance(error, (errors.PhoneCodeInvalidError, errors.PhoneCodeEmptyError)):
            raise InvalidCode from None
        if isinstance(error, errors.PasswordHashInvalidError):
            raise InvalidPassword from None
        if isinstance(error, errors.ApiIdInvalidError):
            raise ConfigurationError from None
        if isinstance(
            error,
            (
                errors.PhoneNumberInvalidError,
                errors.PhoneNumberBannedError,
                errors.PhoneNumberUnoccupiedError,
            ),
        ):
            raise AuthRejected from None
        if isinstance(error, errors.SessionPasswordNeededError):
            raise _PasswordChallenge from None
        if isinstance(
            error,
            (
                errors.AuthKeyInvalidError,
                errors.AuthKeyUnregisteredError,
                errors.SessionRevokedError,
                errors.SessionExpiredError,
                errors.UnauthorizedError,
            ),
        ):
            raise InvalidSession from None
        if isinstance(error, (errors.AuthKeyError, errors.AuthBytesInvalidError)):
            raise AuthRejected from None
        network_types = (OSError, TimeoutError, ConnectionError, socket.error, ssl.SSLError)
        network_errors = tuple(
            item for item in (
                getattr(errors, "RpcCallFailError", None),
                getattr(errors, "ServerError", None),
                getattr(errors, "TimedOutError", None),
            ) if isinstance(item, type)
        )
        if isinstance(error, network_types + network_errors):
            raise NetworkError from None
        raise AdapterError from None

    async def _call(self, awaitable: Any) -> Any:
        try:
            return await awaitable
        except (ConfigurationError, _PasswordChallenge, AuthRejected, ExpiredCode, InvalidCode, InvalidPassword,
                InvalidSession, NetworkError, RateLimited, AdapterError):
            raise
        except (StorageError, IntegrityError):
            raise AdapterError from None
        except Exception as error:
            self._translate(error)

    async def _confirm_and_save(self) -> AuthState:
        try:
            me = await self._call(self._client.get_me())
            if me is None:
                raise AuthRejected from None
            session_value = self._client.session.save()
            if not isinstance(session_value, str) or not session_value:
                raise AdapterError from None
            self._vault._save(session_value)
        except (ConfigurationError, AuthRejected, AdapterError):
            raise
        except (StorageError, IntegrityError):
            raise AdapterError from None
        except Exception as error:
            self._translate(error)
        self._state = AuthState.AUTHENTICATED
        return self._state

    async def restore(self) -> AuthState:
        if self._state is not None:
            raise AdapterError from None
        try:
            stored = self._vault._load()
            self._client = self._new_client(self._session_factory(stored or ""))
            await self._client.connect()
            if stored is None:
                self._state = AuthState.AUTH_REQUIRED
                return self._state
            me = await self._call(self._client.get_me())
            if me is not None:
                self._state = AuthState.AUTHENTICATED
            else:
                self._state = AuthState.SESSION_INVALID
            return self._state
        except ConfigurationError:
            raise
        except (StorageError, IntegrityError):
            raise AdapterError from None
        except InvalidSession:
            self._state = AuthState.SESSION_INVALID
            return self._state
        except Exception as error:
            self._translate(error)

    async def begin(self, phone: str) -> AuthState:
        if self._state not in {AuthState.AUTH_REQUIRED, AuthState.SESSION_INVALID}:
            raise AdapterError from None
        await self._call(self._replace_with_empty())
        self._phone = phone
        result = await self._call(self._client.send_code_request(phone))
        code_hash = getattr(result, "phone_code_hash", None)
        if not isinstance(code_hash, str) or not code_hash:
            raise AdapterError from None
        self._phone_code_hash = code_hash
        self._state = AuthState.CODE_REQUIRED
        return self._state

    async def submit_code(self, code: str) -> AuthState:
        if (self._state is not AuthState.CODE_REQUIRED or self._phone is None
                or self._phone_code_hash is None):
            raise AdapterError from None
        try:
            await self._call(self._client.sign_in(
                self._phone, code, phone_code_hash=self._phone_code_hash
            ))
        except ExpiredCode:
            self._state = AuthState.AUTH_REQUIRED
            self._phone_code_hash = None
            raise
        except AuthRejected:
            self._state = AuthState.AUTH_REQUIRED
            self._phone_code_hash = None
            raise
        except InvalidCode:
            raise
        except _PasswordChallenge:
            self._state = AuthState.PASSWORD_REQUIRED
            self._phone_code_hash = None
            return self._state
        self._phone_code_hash = None
        return await self._confirm_and_save()

    async def submit_password(self, password: str) -> AuthState:
        if self._state is not AuthState.PASSWORD_REQUIRED:
            raise AdapterError from None
        await self._call(self._client.sign_in(password=password))
        return await self._confirm_and_save()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._disconnect()
