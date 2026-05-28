"""Integration tests for `c2o inspect`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from c2o.cli import app


def test_inspect_declined_prints_eligibility_first(declined_udp: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(declined_udp)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Eligibility: declined"
    assert "Blockers: 1" in result.stdout
    assert "transport_udp" in result.stdout
    assert "UDPHelper" in result.stdout


def test_inspect_eligible_prints_readiness(dummy_device: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(dummy_device)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Eligibility: eligible"
    assert "Ready for extraction: yes" in result.stdout
    assert "M4+" in result.stdout


def test_inspect_rejects_non_local_source() -> None:
    result = CliRunner().invoke(
        app,
        ["inspect", "https://github.com/bitfocus/companion-module-x"],
    )

    assert result.exit_code == 1
    assert "M13" in result.stderr
