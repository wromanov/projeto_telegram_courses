from __future__ import annotations

import io
import json
import logging
from datetime import datetime

import pytest

from telegram_courses.config import ConfigurationError, load_configuration
from telegram_courses.operational_logging import (
    OperationalLoggingFailure,
    configure_operational_logging,
    emit_operational_event,
    finalize_operational_logging,
    finalize_s9_child_exit_code,
)


def test_s8_configuration_precedence_and_public_fields(tmp_path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(
        '[logging]\nlevel = "WARNING"\n'
        "[download]\nworkers = 1\nattempts_per_media = 2\n"
        'directory = "from-file"\n'
        "[storage]\ndatabase_path = \"file.sqlite3\"\n",
        encoding="utf-8",
    )
    environ = {
        "TELEGRAM_COURSES_LOG_LEVEL": "ERROR",
        "TELEGRAM_COURSES_WORKERS": "2",
        "TELEGRAM_COURSES_ATTEMPTS_PER_MEDIA": "1",
        "TELEGRAM_COURSES_DOWNLOAD_DIR": "from-env",
        "TELEGRAM_COURSES_DATABASE_PATH": "env.sqlite3",
    }

    result = load_configuration(
        config_path=str(path), log_level="DEBUG", workers=1,
        attempts_per_media=3, download_dir="from-cli", database_path="cli.sqlite3",
        environ=environ,
    )
    assert (
        result.config, result.log_level, result.workers,
        result.attempts_per_media, result.download_dir, result.database_path,
    ) == ("file", "DEBUG", 1, 3, "from-cli", "cli.sqlite3")

    env_result = load_configuration(config_path=str(path), environ=environ)
    assert (
        env_result.log_level, env_result.workers, env_result.attempts_per_media,
        env_result.download_dir, env_result.database_path,
    ) == ("ERROR", 2, 1, "from-env", "env.sqlite3")
    file_result = load_configuration(config_path=str(path), environ={})
    assert (
        file_result.log_level, file_result.workers, file_result.attempts_per_media,
        file_result.download_dir, file_result.database_path,
    ) == ("WARNING", 1, 2, "from-file", "file.sqlite3")


@pytest.mark.parametrize(
    "environ",
    [
        {"TELEGRAM_COURSES_WORKERS": "0"},
        {"TELEGRAM_COURSES_WORKERS": "3"},
        {"TELEGRAM_COURSES_ATTEMPTS_PER_MEDIA": "4"},
        {"TELEGRAM_COURSES_ATTEMPTS_PER_MEDIA": "1.5"},
        {"TELEGRAM_COURSES_DATABASE_PATH": ""},
    ],
)
def test_s8_configuration_rejects_invalid_environment(environ) -> None:
    with pytest.raises(ConfigurationError):
        load_configuration(environ=environ)


def test_s8_configuration_rejects_unknown_toml_settings(tmp_path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('[download]\nworkers = 3\n', encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_configuration(config_path=str(path), environ={})


def test_s8_operational_log_is_utc_json_allowlisted_and_redacted() -> None:
    stream = io.StringIO()
    configure_operational_logging("INFO", stream=stream)
    emit_operational_event(
        "download.retry", component="download_queue", attempt=2,
        category="NETWORK", api_hash="sensitive-hash",
        message="do not log", traceback="secret-traceback",
        unusual="contains whitespace",
    )
    record = json.loads(stream.getvalue())
    assert set(record) == {"timestamp", "severity", "component", "event", "context"}
    timestamp = record["timestamp"]
    assert timestamp.endswith("Z")
    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert record["context"] == {
        "attempt": 2, "category": "NETWORK",
    }
    assert "sensitive-hash" not in stream.getvalue()
    assert "secret-traceback" not in stream.getvalue()
    assert "do not log" not in stream.getvalue()


def test_s8_logging_handler_failure_does_not_leak_traceback_or_secret(
    monkeypatch, capsys,
) -> None:
    class FailingStream:
        def write(self, _message: str) -> None:
            raise RuntimeError("secret-canary-in-log-handler")

        def flush(self) -> None:
            return None

    monkeypatch.setattr(logging, "raiseExceptions", True)
    try:
        configure_operational_logging("INFO", stream=FailingStream())
        emit_operational_event(
            "operation.failed", component="cli", category="INTERNAL",
            traceback="secret-canary-from-exception",
        )
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""
    finally:
        configure_operational_logging("WARNING", stream=io.StringIO())


def test_t24_supervised_handler_failure_is_redacted_and_cannot_exit_zero(
    monkeypatch,
) -> None:
    class FailingStream:
        def write(self, _message: str) -> None:
            raise RuntimeError("secret-canary-in-log-handler")

        def flush(self) -> None:
            return None

    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "scan")
    configure_operational_logging("INFO", stream=FailingStream())
    try:
        with pytest.raises(OperationalLoggingFailure, match="OPERATIONAL_LOGGING_UNAVAILABLE"):
            emit_operational_event(
                "operation.failed", component="scan", category="INTERNAL",
                token="secret-canary-context",
            )
        assert finalize_operational_logging() is False
        assert finalize_s9_child_exit_code(0) == 125
    finally:
        monkeypatch.delenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", raising=False)
        monkeypatch.delenv("TELEGRAM_COURSES_S9_STAGE", raising=False)
        configure_operational_logging("WARNING", stream=io.StringIO())


def test_t24_supervised_flush_failure_blocks_before_child_success(monkeypatch) -> None:
    class FailingFlushStream(io.StringIO):
        def flush(self) -> None:
            raise OSError("secret-canary-flush")

    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "catalog")
    configure_operational_logging("INFO", stream=FailingFlushStream())
    try:
        assert finalize_s9_child_exit_code(0) == 125
    finally:
        monkeypatch.delenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", raising=False)
        monkeypatch.delenv("TELEGRAM_COURSES_S9_STAGE", raising=False)
        configure_operational_logging("WARNING", stream=io.StringIO())


def test_t24_missing_or_unexpected_handler_cannot_exit_zero(monkeypatch) -> None:
    logger = logging.getLogger("telegram_courses")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "scan")
    configure_operational_logging("INFO", stream=io.StringIO())
    try:
        for handler in tuple(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        assert finalize_operational_logging() is False
        assert finalize_s9_child_exit_code(0) == 125

        configure_operational_logging("INFO", stream=io.StringIO())
        logger.addHandler(logging.StreamHandler(io.StringIO()))
        assert finalize_operational_logging() is False
        assert finalize_s9_child_exit_code(0) == 125
    finally:
        monkeypatch.delenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", raising=False)
        monkeypatch.delenv("TELEGRAM_COURSES_S9_STAGE", raising=False)
        configure_operational_logging("WARNING", stream=io.StringIO())


def test_t24_audit_failure_cannot_reuse_message_limit_exit(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "scan")
    monkeypatch.setattr(
        "telegram_courses.operational_logging.finalize_operational_logging",
        lambda: False,
    )
    assert finalize_s9_child_exit_code(4) == 125
    assert finalize_s9_child_exit_code(None) == 125


def test_t24_successful_audit_preserves_message_limit_exit(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", "1")
    monkeypatch.setenv("TELEGRAM_COURSES_S9_STAGE", "scan")
    configure_operational_logging("INFO", stream=io.StringIO())
    try:
        assert finalize_s9_child_exit_code(4) == 4
    finally:
        monkeypatch.delenv("TELEGRAM_COURSES_S9_SUPERVISED_CHILD", raising=False)
        monkeypatch.delenv("TELEGRAM_COURSES_S9_STAGE", raising=False)
        configure_operational_logging("WARNING", stream=io.StringIO())
