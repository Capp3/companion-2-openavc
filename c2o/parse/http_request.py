"""Static HTTP request reconstruction from Companion action callbacks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from tree_sitter import Node

from c2o.model.driver import HttpMethod
from c2o.parse.js import node_text
from c2o.parse.literals import UNRESOLVED, decode_js_value, pair_key
from c2o.parse.send_template import parse_options_member, resolve_string_expression

BodyKind = Literal["json", "xml", "text"]

_HTTP_METHODS: frozenset[HttpMethod] = frozenset({"GET", "POST", "PUT", "DELETE", "PATCH"})
_CONTENT_TYPE_KEYS = {"content-type"}
_JSON_BODY = re.compile(r"^\s*[\{\[]")
_XML_BODY = re.compile(r"^\s*<(?:\?xml|[A-Za-z])")


@dataclass(frozen=True)
class ResolvedHttpRequest:
    """A statically reconstructed HTTP request."""

    method: HttpMethod
    path: str
    body: str | None = None
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None


def resolve_http_request_in_block(
    body: Node,
    source: str,
    known_param_ids: set[str],
) -> ResolvedHttpRequest | None:
    """Return the first statically resolvable ``fetch(...)`` request in source order."""
    for call in _find_fetch_calls(body, source):
        resolved = _resolve_fetch_call(
            call,
            scope=body,
            source=source,
            known_param_ids=known_param_ids,
        )
        if resolved is not None:
            return resolved
    return None


def block_contains_fetch_call(body: Node, source: str) -> bool:
    """Return True when a body subtree contains a direct ``fetch(...)`` call."""
    return bool(_find_fetch_calls(body, source))


def _resolve_fetch_call(
    call: Node,
    *,
    scope: Node,
    source: str,
    known_param_ids: set[str],
) -> ResolvedHttpRequest | None:
    args = call.child_by_field_name("arguments")
    if args is None or not args.named_children:
        return None

    url = resolve_string_expression(
        args.named_children[0],
        scope=scope,
        source=source,
        known_param_ids=known_param_ids,
    )
    if url is None:
        return None

    path, query_params = _decompose_url(url)
    init = args.named_children[1] if len(args.named_children) >= 2 else None
    init_fields = _fetch_init_fields(init, source) if init is not None else {}
    if init_fields is None:
        return None

    headers = _resolve_headers(init_fields.get("headers"), scope, source, known_param_ids)
    body_value = _resolve_body(init_fields.get("body"), scope, source, known_param_ids)
    method = _resolve_method(init_fields.get("method"), source, has_body="body" in init_fields)
    if method is None:
        return None

    if method == "GET":
        body_value = None
    elif body_value is not None and _has_content_type(headers):
        # Explicit Content-Type wins over inferred body classification.
        pass
    elif body_value is not None:
        inferred = _inferred_content_type(body_value)
        if inferred is not None:
            headers = {**(headers or {}), "Content-Type": inferred}

    return ResolvedHttpRequest(
        method=method,
        path=path,
        body=body_value,
        headers=headers or None,
        query_params=query_params or None,
    )


def _fetch_init_fields(node: Node | None, source: str) -> dict[str, Node] | None:
    if node is None:
        return {}
    if node.type != "object":
        return None

    fields: dict[str, Node] = {}
    for child in node.named_children:
        if child.type != "pair":
            continue
        key = pair_key(child, source)
        value = child.child_by_field_name("value")
        if key is None or value is None:
            return None
        fields[key] = value
    return fields


def _resolve_method(node: Node | None, source: str, *, has_body: bool) -> HttpMethod | None:
    if node is None:
        return "POST" if has_body else "GET"
    if node.type != "string":
        return None
    raw = decode_js_value(node, source)
    if not isinstance(raw, str):
        return None
    value = raw.upper()
    return value if value in _HTTP_METHODS else None


def _resolve_body(
    node: Node | None,
    scope: Node,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    if node is None:
        return None

    json_stringify = _resolve_json_stringify(node, source)
    if json_stringify is not None:
        return json_stringify

    return resolve_string_expression(
        node,
        scope=scope,
        source=source,
        known_param_ids=known_param_ids,
    )


def _resolve_headers(
    node: Node | None,
    scope: Node,
    source: str,
    known_param_ids: set[str],
) -> dict[str, str] | None:
    if node is None:
        return None
    if node.type != "object":
        return None

    headers: dict[str, str] = {}
    for child in node.named_children:
        if child.type != "pair":
            continue
        key = pair_key(child, source)
        value = child.child_by_field_name("value")
        if key is None or value is None:
            continue
        resolved = resolve_string_expression(
            value,
            scope=scope,
            source=source,
            known_param_ids=known_param_ids,
        )
        if resolved is not None:
            headers[key] = resolved
    return headers or None


def _resolve_json_stringify(node: Node, source: str) -> str | None:
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    if function is None or node_text(function, source) != "JSON.stringify":
        return None
    args = node.child_by_field_name("arguments")
    if args is None or len(args.named_children) != 1:
        return None
    value = _decode_json_body_literal(args.named_children[0], source)
    if value is None:
        return None
    return json.dumps(value)


def _decode_json_body_literal(node: Node, source: str) -> Any | None:
    if node.type == "member_expression":
        option_id = parse_options_member(node, source)
        return "{" + option_id + "}" if option_id is not None else None

    value = decode_js_value(node, source)
    if value is not UNRESOLVED:
        return value

    if node.type == "object":
        result: dict[str, Any] = {}
        for child in node.named_children:
            if child.type != "pair":
                continue
            key = pair_key(child, source)
            value_node = child.child_by_field_name("value")
            if key is None or value_node is None:
                return None
            value = _decode_json_body_literal(value_node, source)
            if value is None:
                return None
            result[key] = value
        return result

    if node.type == "array":
        values: list[Any] = []
        for child in node.named_children:
            value = _decode_json_body_literal(child, source)
            if value is None:
                return None
            values.append(value)
        return values

    return None


def _inferred_content_type(body: str) -> str | None:
    if _explicit_json_body(body):
        return None
    if _XML_BODY.match(body):
        return "text/xml"
    return None


def _has_content_type(headers: dict[str, str] | None) -> bool:
    if headers is None:
        return False
    return any(key.casefold() in _CONTENT_TYPE_KEYS for key in headers)


def _explicit_json_body(body: str) -> bool:
    return bool(_JSON_BODY.match(body))


def _decompose_url(raw_url: str) -> tuple[str, dict[str, str]]:
    parts = urlsplit(raw_url)
    path = parts.path or "/"
    query_params: dict[str, str] = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key not in query_params:
            query_params[key] = value
    return path, query_params


def _find_fetch_calls(body: Node, source: str) -> list[Node]:
    calls: list[Node] = []
    for node in _walk_nodes(body):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None:
            continue
        if function.type == "identifier" and node_text(function, source) == "fetch":
            calls.append(node)
    calls.sort(key=lambda node: node.start_byte)
    return calls


def _walk_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes
