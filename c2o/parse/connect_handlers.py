"""Discover socket connect event handler callbacks in Companion module sources."""

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from c2o.parse.event_handlers import callback_body_node, string_literal_value
from c2o.parse.js import ParsedModule, find_calls, node_text


@dataclass(frozen=True)
class ConnectHandler:
    """A ``.on('connect', callback)`` handler body."""

    rel_path: str
    callback_body: Node
    source: str
    start_byte: int


def find_socket_connect_handlers(parsed: ParsedModule) -> list[ConnectHandler]:
    """Find ``.on('connect', ...)`` callback bodies in a parsed module."""
    handlers: list[ConnectHandler] = []
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
        if event_name != "connect":
            continue
        callback_body = callback_body_node(match.args_node.named_children[1])
        if callback_body is None:
            continue
        handlers.append(
            ConnectHandler(
                rel_path=match.rel_path,
                callback_body=callback_body,
                source=source,
                start_byte=call_node.start_byte,
            )
        )

    handlers.sort(key=lambda handler: (handler.rel_path, handler.start_byte))
    return handlers
