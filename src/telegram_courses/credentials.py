"""Encrypted, user-scoped Telegram API credential storage."""

from __future__ import annotations

import json
from importlib import import_module
from typing import Any

from telegram_courses.config import ConfigurationError, TelegramCredentials


class CredentialVaultError(Exception):
    """Sanitized credential vault failure."""


def validate_credentials(api_id: str, api_hash: str) -> TelegramCredentials:
    if not isinstance(api_id, str):
        raise ConfigurationError from None
    if not isinstance(api_hash, str) or not api_hash.strip():
        raise ConfigurationError from None
    try:
        numeric_id = int(api_id)
    except (TypeError, ValueError):
        raise ConfigurationError from None
    if numeric_id <= 0:
        raise ConfigurationError from None
    return TelegramCredentials(numeric_id, api_hash)


def _encode(credentials: TelegramCredentials) -> str:
    validate_credentials(str(credentials.api_id), credentials.api_hash)
    return json.dumps(
        {"version": 1, "api_id": credentials.api_id,
         "api_hash": credentials.api_hash},
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _decode(raw: str) -> TelegramCredentials:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicates)
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "api_id", "api_hash"}
            or type(value["version"]) is not int
            or value["version"] != 1
            or type(value["api_id"]) is not int
            or type(value["api_hash"]) is not str
        ):
            raise ValueError
        return validate_credentials(str(value["api_id"]), value["api_hash"])
    except (ValueError, TypeError, ConfigurationError, json.JSONDecodeError):
        raise CredentialVaultError from None


class CredentialVault:
    """Use the existing DPAPI/ACL storage with a distinct artifact and format."""

    def __init__(self, *, _storage: Any | None = None) -> None:
        if _storage is None:
            storage_module = import_module("telegram_courses.telethon_session")
            _storage = storage_module._ProtectedCredentialsVault()
        self._storage = _storage

    def setup(self, credentials: TelegramCredentials) -> None:
        try:
            self._storage._save(_encode(credentials))
        except Exception:
            raise CredentialVaultError from None

    def load(self) -> TelegramCredentials | None:
        try:
            raw = self._storage._load()
        except Exception:
            raise CredentialVaultError from None
        if raw is None:
            return None
        return _decode(raw)

    def status(self) -> bool:
        return self.load() is not None
