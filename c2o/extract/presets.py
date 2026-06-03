"""Extract Companion preset definitions for sibling artefacts."""

from __future__ import annotations

from tree_sitter import Node

from c2o.extract.sibling_helpers import (
    collect_definition_objects,
    decode_options_object,
    decode_style,
    object_field,
    string_field,
)
from c2o.model.driver import (
    PresetActionRef,
    PresetEntry,
    PresetFeedbackRef,
    PresetsSection,
    PresetStep,
)
from c2o.model.review import ReviewReport
from c2o.parse.js import ParsedModule


class PresetsExtractionError(ValueError):
    """Raised when preset extraction encounters unrecoverable input."""


def extract_presets(parsed: ParsedModule) -> tuple[PresetsSection, ReviewReport]:
    """Build informational preset sibling entries from setPresetDefinitions()."""
    entries: list[PresetEntry] = []
    for preset_id, object_node, source in collect_definition_objects(
        parsed,
        "setPresetDefinitions",
    ):
        entry = _decode_preset(preset_id, object_node, source)
        if entry is not None:
            entries.append(entry)
    return PresetsSection(presets=tuple(entries)), ReviewReport()


def _decode_preset(preset_id: str, node: Node, source: str) -> PresetEntry | None:
    preset_type = string_field(node, source, "type")
    name = string_field(node, source, "name")
    if preset_type is None or name is None:
        return None

    return PresetEntry(
        id=preset_id,
        type=preset_type,
        category=string_field(node, source, "category"),
        name=name,
        style=decode_style(object_field(node, source, "style"), source),
        steps=tuple(_decode_steps(object_field(node, source, "steps"), source)),
        feedbacks=tuple(_decode_feedback_refs(object_field(node, source, "feedbacks"), source)),
    )


def _decode_steps(node: Node | None, source: str) -> list[PresetStep]:
    if node is None or node.type != "array":
        return []

    steps: list[PresetStep] = []
    for child in node.named_children:
        if child.type != "object":
            continue
        steps.append(
            PresetStep(
                down=tuple(_decode_action_refs(object_field(child, source, "down"), source)),
                up=tuple(_decode_action_refs(object_field(child, source, "up"), source)),
            )
        )
    return steps


def _decode_action_refs(node: Node | None, source: str) -> list[PresetActionRef]:
    if node is None or node.type != "array":
        return []

    refs: list[PresetActionRef] = []
    for child in node.named_children:
        if child.type != "object":
            continue
        action_id = string_field(child, source, "actionId")
        if action_id is None:
            continue
        refs.append(
            PresetActionRef(
                action_id=action_id,
                options=decode_options_object(object_field(child, source, "options"), source),
            )
        )
    return refs


def _decode_feedback_refs(node: Node | None, source: str) -> list[PresetFeedbackRef]:
    if node is None or node.type != "array":
        return []

    refs: list[PresetFeedbackRef] = []
    for child in node.named_children:
        if child.type != "object":
            continue
        feedback_id = string_field(child, source, "feedbackId")
        if feedback_id is None:
            continue
        refs.append(
            PresetFeedbackRef(
                feedback_id=feedback_id,
                options=decode_options_object(object_field(child, source, "options"), source),
                style=decode_style(object_field(child, source, "style"), source),
            )
        )
    return refs
