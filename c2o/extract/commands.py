"""Extract OpenAVC commands from Companion setActionDefinitions()."""

from __future__ import annotations

from typing import Any

from tree_sitter import Node

from c2o.extract.command_branching import SplitResult, split_or_single
from c2o.extract.http_commands import HttpCommandCandidate, extract_http_command
from c2o.extract.param_schema import build_params_from_options
from c2o.model.driver import CommandEntry, CommandsSection
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport
from c2o.parse.js import (
    ParsedModule,
    collect_inline_object_pairs,
    find_calls,
    node_text,
    resolve_object_via_assignments,
)
from c2o.parse.literals import UNRESOLVED, decode_js_value, pair_key
from c2o.parse.send_template import body_contains_send_call


class CommandsExtractionError(ValueError):
    """Raised when action definitions are malformed beyond recovery."""


def extract_commands(parsed: ParsedModule) -> tuple[CommandsSection, ReviewReport]:
    """Build commands from setActionDefinitions() and branch-split heuristics."""
    definitions = _collect_action_definitions(parsed)
    if not definitions:
        return CommandsSection(), ReviewReport()

    commands: dict[str, CommandEntry] = {}
    flags: list[ReviewFlag] = []

    for action_key, action_field, callback_node, source in definitions:
        if _callback_contains_parse_variables(callback_node, source):
            continue

        label = _action_label(action_field, action_key)
        help_text = _first_option_tooltip(action_field.get("options"))
        base_params = build_params_from_options(action_field.get("options"))

        body = _callback_body(callback_node)
        if body is not None and not body_contains_send_call(body, source):
            http_candidate = extract_http_command(
                action_key=action_key,
                label=label,
                callback_node=callback_node,
                source=source,
                base_params=base_params,
            )
            if http_candidate is not None:
                _merge_http_candidate(
                    http_candidate,
                    help_text=help_text,
                    commands=commands,
                )
                continue

        result = split_or_single(
            action_key=action_key,
            label=label,
            options=action_field.get("options"),
            callback_node=callback_node,
            source=source,
            base_params=base_params,
        )
        _merge_split_result(
            result,
            action_key=action_key,
            help_text=help_text,
            commands=commands,
            flags=flags,
        )

    return CommandsSection(commands=commands), ReviewReport(flags=tuple(flags))


def _merge_http_candidate(
    candidate: HttpCommandCandidate,
    *,
    help_text: str | None,
    commands: dict[str, CommandEntry],
) -> None:
    commands[candidate.command_key] = CommandEntry(
        label=candidate.label,
        method=candidate.method,
        path=candidate.path,
        body=candidate.body,
        headers=candidate.headers,
        query_params=candidate.query_params,
        help=help_text,
        params=candidate.params,
    )


def _merge_split_result(
    result: SplitResult,
    *,
    action_key: str,
    help_text: str | None,
    commands: dict[str, CommandEntry],
    flags: list[ReviewFlag],
) -> None:
    if result.state_dependent_reason is not None:
        flags.append(
            ReviewFlag(
                code=ReviewCode.STATE_DEPENDENT_BRANCH,
                field=f"commands.{action_key}",
                message=(
                    f"Action '{action_key}' contains runtime-state branching "
                    "that cannot be expressed in YAML."
                ),
                details={
                    "action_key": action_key,
                    "reason": result.state_dependent_reason,
                },
            )
        )

    for candidate in result.candidates:
        commands[candidate.command_key] = CommandEntry(
            label=candidate.label,
            send=candidate.send,
            help=help_text,
            params=candidate.params,
        )


def _collect_action_definitions(
    parsed: ParsedModule,
) -> list[tuple[str, dict[str, Any], Node, str]]:
    matches = find_calls(parsed, "setActionDefinitions", include_methods=True)
    if not matches:
        return []

    match = matches[0]
    source = parsed.sources[match.rel_path]
    if match.args_node is None:
        return []

    arg_nodes = list(match.args_node.named_children)
    if not arg_nodes:
        return []

    arg = arg_nodes[0]
    object_pairs: list[tuple[str, Node]] = []
    if arg.type == "object":
        object_pairs = collect_inline_object_pairs(arg, source)
    elif arg.type == "identifier":
        resolved = resolve_object_via_assignments(
            source=source,
            identifier_node=arg,
            call_node=match.node,
        )
        if resolved is not None:
            object_pairs = resolved

    definitions: list[tuple[str, dict[str, Any], Node, str]] = []
    for action_key, object_node in object_pairs:
        callback_node = _find_callback_node(object_node, source)
        if callback_node is None:
            continue
        action_field = _decode_action_metadata(object_node, source)
        definitions.append((action_key, action_field, callback_node, source))
    return definitions


def _decode_action_metadata(object_node: Node, source: str) -> dict[str, Any]:
    """Decode static action metadata, skipping non-literal callback values."""
    field: dict[str, Any] = {}
    for child in object_node.named_children:
        if child.type != "pair":
            continue
        key = pair_key(child, source)
        value_node = child.child_by_field_name("value")
        if key is None or value_node is None or key == "callback":
            continue
        value = decode_js_value(value_node, source)
        if value is not UNRESOLVED:
            field[key] = value
    return field


def _find_callback_node(object_node: Node, source: str) -> Node | None:
    for child in object_node.named_children:
        if child.type != "pair":
            continue
        key = pair_key(child, source)
        if key != "callback":
            continue
        value = child.child_by_field_name("value")
        if value is None:
            return None
        if value.type in {"arrow_function", "function", "function_expression"}:
            return value
    return None


def _callback_body(callback_node: Node) -> Node | None:
    if callback_node.type == "arrow_function":
        return callback_node.child_by_field_name("body")
    if callback_node.type in {"function", "function_expression"}:
        return callback_node.child_by_field_name("body")
    return None


def _action_label(action_field: dict[str, Any], action_key: str) -> str:
    name = action_field.get("name")
    if isinstance(name, str) and name:
        return name
    return action_key


def _first_option_tooltip(options: Any) -> str | None:
    if not isinstance(options, list):
        return None
    for option in options:
        if not isinstance(option, dict):
            continue
        tooltip = option.get("tooltip")
        if isinstance(tooltip, str) and tooltip:
            return tooltip
    return None


def _callback_contains_parse_variables(callback_node: Node, source: str) -> bool:
    for node in _walk_nodes(callback_node):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None:
            continue
        if "parseVariablesInString" in node_text(function, source):
            return True
    return False


def _walk_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes
