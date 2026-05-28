"""Unit tests for setActionDefinitions command extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.commands import extract_commands
from c2o.model.review import ReviewCode
from c2o.parse.js import parse_module


def test_dummy_device_extracts_branch_split_and_state_flag(dummy_device: Path) -> None:
    section, review = extract_commands(parse_module(dummy_device))

    assert set(section.commands) == {"set_input", "stream_start", "stream_stop", "configure"}
    assert section.commands["set_input"].send == "SET INPUT {input}\n"
    assert section.commands["set_input"].params["input"].type == "integer"
    assert section.commands["set_input"].params["input"].min == 1
    assert section.commands["set_input"].params["input"].max == 8
    assert section.commands["stream_start"].send == "STREAM START\n"
    assert section.commands["stream_stop"].send == "STREAM STOP\n"
    assert section.commands["configure"].send == "CFG {mode} {label}\n"
    assert section.commands["configure"].params["mode"].values == ("auto", "manual")

    flags = review.by_code(ReviewCode.STATE_DEPENDENT_BRANCH)
    assert len(flags) == 1
    assert flags[0].field == "commands.toggle_mute"
    assert flags[0].details["reason"] == "instance_state"


def test_bmd_webpresenter_extracts_stream_commands(bmd_webpresenter: Path) -> None:
    section, review = extract_commands(parse_module(bmd_webpresenter))

    assert set(section.commands) == {"stream_start", "stream_stop"}
    assert section.commands["stream_start"].send == "STREAM STATE:\nAction: Start\n\n"
    assert section.commands["stream_stop"].send == "STREAM STATE:\nAction: Stop\n\n"

    flags = review.by_code(ReviewCode.STATE_DEPENDENT_BRANCH)
    assert len(flags) == 1
    assert flags[0].field == "commands.stream"
    assert flags[0].details["reason"] == "toggle_branch"


def test_unknown_vendor_returns_empty_commands(unknown_vendor: Path) -> None:
    section, review = extract_commands(parse_module(unknown_vendor))

    assert section.commands == {}
    assert review.by_code(ReviewCode.STATE_DEPENDENT_BRANCH) == ()
