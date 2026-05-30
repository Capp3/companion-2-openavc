"""Discover socket event handler callbacks in Companion module sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tree_sitter import Node

from c2o.parse.js import ParsedModule, find_calls, node_text

SocketEvent = Literal["data", "receiveline"]


@dataclass(frozen=True)
class EventHandler:
    """A ``.on('data'|'receiveline', callback)`` handler body."""

    rel_path: str
    event: SocketEvent
    callback_body: Node
    source: str


def find_socket_event_handlers(parsed: ParsedModule) -> list[EventHandler]:
    """Find ``.on('data'|'receiveline', …)`` callback bodies in a parsed module."""
    handlers: list[EventHandler] = []
    for match in find_calls(parsed, "on", include_methods=True):
        source = parsed.sources[match.rel_path]
        call_node = match.node
        function = call_node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            continue
        prop = function.child_by_field_name("property")
        if prop is None or node_text(prop, source) != "on":
            continue
        if match.args_node is None or match.args_node.named_child_count < 2:
            continue
        event_name = string_literal_value(match.args_node.named_children[0], source)
        if event_name not in {"data", "receiveline"}:
            continue
        callback_body = callback_body_node(match.args_node.named_children[1])
        if callback_body is None:
            continue
        handlers.append(
            EventHandler(
                rel_path=match.rel_path,
                event=event_name,  # type: ignore[arg-type]
                callback_body=callback_body,
                source=source,
            )
        )
    return handlers


_SOCKET_API_METHODS = frozenset(
    {
        "setVariableValues",
        "updateActions",
        "updateVariables",
        "updateFeedbacks",
        "updatePresets",
        "send",
        "emit",
        "on",
        "off",
        "bind",
        "log",
        "checkFeedbacks",
    }
)


def delegated_line_methods(handler: EventHandler) -> list[str]:
    """Return ``this.<method>(…)`` names invoked from a handler body."""
    names: list[str] = []
    for node in _iter_nodes(handler.callback_body):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            continue
        obj = function.child_by_field_name("object")
        prop = function.child_by_field_name("property")
        if obj is None or prop is None:
            continue
        if node_text(obj, handler.source) != "this":
            continue
        method_name = node_text(prop, handler.source)
        if method_name in _SOCKET_API_METHODS:
            continue
        if method_name not in names:
            names.append(method_name)
    return names


def callback_body_node(callback: Node) -> Node | None:
    """Extract the statement block from an arrow/function callback."""
    if callback.type == "arrow_function":
        body = callback.child_by_field_name("body")
        if body is not None and body.type == "statement_block":
            return body
        return None
    if callback.type == "function_expression":
        return callback.child_by_field_name("body")
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


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes
