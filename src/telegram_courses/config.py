"""Load and validate the minimal S0 configuration."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path("config/settings.toml")
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_SENSITIVE_KEYS = {"api_id", "api_hash", "password", "session", "session_string"}


class ConfigurationError(Exception):
    """Raised when a selected configuration source is invalid."""


@dataclass(frozen=True)
class Configuration:
    config: str
    log_level: str


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
) -> tuple[str, str | None]:
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
        return "defaults", None
    except OSError:
        raise ConfigurationError from None

    try:
        data = tomllib.loads(contents.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        raise ConfigurationError from None

    _validate_sensitive_keys(data)
    if set(data) - {"logging"}:
        raise ConfigurationError
    level: str | None = None
    if "logging" in data:
        logging = data["logging"]
        if not isinstance(logging, dict) or set(logging) - {"level"}:
            raise ConfigurationError
        if "level" in logging:
            level = _validate_log_level(logging["level"])
    return "file", level


def load_configuration(
    *, config_path: str | None = None, log_level: str | None = None
) -> Configuration:
    """Return the public config indicator and effective logging level."""
    environ = os.environ
    indicator, file_level = _read_configuration(config_path, environ)

    environment_level = environ.get("TELEGRAM_COURSES_LOG_LEVEL")
    if environment_level is not None:
        _validate_log_level(environment_level)
    cli_level = _validate_log_level(log_level) if log_level is not None else None

    return Configuration(
        config=indicator,
        log_level=cli_level or environment_level or file_level or "INFO",
    )
