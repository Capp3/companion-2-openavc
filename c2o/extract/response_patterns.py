"""Helpers for synthesizing OpenAVC response entries from JS receive patterns."""

from __future__ import annotations

import re
from enum import StrEnum

from tree_sitter import Node

from c2o.model.driver import ResponseEntry, ResponseMappingEntry
from c2o.parse.js import node_text

_BOOLEAN_METHODS = frozenset({"includes", "startsWith", "endsWith", "test"})
_STRING_METHODS = frozenset(
    {
        "slice",
        "substr",
        "substring",
        "trim",
        "toString",
        "toLowerCase",
        "toUpperCase",
    }
)


class ResponseValueKind(StrEnum):
    """Classification of setVariableValues RHS expressions for response emission."""

    PASSTHROUGH = "passthrough"
    INTEGER = "integer"
    NUMBER = "number"
    REJECTED = "rejected"


def anchor_pattern(pattern: str) -> str:
    """Ensure a regex pattern is anchored for full-line matching."""
    result = pattern
    if not result.startswith("^"):
        result = f"^{result}"
    if not result.endswith("$"):
        result = f"{result}$"
    return result


def fan_out_match(device_key: str) -> str:
    """Build a per-line key/value response pattern for aggregating handlers."""
    return f"^{re.escape(device_key)}:\\s*(.+)$"


def compile_check(match: str) -> bool:
    """Return True when ``match`` is a valid Python regex."""
    try:
        re.compile(match)
    except re.error:
        return False
    return True


def build_prefix_capture_entry(prefix: str, state_var: str) -> ResponseEntry | None:
    """Synthesize ``^PREFIX=(.+)$`` shorthand for startsWith + slice patterns."""
    if not prefix.endswith("="):
        prefix = f"{prefix}="
    match = anchor_pattern(f"{re.escape(prefix)}(.+)")
    if not compile_check(match):
        return None
    return ResponseEntry(match=match, set={state_var: "$1"})


def build_boolean_map_entry(prefix: str, state_var: str) -> ResponseEntry | None:
    """Synthesize ON/OFF boolean map for startsWith + includes('ON') patterns."""
    if not prefix.endswith("="):
        prefix = f"{prefix}="
    match = anchor_pattern(f"{re.escape(prefix)}(ON|OFF)")
    if not compile_check(match):
        return None
    return ResponseEntry(
        match=match,
        mappings=(
            ResponseMappingEntry(
                group=1,
                state=state_var,
                map={"ON": True, "OFF": False},
            ),
        ),
    )


def build_fan_out_entry(device_key: str, state_var: str) -> ResponseEntry | None:
    """Build a fan-out response entry for a device key → state var mapping."""
    match = fan_out_match(device_key)
    if not compile_check(match):
        return None
    return ResponseEntry(match=match, set={state_var: "$1"})


def build_entry(
    pattern: str,
    state_var: str,
    value_node: Node,
    source: str,
    *,
    group: int = 1,
) -> ResponseEntry | None:
    """Build a response entry from a regex pattern and RHS value expression."""
    match = anchor_pattern(pattern)
    if not compile_check(match):
        return None

    kind = classify_response_value(value_node, source)
    if kind == ResponseValueKind.REJECTED:
        return None
    if kind == ResponseValueKind.INTEGER:
        return ResponseEntry(
            match=match,
            mappings=(ResponseMappingEntry(group=group, state=state_var, type="integer"),),
        )
    if kind == ResponseValueKind.NUMBER:
        return ResponseEntry(
            match=match,
            mappings=(ResponseMappingEntry(group=group, state=state_var, type="number"),),
        )
    return ResponseEntry(match=match, set={state_var: f"${group}"})


def classify_response_value(node: Node, source: str) -> ResponseValueKind:
    """Classify a setVariableValues value for shorthand vs verbose emission."""
    if is_rejected_value(node, source):
        return ResponseValueKind.REJECTED
    if node.type == "call_expression":
        call_kind = _classify_call_shape(node, source)
        if call_kind is not None:
            return call_kind
    if node.type == "subscript_expression":
        return ResponseValueKind.PASSTHROUGH
    if node.type in {"identifier", "member_expression"}:
        if _is_data_subscript(node, source):
            return ResponseValueKind.PASSTHROUGH
    if node.type in {"string", "template_string", "number", "true", "false"}:
        return ResponseValueKind.PASSTHROUGH
    if node.type == "call_expression":
        function = node.child_by_field_name("function")
        if function is not None and function.type == "member_expression":
            prop = function.child_by_field_name("property")
            if prop is not None and node_text(prop, source) == "trim":
                return ResponseValueKind.PASSTHROUGH
    return ResponseValueKind.PASSTHROUGH


def is_rejected_value(node: Node, source: str) -> bool:
    """Return True when a value cannot be expressed as a static response mapping."""
    if node.type == "member_expression":
        obj = node.child_by_field_name("object")
        if obj is not None and obj.type == "member_expression":
            return True
    if node.type == "call_expression":
        function = node.child_by_field_name("function")
        if function is None:
            return False
        if function.type == "member_expression":
            prop = function.child_by_field_name("property")
            if prop is not None and node_text(prop, source) in {
                "substring",
                "slice",
                "split",
                "substr",
            }:
                return True
    return False


def regex_pattern_from_node(node: Node, source: str) -> str | None:
    """Extract the pattern string from a regex literal AST node."""
    if node.type == "regex":
        pattern_node = node.child_by_field_name("pattern")
        if pattern_node is None:
            return None
        return node_text(pattern_node, source)
    return None


def string_literal_value(node: Node, source: str) -> str | None:
    """Decode a string literal node, or None."""
    if node.type != "string":
        return None
    raw = node_text(node, source)
    try:
        import ast

        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw[1:-1] if len(raw) >= 2 else None
    return value if isinstance(value, str) else None


def data_subscript_key(node: Node, source: str) -> str | None:
    """Return the static key from ``data['Key']`` / ``data["Key"]``, if present."""
    if node.type != "subscript_expression":
        return None
    obj = node.child_by_field_name("object")
    index = node.child_by_field_name("index")
    if obj is None or index is None:
        return None
    if obj.type != "identifier" or node_text(obj, source) != "data":
        return None
    return string_literal_value(index, source)


def match_group_index(node: Node, source: str, match_var: str) -> int | None:
    """Return 1-based capture group index from ``match[N]``."""
    if node.type != "subscript_expression":
        return None
    obj = node.child_by_field_name("object")
    index = node.child_by_field_name("index")
    if obj is None or index is None:
        return None
    if obj.type != "identifier" or node_text(obj, source) != match_var:
        return None
    if index.type != "number":
        return None
    return int(node_text(index, source))


def _is_data_subscript(node: Node, source: str) -> bool:
    return data_subscript_key(node, source) is not None


def _classify_call_shape(node: Node, source: str) -> ResponseValueKind | None:
    function = node.child_by_field_name("function")
    if function is None:
        return None

    if function.type == "identifier":
        name = node_text(function, source)
        if name == "parseInt":
            return ResponseValueKind.INTEGER
        if name in {"parseFloat", "Number"}:
            return ResponseValueKind.NUMBER

    if function.type == "member_expression":
        prop = function.child_by_field_name("property")
        if prop is None:
            return None
        method = node_text(prop, source)
        if method in _BOOLEAN_METHODS:
            return ResponseValueKind.REJECTED
        if method in _STRING_METHODS:
            return ResponseValueKind.PASSTHROUGH

    return None
