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
    assert "--verbose" in result.stdout
    assert "--log-format" in result.stdout


def test_version_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.0.0"
    assert result.stderr == ""


def test_global_verbose_flag_before_subcommand_is_accepted() -> None:
    result = CliRunner().invoke(app, ["-v", "version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.0.0"


def test_global_json_log_format_before_subcommand_is_accepted() -> None:
    result = CliRunner().invoke(app, ["--log-format", "json", "version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.0.0"


def test_invalid_log_format_fails() -> None:
    result = CliRunner().invoke(app, ["--log-format", "yaml", "version"])

    assert result.exit_code != 0
    assert "yaml" in result.stderr


def test_global_verbose_flag_after_subcommand_is_not_supported() -> None:
    result = CliRunner().invoke(app, ["version", "-v"])

    assert result.exit_code != 0
    assert "-v" in result.stderr
