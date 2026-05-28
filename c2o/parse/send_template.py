"""Send template reconstruction from Companion action callbacks."""

from __future__ import annotations

import re
from typing import Final

from tree_sitter import Node

from c2o.parse.js import StringTemplate, extract_string_concat, node_text

_SEND_METHODS: Final[frozenset[str]] = frozenset({"send", "sendCommand"})
_ALLOWED_THIS_PROPS: Final[frozenset[str]] = frozenset({"socket", "sendCommand", "log"})
_OPTIONS_PLACEHOLDER = re.compile(r"^(?:event\.|action\.)?options\.([A-Za-z_][A-Za-z0-9_]*)$")


def snake_lower(value: str) -> str:
    """Convert a branch choice id to a snake_case command suffix."""
    lowered = value.lower()
    snake = re.sub(r"[^a-z0-9]+", "_", lowered)
    snake = snake.strip("_")
    return re.sub(r"_+", "_", snake)


def normalize_placeholder(text: str, known_param_ids: set[str]) -> str | None:
    """Map Companion option references to OpenAVC ``{param}`` placeholders."""
    match = _OPTIONS_PLACEHOLDER.match(text.strip())
    if match:
        return "{" + match.group(1) + "}"
    if text in known_param_ids:
        return "{" + text + "}"
    return None


def contains_rejected_expression(node: Node, source: str) -> bool:
    """Return True when an expression cannot be statically reconstructed."""
    for child in _walk_nodes(node):
        if child.type == "await_expression":
            return True
        if child.type == "call_expression":
            function = child.child_by_field_name("function")
            if function is not None and "parseVariablesInString" in node_text(function, source):
                return True
        if child.type == "subscript_expression":
            return True
        if child.type == "member_expression":
            obj = child.child_by_field_name("object")
            prop = child.child_by_field_name("property")
            if obj is None or prop is None:
                continue
            if obj.type == "this":
                prop_name = node_text(prop, source)
                if prop_name not in _ALLOWED_THIS_PROPS:
                    return True
    return False


def resolve_send_in_block(
    body: Node,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    """Resolve a static send template from a callback or branch body."""
    send_calls = _find_send_calls(body, source)
    if not send_calls:
        return None

    arg = send_calls[-1].child_by_field_name("arguments")
    if arg is None or not arg.named_children:
        return None

    return _resolve_send_expression(
        arg.named_children[0],
        scope=body,
        source=source,
        known_param_ids=known_param_ids,
    )


def parse_options_member(node: Node, source: str) -> str | None:
    """Return the option id from ``options.id`` / ``event.options.id`` / ``action.options.id``."""
    if node.type != "member_expression":
        return None

    prop = node.child_by_field_name("property")
    obj = node.child_by_field_name("object")
    if prop is None or obj is None:
        return None

    prop_name = node_text(prop, source)
    if obj.type == "identifier" and node_text(obj, source) == "options":
        return prop_name

    if obj.type == "member_expression":
        inner_obj = obj.child_by_field_name("object")
        inner_prop = obj.child_by_field_name("property")
        if inner_obj is None or inner_prop is None:
            return None
        if (
            node_text(inner_obj, source) in {"event", "action"}
            and node_text(inner_prop, source) == "options"
        ):
            return prop_name

    return None


def parse_branch_condition(node: Node, source: str) -> tuple[str, str] | None:
    """Return ``(branch_option_id, literal)`` for an options equality test."""
    if node.type == "parenthesized_expression" and node.named_child_count == 1:
        return parse_branch_condition(node.named_children[0], source)

    if node.type != "binary_expression":
        return None

    operator = node.child_by_field_name("operator")
    if operator is None or node_text(operator, source) not in {"===", "=="}:
        return None

    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    if left is None or right is None:
        return None

    option_id = parse_options_member(left, source)
    if option_id is not None and right.type == "string":
        return option_id, _decode_js_string(node_text(right, source))

    option_id = parse_options_member(right, source)
    if option_id is not None and left.type == "string":
        return option_id, _decode_js_string(node_text(left, source))

    return None


def callback_has_options_access(body: Node, source: str) -> bool:
    """Return True when the callback reads action option values."""
    for node in _walk_nodes(body):
        if node.type == "member_expression":
            if parse_options_member(node, source) is not None:
                return True
    return False


def callback_reads_instance_state(body: Node, source: str) -> bool:
    """Return True when the callback reads runtime instance state via ``this.*``."""
    for node in _walk_nodes(body):
        if node.type != "member_expression":
            continue
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        if obj is None or prop is None or obj.type != "this":
            continue
        prop_name = node_text(prop, source)
        if prop_name not in _ALLOWED_THIS_PROPS:
            return True
    return False


def _resolve_send_expression(
    node: Node,
    *,
    scope: Node,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    if contains_rejected_expression(node, source):
        return None

    if node.type == "string":
        return _decode_js_string(node_text(node, source))

    if node.type == "template_string":
        return _resolve_template_string(node, source, known_param_ids)

    if node.type == "identifier":
        return _trace_variable(node, scope=scope, source=source, known_param_ids=known_param_ids)

    if node.type in {"binary_expression", "parenthesized_expression"}:
        concat = extract_string_concat(node, source)
        if concat is not None:
            return _normalize_concat_template(concat, known_param_ids)

    return None


def _resolve_template_string(node: Node, source: str, known_param_ids: set[str]) -> str | None:
    parts: list[str] = []
    for child in node.children:
        if child.type == "string_fragment":
            parts.append(node_text(child, source))
            continue
        if child.type == "escape_sequence":
            parts.append(_decode_escape_sequence(node_text(child, source)))
            continue
        if child.type != "template_substitution":
            continue
        if not child.named_children:
            return None
        expr = child.named_children[0]
        if contains_rejected_expression(expr, source):
            return None
        placeholder = node_text(expr, source)
        normalized = normalize_placeholder(placeholder, known_param_ids)
        if normalized is None:
            return None
        parts.append(normalized)
    return "".join(parts)


def _decode_escape_sequence(raw: str) -> str:
    import ast

    try:
        value = ast.literal_eval(f'"{raw}"')
    except (SyntaxError, ValueError):
        return raw
    return value if isinstance(value, str) else raw


def _trace_variable(
    node: Node,
    *,
    scope: Node,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    name = node_text(node, source)
    current = _find_variable_value(name, scope, source)
    if current is None:
        return None
    return _resolve_tracked_expression(
        name,
        current,
        source=source,
        known_param_ids=known_param_ids,
    )


def _find_variable_value(name: str, scope: Node, source: str) -> _TrackedValue | None:
    declarator_value: Node | None = None
    reassignments: list[tuple[int, Node]] = []

    for node in _walk_nodes(scope):
        if node.type == "variable_declarator":
            var_name = node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            if var_name is None or value is None:
                continue
            if node_text(var_name, source) != name:
                continue
            declarator_value = value
            continue

        if node.type != "assignment_expression":
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            continue
        if left.type != "identifier" or node_text(left, source) != name:
            continue
        reassignments.append((node.start_byte, right))

    if declarator_value is None and not reassignments:
        return None

    reassignments.sort(key=lambda item: item[0])
    return _TrackedValue(initial=declarator_value, reassignments=[rhs for _, rhs in reassignments])


class _TrackedValue:
    __slots__ = ("initial", "reassignments")

    def __init__(self, *, initial: Node | None, reassignments: list[Node]) -> None:
        self.initial = initial
        self.reassignments = reassignments


def _resolve_tracked_expression(
    name: str,
    tracked: _TrackedValue,
    *,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    current: str | None
    if tracked.initial is not None:
        if tracked.initial.type == "string":
            current = _decode_js_string(node_text(tracked.initial, source))
        elif tracked.initial.type == "template_string":
            current = _resolve_template_string(tracked.initial, source, known_param_ids)
        else:
            current = None
    else:
        current = None

    for rhs in tracked.reassignments:
        if current is None:
            break
        appended = _resolve_reassignment_append(
            name,
            rhs,
            source=source,
            known_param_ids=known_param_ids,
        )
        if appended is None:
            return None
        current = current + appended

    return current


def _resolve_reassignment_append(
    name: str,
    node: Node,
    *,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    parts = _flatten_plus_chain(node, source)
    if parts is None or not parts:
        return None
    if parts[0].type != "identifier" or node_text(parts[0], source) != name:
        return None
    if len(parts) == 1:
        return ""
    return _resolve_concat_parts(parts[1:], source=source, known_param_ids=known_param_ids)


def _flatten_plus_chain(node: Node, source: str) -> list[Node] | None:
    if node.type == "binary_expression":
        operator = node.child_by_field_name("operator")
        if operator is None or node_text(operator, source) != "+":
            return None
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return None
        left_parts = _flatten_plus_chain(left, source)
        if left_parts is None:
            left_parts = [left]
        right_parts = _flatten_plus_chain(right, source)
        if right_parts is None:
            right_parts = [right]
        return [*left_parts, *right_parts]

    return [node]


def _resolve_concat_parts(
    parts: list[Node],
    *,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    rendered: list[str] = []
    for part in parts:
        if part.type == "string":
            rendered.append(_decode_js_string(node_text(part, source)))
            continue
        if part.type == "member_expression":
            option_id = parse_options_member(part, source)
            if option_id is None:
                return None
            rendered.append("{" + option_id + "}")
            continue
        if part.type == "binary_expression":
            nested = extract_string_concat(part, source)
            if nested is None:
                return None
            normalized = _normalize_concat_template(nested, known_param_ids)
            if normalized is None:
                return None
            rendered.append(normalized)
            continue
        return None
    return "".join(rendered)


def _resolve_append_expression(
    node: Node,
    *,
    source: str,
    known_param_ids: set[str],
) -> str | None:
    if contains_rejected_expression(node, source):
        return None

    if node.type == "binary_expression":
        concat = extract_string_concat(node, source)
        if concat is None:
            return None
        return _normalize_concat_template(concat, known_param_ids)

    if node.type == "string":
        return _decode_js_string(node_text(node, source))

    if node.type == "member_expression":
        option_id = parse_options_member(node, source)
        if option_id is None:
            return None
        return "{" + option_id + "}"

    return None


def _normalize_concat_template(template: StringTemplate, known_param_ids: set[str]) -> str | None:
    result = template.template
    for placeholder in template.placeholders:
        normalized = normalize_placeholder(placeholder, known_param_ids)
        if normalized is None:
            return None
        result = result.replace("{" + placeholder + "}", normalized, 1)
    return result


def _find_send_calls(body: Node, source: str) -> list[Node]:
    calls: list[Node] = []
    for node in _walk_nodes(body):
        if _is_send_call(node, source):
            calls.append(node)
    return calls


def _is_send_call(node: Node, source: str) -> bool:
    if node.type != "call_expression":
        return False
    function = node.child_by_field_name("function")
    if function is None:
        return False
    if function.type == "identifier":
        return node_text(function, source) in _SEND_METHODS
    if function.type == "member_expression":
        prop = function.child_by_field_name("property")
        if prop is None:
            return False
        return node_text(prop, source) in _SEND_METHODS
    return False


def _decode_js_string(raw: str) -> str:
    import ast

    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw[1:-1] if len(raw) >= 2 else raw
    if isinstance(value, str):
        return value
    return raw[1:-1] if len(raw) >= 2 else raw


def _walk_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes
