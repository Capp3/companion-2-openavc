"""Unit tests for Companion color decoding."""

from __future__ import annotations

from tree_sitter import Node

from c2o.parse.colors import decode_color_number
from c2o.parse.js import node_text, parse_source


def _node_for(source: str, wanted: str) -> Node:
    tree = parse_source(source)
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node_text(node, source) == wanted:
            return node
        stack.extend(reversed(node.named_children))
    msg = f"Could not find node text {wanted!r}"
    raise AssertionError(msg)


def test_decode_hex_color_literal() -> None:
    source = "const style = { bgcolor: 0xff0000 }"
    node = _node_for(source, "0xff0000")

    assert decode_color_number(node, source) == 16711680


def test_decode_decimal_color_literal() -> None:
    source = "const style = { color: 16777215 }"
    node = _node_for(source, "16777215")

    assert decode_color_number(node, source) == 16777215


def test_decode_combine_rgb_call() -> None:
    source = "const style = { bgcolor: combineRgb(0, 204, 0) }"
    node = _node_for(source, "combineRgb(0, 204, 0)")

    assert decode_color_number(node, source) == 52224


def test_decode_dynamic_color_returns_none() -> None:
    source = "const style = { bgcolor: combineRgb(red, 204, 0) }"
    node = _node_for(source, "combineRgb(red, 204, 0)")

    assert decode_color_number(node, source) is None
