"""Unit tests for static JavaScript literal decoding."""

from __future__ import annotations

from pathlib import Path

from c2o.parse.js import parse_source
from c2o.parse.literals import UNRESOLVED, decode_js_value, decode_object


def _decode_expr(source: str) -> object:
    tree = parse_source(source)
    stmt = tree.root_node.named_children[0]
    expr = stmt.named_children[0] if stmt.type == "expression_statement" else stmt
    return decode_js_value(expr, source)


def _decode_object_expr(source: str) -> object:
    tree = parse_source(source)
    stmt = tree.root_node.named_children[0]
    obj = stmt.named_children[0] if stmt.type == "expression_statement" else stmt
    return decode_object(obj, source)


def test_decode_string_literal() -> None:
    assert _decode_expr("'hello'") == "hello"


def test_decode_number_literals() -> None:
    assert _decode_expr("42") == 42
    assert _decode_expr("3.14") == 3.14


def test_decode_boolean_and_null_literals() -> None:
    assert _decode_expr("true") is True
    assert _decode_expr("false") is False
    assert _decode_expr("null") is None


def test_decode_negative_number() -> None:
    assert _decode_expr("-5") == -5
    assert _decode_expr("-1.5") == -1.5


def test_decode_nested_object_and_array() -> None:
    source = "{ a: 1, b: ['x', true], c: { d: 2 } }"
    result = _decode_object_expr(source)
    assert result == {"a": 1, "b": ["x", True], "c": {"d": 2}}


def test_decode_regex_member_expression() -> None:
    assert _decode_expr("Regex.IP") == "Regex.IP"
    assert _decode_expr("Regex.Port") == "Regex.Port"
    assert _decode_expr("Regex.Number") == "Regex.Number"


def test_decode_unknown_member_expression_returns_unresolved() -> None:
    assert _decode_expr("SomeOther.Thing") is UNRESOLVED


def test_decode_object_with_unresolved_value_returns_unresolved() -> None:
    source = "{ id: 'host', regex: SomeOther.Thing }"
    assert _decode_object_expr(source) is UNRESOLVED


def test_decode_object_via_pair_key(tmp_path: Path) -> None:
    del tmp_path
    source = "{ type: 'textinput', id: 'host' }"
    assert _decode_object_expr(source) == {"type": "textinput", "id": "host"}
