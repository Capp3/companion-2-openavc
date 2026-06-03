"""Integration tests for structured CLI logging."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from c2o.cli import app


def _json_log_lines(stderr: str) -> str:
    lines = [line for line in stderr.splitlines() if line.startswith("{")]
    for line in lines:
        json.loads(line)
    return "\n".join(lines) + ("\n" if lines else "")


def _normalize_paths(value: str, replacements: dict[Path, str]) -> str:
    normalized = value
    for path, replacement in replacements.items():
        normalized = normalized.replace(str(path), replacement)
    return normalized


def test_default_inspect_emits_no_logs(dummy_device: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(dummy_device)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stderr == ""


def test_inspect_verbose_json_logs_match_snapshot(
    bmd_webpresenter: Path,
    snapshot: Any,
) -> None:
    result = CliRunner().invoke(
        app,
        ["-vv", "--log-format", "json", "inspect", str(bmd_webpresenter)],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    logs = _normalize_paths(
        _json_log_lines(result.stderr),
        {bmd_webpresenter: "<bmd-webpresenter>"},
    )
    assert logs == snapshot


def test_convert_declined_verbose_json_logs_match_snapshot(
    declined_udp: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["-v", "--log-format", "json", "convert", str(declined_udp), "-o", str(out_avc)],
    )

    assert result.exit_code == 2, result.stdout + result.stderr
    logs = _normalize_paths(
        _json_log_lines(result.stderr),
        {
            declined_udp: "<declined-udp>",
            tmp_path: "<tmp>",
        },
    )
    logs = re.sub(r'"bytes": \d+', '"bytes": 0', logs)
    assert logs == snapshot
