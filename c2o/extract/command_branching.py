"""Branch-splitting heuristics for Companion action → OpenAVC command mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from c2o.extract.param_schema import extract_static_choice_values
from c2o.model.driver import ParamEntry
from c2o.parse.js import node_text
from c2o.parse.send_template import (
    callback_has_options_access,
    callback_reads_instance_state,
    parse_branch_condition,
    resolve_send_in_block,
    snake_lower,
)


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
) -> SplitResult:
    """Split branch-driven actions or emit a single command candidate."""
    body = _callback_body(callback_node)
    if body is None:
        return SplitResult(())

    known_param_ids = set(base_params)

    if _is_whole_action_state_dependent(body, source):
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
