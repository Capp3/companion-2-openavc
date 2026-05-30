"""Discover setInterval polling handler bodies in Companion module sources."""

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from c2o.parse.event_handlers import callback_body_node
from c2o.parse.js import ParsedModule, find_calls, find_method_definitions, node_text
from c2o.parse.literals import decode_number
from c2o.parse.send_template import body_contains_send_call


@dataclass(frozen=True)
class PollingHandler:
    """A resolved polling callback body and its setInterval delay expression."""

    rel_path: str
    callback_body: Node
    source: str
    delay_ms_node: Node | None
    start_byte: int


def find_polling_handlers(parsed: ParsedModule) -> list[PollingHandler]:
    """Find setInterval callbacks whose bodies contain static send calls."""
    handlers: list[PollingHandler] = []
    for match in find_calls(parsed, "setInterval", include_methods=False):
        if match.args_node is None or match.args_node.named_child_count < 2:
            continue
        source = parsed.sources[match.rel_path]
        callback = match.args_node.named_children[0]
        delay_node = match.args_node.named_children[1]
        body = _resolve_setinterval_callback(callback, parsed, source)
        if body is None:
            continue
        if not body_contains_send_call(body, source):
            continue
        handlers.append(
            PollingHandler(
                rel_path=match.rel_path,
                callback_body=body,
                source=source,
                delay_ms_node=delay_node,
                start_byte=match.node.start_byte,
            )
        )
    handlers.sort(key=lambda handler: (handler.rel_path, handler.start_byte))
    return handlers


def infer_poll_interval_seconds(delay_node: Node | None, source: str) -> int | None:
    """Infer poll cadence in seconds from a setInterval delay expression."""
    if delay_node is None:
        return None
    if _contains_poll_interval_reference(delay_node, source):
        return None
    if delay_node.type != "number":
        return None
    try:
        milliseconds = decode_number(node_text(delay_node, source))
    except ValueError:
        return None
    if not isinstance(milliseconds, int | float):
        return None
    ms_int = int(milliseconds)
    if ms_int <= 0 or ms_int % 1000 != 0:
        return None
    return ms_int // 1000


def _resolve_setinterval_callback(
    callback: Node,
    parsed: ParsedModule,
    source: str,
) -> Node | None:
    inline_body = callback_body_node(callback)
    if inline_body is not None:
        return inline_body
    return _resolve_bound_method_body(callback, parsed, source)


def _resolve_bound_method_body(
    callback: Node,
    parsed: ParsedModule,
    source: str,
) -> Node | None:
    if callback.type != "call_expression":
        return None
    function = callback.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return None
    bind_prop = function.child_by_field_name("property")
    method_member = function.child_by_field_name("object")
    if bind_prop is None or node_text(bind_prop, source) != "bind":
        return None
    if method_member is None or method_member.type != "member_expression":
        return None
    this_obj = method_member.child_by_field_name("object")
    method_prop = method_member.child_by_field_name("property")
    if this_obj is None or method_prop is None or this_obj.type != "this":
        return None
    if not _bind_receiver_is_this(callback, source):
        return None
    method_name = node_text(method_prop, source)
    for method in find_method_definitions(parsed, method_name):
        if method.body is not None:
            return method.body
    return None


def _bind_receiver_is_this(callback: Node, source: str) -> bool:
    arguments = callback.child_by_field_name("arguments")
    if arguments is None or not arguments.named_children:
        return False
    receiver = arguments.named_children[0]
    return receiver.type == "this"


def _contains_poll_interval_reference(node: Node, source: str) -> bool:
    for child in _iter_nodes(node):
        if child.type == "identifier" and node_text(child, source) == "poll_interval":
            return True
        if child.type == "property_identifier" and node_text(child, source) == "poll_interval":
            return True
    return False


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes
