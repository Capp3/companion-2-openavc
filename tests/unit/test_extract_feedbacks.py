"""Unit tests for Companion feedback sibling extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.feedbacks import extract_feedbacks
from c2o.parse.js import parse_module


def test_dummy_feedbacks_extract_direct_literal(dummy_device: Path) -> None:
    section, review = extract_feedbacks(parse_module(dummy_device))

    assert len(review) == 0
    assert len(section.feedbacks) == 1
    feedback = section.feedbacks[0]
    assert feedback.id == "mute_on"
    assert feedback.type == "boolean"
    assert feedback.name == "Mute is on"
    assert feedback.default_style == {"bgcolor": 16711680}
    assert feedback.options == ()
    assert feedback.callback_condition == "this.mute_state"


def test_bmd_feedbacks_extract_assignment_built_object(bmd_webpresenter: Path) -> None:
    section, review = extract_feedbacks(parse_module(bmd_webpresenter))

    assert len(review) == 0
    assert len(section.feedbacks) == 1
    feedback = section.feedbacks[0]
    assert feedback.id == "streaming_state"
    assert feedback.name == "Device is streaming"
    assert feedback.description == "Change background colour based on streaming state"
    assert feedback.default_style == {"color": 0, "bgcolor": 52224}
    assert feedback.callback_condition is None
    assert len(feedback.options) == 1
    option = feedback.options[0]
    assert option.id == "stream_state"
    assert option.type == "enum"
    assert option.label == "State"
    assert option.default == "Streaming"
    assert option.values == ("Idle", "Connecting", "Streaming", "Interrupted")
