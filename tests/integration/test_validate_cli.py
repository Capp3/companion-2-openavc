"""Integration tests for the c2o validate command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from c2o.cli import app

VALIDATE_FIXTURES = Path(__file__).parents[1] / "fixtures" / "validate"
VALID_DRIVER = VALIDATE_FIXTURES / "minimal-valid.avcdriver"
INVALID_DRIVER = VALIDATE_FIXTURES / "tampered-invalid.avcdriver"


def _json_log_events(stderr: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stderr.splitlines() if line.startswith("{")]


def test_validate_valid_driver_succeeds() -> None:
    result = CliRunner().invoke(app, ["validate", str(VALID_DRIVER)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Validated 1 driver(s), 0 device(s)." in result.stdout
    assert result.stderr == ""


def test_validate_tampered_driver_fails_with_upstream_error() -> None:
    result = CliRunner().invoke(app, ["validate", str(INVALID_DRIVER)])

    assert result.exit_code == 1
    assert "FAILED: 1 validation error(s):" in result.stderr
    assert "  - utility/tampered-invalid.avcdriver: version:" in result.stderr


def test_validate_verbose_json_logs_schema_validation_result() -> None:
    result = CliRunner().invoke(
        app,
        ["-v", "--log-format", "json", "validate", str(INVALID_DRIVER)],
    )

    assert result.exit_code == 1
    events = _json_log_events(result.stderr)

    assert events[-1]["event"] == "schema_validation_result"
    assert events[-1]["level"] == "WARNING"
    assert events[-1]["details"]["passed"] is False
    assert events[-1]["details"]["error_count"] == 1
    assert events[-1]["details"]["pointer"] == "/version"
    assert "utility/tampered-invalid.avcdriver: version:" in events[-1]["details"]["first_error"]


def test_validate_wrong_suffix_exits_one(tmp_path: Path) -> None:
    wrong_suffix = tmp_path / "driver.yaml"
    wrong_suffix.write_text("id: wrong_suffix\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["validate", str(wrong_suffix)])

    assert result.exit_code == 1
    assert "expected a .avcdriver file" in result.stderr
