"""Unit tests for static HTTP request reconstruction."""

from __future__ import annotations

from tree_sitter import Node

from c2o.parse.http_request import (
    block_contains_fetch_call,
    resolve_http_request_in_block,
)
from c2o.parse.js import parse_source


def test_resolves_fetch_get_with_query_placeholder() -> None:
    body, source = _callback_body("fetch('/api/status?include=' + options.include)")

    request = resolve_http_request_in_block(body, source, {"include"})

    assert request is not None
    assert request.method == "GET"
    assert request.path == "/api/status"
    assert request.query_params == {"include": "{include}"}
    assert request.body is None
    assert request.headers is None


def test_resolves_fetch_template_path_placeholder() -> None:
    body, source = _callback_body("fetch(`/api/devices/${options.id}/status`)")

    request = resolve_http_request_in_block(body, source, {"id"})

    assert request is not None
    assert request.method == "GET"
    assert request.path == "/api/devices/{id}/status"
    assert request.query_params is None


def test_strips_url_scheme_and_host() -> None:
    body, source = _callback_body("fetch('https://api.example.com/v1/status?k=v#ignored')")

    request = resolve_http_request_in_block(body, source, set())

    assert request is not None
    assert request.path == "/v1/status"
    assert request.query_params == {"k": "v"}


def test_resolves_fetch_post_json_stringify_body_without_content_type() -> None:
    body, source = _callback_body(
        "fetch('/api/event', { method: 'POST', body: JSON.stringify({ name: options.name }) })"
    )

    request = resolve_http_request_in_block(body, source, {"name"})

    assert request is not None
    assert request.method == "POST"
    assert request.path == "/api/event"
    assert request.body == '{"name": "{name}"}'
    assert request.headers is None


def test_resolves_fetch_post_xml_body_with_inferred_content_type() -> None:
    body, source = _callback_body(
        "fetch('/api/payload', { method: 'POST', body: '<msg>' + options.value + '</msg>' })"
    )

    request = resolve_http_request_in_block(body, source, {"value"})

    assert request is not None
    assert request.body == "<msg>{value}</msg>"
    assert request.headers == {"Content-Type": "text/xml"}


def test_explicit_content_type_header_wins() -> None:
    body, source = _callback_body(
        "fetch('/api/payload', {"
        " method: 'POST',"
        " body: '<msg>' + options.value + '</msg>',"
        " headers: { 'Content-Type': 'application/custom+xml' }"
        "})"
    )

    request = resolve_http_request_in_block(body, source, {"value"})

    assert request is not None
    assert request.headers == {"Content-Type": "application/custom+xml"}


def test_body_failure_still_emits_url_and_method() -> None:
    body, source = _callback_body(
        "fetch('/api/event', { method: 'POST', body: buildPayload(options.name) })"
    )

    request = resolve_http_request_in_block(body, source, {"name"})

    assert request is not None
    assert request.method == "POST"
    assert request.path == "/api/event"
    assert request.body is None


def test_get_omits_body_even_when_source_sets_body() -> None:
    body, source = _callback_body("fetch('/api/status', { method: 'GET', body: '<ignored />' })")

    request = resolve_http_request_in_block(body, source, set())

    assert request is not None
    assert request.method == "GET"
    assert request.body is None
    assert request.headers is None


def test_first_static_fetch_wins_over_later_fetches() -> None:
    body, source = _callback_body("fetch('/api/first?x=1')\nfetch('/api/second?x=2')")

    request = resolve_http_request_in_block(body, source, set())

    assert request is not None
    assert request.path == "/api/first"
    assert request.query_params == {"x": "1"}


def test_dynamic_url_returns_none() -> None:
    body, source = _callback_body("fetch(`${this.api}/status`)")

    assert resolve_http_request_in_block(body, source, set()) is None


def test_fetch_presence_detection() -> None:
    body, source = _callback_body("fetch('/api/status')")

    assert block_contains_fetch_call(body, source) is True


def _callback_body(statement_source: str) -> tuple[Node, str]:
    source = f"const cb = async (event) => {{\n{statement_source}\n}}\n"
    tree = parse_source(source)
    for node in _walk_nodes(tree.root_node):
        if node.type == "arrow_function":
            body = node.child_by_field_name("body")
            if body is not None:
                return body, source
    raise AssertionError("test source did not contain an arrow function body")


def _walk_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes
