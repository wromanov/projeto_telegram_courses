"""Structured operational logging with an allow-list of safe context fields."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import TextIO

_LOGGER_NAME = "telegram_courses"
_SAFE_KEYS = {
    "run_id",
    "correlation_id",
    "channel_id",
    "message_id",
    "media_ordinal",
    "category",
    "attempt",
    "retry_after_seconds",
    "state",
    "status",
    "elapsed_seconds",
    "bytes_transferred",
    "bytes_expected",
    "workers",
    "items_total",
    "items_completed",
    "items_failed",
    "items_skipped",
}
_SAFE_TEXT = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


class _SafeJsonFormatter(logging.Formatter):
    """Serialize only explicitly whitelisted data; omit messages and tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        event_data = getattr(record, "operational_event", None)
        if not isinstance(event_data, dict):
            event_data = {}
        context = event_data.get("context", {})
        if not isinstance(context, dict):
            context = {}
        safe_context = {
            key: value
            for key, raw in context.items()
            if key in _SAFE_KEYS
            for value in (_safe_value(raw),)
            if value is not None
        }
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "severity": record.levelname,
            "component": _safe_label(event_data.get("component"), "application"),
            "event": _safe_label(event_data.get("event"), "log_record"),
            "context": safe_context,
        }
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def _safe_label(value: object, fallback: str) -> str:
    if isinstance(value, str) and _SAFE_TEXT.fullmatch(value):
        return value
    return fallback


def _safe_value(value: object) -> str | int | float | bool | None:
    if type(value) in {int, float, bool}:
        return value
    if isinstance(value, str):
        return value if _SAFE_TEXT.fullmatch(value) else "<redacted>"
    return None


class _SafeStreamHandler(logging.StreamHandler):
    """Never expose internal log-handler exceptions or their tracebacks."""

    def handleError(self, record: logging.LogRecord) -> None:
        # The default handler dumps a traceback (possibly containing secrets)
        # to stderr if the stream is closed, unavailable or refuses a write.
        # Logging is best-effort; the CLI still emits its generic error message.
        return None


def configure_operational_logging(level: str, *, stream: TextIO | None = None) -> None:
    """Install one sanitized JSON handler for application operational events."""
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = _SafeStreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(_SafeJsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def emit_operational_event(
    event: str,
    *,
    component: str,
    level: int = logging.INFO,
    **context: object,
) -> None:
    """Emit a structured event without accepting free-form messages or paths."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.log(
        level,
        event,
        extra={
            "operational_event": {
                "component": component,
                "event": event,
                "context": context,
            }
        },
    )
