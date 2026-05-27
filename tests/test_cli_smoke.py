"""CLI smoke tests."""

from typer.testing import CliRunner

from c2o.cli import app


def test_cli_help_exits_zero() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "convert" in result.stdout
    assert "inspect" in result.stdout
    assert "validate" in result.stdout
    assert "version" in result.stdout


def test_version_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.0.0"
