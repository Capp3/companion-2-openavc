"""Integration tests for interactive CLI conversion prompts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import c2o.cli as cli_module
from c2o.cli import app
from c2o.prompt import TyperPrompter


def _copy_with_promptable_manifest(source: Path, tmp_path: Path) -> Path:
    root = tmp_path / "promptable-device"
    shutil.copytree(source, root)
    manifest_path = root / "companion" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["keywords"] = ["fixture"]
    manifest["manufacturer"] = "Blackmagic Designs"
    manifest["maintainers"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_convert_interactive_resolves_metadata_then_strict_fails_on_remaining_flags(
    dummy_device: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _copy_with_promptable_manifest(dummy_device, tmp_path)
    out_avc = tmp_path / "out.avcdriver"
    monkeypatch.setattr(cli_module, "_prompter_override", TyperPrompter(is_tty=True))

    result = CliRunner().invoke(
        app,
        ["convert", str(root), "-o", str(out_avc), "--interactive"],
        input="6\n1\n\n",
    )

    assert result.exit_code == 1, result.stdout + result.stderr
    assert "Interactive metadata:" in result.stdout
    assert "  category: video" in result.stdout
    assert "  manufacturer: Blackmagic Design" in result.stdout
    assert "  author: Community" in result.stdout
    assert "  unresolved review flags: 0" in result.stdout
    assert "Strict mode: conversion requires 7 review flag(s) to be resolved." in result.stderr
    assert not out_avc.exists()
    assert not (tmp_path / "out.review.json").exists()


def test_convert_interactive_declined_module_does_not_prompt(
    declined_udp: Path,
    tmp_path: Path,
) -> None:
    out_avc = tmp_path / "out.avcdriver"

    result = CliRunner().invoke(
        app,
        ["convert", str(declined_udp), "-o", str(out_avc), "--interactive"],
        input="6\n1\n\n",
    )

    assert result.exit_code == 2, result.stdout + result.stderr
    assert "Interactive metadata:" not in result.stdout
    assert "Category could not be inferred safely." not in result.stdout
    assert (tmp_path / "out.declined.json").is_file()
    assert not out_avc.exists()
