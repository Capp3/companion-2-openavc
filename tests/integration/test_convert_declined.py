"""Integration tests for CLI conversion paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from c2o.cli import app


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
    assert not out_avc.exists()
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


def test_convert_rejects_strict_and_lenient_together(
    dummy_device: Path,
    tmp_path: Path,
) -> None:
    out_avc = tmp_path / "out.avcdriver"
    result = CliRunner().invoke(
        app,
        ["convert", str(dummy_device), "-o", str(out_avc), "--strict", "--lenient"],
    )
    assert result.exit_code == 2
    assert "--strict and --lenient cannot be used together" in result.stderr
    assert not out_avc.exists()
