"""Unit tests for setInterval polling handler discovery."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from c2o.parse.js import node_text, parse_module, parse_source
from c2o.parse.polling_handlers import (
    find_polling_handlers,
    infer_poll_interval_seconds,
)


def _setinterval_delay_node(source: str) -> Node:
    tree = parse_source(source)
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "call_expression":
            function = node.child_by_field_name("function")
            if function is not None and node_text(function, source) == "setInterval":
                arguments = node.child_by_field_name("arguments")
                assert arguments is not None
                return arguments.named_children[1]
        stack.extend(reversed(node.children))
    msg = "setInterval call not found"
    raise AssertionError(msg)


def test_infer_poll_interval_seconds_from_literal_ms() -> None:
    source = "function f() { setInterval(() => {}, 1000) }"
    delay = _setinterval_delay_node(source)

    assert infer_poll_interval_seconds(delay, source) == 1


def test_infer_poll_interval_seconds_defers_config_expression() -> None:
    source = "function f() { setInterval(() => {}, (config.poll_interval || 5) * 1000) }"
    delay = _setinterval_delay_node(source)

    assert infer_poll_interval_seconds(delay, source) is None


def test_find_polling_handlers_inline_callback(dummy_device: Path) -> None:
    handlers = find_polling_handlers(parse_module(dummy_device))

    assert len(handlers) == 1
    assert handlers[0].delay_ms_node is not None


def test_find_polling_handlers_bound_method(bmd_webpresenter: Path) -> None:
    handlers = find_polling_handlers(parse_module(bmd_webpresenter))

    assert len(handlers) == 1


def test_find_polling_handlers_empty_when_no_sends(unknown_vendor: Path) -> None:
    handlers = find_polling_handlers(parse_module(unknown_vendor))

    assert handlers == []
