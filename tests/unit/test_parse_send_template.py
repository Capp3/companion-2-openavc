"""Unit tests for send template reconstruction."""

from __future__ import annotations

from tree_sitter import Node

from c2o.parse.js import parse_source
from c2o.parse.send_template import (
    normalize_placeholder,
    resolve_send_in_block,
    snake_lower,
)


def _body(source: str) -> Node | None:
    tree = parse_source(source)
    function = tree.root_node.named_children[0]
    return function.child_by_field_name("body")


def test_snake_lower_normalizes_branch_ids() -> None:
    assert snake_lower("Start") == "start"
    assert snake_lower("Factory Reset") == "factory_reset"


def test_normalize_placeholder_strips_event_options_prefix() -> None:
    assert normalize_placeholder("event.options.input", {"input"}) == "{input}"
    assert normalize_placeholder("action.options.mode", {"mode"}) == "{mode}"
    assert normalize_placeholder("options.stream_control", {"stream_control"}) == "{stream_control}"


def test_resolve_send_in_block_handles_literal_send() -> None:
    source = "function f() { this.socket.send('STREAM START\\n') }"
    body = _body(source)
    assert body is not None
    assert resolve_send_in_block(body, source, set()) == "STREAM START\n"


def test_resolve_send_in_block_handles_template_and_trace() -> None:
    source = (
        "function f() { const cmd = `SET INPUT ${event.options.input}\\n`; this.socket.send(cmd) }"
    )
    body = _body(source)
    assert body is not None
    assert resolve_send_in_block(body, source, {"input"}) == "SET INPUT {input}\n"


def test_resolve_send_in_block_handles_prefix_options_suffix() -> None:
    source = (
        "function f() { var cmd = 'STREAM STATE:\\nAction: '; "
        "cmd = cmd + options.stream_control + '\\n\\n'; this.sendCommand(cmd) }"
    )
    body = _body(source)
    assert body is not None
    assert resolve_send_in_block(body, source, {"stream_control"}) == (
        "STREAM STATE:\nAction: {stream_control}\n\n"
    )


def test_resolve_send_in_block_rejects_parse_variables() -> None:
    source = (
        "function f() { const key = await context.parseVariablesInString(action.options.key); "
        "this.sendCommand(key) }"
    )
    body = _body(source)
    assert body is not None
    assert resolve_send_in_block(body, source, {"key"}) is None
