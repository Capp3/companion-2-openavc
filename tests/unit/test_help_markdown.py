"""Unit tests for HELP.md markdown parsing."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.help_markdown import parse_help_markdown

DUMMY_HELP = """# Dummy Device

Connect to the dummy device on the configured host and port.

## Setup

Enter the device IP address and TCP port, then enable polling if needed.

## Version 1.0.0

Initial fixture release.
"""


def test_parse_help_markdown_dummy_shape() -> None:
    result = parse_help_markdown(DUMMY_HELP)
    assert result is not None
    overview, setup = result
    assert overview == "Connect to the dummy device on the configured host and port."
    assert setup == (
        "## Setup\n\nEnter the device IP address and TCP port, then enable polling if needed."
    )


def test_parse_help_markdown_strips_changelog() -> None:
    result = parse_help_markdown(DUMMY_HELP)
    assert result is not None
    _, setup = result
    assert "Version 1.0.0" not in setup
    assert "Initial fixture release" not in setup


def test_parse_help_markdown_bmd_splits_overview_and_setup(bmd_webpresenter: Path) -> None:
    help_text = (bmd_webpresenter / "companion" / "HELP.md").read_text(encoding="utf-8")
    result = parse_help_markdown(help_text)
    assert result is not None
    overview, setup = result
    assert overview.startswith("Module to control and monitor the [Blackmagic")
    assert "Web Presenter** product." in overview
    assert "Once connection to the device has been established" in setup
    assert "Please log issues and feature requests on [github]" in setup


def test_parse_help_markdown_returns_none_for_empty_input() -> None:
    assert parse_help_markdown("") is None
    assert parse_help_markdown("   \n\n  ") is None


def test_parse_help_markdown_single_block_has_empty_setup() -> None:
    text = "# Title\n\nOnly one paragraph.\n\n## Version 1.0.0\nChangelog"
    result = parse_help_markdown(text)
    assert result is not None
    overview, setup = result
    assert overview == "Only one paragraph."
    assert setup == ""
