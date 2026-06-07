"""Extract OpenAVC commands from Companion setActionDefinitions()."""

from __future__ import annotations

from typing import Any

from tree_sitter import Node

from c2o.extract.command_branching import SplitResult, split_or_single
from c2o.extract.http_commands import HttpCommandCandidate, extract_http_command
from c2o.extract.identifiers import normalize_identifier
from c2o.extract.param_schema import build_params_from_options
from c2o.model.driver import CommandEntry, CommandsSection
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport
from c2o.parse.cross_file import (
    DefinitionObject,
    call_body_contains_send_helper,
    resolve_factory_call_definitions,
)
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
            if call_body_contains_send_helper(body, source):
                flags.append(
                    ReviewFlag(
                        code=ReviewCode.STATE_DEPENDENT_BRANCH,
                        field=f"commands.{action_key}",
                        message=(
                            f"Action '{action_key}' calls an HTTP send helper with "
                            "a payload that cannot be reconstructed statically."
                        ),
                        details={
                            "action_key": action_key,
                            "reason": "http_send_helper_dynamic",
                        },
                    )
                )
                continue

        result = split_or_single(
            action_key=action_key,
            label=label,
            options=action_field.get("options"),
            callback_node=callback_node,
            source=source,
            base_params=base_params,
            parsed=parsed,
        )
        _merge_split_result(
            result,
            action_key=action_key,
            help_text=help_text,
            commands=commands,
            flags=flags,
        )

    commands, normalize_flags = _normalize_command_ids(commands)
    flags.extend(normalize_flags)

    return CommandsSection(commands=commands), ReviewReport(flags=tuple(flags))


def _normalize_command_ids(
    commands: dict[str, CommandEntry],
) -> tuple[dict[str, CommandEntry], list[ReviewFlag]]:
    """Normalize Companion action ids to snake_case OpenAVC command ids.

    Companion modules name actions in mixed conventions (e.g. ``zoomS``,
    ``recallPset``). OpenAVC command ids are snake_case, so they are normalized
    here. Each rename is review-flagged, and collisions get a numeric suffix so
    every command keeps a unique id.
    """
    normalized: dict[str, CommandEntry] = {}
    flags: list[ReviewFlag] = []
    for original, entry in commands.items():
        new_id = _unique_command_id(normalize_identifier(original), normalized)
        normalized[new_id] = entry
        if new_id != original:
            flags.append(
                ReviewFlag(
                    code=ReviewCode.COMMAND_ID_NORMALIZED,
                    field=f"commands.{new_id}",
                    message=f"Command id '{original}' was normalized to '{new_id}'.",
                    details={"old": original, "new": new_id},
                )
            )
    return normalized, flags


def _unique_command_id(candidate: str, taken: dict[str, CommandEntry]) -> str:
    if candidate not in taken:
        return candidate
    suffix = 2
    while f"{candidate}_{suffix}" in taken:
        suffix += 1
    return f"{candidate}_{suffix}"


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
    definitions_nodes: list[DefinitionObject] = []
    if arg.type == "object":
        definitions_nodes = [
            DefinitionObject(key=key, node=node, source=source)
            for key, node in collect_inline_object_pairs(arg, source)
        ]
    elif arg.type == "identifier":
        resolved = resolve_object_via_assignments(
            source=source,
            identifier_node=arg,
            call_node=match.node,
        )
        if resolved is not None:
            definitions_nodes = [
                DefinitionObject(key=key, node=node, source=source) for key, node in resolved
            ]
    elif arg.type == "call_expression":
        resolved_factory = resolve_factory_call_definitions(arg, parsed, source=source)
        if resolved_factory is not None:
            definitions_nodes = resolved_factory

    definitions: list[tuple[str, dict[str, Any], Node, str]] = []
    for definition in definitions_nodes:
        callback_node = _find_callback_node(definition.node, definition.source)
        if callback_node is None:
            continue
        action_field = _decode_action_metadata(definition.node, definition.source)
        definitions.append((definition.key, action_field, callback_node, definition.source))
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
