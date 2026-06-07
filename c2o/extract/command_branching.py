"""Branch-splitting heuristics for Companion action → OpenAVC command mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from c2o.extract.param_schema import extract_static_choice_values
from c2o.model.driver import ParamEntry
from c2o.parse.js import ParsedModule, node_text
from c2o.parse.send_template import (
    callback_has_options_access,
    callback_reads_instance_state,
    parse_branch_condition,
    resolve_send_in_block,
    snake_lower,
)

# Instance properties that are commonly used as speed/value params in drive commands.
_SPEED_PROP_PATTERN = re.compile(r"(?i)(speed|rate|level|value|velocity|step|amount)$")


@dataclass(frozen=True)
class CommandCandidate:
    """A command ready to merge into ``CommandsSection``."""

    command_key: str
    label: str
    send: str
    params: dict[str, ParamEntry]
    branch_driver_id: str | None = None


@dataclass(frozen=True)
class SplitResult:
    """Branch splitter output for one action definition."""

    candidates: tuple[CommandCandidate, ...]
    state_dependent_reason: str | None = None


def split_or_single(
    *,
    action_key: str,
    label: str,
    options: Any,
    callback_node: Node,
    source: str,
    base_params: dict[str, ParamEntry],
    parsed: ParsedModule | None = None,
) -> SplitResult:
    """Split branch-driven actions or emit a single command candidate."""
    body = _callback_body(callback_node)
    if body is None:
        return SplitResult(())

    known_param_ids = set(base_params)

    if _is_whole_action_state_dependent(body, source):
        # P2-5: Try to convert to parametric form when the only dependency is a
        # simple numeric instance variable used as a speed/value argument.
        if parsed is not None:
            parametric = _try_instance_state_parametric(
                action_key=action_key,
                label=label,
                body=body,
                source=source,
                base_params=base_params,
                parsed=parsed,
            )
            if parametric is not None:
                return parametric
        return SplitResult((), state_dependent_reason="instance_state")

    if_chain = _try_if_chain_split(
        action_key=action_key,
        label=label,
        body=body,
        source=source,
        base_params=base_params,
        known_param_ids=known_param_ids,
    )
    if if_chain is not None:
        return if_chain

    prefix_suffix = _try_prefix_suffix_split(
        action_key=action_key,
        label=label,
        options=options,
        body=body,
        source=source,
        base_params=base_params,
    )
    if prefix_suffix is not None:
        return prefix_suffix

    send = resolve_send_in_block(body, source, known_param_ids)
    if send is None:
        return SplitResult(())

    return SplitResult(
        (
            CommandCandidate(
                command_key=action_key,
                label=label,
                send=send,
                params=dict(base_params),
            ),
        )
    )


def _try_instance_state_parametric(
    *,
    action_key: str,
    label: str,
    body: Node,
    source: str,
    base_params: dict[str, ParamEntry],
    parsed: ParsedModule,
) -> SplitResult | None:
    """Convert a drive command that reads a single this.X speed property to a param.

    Detects the pattern: ``this.sendCommand('camera pan left ' + this.panSpeed)``
    and converts it to ``send: 'camera pan left {panSpeed}'`` with
    ``params: {panSpeed: {type: integer, default: <init_value>}}``.
    """
    instance_props = _collect_instance_prop_reads(body, source)
    if len(instance_props) != 1:
        return None
    prop_name = instance_props[0]

    if not _SPEED_PROP_PATTERN.search(prop_name):
        return None

    send = _resolve_send_replacing_this_props(body, source, {prop_name})
    if send is None:
        return None

    default_val = _get_this_prop_initial_value(prop_name, parsed)
    param = ParamEntry(
        type="integer",
        label=prop_name,
        default=default_val,
        min=None,
        max=None,
    )
    merged_params = {**base_params, prop_name: param}

    return SplitResult(
        (
            CommandCandidate(
                command_key=action_key,
                label=label,
                send=send,
                params=merged_params,
            ),
        )
    )


def _collect_instance_prop_reads(body: Node, source: str) -> list[str]:
    """Return names of ``this.X`` property accesses found in a body (excluding known API props)."""
    from c2o.parse.send_template import _ALLOWED_THIS_PROPS  # noqa: PLC0415

    found: list[str] = []
    for node in _walk_nodes(body):
        if node.type != "member_expression":
            continue
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        if obj is None or prop is None or obj.type != "this":
            continue
        prop_name = node_text(prop, source)
        if prop_name in _ALLOWED_THIS_PROPS:
            continue
        if prop_name not in found:
            found.append(prop_name)
    return found


def _resolve_send_replacing_this_props(
    body: Node,
    source: str,
    prop_names: set[str],
) -> str | None:
    """Resolve the send expression, replacing ``this.X`` with ``{X}`` placeholders."""
    from c2o.parse.send_template import _find_send_calls  # noqa: PLC0415

    send_calls = _find_send_calls(body, source)
    if not send_calls:
        return None

    arg = send_calls[-1].child_by_field_name("arguments")
    if arg is None or not arg.named_children:
        return None

    return _resolve_with_this_prop_replacement(arg.named_children[0], source, prop_names, body)


def _resolve_with_this_prop_replacement(
    node: Node,
    source: str,
    prop_names: set[str],
    scope: Node,
) -> str | None:
    """Recursively resolve a send expression, substituting this.X → {X}."""
    import ast as _ast

    if node.type == "string":
        raw = node_text(node, source)
        try:
            value = _ast.literal_eval(raw)
            return value if isinstance(value, str) else None
        except (SyntaxError, ValueError):
            return raw[1:-1] if len(raw) >= 2 else raw

    if node.type == "member_expression":
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        if obj is not None and prop is not None and obj.type == "this":
            prop_name = node_text(prop, source)
            if prop_name in prop_names:
                return "{" + prop_name + "}"
        return None

    if node.type in {"binary_expression", "parenthesized_expression"}:
        if node.type == "parenthesized_expression":
            inner = node.named_children[0] if node.named_children else None
            if inner is None:
                return None
            return _resolve_with_this_prop_replacement(inner, source, prop_names, scope)
        operator = node.child_by_field_name("operator")
        if operator is None or node_text(operator, source) != "+":
            return None
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return None
        left_str = _resolve_with_this_prop_replacement(left, source, prop_names, scope)
        right_str = _resolve_with_this_prop_replacement(right, source, prop_names, scope)
        if left_str is None or right_str is None:
            return None
        return left_str + right_str

    if node.type == "template_string":
        parts: list[str] = []
        for child in node.children:
            if child.type == "string_fragment":
                parts.append(node_text(child, source))
            elif child.type == "template_substitution":
                inner = child.named_children[0] if child.named_children else None
                if inner is None:
                    return None
                sub = _resolve_with_this_prop_replacement(inner, source, prop_names, scope)
                if sub is None:
                    return None
                parts.append(sub)
        return "".join(parts)

    return None


def _get_this_prop_initial_value(prop_name: str, parsed: ParsedModule) -> int | None:
    """Find the initial integer value of ``this.X = N`` in constructor/init methods."""
    for rel_path, tree in parsed.trees.items():
        source = parsed.sources[rel_path]
        for node in _walk_nodes(tree.root_node):
            if node.type != "assignment_expression":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None:
                continue
            if not _is_this_prop(left, source, prop_name):
                continue
            if right.type == "number":
                try:
                    return int(float(node_text(right, source)))
                except ValueError:
                    pass
    return None


def _is_this_prop(node: Node, source: str, prop_name: str) -> bool:
    if node.type != "member_expression":
        return False
    obj = node.child_by_field_name("object")
    prop = node.child_by_field_name("property")
    if obj is None or prop is None:
        return False
    return obj.type == "this" and node_text(prop, source) == prop_name


def _is_whole_action_state_dependent(body: Node, source: str) -> bool:
    if callback_has_options_access(body, source):
        return False
    return callback_reads_instance_state(body, source)


def _try_if_chain_split(
    *,
    action_key: str,
    label: str,
    body: Node,
    source: str,
    base_params: dict[str, ParamEntry],
    known_param_ids: set[str],
) -> SplitResult | None:
    branches: list[tuple[str, str, str]] = []
    branch_driver_id: str | None = None

    for node in _walk_nodes(body):
        if node.type != "if_statement":
            continue
        chain = _collect_if_chain_branches(node, source, known_param_ids)
        if len(chain) >= 2:
            branches = chain
            branch_driver_id = chain[0][0]
            break

    if len(branches) < 2:
        return None

    sends = {send for _, _, send in branches}
    if len(sends) < 2:
        return None

    candidates: list[CommandCandidate] = []
    for _, literal, send in branches:
        command_key = f"{action_key}_{snake_lower(literal)}"
        params = _params_without_branch_driver(base_params, branch_driver_id)
        candidates.append(
            CommandCandidate(
                command_key=command_key,
                label=label,
                send=send,
                params=params,
                branch_driver_id=branch_driver_id,
            )
        )
    return SplitResult(tuple(candidates))


def _collect_if_chain_branches(
    node: Node,
    source: str,
    known_param_ids: set[str],
) -> list[tuple[str, str, str]]:
    branches: list[tuple[str, str, str]] = []
    current: Node | None = node

    while current is not None and current.type == "if_statement":
        condition = current.child_by_field_name("condition")
        consequence = current.child_by_field_name("consequence")
        if condition is None or consequence is None:
            break

        parsed = parse_branch_condition(condition, source)
        if parsed is None:
            break
        option_id, literal = parsed
        send = resolve_send_in_block(consequence, source, known_param_ids)
        if send is None:
            break
        branches.append((option_id, literal, send))

        alternative = current.child_by_field_name("alternative")
        if alternative is None:
            break
        if alternative.type != "else_clause" or not alternative.named_children:
            break
        inner = alternative.named_children[0]
        if inner.type == "if_statement":
            current = inner
            continue
        break

    return branches


def _try_prefix_suffix_split(
    *,
    action_key: str,
    label: str,
    options: Any,
    body: Node,
    source: str,
    base_params: dict[str, ParamEntry],
) -> SplitResult | None:
    branch_option = _find_branch_dropdown_option(options)
    if branch_option is None:
        return None

    option_id, choice_ids = branch_option
    prefix = _find_cmd_prefix(body, source)
    suffix = _find_cmd_suffix(body, source, option_id)
    if prefix is None or suffix is None:
        return None

    toggle_flag = _toggle_branch_reads_instance_state(body, source, option_id)
    candidates: list[CommandCandidate] = []
    for choice_id in choice_ids:
        if choice_id.lower() == "toggle":
            continue
        command_key = f"{action_key}_{snake_lower(choice_id)}"
        send = prefix + choice_id + suffix
        params = _params_without_branch_driver(base_params, option_id)
        candidates.append(
            CommandCandidate(
                command_key=command_key,
                label=label,
                send=send,
                params=params,
                branch_driver_id=option_id,
            )
        )

    if len(candidates) < 2:
        return None

    reason = "toggle_branch" if toggle_flag else None
    return SplitResult(tuple(candidates), state_dependent_reason=reason)


def _find_branch_dropdown_option(options: Any) -> tuple[str, tuple[str, ...]] | None:
    if not isinstance(options, list):
        return None

    for option in options:
        if not isinstance(option, dict):
            continue
        if option.get("type") != "dropdown":
            continue
        option_id = option.get("id")
        values = extract_static_choice_values(option.get("choices"))
        if isinstance(option_id, str) and values is not None:
            return option_id, values
    return None


def _find_cmd_prefix(body: Node, source: str) -> str | None:
    for node in _walk_nodes(body):
        if node.type != "variable_declarator":
            continue
        value = node.child_by_field_name("value")
        if value is None or value.type != "string":
            continue
        return _decode_js_string(node_text(value, source))
    return None


def _find_cmd_suffix(body: Node, source: str, branch_option_id: str) -> str | None:
    for node in _walk_nodes(body):
        if node.type != "assignment_expression":
            continue
        right = node.child_by_field_name("right")
        if right is None:
            continue
        if not _append_includes_option(right, source, branch_option_id):
            continue
        suffix = _static_suffix_from_append(right, source, branch_option_id)
        if suffix is not None:
            return suffix
    return None


def _append_includes_option(node: Node, source: str, branch_option_id: str) -> bool:
    from c2o.parse.send_template import parse_options_member

    for child in _walk_nodes(node):
        if child.type != "member_expression":
            continue
        if parse_options_member(child, source) == branch_option_id:
            return True
    return False


def _static_suffix_from_append(node: Node, source: str, branch_option_id: str) -> str | None:
    parts = _flatten_plus_chain(node, source)
    if parts is None:
        return None

    from c2o.parse.send_template import parse_options_member

    for index, part in enumerate(parts):
        if part.type != "member_expression":
            continue
        if parse_options_member(part, source) != branch_option_id:
            continue
        suffix_parts: list[str] = []
        for rest in parts[index + 1 :]:
            if rest.type != "string":
                return None
            suffix_parts.append(_decode_js_string(node_text(rest, source)))
        return "".join(suffix_parts)
    return None


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


def _toggle_branch_reads_instance_state(body: Node, source: str, branch_option_id: str) -> bool:
    for node in _walk_nodes(body):
        if node.type != "if_statement":
            continue
        condition = node.child_by_field_name("condition")
        consequence = node.child_by_field_name("consequence")
        if condition is None or consequence is None:
            continue
        parsed = parse_branch_condition(condition, source)
        if parsed is None:
            continue
        option_id, literal = parsed
        if option_id != branch_option_id or literal.lower() != "toggle":
            continue
        if callback_reads_instance_state(consequence, source):
            return True
    return False


def _params_without_branch_driver(
    base_params: dict[str, ParamEntry],
    branch_driver_id: str | None,
) -> dict[str, ParamEntry]:
    if branch_driver_id is None:
        return dict(base_params)
    return {key: value for key, value in base_params.items() if key != branch_driver_id}


def _callback_body(callback_node: Node) -> Node | None:
    if callback_node.type == "arrow_function":
        return callback_node.child_by_field_name("body")
    if callback_node.type in {"function", "function_expression"}:
        return callback_node.child_by_field_name("body")
    return None


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
