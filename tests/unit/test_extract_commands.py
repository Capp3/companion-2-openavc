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


def test_panasonic_ptz_extracts_static_http_helper_commands(panasonic_ptz: Path) -> None:
    section, review = extract_commands(parse_module(panasonic_ptz))

    assert len(section.commands) >= 20
    assert section.commands["power_on"].method == "GET"
    assert section.commands["power_on"].path == "/cgi-bin/aw_ptz"
    assert section.commands["power_on"].query_params == {"cmd": "#O1", "res": "1"}
    assert section.commands["stop"].query_params == {"cmd": "#PTS5050", "res": "1"}
    assert section.commands["sd_card_rec"].path == "/cgi-bin/sdctrl"
    assert section.commands["sd_card_rec"].query_params == {"save": "{value}"}
    assert section.commands["sd_card_rec"].params["value"].values == ("start", "end")

    # Command ids are normalized to snake_case and review-flagged.
    assert all(cid == cid.lower() for cid in section.commands)
    normalized = review.by_code(ReviewCode.COMMAND_ID_NORMALIZED)
    assert any(flag.details == {"old": "powerOn", "new": "power_on"} for flag in normalized)

    flags = review.by_code(ReviewCode.STATE_DEPENDENT_BRANCH)
    assert len(flags) >= 20
    assert any(flag.field == "commands.left" for flag in flags)
    assert all(flag.details["reason"] == "http_send_helper_dynamic" for flag in flags)


def test_unknown_vendor_returns_empty_commands(unknown_vendor: Path) -> None:
    section, review = extract_commands(parse_module(unknown_vendor))

    assert section.commands == {}
    assert review.by_code(ReviewCode.STATE_DEPENDENT_BRANCH) == ()
