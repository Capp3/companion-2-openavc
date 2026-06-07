"""Static decoding for Companion storeData/checkVariables response pipelines."""

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from c2o.parse.cross_file import resolve_single_function
from c2o.parse.js import ParsedModule, find_method_definitions, node_text
from c2o.parse.literals import decode_js_string, pair_key


@dataclass(frozen=True)
class ConstantValue:
    """A literal value assigned to ``this.data.X``."""

    value: str


@dataclass(frozen=True)
class CapturedField:
    """A direct capture from a colon-split ``str[N]`` field."""

    position: int
    is_integer: bool = False


@dataclass(frozen=True)
class SuffixCapture:
    """A suffix capture from ``str[0].substring(N)`` after a prefix guard."""

    prefix: str
    prefix_len: int


@dataclass(frozen=True)
class TransformedValue:
    """A runtime transform that cannot be emitted as a static response."""

    description: str


ValueSpec = ConstantValue | CapturedField | SuffixCapture | TransformedValue


@dataclass(frozen=True)
class StoreDataTriple:
    """One token -> ``this.data`` field -> value mapping decoded from storeData."""

    token: str
    field: str
    value: ValueSpec
    is_prefix_match: bool = False


def find_check_variables_sink_map(parsed: ParsedModule) -> dict[str, str | None]:
    """Build a ``this.data`` field -> variable id map from ``checkVariables``.

    The returned values are variable IDs. ``None`` means the variable is present
    but its RHS is a computed expression that cannot be traced to a direct
    ``self.data.X``/``this.data.X`` sink.
    """
    resolved = resolve_single_function(parsed, "checkVariables")
    if resolved is None:
        return {}

    sinks: dict[str, str | None] = {}
    for call in _iter_nodes(resolved.body):
        if call.type != "call_expression":
            continue
        if _call_property(call, resolved.source) != "setVariableValues":
            continue
        args = call.child_by_field_name("arguments")
        if args is None or not args.named_children:
            continue
        obj = args.named_children[0]
        if obj.type != "object":
            continue
        for pair in obj.named_children:
            if pair.type != "pair":
                continue
            variable_id = pair_key(pair, resolved.source)
            value = pair.child_by_field_name("value")
            if variable_id is None or value is None:
                continue
            field = _data_member_field(value, resolved.source)
            if field is not None:
                sinks[field] = variable_id
                continue
            if _is_instance_member(value, resolved.source):
                continue
            sinks[variable_id] = None
    return sinks


def decode_store_data(parsed: ParsedModule) -> list[StoreDataTriple]:
    """Decode supported ``storeData(str)`` token mappings."""
    triples: list[StoreDataTriple] = []
    for method in find_method_definitions(parsed, "storeData"):
        if method.body is None:
            continue
        source = parsed.sources[method.rel_path]
        for switch in _iter_nodes(method.body):
            if switch.type == "switch_statement":
                triples.extend(_decode_switch(switch, source))
        triples.extend(_decode_prefix_guards(method.body, source))
    return _dedupe_triples(triples)


def _decode_switch(switch: Node, source: str) -> list[StoreDataTriple]:
    triples: list[StoreDataTriple] = []
    for case in _iter_nodes(switch):
        if case.type != "switch_case":
            continue
        case_token = _case_token(case, source)
        if case_token is None:
            continue
        triples.extend(_decode_case_nodes(case.named_children[1:], source, [case_token]))
    return triples


def _decode_case_nodes(
    nodes: list[Node],
    source: str,
    token_parts: list[str],
) -> list[StoreDataTriple]:
    triples: list[StoreDataTriple] = []
    for node in nodes:
        assign = _assignment_node(node)
        if assign is not None:
            triple = _assignment_to_triple(assign, source, token_parts)
            if triple is not None:
                triples.append(triple)
            continue

        if node.type == "if_statement":
            triples.extend(_decode_if_statement(node, source, token_parts))
            continue

        if node.type == "statement_block":
            triples.extend(_decode_case_nodes(list(node.named_children), source, token_parts))
    return triples


def _decode_if_statement(
    node: Node,
    source: str,
    token_parts: list[str],
) -> list[StoreDataTriple]:
    triples: list[StoreDataTriple] = []
    condition = node.child_by_field_name("condition")
    guard = _str_equals_guard(condition, source) if condition is not None else None
    next_parts = token_parts
    if guard is not None:
        position, value = guard
        if position == len(token_parts):
            next_parts = [*token_parts, value]
        else:
            return triples
    consequence = node.child_by_field_name("consequence")
    if consequence is not None:
        triples.extend(_decode_case_nodes(list(consequence.named_children), source, next_parts))

    alternative = node.child_by_field_name("alternative")
    if alternative is not None:
        triples.extend(_decode_alternative(alternative, source, token_parts))
    return triples


def _decode_alternative(
    node: Node,
    source: str,
    token_parts: list[str],
) -> list[StoreDataTriple]:
    if node.type == "if_statement":
        return _decode_if_statement(node, source, token_parts)
    if node.type == "else_clause":
        triples: list[StoreDataTriple] = []
        for child in node.named_children:
            if child.type == "if_statement":
                triples.extend(_decode_if_statement(child, source, token_parts))
            elif child.type == "statement_block":
                triples.extend(_decode_case_nodes(list(child.named_children), source, token_parts))
        return triples
    return []


def _decode_prefix_guards(body: Node, source: str) -> list[StoreDataTriple]:
    triples: list[StoreDataTriple] = []
    for node in _iter_nodes(body):
        if node.type != "if_statement":
            continue
        condition = node.child_by_field_name("condition")
        guard = _substring_prefix_guard(condition, source) if condition is not None else None
        if guard is None:
            continue
        prefix, prefix_len = guard
        consequence = node.child_by_field_name("consequence")
        if consequence is None:
            continue
        for assign in _direct_assignment_nodes(consequence):
            field = _assignment_data_field(assign, source)
            rhs = assign.child_by_field_name("right")
            if field is None or rhs is None:
                continue
            if _str0_substring_start(rhs, source) != prefix_len:
                continue
            value: ValueSpec = SuffixCapture(prefix=prefix, prefix_len=prefix_len)
            triples.append(
                StoreDataTriple(
                    token=prefix,
                    field=field,
                    value=value,
                    is_prefix_match=True,
                )
            )
    return triples


def _assignment_to_triple(
    assign: Node,
    source: str,
    token_parts: list[str],
) -> StoreDataTriple | None:
    field = _assignment_data_field(assign, source)
    rhs = assign.child_by_field_name("right")
    if field is None or rhs is None:
        return None
    return StoreDataTriple(
        token=":".join(token_parts),
        field=field,
        value=_rhs_value_spec(rhs, source),
    )


def _rhs_value_spec(node: Node, source: str) -> ValueSpec:
    if node.type == "string":
        return ConstantValue(decode_js_string(node_text(node, source)))
    direct = _str_subscript_position(node, source)
    if direct is not None:
        return CapturedField(position=direct)
    parse_int = _parse_int_str_subscript_position(node, source)
    if parse_int is not None:
        return CapturedField(position=parse_int, is_integer=True)
    return TransformedValue(description=node_text(node, source))


def _case_token(case: Node, source: str) -> str | None:
    for child in case.named_children:
        if child.type == "string":
            return decode_js_string(node_text(child, source))
    return None


def _assignment_nodes(root: Node) -> list[Node]:
    return [node for node in _iter_nodes(root) if node.type == "assignment_expression"]


def _direct_assignment_nodes(block: Node) -> list[Node]:
    assigns: list[Node] = []
    for child in block.named_children:
        assign = _assignment_node(child)
        if assign is not None:
            assigns.append(assign)
    return assigns


def _assignment_node(node: Node) -> Node | None:
    if node.type == "assignment_expression":
        return node
    if node.type == "expression_statement" and node.named_children:
        child = node.named_children[0]
        return child if child.type == "assignment_expression" else None
    return None


def _assignment_data_field(assign: Node, source: str) -> str | None:
    left = assign.child_by_field_name("left")
    return _this_data_member_field(left, source) if left is not None else None


def _this_data_member_field(node: Node | None, source: str) -> str | None:
    return _data_member_field(node, source, root_names=frozenset({"this"}))


def _data_member_field(
    node: Node | None,
    source: str,
    *,
    root_names: frozenset[str] = frozenset({"this", "self"}),
) -> str | None:
    if node is None or node.type != "member_expression":
        return None
    obj = node.child_by_field_name("object")
    prop = node.child_by_field_name("property")
    if obj is None or prop is None or obj.type != "member_expression":
        return None
    inner_obj = obj.child_by_field_name("object")
    inner_prop = obj.child_by_field_name("property")
    if inner_obj is None or inner_prop is None:
        return None
    root = node_text(inner_obj, source)
    if root not in root_names or node_text(inner_prop, source) != "data":
        return None
    return node_text(prop, source)


def _is_instance_member(node: Node, source: str) -> bool:
    if node.type != "member_expression":
        return False
    obj = node.child_by_field_name("object")
    return obj is not None and node_text(obj, source) in {"self", "this"}


def _str_equals_guard(node: Node | None, source: str) -> tuple[int, str] | None:
    node = _unwrap_parenthesized(node)
    if node is None or node.type != "binary_expression":
        return None
    operator = node.child_by_field_name("operator")
    if operator is None or node_text(operator, source) not in {"==", "==="}:
        return None
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    if left is None or right is None:
        return None
    return _str_equals_pair(left, right, source) or _str_equals_pair(right, left, source)


def _str_equals_pair(candidate: Node, literal: Node, source: str) -> tuple[int, str] | None:
    position = _str_subscript_position(candidate, source)
    if position is None or literal.type != "string":
        return None
    return position, decode_js_string(node_text(literal, source))


def _substring_prefix_guard(node: Node | None, source: str) -> tuple[str, int] | None:
    node = _unwrap_parenthesized(node)
    if node is None or node.type != "binary_expression":
        return None
    operator = node.child_by_field_name("operator")
    if operator is None or node_text(operator, source) not in {"==", "==="}:
        return None
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    if left is None or right is None:
        return None
    return _substring_prefix_pair(left, right, source) or _substring_prefix_pair(
        right, left, source
    )


def _substring_prefix_pair(candidate: Node, literal: Node, source: str) -> tuple[str, int] | None:
    prefix_len = _str0_substring_span(candidate, source)
    if prefix_len is None or literal.type != "string":
        return None
    prefix = decode_js_string(node_text(literal, source))
    return prefix, prefix_len


def _str0_substring_span(node: Node, source: str) -> int | None:
    """Return N from ``str[0].substring(0, N)``/``substr(0, N)``."""
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return None
    prop = function.child_by_field_name("property")
    obj = function.child_by_field_name("object")
    if prop is None or obj is None:
        return None
    if node_text(prop, source) not in {"substring", "substr"}:
        return None
    if _str_subscript_position(obj, source) != 0:
        return None
    args = node.child_by_field_name("arguments")
    if args is None or len(args.named_children) < 2:
        return None
    start, end = args.named_children[0], args.named_children[1]
    if start.type != "number" or node_text(start, source) != "0" or end.type != "number":
        return None
    return int(node_text(end, source))


def _str0_substring_start(node: Node, source: str) -> int | None:
    """Return N from ``str[0].substring(N)``."""
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return None
    prop = function.child_by_field_name("property")
    obj = function.child_by_field_name("object")
    if prop is None or obj is None:
        return None
    if node_text(prop, source) not in {"substring", "substr"}:
        return None
    if _str_subscript_position(obj, source) != 0:
        return None
    args = node.child_by_field_name("arguments")
    if args is None or len(args.named_children) != 1:
        return None
    start = args.named_children[0]
    if start.type != "number":
        return None
    return int(node_text(start, source))


def _parse_int_str_subscript_position(node: Node, source: str) -> int | None:
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None
    if node_text(function, source) != "parseInt":
        return None
    args = node.child_by_field_name("arguments")
    if args is None or not args.named_children:
        return None
    return _str_subscript_position(args.named_children[0], source)


def _str_subscript_position(node: Node | None, source: str) -> int | None:
    if node is None or node.type != "subscript_expression":
        return None
    obj = node.child_by_field_name("object")
    index = node.child_by_field_name("index")
    if obj is None or index is None:
        return None
    if obj.type != "identifier" or node_text(obj, source) != "str":
        return None
    if index.type != "number":
        return None
    return int(node_text(index, source))


def _call_property(call: Node, source: str) -> str | None:
    function = call.child_by_field_name("function")
    if function is None:
        return None
    if function.type == "identifier":
        return node_text(function, source)
    if function.type == "member_expression":
        prop = function.child_by_field_name("property")
        return node_text(prop, source) if prop is not None else None
    return None


def _unwrap_parenthesized(node: Node | None) -> Node | None:
    if node is not None and node.type == "parenthesized_expression" and node.named_child_count == 1:
        return node.named_children[0]
    return node


def _dedupe_triples(triples: list[StoreDataTriple]) -> list[StoreDataTriple]:
    seen: set[tuple[str, str, str]] = set()
    result: list[StoreDataTriple] = []
    for triple in triples:
        key = (triple.token, triple.field, repr(triple.value))
        if key in seen:
            continue
        seen.add(key)
        result.append(triple)
    return result


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes
