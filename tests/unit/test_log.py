"""Unit tests for C2O structured logging."""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime

import c2o.log as log_mod
from c2o.log import LogFormat, configure_logging, emit


def test_configure_logging_maps_verbosity_to_levels() -> None:
    assert configure_logging(verbosity=0, log_format=LogFormat.text).level == logging.WARNING
    assert configure_logging(verbosity=1, log_format=LogFormat.text).level == logging.INFO
    assert configure_logging(verbosity=2, log_format=LogFormat.text).level == logging.DEBUG
    assert configure_logging(verbosity=3, log_format=LogFormat.text).level == logging.DEBUG


def test_configure_logging_replaces_handlers() -> None:
    first = configure_logging(verbosity=1, log_format=LogFormat.text, stream=io.StringIO())
    first_handler = first.handlers[0]

    second = configure_logging(verbosity=1, log_format=LogFormat.text, stream=io.StringIO())

    assert second is first
    assert len(second.handlers) == 1
    assert second.handlers[0] is not first_handler


def test_json_formatter_emits_required_shape_with_frozen_clock(
    monkeypatch: object,
) -> None:
    stream = io.StringIO()
    log_mod._clock_override = lambda: datetime(2024, 1, 1, tzinfo=UTC)
    try:
        logger = configure_logging(verbosity=1, log_format=LogFormat.json, stream=stream)
        emit(logger, logging.INFO, "source_resolution_complete", kind="local", root="/tmp/mod")
    finally:
        log_mod._clock_override = None

    payload = json.loads(stream.getvalue())
    assert payload == {
        "ts": "2024-01-01T00:00:00Z",
        "level": "INFO",
        "event": "source_resolution_complete",
        "module": "c2o",
        "details": {"kind": "local", "root": "/tmp/mod"},
    }


def test_json_formatter_defaults_details_to_empty_dict() -> None:
    stream = io.StringIO()
    log_mod._clock_override = lambda: datetime(2024, 1, 1, tzinfo=UTC)
    try:
        logger = configure_logging(verbosity=1, log_format=LogFormat.json, stream=stream)
        emit(logger, logging.INFO, "ready")
    finally:
        log_mod._clock_override = None

    payload = json.loads(stream.getvalue())
    assert payload["details"] == {}


def test_text_formatter_emits_human_readable_event() -> None:
    stream = io.StringIO()
    logger = configure_logging(verbosity=1, log_format=LogFormat.text, stream=stream)

    emit(logger, logging.INFO, "suitability_gate_result", eligible=True, blocker_codes=[])

    assert stream.getvalue().strip() == (
        'INFO: suitability_gate_result {"eligible": true, "blocker_codes": []}'
    )
