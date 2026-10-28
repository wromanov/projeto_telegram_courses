"""Load and validate local application settings and credentials."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path("config/settings.toml")
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_SENSITIVE_KEYS = {
    "api_id",
    "api_hash",
    "api_key",
    "access_token",
    "auth_token",
    "bot_token",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "refresh_token",
    "secret",
    "secret_key",
    "session",
    "session_string",
    "token",
}


class ConfigurationError(Exception):
    """Raised when a selected configuration source is invalid."""


@dataclass(frozen=True)
class Configuration:
    config: str
    log_level: str
    workers: int = 2
    attempts_per_media: int = 3
    download_dir: str = "downloads"
    database_path: str = "data/catalog.sqlite3"


@dataclass(frozen=True)
class TelegramCredentials:
    api_id: int
    api_hash: str


def load_telegram_credentials(
    environ: Mapping[str, str] | None = None,
    *,
    vault: Any | None = None,
) -> TelegramCredentials:
    """Resolve one complete environment pair, then the encrypted local vault."""
    source = os.environ if environ is None else environ
    has_id = "TELEGRAM_API_ID" in source
    has_hash = "TELEGRAM_API_HASH" in source
    if has_id or has_hash:
        if not has_id or not has_hash:
            raise ConfigurationError from None
        try:
            from telegram_courses.credentials import validate_credentials

            return validate_credentials(
                source["TELEGRAM_API_ID"], source["TELEGRAM_API_HASH"]
            )
        except Exception:
            raise ConfigurationError from None

    try:
        from telegram_courses.credentials import CredentialVault

        selected_vault = vault if vault is not None else CredentialVault()
        credentials = selected_vault.load()
    except Exception:
        raise ConfigurationError from None
    if credentials is None:
        raise ConfigurationError from None
    return credentials


def _validate_sensitive_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in _SENSITIVE_KEYS:
                raise ConfigurationError
            _validate_sensitive_keys(child)
    elif isinstance(value, list):
        for child in value:
            _validate_sensitive_keys(child)


def _validate_log_level(value: Any) -> str:
    if not isinstance(value, str) or value not in _LOG_LEVELS:
        raise ConfigurationError
    return value


def _read_configuration(
    config_path: str | None, environ: Mapping[str, str]
) -> tuple[str, dict[str, Any]]:
    environment_path = environ.get("TELEGRAM_COURSES_CONFIG")
    explicit_path = config_path if config_path is not None else environment_path
    selected_path = explicit_path if explicit_path is not None else _DEFAULT_CONFIG_PATH
    invalid_explicit_path = (
        explicit_path is not None
        and (not explicit_path or not explicit_path.lower().endswith(".toml"))
    )
    if invalid_explicit_path:
        raise ConfigurationError

    path = Path(selected_path)
    try:
        contents = path.read_bytes()
    except FileNotFoundError:
        if explicit_path is not None:
            raise ConfigurationError from None
        return "defaults", {}
    except OSError:
        raise ConfigurationError from None

    try:
        data = tomllib.loads(contents.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        raise ConfigurationError from None

    _validate_sensitive_keys(data)
    if set(data) - {"logging", "download", "storage"}:
        raise ConfigurationError
    settings: dict[str, Any] = {}
    if "logging" in data:
        logging = data["logging"]
        if not isinstance(logging, dict) or set(logging) - {"level"}:
            raise ConfigurationError
        if "level" in logging:
            settings["log_level"] = _validate_log_level(logging["level"])
    if "download" in data:
        download = data["download"]
        if not isinstance(download, dict) or set(download) - {
            "workers", "attempts_per_media", "directory"
        }:
            raise ConfigurationError
        if "workers" in download:
            settings["workers"] = _validate_workers(download["workers"])
        if "attempts_per_media" in download:
            settings["attempts_per_media"] = _validate_attempts(
                download["attempts_per_media"]
            )
        if "directory" in download:
            settings["download_dir"] = _validate_path_setting(
                download["directory"]
            )
    if "storage" in data:
        storage = data["storage"]
        if not isinstance(storage, dict) or set(storage) - {"database_path"}:
            raise ConfigurationError
        if "database_path" in storage:
            settings["database_path"] = _validate_path_setting(
                storage["database_path"]
            )
    return "file", settings


def _validate_workers(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 2:
        raise ConfigurationError
    return value


def _validate_attempts(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 3:
        raise ConfigurationError
    return value


def _validate_path_setting(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ConfigurationError
    return value


def _environment_integer(
    environ: Mapping[str, str], name: str, validate: Callable[[Any], int]
) -> int | None:
    if name not in environ:
        return None
    raw = environ[name]
    if not raw.isascii() or not raw.isdecimal():
        raise ConfigurationError
    return validate(int(raw))


def load_configuration(
    *,
    config_path: str | None = None,
    log_level: str | None = None,
    workers: int | None = None,
    attempts_per_media: int | None = None,
    download_dir: str | None = None,
    database_path: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Configuration:
    """Resolve CLI, environment, TOML, then application defaults."""
    source = os.environ if environ is None else environ
    indicator, file_settings = _read_configuration(config_path, source)

    environment_level = source.get("TELEGRAM_COURSES_LOG_LEVEL")
    if environment_level is not None:
        _validate_log_level(environment_level)
    cli_level = _validate_log_level(log_level) if log_level is not None else None

    environment_workers = _environment_integer(
        source, "TELEGRAM_COURSES_WORKERS", _validate_workers
    )
    environment_attempts = _environment_integer(
        source, "TELEGRAM_COURSES_ATTEMPTS_PER_MEDIA", _validate_attempts
    )
    environment_download_dir = source.get("TELEGRAM_COURSES_DOWNLOAD_DIR")
    if environment_download_dir is not None:
        _validate_path_setting(environment_download_dir)
    environment_database = source.get("TELEGRAM_COURSES_DATABASE_PATH")
    if environment_database is not None:
        _validate_path_setting(environment_database)

    cli_workers = _validate_workers(workers) if workers is not None else None
    cli_attempts = (
        _validate_attempts(attempts_per_media)
        if attempts_per_media is not None
        else None
    )
    cli_download_dir = (
        _validate_path_setting(download_dir) if download_dir is not None else None
    )
    cli_database = (
        _validate_path_setting(database_path) if database_path is not None else None
    )

    return Configuration(
        config=indicator,
        log_level=cli_level or environment_level or file_settings.get("log_level", "INFO"),
        workers=(
            cli_workers
            if cli_workers is not None
            else environment_workers
            if environment_workers is not None
            else file_settings.get("workers", 2)
        ),
        attempts_per_media=(
            cli_attempts
            if cli_attempts is not None
            else environment_attempts
            if environment_attempts is not None
            else file_settings.get("attempts_per_media", 3)
        ),
        download_dir=(
            cli_download_dir
            if cli_download_dir is not None
            else environment_download_dir
            if environment_download_dir is not None
            else file_settings.get("download_dir", "downloads")
        ),
        database_path=(
            cli_database
            if cli_database is not None
            else environment_database
            if environment_database is not None
            else file_settings.get("database_path", "data/catalog.sqlite3")
        ),
    )
