"""Unit tests for tree-sitter query helpers."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node, QueryCursor

from c2o.parse.js import (
    ParsedModule,
    _load_query,
    extract_string_concat,
    find_calls,
    find_regex_literals,
    parse_source,
)


def _parsed(source: str) -> ParsedModule:
    return ParsedModule(
        root=Path("."),
        sources={"snippet.js": source},
        trees={"snippet.js": parse_source(source)},
    )


def _first_node_of_type(node: Node, node_type: str) -> Node:
    if node.type == node_type:
        return node
    for child in node.children:
        try:
            return _first_node_of_type(child, node_type)
        except AssertionError:
            continue
    msg = f"Could not find node type {node_type!r}"
    raise AssertionError(msg)


def test_call_expression_query_captures_direct_and_method_calls() -> None:
    source = 'cmd("HELLO"); sock.send("x");'
    tree = parse_source(source)
    query = _load_query("call_expression")

    matches = QueryCursor(query).matches(tree.root_node)

    assert len(matches) == 2
    assert "function.name" in matches[0][1]
    assert "function.member" in matches[1][1]
    assert "function.arguments" in matches[1][1]


def test_regex_literal_query_captures_pattern_and_optional_flags() -> None:
    source = r"const a = /^STATE (\d+)$/i; const b = /foo/;"
    tree = parse_source(source)
    query = _load_query("regex_literal")

    matches = QueryCursor(query).matches(tree.root_node)

    assert len(matches) == 2
    assert "regex.pattern" in matches[0][1]
    assert "regex.flags" in matches[0][1]
    assert "regex.pattern" in matches[1][1]
    assert "regex.flags" not in matches[1][1]


def test_find_calls_matches_direct_calls() -> None:
    calls = find_calls(_parsed('cmd("HELLO");'), "cmd")

    assert len(calls) == 1
    assert calls[0].rel_path == "snippet.js"
    assert calls[0].function_text == "cmd"
    assert calls[0].node.type == "call_expression"
    assert calls[0].args_node is not None


def test_find_calls_matches_method_calls_when_enabled() -> None:
    calls = find_calls(_parsed('sock.send("x");'), "send")

    assert len(calls) == 1
    assert calls[0].function_text == "sock.send"


def test_find_calls_skips_method_calls_when_disabled() -> None:
    assert find_calls(_parsed('sock.send("x");'), "send", include_methods=False) == []


def test_find_calls_returns_empty_for_absent_function() -> None:
    assert find_calls(_parsed('cmd("HELLO");'), "absent") == []


def test_extract_string_concat_collapses_literal_parts() -> None:
    source = 'const value = "a" + "b" + "c";'
    tree = parse_source(source)
    expression = _first_node_of_type(tree.root_node, "binary_expression")

    template = extract_string_concat(expression, source)

    assert template is not None
    assert template.template == "abc"
    assert template.placeholders == []


def test_extract_string_concat_converts_identifiers_to_placeholders() -> None:
    source = 'const value = "GET " + path + " HTTP/1.1";'
    tree = parse_source(source)
    expression = _first_node_of_type(tree.root_node, "binary_expression")

    template = extract_string_concat(expression, source)

    assert template is not None
    assert template.template == "GET {path} HTTP/1.1"
    assert template.placeholders == ["path"]


def test_extract_string_concat_converts_multiple_placeholders() -> None:
    source = 'const value = name + "@" + domain;'
    tree = parse_source(source)
    expression = _first_node_of_type(tree.root_node, "binary_expression")

    template = extract_string_concat(expression, source)

    assert template is not None
    assert template.template == "{name}@{domain}"
    assert template.placeholders == ["name", "domain"]


def test_extract_string_concat_returns_none_for_non_concat_root() -> None:
    source = "foo();"
    tree = parse_source(source)
    expression = _first_node_of_type(tree.root_node, "call_expression")

    assert extract_string_concat(expression, source) is None


def test_extract_string_concat_returns_none_for_complex_operands() -> None:
    source = 'const value = "x" + complex();'
    tree = parse_source(source)
    expression = _first_node_of_type(tree.root_node, "binary_expression")

    assert extract_string_concat(expression, source) is None


def test_find_regex_literals_extracts_pattern_and_flags() -> None:
    regexes = find_regex_literals(_parsed(r"const state = /^STATE (\d+)$/i;"))

    assert len(regexes) == 1
    assert regexes[0].rel_path == "snippet.js"
    assert regexes[0].pattern == r"^STATE (\d+)$"
    assert regexes[0].flags == "i"
    assert regexes[0].node.type == "regex"


def test_find_regex_literals_defaults_missing_flags_to_empty_string() -> None:
    regexes = find_regex_literals(_parsed("const value = /foo/;"))

    assert len(regexes) == 1
    assert regexes[0].pattern == "foo"
    assert regexes[0].flags == ""


def test_find_regex_literals_returns_empty_when_absent() -> None:
    assert find_regex_literals(_parsed('const value = "not a regex";')) == []
