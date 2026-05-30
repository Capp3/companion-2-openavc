"""Unit tests for help extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.help import extract_help
from c2o.parse.js import parse_module


def test_dummy_help_from_help_md(dummy_device: Path) -> None:
    section, review = extract_help(dummy_device, parse_module(dummy_device))

    assert section.overview == "Connect to the dummy device on the configured host and port."
    assert section.setup == (
        "## Setup\n\nEnter the device IP address and TCP port, then enable polling if needed."
    )
    assert review.flags == ()


def test_bmd_help_from_help_md(bmd_webpresenter: Path) -> None:
    section, review = extract_help(bmd_webpresenter, parse_module(bmd_webpresenter))

    assert section.overview.startswith("Module to control and monitor the [Blackmagic")
    assert "Once connection to the device has been established" in section.setup
    assert "Please log issues and feature requests on [github]" in section.setup
    assert review.flags == ()


def test_unknown_vendor_uses_manifest_description_fallback(unknown_vendor: Path) -> None:
    description = "Eligible TCP fixture with a manufacturer that is not in the upstream registry."
    section, review = extract_help(unknown_vendor, parse_module(unknown_vendor))

    assert section.overview == description
    assert section.setup == description
    assert review.flags == ()


def test_extract_help_accepts_manifest_description_override(dummy_device: Path) -> None:
    section, _ = extract_help(
        dummy_device,
        parse_module(dummy_device),
        manifest_description="Override description",
    )

    assert section.overview == "Connect to the dummy device on the configured host and port."
