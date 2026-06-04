"""Integration tests for CLI conversion paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from c2o.cli import app
from c2o.validate import validate_upstream


def test_convert_declined_udp_writes_golden_json(
    declined_udp: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(declined_udp), "-o", str(out_avc)],
    )
    assert result.exit_code == 2, result.stdout + result.stderr
    assert not out_avc.exists()

    decline_path = tmp_path / "out.declined.json"
    assert decline_path.is_file()

    payload = json.loads(decline_path.read_text(encoding="utf-8"))
    payload["source"] = "<fixture>"
    assert payload == snapshot


@pytest.mark.parametrize("mode_args", [[], ["--strict"]])
def test_convert_strict_eligible_dummy_exits_one_with_review_flags(
    dummy_device: Path,
    tmp_path: Path,
    mode_args: list[str],
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(dummy_device), "-o", str(out_avc), *mode_args],
    )
    assert result.exit_code == 1, result.stdout + result.stderr
    assert "Strict mode: conversion requires 7 review flag(s) to be resolved." in result.stderr
    assert "[compatible_models_confidence] compatible_models:" in result.stderr
    assert not out_avc.exists()
    assert not (tmp_path / "out.declined.json").exists()
    assert not (tmp_path / "out.review.json").exists()


def test_convert_lenient_declined_udp_still_exits_two(
    declined_udp: Path,
    tmp_path: Path,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(declined_udp), "-o", str(out_avc), "--lenient"],
    )
    assert result.exit_code == 2, result.stdout + result.stderr
    assert not out_avc.exists()
    assert (tmp_path / "out.declined.json").is_file()
    assert not (tmp_path / "out.review.json").exists()


def test_convert_lenient_eligible_dummy_exits_zero(
    dummy_device: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(dummy_device), "-o", str(out_avc), "--lenient"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert out_avc.is_file()
    assert yaml.safe_load(out_avc.read_text(encoding="utf-8"))["id"] == "dummy_device"
    assert validate_upstream(out_avc).passed
    assert not (tmp_path / "out.declined.json").exists()

    review_path = tmp_path / "out.review.json"
    assert review_path.is_file()
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload["source"] = "<fixture>"
    assert payload == snapshot


def test_convert_strict_declined_udp_still_exits_two(
    declined_udp: Path,
    tmp_path: Path,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(declined_udp), "-o", str(out_avc), "--strict"],
    )
    assert result.exit_code == 2, result.stdout + result.stderr
    assert not out_avc.exists()
    assert (tmp_path / "out.declined.json").is_file()
    assert not (tmp_path / "out.review.json").exists()


@pytest.mark.parametrize(
    ("mode_args", "expected"),
    [
        (["--strict", "--lenient"], "--strict, --lenient cannot be used together"),
        (["--strict", "--todo"], "--strict, --todo cannot be used together"),
        (["--lenient", "--todo"], "--lenient, --todo cannot be used together"),
    ],
)
def test_convert_rejects_multiple_review_modes(
    dummy_device: Path,
    tmp_path: Path,
    mode_args: list[str],
    expected: str,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(dummy_device), "-o", str(out_avc), *mode_args],
    )
    assert result.exit_code == 2
    assert expected in result.stderr
    assert not out_avc.exists()


def test_convert_rejects_output_and_output_root_together(
    dummy_device: Path,
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "convert",
            str(dummy_device),
            "-o",
            str(tmp_path / "out.avcdriver"),
            "--output-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 2
    assert "--output and --output-root cannot be used together" in result.stderr


def test_convert_defaults_output_root_to_out_dir(
    dummy_device: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app,
        ["convert", str(dummy_device), "--lenient"],
    )

    out_avc = tmp_path / "out" / "utility" / "dummy_device.avcdriver"
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out_avc.is_file()


@pytest.mark.parametrize("mode_arg", ["--todo", "-todo"])
def test_convert_todo_eligible_dummy_exits_zero_with_annotated_yaml(
    dummy_device: Path,
    tmp_path: Path,
    mode_arg: str,
) -> None:
    out_avc = tmp_path / f"{mode_arg.replace('-', '')}.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(dummy_device), "-o", str(out_avc), mode_arg],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stderr == ""
    text = out_avc.read_text(encoding="utf-8")
    assert "#TODO" in text
    assert "# companion/manifest.json:[Unknown]" in text
    assert yaml.safe_load(text)["id"] == "dummy_device"
    assert validate_upstream(out_avc).passed
    assert out_avc.with_suffix(".review.json").is_file()


def test_convert_todo_declined_udp_still_exits_two(
    declined_udp: Path,
    tmp_path: Path,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(declined_udp), "-o", str(out_avc), "--todo"],
    )

    assert result.exit_code == 2, result.stdout + result.stderr
    assert not out_avc.exists()
    assert (tmp_path / "out.declined.json").is_file()
    assert not (tmp_path / "out.review.json").exists()


def test_convert_output_root_derives_eligible_driver_path(
    dummy_device: Path,
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        app,
        ["convert", str(dummy_device), "--output-root", str(tmp_path), "--lenient"],
    )

    out_avc = tmp_path / "utility" / "dummy_device.avcdriver"
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out_avc.is_file()
    assert out_avc.with_suffix(".review.json").is_file()
    assert out_avc.with_suffix(".companion-feedbacks.yml").is_file()
    assert out_avc.with_suffix(".companion-presets.yml").is_file()


def test_convert_output_root_derives_declined_sidecar_path(
    declined_udp: Path,
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        app,
        ["convert", str(declined_udp), "--output-root", str(tmp_path)],
    )

    assert result.exit_code == 2, result.stdout + result.stderr
    assert not (tmp_path / "declined_udp.avcdriver").exists()
    assert (tmp_path / "declined_udp.declined.json").is_file()
