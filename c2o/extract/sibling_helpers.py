"""Shared helpers for Companion sibling artefact extraction."""

from __future__ import annotations

from typing import Any

from tree_sitter import Node

from c2o.model.driver import CompanionStyleValue
from c2o.parse.colors import decode_color_number
from c2o.parse.cross_file import DefinitionObject, resolve_factory_call_definitions
from c2o.parse.js import (
    ParsedModule,
    collect_inline_object_pairs,
    find_calls,
    node_text,
    resolve_object_via_assignments,
)
from c2o.parse.literals import UNRESOLVED, decode_js_value, pair_key


def collect_definition_objects(
    parsed: ParsedModule,
    function_name: str,
) -> list[tuple[str, Node, str]]:
    """Return `(definition_id, object_node, source)` for a definition call."""
    definitions: list[tuple[str, Node, str]] = []
    for call in find_calls(parsed, function_name):
        if call.args_node is None:
            continue
        first_arg = next(iter(call.args_node.named_children), None)
        if first_arg is None:
            continue

        source = parsed.sources[call.rel_path]
        if first_arg.type == "object":
            definition_nodes = [
                DefinitionObject(key=key, node=node, source=source)
                for key, node in collect_inline_object_pairs(first_arg, source)
            ]
        elif first_arg.type == "call_expression":
            resolved_factory = resolve_factory_call_definitions(first_arg, parsed, source=source)
            definition_nodes = resolved_factory if resolved_factory is not None else []
        else:
            resolved_pairs = resolve_object_via_assignments(
                source=source,
                identifier_node=first_arg,
                call_node=call.node,
            )
            definition_nodes = (
                [
                    DefinitionObject(key=key, node=node, source=source)
                    for key, node in resolved_pairs
                ]
                if resolved_pairs is not None
                else []
            )
        definitions.extend(
            (definition.key, definition.node, definition.source) for definition in definition_nodes
        )
    return definitions


def object_field(node: Node, source: str, field: str) -> Node | None:
    """Return an object field value node by key."""
    if node.type != "object":
        return None
    for child in node.named_children:
        if child.type != "pair":
            continue
        if pair_key(child, source) != field:
            continue
        return child.child_by_field_name("value")
    return None


def decoded_field(node: Node, source: str, field: str) -> Any:
    """Decode one object field, returning None for missing/unresolved values."""
    value_node = object_field(node, source, field)
    if value_node is None:
        return None
    value = decode_js_value(value_node, source)
    return None if value is UNRESOLVED else value


def string_field(node: Node, source: str, field: str) -> str | None:
    value = decoded_field(node, source, field)
    return value if isinstance(value, str) and value else None


def decode_style(node: Node | None, source: str) -> dict[str, CompanionStyleValue] | None:
    """Decode a Companion `style`/`defaultStyle` object, including color calls."""
    if node is None or node.type != "object":
        return None

    style: dict[str, CompanionStyleValue] = {}
    for child in node.named_children:
        if child.type != "pair":
            continue
        key = pair_key(child, source)
        value_node = child.child_by_field_name("value")
        if key is None or value_node is None:
            continue

        color = decode_color_number(value_node, source)
        if color is not None:
            style[key] = color
            continue

        value = decode_js_value(value_node, source)
        if isinstance(value, str | int | float | bool):
            style[key] = value
    return style or None


def decode_options_object(node: Node | None, source: str) -> dict[str, Any]:
    if node is None or node.type != "object":
        return {}
    value = decode_js_value(node, source)
    return value if isinstance(value, dict) else {}


def expression_arrow_body(node: Node | None, source: str) -> str | None:
    """Return an expression-body arrow callback body, or None for block/dynamic callbacks."""
    if node is None or node.type != "arrow_function":
        return None
    body = node.child_by_field_name("body")
    if body is None or body.type == "statement_block":
        return None
    return node_text(body, source)
