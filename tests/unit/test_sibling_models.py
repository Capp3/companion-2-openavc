"""Unit tests for Companion sibling artefact models."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from c2o.model.driver import (
    CompanionOption,
    FeedbackEntry,
    FeedbacksSection,
    PresetActionRef,
    PresetEntry,
    PresetFeedbackRef,
    PresetsSection,
    PresetStep,
)


def test_feedback_entry_preserves_informational_shape() -> None:
    entry = FeedbackEntry(
        id="streaming_state",
        type="boolean",
        name="Device is streaming",
        description="Change background colour based on streaming state",
        default_style={"color": 0, "bgcolor": 52224},
        options=(
            CompanionOption(
                id="stream_state",
                type="enum",
                label="State",
                default="Streaming",
                values=("Idle", "Streaming"),
            ),
        ),
        callback_condition="this.streaming === options.stream_state",
    )
    section = FeedbacksSection(feedbacks=(entry,))

    assert section.model_dump(exclude_none=True) == {
        "feedbacks": (
            {
                "id": "streaming_state",
                "type": "boolean",
                "name": "Device is streaming",
                "description": "Change background colour based on streaming state",
                "default_style": {"color": 0, "bgcolor": 52224},
                "options": (
                    {
                        "id": "stream_state",
                        "type": "enum",
                        "label": "State",
                        "default": "Streaming",
                        "values": ("Idle", "Streaming"),
                    },
                ),
                "callback_condition": "this.streaming === options.stream_state",
            },
        )
    }


def test_preset_entry_preserves_steps_and_feedback_refs() -> None:
    entry = PresetEntry(
        id="Start",
        type="button",
        category="Streaming",
        name="Start Stream",
        style={"text": "Start Stream", "size": "auto", "bgcolor": 0, "color": 16777215},
        steps=(
            PresetStep(
                down=(PresetActionRef(action_id="stream", options={"stream_control": "Start"}),),
            ),
        ),
        feedbacks=(
            PresetFeedbackRef(
                feedback_id="streaming_state",
                options={"stream_state": "Idle"},
                style={"bgcolor": 0, "color": 16777215},
            ),
        ),
    )
    section = PresetsSection(presets=(entry,))

    assert section.presets[0].steps[0].down[0].action_id == "stream"
    assert section.presets[0].feedbacks[0].feedback_id == "streaming_state"


def test_sibling_models_are_frozen() -> None:
    entry = FeedbackEntry(id="mute_on", type="boolean", name="Mute is on")

    with pytest.raises(ValidationError):
        entry.name = "Changed"


def test_preset_action_ref_requires_non_empty_action_id() -> None:
    invalid_action_id: Any = ""

    with pytest.raises(ValidationError):
        PresetActionRef(action_id=invalid_action_id)
