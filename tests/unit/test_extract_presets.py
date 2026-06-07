"""Unit tests for Companion preset sibling extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.presets import extract_presets
from c2o.parse.js import parse_module


def test_dummy_presets_extract_direct_literal(dummy_device: Path) -> None:
    section, review = extract_presets(parse_module(dummy_device))

    assert len(review) == 0
    assert len(section.presets) == 1
    preset = section.presets[0]
    assert preset.id == "mute"
    assert preset.type == "button"
    assert preset.category == "Device"
    assert preset.name == "Mute"
    assert preset.style == {
        "text": "MUTE",
        "size": "14",
        "color": 16777215,
        "bgcolor": 16711680,
    }
    assert len(preset.steps) == 1
    assert preset.steps[0].down[0].action_id == "toggle_mute"
    assert preset.steps[0].down[0].options == {}
    assert preset.steps[0].up == ()


def test_bmd_presets_extract_assignment_built_objects(bmd_webpresenter: Path) -> None:
    section, review = extract_presets(parse_module(bmd_webpresenter))

    assert len(review) == 0
    assert [preset.id for preset in section.presets] == ["Start", "Stop", "Reboot"]

    start = section.presets[0]
    assert start.category == "Streaming"
    assert start.name == "Start Stream"
    assert start.style == {
        "text": "Start Stream",
        "size": "auto",
        "bgcolor": 0,
        "color": 16777215,
    }
    assert start.steps[0].down[0].action_id == "stream"
    assert start.steps[0].down[0].options == {"stream_control": "Start"}
    assert start.steps[0].up == ()
    assert len(start.feedbacks) == 3
    assert start.feedbacks[0].feedback_id == "streaming_state"
    assert start.feedbacks[0].options == {"stream_state": "Idle"}
    assert start.feedbacks[0].style == {"bgcolor": 0, "color": 16777215}
    assert start.feedbacks[1].style == {"bgcolor": 16744448, "color": 16777215}
    assert start.feedbacks[2].style == {"bgcolor": 52224, "color": 16777215}

    reboot = section.presets[2]
    assert reboot.steps[0].down[0].action_id == "device"
    assert reboot.steps[0].down[0].options == {"device_control": "Reboot"}
    assert reboot.feedbacks == ()


def test_panasonic_presets_extract_factory_definitions(panasonic_ptz: Path) -> None:
    section, review = extract_presets(parse_module(panasonic_ptz))

    assert len(review) == 0
    assert len(section.presets) >= 60
    assert [preset.id for preset in section.presets[:3]] == [
        "pan-tilt-up",
        "pan-tilt-down",
        "pan-tilt-left",
    ]
    assert section.presets[0].steps[0].down[0].action_id == "up"
