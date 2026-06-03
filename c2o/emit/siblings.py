"""YAML sibling artefact emission for Companion feedbacks and presets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from c2o.model.driver import (
    FeedbackEntry,
    FeedbacksSection,
    PresetActionRef,
    PresetEntry,
    PresetFeedbackRef,
    PresetsSection,
    PresetStep,
)


class _NoAliasSafeDumper(yaml.SafeDumper):  # type: ignore[misc]
    """Safe dumper that never emits anchors for repeated scalar/dict values."""

    def ignore_aliases(self, data: object) -> bool:
        return True


def feedbacks_yml_path_for_output(output: Path) -> Path:
    """Map `-o foo.avcdriver` -> `foo.companion-feedbacks.yml`."""
    if output.suffix == ".avcdriver":
        return output.with_suffix(".companion-feedbacks.yml")
    return output.parent / f"{output.name}.companion-feedbacks.yml"


def presets_yml_path_for_output(output: Path) -> Path:
    """Map `-o foo.avcdriver` -> `foo.companion-presets.yml`."""
    if output.suffix == ".avcdriver":
        return output.with_suffix(".companion-presets.yml")
    return output.parent / f"{output.name}.companion-presets.yml"


def feedbacks_payload(section: FeedbacksSection) -> list[dict[str, Any]]:
    """Build deterministic YAML payload for feedback entries."""
    return [_feedback_payload(entry) for entry in section.feedbacks]


def presets_payload(section: PresetsSection) -> list[dict[str, Any]]:
    """Build deterministic YAML payload for preset entries."""
    return [_preset_payload(entry) for entry in section.presets]


def write_feedbacks_yml(path: Path, section: FeedbacksSection) -> None:
    """Write feedback sibling YAML with stable formatting."""
    _write_yaml(path, feedbacks_payload(section))


def write_presets_yml(path: Path, section: PresetsSection) -> None:
    """Write preset sibling YAML with stable formatting."""
    _write_yaml(path, presets_payload(section))


def _feedback_payload(entry: FeedbackEntry) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": entry.id,
        "type": entry.type,
        "name": entry.name,
    }
    if entry.description is not None:
        payload["description"] = entry.description
    if entry.default_style:
        payload["default_style"] = entry.default_style
    if entry.options:
        payload["options"] = [option.model_dump(exclude_none=True) for option in entry.options]
    if entry.callback_condition is not None:
        payload["callback_condition"] = entry.callback_condition
    return payload


def _preset_payload(entry: PresetEntry) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": entry.id,
        "type": entry.type,
    }
    if entry.category is not None:
        payload["category"] = entry.category
    payload["name"] = entry.name
    if entry.style:
        payload["style"] = entry.style
    if entry.steps:
        payload["steps"] = [_step_payload(step) for step in entry.steps]
    if entry.feedbacks:
        payload["feedbacks"] = [_feedback_ref_payload(feedback) for feedback in entry.feedbacks]
    return payload


def _step_payload(step: PresetStep) -> dict[str, Any]:
    return {
        "down": [_action_ref_payload(action) for action in step.down],
        "up": [_action_ref_payload(action) for action in step.up],
    }


def _action_ref_payload(action: PresetActionRef) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "options": action.options,
    }


def _feedback_ref_payload(feedback: PresetFeedbackRef) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "feedback_id": feedback.feedback_id,
        "options": feedback.options,
    }
    if feedback.style:
        payload["style"] = feedback.style
    return payload


def _write_yaml(path: Path, payload: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(
        payload,
        Dumper=_NoAliasSafeDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )
    path.write_text(text if text.endswith("\n") else f"{text}\n", encoding="utf-8")
