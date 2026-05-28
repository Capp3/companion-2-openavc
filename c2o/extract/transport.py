"""Infer OpenAVC transport fields from parsed Companion JavaScript sources."""

from __future__ import annotations

import ast

from tree_sitter import Node

from c2o.model.driver import DriverTransport, TransportSection
from c2o.parse.js import (
    ParsedModule,
    collect_import_binding_names,
    find_calls,
    node_text,
)

_TRANSPORT_PRIORITY: tuple[tuple[str, DriverTransport], ...] = (
    ("TCPHelper", "tcp"),
    ("SerialPort", "serial"),
    ("SerialHelper", "serial"),
    ("OSC", "osc"),
)
_HTTP_HINTS = ("fetch", "axios", "got", "node-fetch")
_DELIMITER_METHODS = ("split", "indexOf", "lastIndexOf", "substr", "substring", "includes")
_DELIMITER_RECEIVERS = frozenset(
    {
        "chunk",
        "data",
        "buf",
        "buffer",
        "receivebuffer",
        "payload",
        "recv",
        "message",
        "msg",
    }
)
_DELIMITER_PRIORITY = ("\r\n", "\n", "\r")
_CALL_THROUGH_METHODS = {"toString"}


class TransportExtractionError(ValueError):
    """Raised when transport metadata cannot be inferred."""


def extract_transport(parsed: ParsedModule) -> TransportSection:
    """Infer the M6 transport fields from an eligible parsed Companion module."""
    transport = _infer_transport(parsed)
    delimiter = _infer_delimiter(parsed)
    return TransportSection(transport=transport, delimiter=delimiter)


def _infer_transport(parsed: ParsedModule) -> DriverTransport:
    bindings = _import_binding_names(parsed)
    if "UDPHelper" in bindings:
        msg = "UDP transport is not YAML-suitable and should have been declined by the gate."
        raise TransportExtractionError(msg)

    for symbol, transport in _TRANSPORT_PRIORITY:
        if symbol in bindings:
            return transport

    if any(
        hint in bindings or any(hint in source for source in parsed.sources.values())
        for hint in _HTTP_HINTS
    ):
        return "http"

    msg = "Transport could not be inferred from recognised Companion helpers or HTTP hints."
    raise TransportExtractionError(msg)


def _infer_delimiter(parsed: ParsedModule) -> str | None:
    candidates: set[str] = set()
    for method in _DELIMITER_METHODS:
        for match in find_calls(parsed, method, include_methods=True):
            source = parsed.sources[match.rel_path]
            delimiter = _delimiter_from_call(match.node, match.args_node, source)
            if delimiter is not None:
                candidates.add(delimiter)

    for delimiter in _DELIMITER_PRIORITY:
        if delimiter in candidates:
            return None if delimiter == "\r" else delimiter
    return None


def _import_binding_names(parsed: ParsedModule) -> set[str]:
    names: set[str] = set()
    for rel_path, tree in parsed.trees.items():
        names.update(collect_import_binding_names(tree, parsed.sources[rel_path]))
    return names


def _delimiter_from_call(call: Node, args: Node | None, source: str) -> str | None:
    if args is None:
        return None
    receiver = _call_receiver_name(call, source)
    if receiver is None or receiver.casefold() not in _DELIMITER_RECEIVERS:
        return None

    first_arg = next((child for child in args.named_children if child.type == "string"), None)
    if first_arg is None:
        return None
    value = _decode_js_string(node_text(first_arg, source))
    return value if value in _DELIMITER_PRIORITY else None


def _call_receiver_name(call: Node, source: str) -> str | None:
    function = call.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return None
    receiver = function.child_by_field_name("object")
    if receiver is None:
        return None
    return _receiver_name(receiver, source)


def _receiver_name(node: Node, source: str) -> str | None:
    if node.type == "identifier":
        return node_text(node, source)
    if node.type == "member_expression":
        prop = node.child_by_field_name("property")
        if prop is not None:
            return node_text(prop, source)
        obj = node.child_by_field_name("object")
        return _receiver_name(obj, source) if obj is not None else None
    if node.type == "call_expression":
        function = node.child_by_field_name("function")
        if function is not None and function.type == "member_expression":
            prop = function.child_by_field_name("property")
            if prop is not None and node_text(prop, source) in _CALL_THROUGH_METHODS:
                obj = function.child_by_field_name("object")
                return _receiver_name(obj, source) if obj is not None else None
        return None
    return None


def _decode_js_string(raw: str) -> str:
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw[1:-1] if len(raw) >= 2 else raw
    return value if isinstance(value, str) else raw[1:-1]
