"""Companion color literal decoding helpers."""

from __future__ import annotations

from tree_sitter import Node

from c2o.parse.js import node_text


def decode_color_number(node: Node, source: str) -> int | None:
    """Decode a Companion color value to a packed RGB integer."""
    if node.type == "number":
        return _decode_int_literal(node_text(node, source))
    if node.type != "call_expression":
        return None

    function = node.child_by_field_name("function")
    args = node.child_by_field_name("arguments")
    if function is None or args is None or node_text(function, source) != "combineRgb":
        return None

    channels = [_decode_int_literal(node_text(child, source)) for child in args.named_children]
    if len(channels) != 3 or any(channel is None for channel in channels):
        return None
    red, green, blue = channels
    if red is None or green is None or blue is None:
        return None
    if not all(0 <= channel <= 255 for channel in (red, green, blue)):
        return None
    return (red << 16) | (green << 8) | blue


def _decode_int_literal(raw: str) -> int | None:
    try:
        return int(raw.strip(), 0)
    except ValueError:
        return None
