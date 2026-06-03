"""Unit tests for Companion sibling YAML emission."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from c2o.emit.siblings import (
    feedbacks_yml_path_for_output,
    presets_yml_path_for_output,
    write_feedbacks_yml,
    write_presets_yml,
)
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


def test_sibling_paths_for_avcdriver_output() -> None:
    output = Path("drivers/foo.avcdriver")

    assert feedbacks_yml_path_for_output(output) == Path("drivers/foo.companion-feedbacks.yml")
    assert presets_yml_path_for_output(output) == Path("drivers/foo.companion-presets.yml")


def test_sibling_paths_for_non_avcdriver_output() -> None:
    output = Path("drivers/foo")

    assert feedbacks_yml_path_for_output(output) == Path("drivers/foo.companion-feedbacks.yml")
    assert presets_yml_path_for_output(output) == Path("drivers/foo.companion-presets.yml")


def test_write_feedbacks_yml_uses_stable_payload(tmp_path: Path) -> None:
    section = FeedbacksSection(
        feedbacks=(
            FeedbackEntry(
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
            ),
        )
    )
    path = tmp_path / "out.companion-feedbacks.yml"

    write_feedbacks_yml(path, section)

    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert yaml.safe_load(text) == [
        {
            "id": "streaming_state",
            "type": "boolean",
            "name": "Device is streaming",
            "description": "Change background colour based on streaming state",
            "default_style": {"color": 0, "bgcolor": 52224},
            "options": [
                {
                    "id": "stream_state",
                    "type": "enum",
                    "label": "State",
                    "default": "Streaming",
                    "values": ["Idle", "Streaming"],
                }
            ],
            "callback_condition": "this.streaming === options.stream_state",
        }
    ]


def test_write_presets_yml_uses_stable_payload(tmp_path: Path) -> None:
    section = PresetsSection(
        presets=(
            PresetEntry(
                id="Start",
                type="button",
                category="Streaming",
                name="Start Stream",
                style={"text": "Start Stream", "size": "auto", "bgcolor": 0, "color": 16777215},
                steps=(
                    PresetStep(
                        down=(
                            PresetActionRef(
                                action_id="stream",
                                options={"stream_control": "Start"},
                            ),
                        ),
                    ),
                ),
                feedbacks=(
                    PresetFeedbackRef(
                        feedback_id="streaming_state",
                        options={"stream_state": "Idle"},
                        style={"bgcolor": 0, "color": 16777215},
                    ),
                ),
            ),
        )
    )
    path = tmp_path / "out.companion-presets.yml"

    write_presets_yml(path, section)

    assert yaml.safe_load(path.read_text(encoding="utf-8")) == [
        {
            "id": "Start",
            "type": "button",
            "category": "Streaming",
            "name": "Start Stream",
            "style": {
                "text": "Start Stream",
                "size": "auto",
                "bgcolor": 0,
                "color": 16777215,
            },
            "steps": [
                {
                    "down": [
                        {
                            "action_id": "stream",
                            "options": {"stream_control": "Start"},
                        }
                    ],
                    "up": [],
                }
            ],
            "feedbacks": [
                {
                    "feedback_id": "streaming_state",
                    "options": {"stream_state": "Idle"},
                    "style": {"bgcolor": 0, "color": 16777215},
                }
            ],
        }
    ]
