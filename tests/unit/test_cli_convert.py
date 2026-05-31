"""CLI edge-case tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import c2o.source.remote as remote
from c2o.cli import app


def test_convert_remote_clone_failure_exits_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=128,
            stdout="",
            stderr="clone failed",
        )

    monkeypatch.setattr(remote, "_git_runner_override", runner)

    result = CliRunner().invoke(
        app,
        [
            "convert",
            "https://github.com/bitfocus/companion-module-x",
            "-o",
            str(tmp_path / "o.avcdriver"),
        ],
    )
    assert result.exit_code == 1
    assert "Failed to clone" in result.stderr
    assert "clone failed" in result.stderr
