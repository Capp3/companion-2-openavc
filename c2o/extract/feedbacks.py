"""Extract Companion feedback definitions for sibling artefacts."""

from __future__ import annotations

from typing import Any

from tree_sitter import Node

from c2o.extract.param_schema import extract_static_choice_values, infer_option_type
from c2o.extract.sibling_helpers import (
    collect_definition_objects,
    decode_style,
    expression_arrow_body,
    object_field,
    string_field,
)
from c2o.model.driver import CompanionOption, FeedbackEntry, FeedbacksSection
from c2o.model.review import ReviewReport
from c2o.parse.js import ParsedModule
from c2o.parse.literals import UNRESOLVED, decode_js_value


class FeedbacksExtractionError(ValueError):
    """Raised when feedback extraction encounters unrecoverable input."""


def extract_feedbacks(parsed: ParsedModule) -> tuple[FeedbacksSection, ReviewReport]:
    """Build informational feedback sibling entries from setFeedbackDefinitions()."""
    entries: list[FeedbackEntry] = []
    for feedback_id, object_node, source in collect_definition_objects(
        parsed,
        "setFeedbackDefinitions",
    ):
        entry = _decode_feedback(feedback_id, object_node, source)
        if entry is not None:
            entries.append(entry)
    return FeedbacksSection(feedbacks=tuple(entries)), ReviewReport()


def _decode_feedback(feedback_id: str, node: Node, source: str) -> FeedbackEntry | None:
    feedback_type = string_field(node, source, "type")
    name = string_field(node, source, "name")
    if feedback_type is None or name is None:
        return None

    return FeedbackEntry(
        id=feedback_id,
        type=feedback_type,
        name=name,
        description=string_field(node, source, "description"),
        default_style=decode_style(object_field(node, source, "defaultStyle"), source),
        options=tuple(_decode_options(object_field(node, source, "options"), source)),
        callback_condition=expression_arrow_body(object_field(node, source, "callback"), source),
    )


def _decode_options(node: Node | None, source: str) -> list[CompanionOption]:
    if node is None or node.type != "array":
        return []

    options: list[CompanionOption] = []
    for child in node.named_children:
        if child.type != "object":
            continue
        decoded = decode_js_value(child, source)
        if not isinstance(decoded, dict):
            continue
        option = _option_from_dict(decoded)
        if option is not None:
            options.append(option)
    return options


def _option_from_dict(field: dict[str, Any]) -> CompanionOption | None:
    option_id = field.get("id")
    if not isinstance(option_id, str) or not option_id:
        return None
    inferred_type, _, _ = infer_option_type(field)
    companion_type = field.get("type")
    option_type = inferred_type or (
        companion_type if isinstance(companion_type, str) else "unknown"
    )
    label = field.get("label")
    values = extract_static_choice_values(field.get("choices"))
    return CompanionOption(
        id=option_id,
        type=option_type,
        label=label if isinstance(label, str) else None,
        default=decoded_field_from_dict(field, "default"),
        values=values,
    )


def decoded_field_from_dict(field: dict[str, Any], key: str) -> Any:
    value = field.get(key)
    return None if value is UNRESOLVED else value
