"""Extract OpenAVC responses from Companion receive handlers."""

from __future__ import annotations

from tree_sitter import Node

from c2o.extract.response_patterns import (
    build_boolean_map_entry,
    build_entry,
    build_fan_out_entry,
    build_prefix_capture_entry,
    compile_check,
    data_subscript_key,
    is_rejected_value,
    match_group_index,
    regex_pattern_from_node,
    string_literal_value,
)
from c2o.model.driver import ResponseEntry, ResponsesSection
from c2o.model.review import ReviewReport
from c2o.parse.event_handlers import (
    EventHandler,
    delegated_line_methods,
    find_socket_event_handlers,
)
from c2o.parse.js import ParsedModule, find_all_method_definitions, node_text
from c2o.parse.literals import pair_key


class ResponsesExtractionError(ValueError):
    """Raised when response extraction encounters unrecoverable malformed input."""


def extract_responses(parsed: ParsedModule) -> tuple[ResponsesSection, ReviewReport]:
    """Build responses from static receive-handler patterns."""
    handlers = find_socket_event_handlers(parsed)
    entries: list[ResponseEntry] = []
    entries.extend(_extract_inline_handlers(handlers))
    entries.extend(_extract_delegated_helpers(parsed, handlers))
    entries.extend(_extract_aggregating_fanout(parsed))
    merged = _merge_entries(entries)
    return ResponsesSection(responses=tuple(merged)), ReviewReport()


def _extract_inline_handlers(handlers: list[EventHandler]) -> list[ResponseEntry]:
    entries: list[ResponseEntry] = []
    for handler in handlers:
        entries.extend(_extract_match_patterns_from_body(handler.callback_body, handler.source))
    return entries


def _extract_delegated_helpers(
    parsed: ParsedModule,
    handlers: list[EventHandler],
) -> list[ResponseEntry]:
    seen: set[tuple[str, str]] = set()
    entries: list[ResponseEntry] = []
    for handler in handlers:
        for method_name in delegated_line_methods(handler):
            key = (handler.rel_path, method_name)
            if key in seen:
                continue
            seen.add(key)
            for method in find_all_method_definitions(parsed):
                if method.rel_path != handler.rel_path or method.name != method_name:
                    continue
                if method.body is None:
                    continue
                source = parsed.sources[method.rel_path]
                entries.extend(_extract_prefix_patterns(method.body, source))
                entries.extend(_extract_match_patterns_from_body(method.body, source))
    return entries


def _extract_aggregating_fanout(parsed: ParsedModule) -> list[ResponseEntry]:
    entries: list[ResponseEntry] = []
    for method in find_all_method_definitions(parsed):
        if method.body is None:
            continue
        source = parsed.sources[method.rel_path]
        branch_keys = _collect_data_key_branches(method.body, source)
        if len(branch_keys) < 2:
            continue
        for device_key, if_node in branch_keys:
            entries.extend(_extract_fanout_from_branch(if_node, device_key, source))
    return entries


def _extract_match_patterns_from_body(body: Node, source: str) -> list[ResponseEntry]:
    entries: list[ResponseEntry] = []
    bindings = _collect_match_bindings(body, source)
    for match_var, pattern in bindings.items():
        for if_node in _find_guarded_ifs(body, source, match_var):
            consequent = if_node.child_by_field_name("consequence")
            if consequent is None:
                continue
            entries.extend(_extract_set_values_from_block(consequent, source, match_var, pattern))
    return entries


def _extract_prefix_patterns(body: Node, source: str) -> list[ResponseEntry]:
    entries: list[ResponseEntry] = []
    for if_node in _iter_nodes(body):
        if if_node.type != "if_statement":
            continue
        prefix = _starts_with_prefix(if_node, source)
        if prefix is None:
            continue
        consequent = if_node.child_by_field_name("consequence")
        if consequent is None:
            continue
        for call in _find_set_variable_values_calls(consequent, source):
            obj = _set_variable_values_object(call)
            if obj is None:
                continue
            for pair in obj.named_children:
                if pair.type != "pair":
                    continue
                state_var = pair_key(pair, source)
                if state_var is None:
                    continue
                value_node = pair.child_by_field_name("value")
                if value_node is None:
                    continue
                if _is_includes_on_check(value_node, source):
                    entry = build_boolean_map_entry(prefix, state_var)
                elif _is_slice_trim_value(value_node, source):
                    entry = build_prefix_capture_entry(prefix, state_var)
                else:
                    continue
                if entry is not None:
                    entries.append(entry)
    return entries


def _extract_set_values_from_block(
    block: Node,
    source: str,
    match_var: str,
    pattern: str,
) -> list[ResponseEntry]:
    entries: list[ResponseEntry] = []
    for call in _find_set_variable_values_calls(block, source):
        obj = _set_variable_values_object(call)
        if obj is None:
            continue
        for pair in obj.named_children:
            if pair.type != "pair":
                continue
            state_var = pair_key(pair, source)
            if state_var is None:
                continue
            value_node = pair.child_by_field_name("value")
            if value_node is None:
                continue
            group = _value_group_index(value_node, source, match_var) or 1
            entry = build_entry(pattern, state_var, value_node, source, group=group)
            if entry is not None:
                entries.append(entry)
    return entries


def _extract_fanout_from_branch(
    if_node: Node,
    device_key: str,
    source: str,
) -> list[ResponseEntry]:
    entries: list[ResponseEntry] = []
    consequent = if_node.child_by_field_name("consequence")
    if consequent is None:
        return entries

    one_hop = _collect_one_hop_assignments(consequent, source)
    for call in _find_set_variable_values_calls(consequent, source):
        obj = _set_variable_values_object(call)
        if obj is None:
            continue
        for pair in obj.named_children:
            if pair.type != "pair":
                continue
            state_var = pair_key(pair, source)
            if state_var is None:
                continue
            value_node = pair.child_by_field_name("value")
            if value_node is None:
                continue
            resolved_key = _resolve_fanout_device_key(value_node, source, device_key, one_hop)
            if resolved_key is None:
                continue
            entry = build_fan_out_entry(resolved_key, state_var)
            if entry is not None:
                entries.append(entry)
    return entries


def _resolve_fanout_device_key(
    value_node: Node,
    source: str,
    guard_key: str,
    one_hop: dict[str, str],
) -> str | None:
    if is_rejected_value(value_node, source):
        return None

    direct = data_subscript_key(value_node, source)
    if direct is not None:
        return direct

    if value_node.type == "member_expression":
        obj = value_node.child_by_field_name("object")
        prop = value_node.child_by_field_name("property")
        if obj is not None and prop is not None and obj.type == "this":
            return one_hop.get(node_text(prop, source))

    return None


def _collect_match_bindings(body: Node, source: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for node in _iter_nodes(body):
        if node.type not in {"lexical_declaration", "variable_declaration"}:
            continue
        for child in node.named_children:
            if child.type != "variable_declarator":
                continue
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            if name_node.type != "identifier":
                continue
            pattern = _regex_from_match_call(value_node, source)
            if pattern is None:
                continue
            bindings[node_text(name_node, source)] = pattern
    return bindings


def _regex_from_match_call(node: Node, source: str) -> str | None:
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return None
    prop = function.child_by_field_name("property")
    if prop is None or node_text(prop, source) != "match":
        return None
    args = node.child_by_field_name("arguments")
    if args is None or args.named_child_count == 0:
        return None
    return regex_pattern_from_node(args.named_children[0], source)


def _find_guarded_ifs(body: Node, source: str, match_var: str) -> list[Node]:
    hits: list[Node] = []
    for node in _iter_nodes(body):
        if node.type != "if_statement":
            continue
        condition = node.child_by_field_name("condition")
        if condition is None:
            continue
        if _condition_references_identifier(condition, source, match_var):
            hits.append(node)
    return hits


def _condition_references_identifier(node: Node, source: str, identifier: str) -> bool:
    if node.type == "identifier" and node_text(node, source) == identifier:
        return True
    if node.type == "subscript_expression":
        obj = node.child_by_field_name("object")
        if obj is not None and obj.type == "identifier" and node_text(obj, source) == identifier:
            return True
    for child in node.children:
        if _condition_references_identifier(child, source, identifier):
            return True
    return False


def _collect_data_key_branches(body: Node, source: str) -> list[tuple[str, Node]]:
    branches: list[tuple[str, Node]] = []
    for node in _iter_nodes(body):
        if node.type != "if_statement":
            continue
        device_key = _data_key_guard(node, source)
        if device_key is None:
            continue
        consequent = node.child_by_field_name("consequence")
        if consequent is None:
            continue
        if not _branch_has_set_variable_values(consequent, source):
            continue
        branches.append((device_key, node))
    return branches


def _data_key_guard(if_node: Node, source: str) -> str | None:
    condition = if_node.child_by_field_name("condition")
    if condition is None:
        return None
    condition = _unwrap_parenthesized(condition)
    if condition.type != "binary_expression":
        return None
    operator = condition.child_by_field_name("operator")
    if operator is None:
        return None
    op = node_text(operator, source)
    if op not in {"!==", "!="}:
        return None
    left = condition.child_by_field_name("left")
    right = condition.child_by_field_name("right")
    if left is None or right is None:
        return None
    if right.type == "undefined":
        pass
    elif right.type == "identifier" and node_text(right, source) == "undefined":
        pass
    else:
        return None
    return data_subscript_key(left, source)


def _branch_has_set_variable_values(block: Node, source: str) -> bool:
    return bool(_find_set_variable_values_calls(block, source))


def _collect_one_hop_assignments(block: Node, source: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for node in _iter_nodes(block):
        if node.type == "expression_statement" and node.named_children:
            expr = node.named_children[0]
            if expr.type == "assignment_expression":
                _record_one_hop_assignment(expr, source, mapping)
        if node.type == "assignment_expression":
            _record_one_hop_assignment(node, source, mapping)
    return mapping


def _record_one_hop_assignment(node: Node, source: str, mapping: dict[str, str]) -> None:
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    if left is None or right is None:
        return
    if left.type != "member_expression":
        return
    obj = left.child_by_field_name("object")
    prop = left.child_by_field_name("property")
    if obj is None or prop is None or obj.type != "this":
        return
    key = data_subscript_key(right, source)
    if key is None:
        return
    mapping[node_text(prop, source)] = key


def _starts_with_prefix(if_node: Node, source: str) -> str | None:
    condition = if_node.child_by_field_name("condition")
    if condition is None:
        return None
    condition = _unwrap_parenthesized(condition)
    if condition.type != "call_expression":
        return None
    function = condition.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return None
    prop = function.child_by_field_name("property")
    if prop is None or node_text(prop, source) != "startsWith":
        return None
    args = condition.child_by_field_name("arguments")
    if args is None or args.named_child_count == 0:
        return None
    return string_literal_value(args.named_children[0], source)


def _is_includes_on_check(node: Node, source: str) -> bool:
    if node.type != "call_expression":
        return False
    function = node.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return False
    prop = function.child_by_field_name("property")
    if prop is None or node_text(prop, source) != "includes":
        return False
    args = node.child_by_field_name("arguments")
    if args is None or args.named_child_count == 0:
        return False
    return string_literal_value(args.named_children[0], source) == "ON"


def _is_slice_trim_value(node: Node, source: str) -> bool:
    if node.type != "call_expression":
        return False
    function = node.child_by_field_name("function")
    if function is None or function.type != "member_expression":
        return False
    prop = function.child_by_field_name("property")
    return prop is not None and node_text(prop, source) == "trim"


def _value_group_index(value_node: Node, source: str, match_var: str) -> int | None:
    if value_node.type == "subscript_expression":
        return match_group_index(value_node, source, match_var)
    if value_node.type == "call_expression":
        args = value_node.child_by_field_name("arguments")
        if args is None or args.named_child_count == 0:
            return None
        return match_group_index(args.named_children[0], source, match_var)
    return None


def _find_set_variable_values_calls(block: Node, source: str) -> list[Node]:
    hits: list[Node] = []
    for node in _iter_nodes(block):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None:
            continue
        if function.type == "member_expression":
            prop = function.child_by_field_name("property")
            if prop is not None and node_text(prop, source) == "setVariableValues":
                hits.append(node)
        elif function.type == "identifier" and node_text(function, source) == "setVariableValues":
            hits.append(node)
    return hits


def _set_variable_values_object(call: Node) -> Node | None:
    args = call.child_by_field_name("arguments")
    if args is None or args.named_child_count == 0:
        return None
    first = args.named_children[0]
    return first if first.type == "object" else None


def _merge_entries(entries: list[ResponseEntry]) -> list[ResponseEntry]:
    seen: set[tuple[str, str]] = set()
    merged: list[ResponseEntry] = []
    for entry in entries:
        if not compile_check(entry.match):
            continue
        state_keys = _entry_state_vars(entry)
        if not state_keys:
            continue
        if any((entry.match, state_var) in seen for state_var in state_keys):
            continue
        for state_var in state_keys:
            seen.add((entry.match, state_var))
        merged.append(entry)
    return merged


def _entry_state_vars(entry: ResponseEntry) -> set[str]:
    if entry.set is not None:
        return set(entry.set)
    if entry.mappings is not None:
        return {mapping.state for mapping in entry.mappings}
    return set()


def _unwrap_parenthesized(node: Node) -> Node:
    if node.type == "parenthesized_expression" and node.named_child_count == 1:
        return node.named_children[0]
    return node


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes
