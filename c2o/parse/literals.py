"""Static JavaScript literal decoding for tree-sitter AST nodes."""

from __future__ import annotations

import ast
import re
from typing import Any, Final

from tree_sitter import Node

from c2o.parse.js import node_text

UNRESOLVED: Final[object] = object()

_REGEX_HINT_NAMES = frozenset({"Regex.IP", "Regex.Port", "Regex.Number"})
_NUMERIC_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")


def decode_object(node: Node, source: str) -> dict[str, Any] | object:
    """Decode a JavaScript object literal into a Python dict, or UNRESOLVED."""
    if node.type != "object":
        return UNRESOLVED

    result: dict[str, Any] = {}
    for child in node.named_children:
        if child.type != "pair":
            continue
        key = pair_key(child, source)
        if key is None:
            return UNRESOLVED
        value_node = child.child_by_field_name("value")
        if value_node is None:
            return UNRESOLVED
        value = decode_js_value(value_node, source)
        if value is UNRESOLVED:
            return UNRESOLVED
        result[key] = value
    return result


def pair_key(pair: Node, source: str) -> str | None:
    """Extract the key from an object-literal pair node."""
    key = pair.child_by_field_name("key")
    if key is None:
        return None
    if key.type in {"property_identifier", "identifier"}:
        return node_text(key, source)
    if key.type == "string":
        value = decode_js_string(node_text(key, source))
        return value if isinstance(value, str) else None
    return None


def decode_js_value(node: Node, source: str) -> object:
    """Decode a static JavaScript value node into a Python primitive."""
    if node.type == "string":
        return decode_js_string(node_text(node, source))
    if node.type == "number":
        return decode_number(node_text(node, source))
    if node.type == "true":
        return True
    if node.type == "false":
        return False
    if node.type == "null":
        return None
    if node.type == "array":
        values: list[Any] = []
        for child in node.named_children:
            value = decode_js_value(child, source)
            if value is UNRESOLVED:
                return UNRESOLVED
            values.append(value)
        return values
    if node.type == "object":
        return decode_object(node, source)
    if node.type == "member_expression":
        text = node_text(node, source)
        return text if text in _REGEX_HINT_NAMES else UNRESOLVED
    if node.type == "unary_expression":
        return _decode_unary_expression(node, source)
    return UNRESOLVED


def decode_number(raw: str) -> int | float:
    """Decode a JavaScript numeric literal string."""
    text = raw.strip()
    if "." in text or "e" in text.lower():
        return float(text)
    return int(text)


def decode_js_string(raw: str) -> str:
    """Decode a JavaScript string literal using ast.literal_eval."""
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw[1:-1] if len(raw) >= 2 else raw
    return value if isinstance(value, str) else raw[1:-1]


def _decode_unary_expression(node: Node, source: str) -> object:
    text = node_text(node, source).strip()
    if text.startswith("-") and _NUMERIC_PATTERN.match(text):
        return decode_number(text)
    return UNRESOLVED
