"""Structured logging helpers for the C2O CLI."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, TextIO


class LogFormat(StrEnum):
    """Supported CLI log output formats."""

    text = "text"
    json = "json"


# Injectable clock for deterministic JSON log snapshots.
_clock_override: Callable[[], datetime] | None = None


def _now() -> datetime:
    if _clock_override is not None:
        return _clock_override()
    return datetime.now(tz=UTC)


def _format_ts(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _level_for_verbosity(verbosity: int) -> int:
    if verbosity <= 0:
        return logging.WARNING
    if verbosity == 1:
        return logging.INFO
    return logging.DEBUG


def _json_safe(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        details = getattr(record, "c2o_details", {})
        if not isinstance(details, Mapping):
            details = {"value": details}
        payload = {
            "ts": _format_ts(_now()),
            "level": record.levelname,
            "event": getattr(record, "c2o_event", record.getMessage()),
            "module": record.name,
            "details": _json_safe(details),
        }
        return json.dumps(payload, ensure_ascii=True)


class TextFormatter(logging.Formatter):
    """Render compact human-readable log records."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "c2o_event", record.getMessage())
        details = getattr(record, "c2o_details", {})
        if not details:
            return f"{record.levelname}: {event}"
        return f"{record.levelname}: {event} {json.dumps(_json_safe(details), ensure_ascii=True)}"


def configure_logging(
    *,
    verbosity: int,
    log_format: LogFormat,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure the C2O logger idempotently for a CLI invocation."""
    logger = logging.getLogger("c2o")
    logger.handlers.clear()
    logger.setLevel(_level_for_verbosity(verbosity))
    logger.propagate = False

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter() if log_format is LogFormat.json else TextFormatter())
    logger.addHandler(handler)
    return logger


def emit(
    logger: logging.Logger,
    level: int,
    event: str,
    **details: Any,
) -> None:
    """Emit a structured log event."""
    logger.log(level, event, extra={"c2o_event": event, "c2o_details": details})
