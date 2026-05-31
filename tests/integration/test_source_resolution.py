"""Source-resolution smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import c2o.source.classify as classify
from c2o.cli import app


def test_inspect_local_source_smoke(dummy_device: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(dummy_device)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Eligibility: eligible"
    assert "Module: dummy_device" in result.stdout


def test_inspect_file_url_source_smoke(dummy_device_git_url: str) -> None:
    result = CliRunner().invoke(app, ["inspect", dummy_device_git_url])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Eligibility: eligible"
    assert "Module: dummy_device" in result.stdout


def test_inspect_bare_id_source_smoke(
    dummy_device_git_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(classify, "expand_bare_id", lambda _module_id: dummy_device_git_url)

    result = CliRunner().invoke(app, ["inspect", "dummy-device"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Eligibility: eligible"
    assert "Module: dummy_device" in result.stdout


def test_inspect_keep_temp_preserves_cloned_source(dummy_device_git_url: str) -> None:
    result = CliRunner().invoke(app, ["inspect", dummy_device_git_url, "--keep-temp"])

    assert result.exit_code == 0, result.stdout + result.stderr
    preserved_line = next(
        line for line in result.stderr.splitlines() if line.startswith("Preserved clone at: ")
    )
    preserved_path = Path(preserved_line.removeprefix("Preserved clone at: "))
    try:
        assert preserved_path.is_dir()
        assert (preserved_path / "companion" / "manifest.json").is_file()
    finally:
        if preserved_path.exists():
            for path in sorted(preserved_path.rglob("*"), reverse=True):
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            preserved_path.rmdir()
