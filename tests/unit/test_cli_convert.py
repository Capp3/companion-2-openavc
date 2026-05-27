"""CLI edge-case tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from c2o.cli import app


def test_convert_rejects_non_local_source(tmp_path: Path) -> None:
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
    assert "M13" in result.stderr
