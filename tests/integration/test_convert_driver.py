"""Integration tests for primary .avcdriver emission."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from c2o.cli import app
from c2o.validate import validate_upstream


def _convert_lenient(root: Path, out_path: Path) -> str:
    result = CliRunner().invoke(
        app,
        ["convert", str(root), "-o", str(out_path), "--lenient"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out_path.is_file()
    validation = validate_upstream(out_path)
    assert validation.passed, validation.stderr
    return out_path.read_text(encoding="utf-8")


def _convert_todo(root: Path, out_path: Path) -> str:
    result = CliRunner().invoke(
        app,
        ["convert", str(root), "-o", str(out_path), "--todo"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out_path.is_file()
    validation = validate_upstream(out_path)
    assert validation.passed, validation.stderr
    return out_path.read_text(encoding="utf-8")


def test_convert_dummy_writes_valid_avcdriver_golden(
    dummy_device: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    assert _convert_lenient(dummy_device, tmp_path / "dummy_device.avcdriver") == snapshot


def test_convert_bmd_writes_valid_avcdriver_golden(
    bmd_webpresenter: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    assert _convert_lenient(bmd_webpresenter, tmp_path / "bmd_webpresenter.avcdriver") == snapshot


def test_convert_bmd_writes_valid_todo_avcdriver_golden(
    bmd_webpresenter: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    plain = _convert_lenient(bmd_webpresenter, tmp_path / "plain.avcdriver")
    annotated = _convert_todo(bmd_webpresenter, tmp_path / "todo.avcdriver")

    assert "#TODO" in annotated
    assert yaml.safe_load(annotated) == yaml.safe_load(plain)
    assert annotated == snapshot
