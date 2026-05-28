"""Extract OpenAVC state variables from Companion setVariableDefinitions()."""

from __future__ import annotations

from typing import cast

from tree_sitter import Node

from c2o.model.driver import StateVariableEntry, StateVariablesSection, StateVariableType
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport
from c2o.parse.js import ParsedModule, find_calls, node_text, resolve_array_via_pushes
from c2o.parse.literals import UNRESOLVED, decode_object, pair_key

_TYPE_PRECEDENCE: tuple[StateVariableType, ...] = ("boolean", "integer", "number", "string")
_BOOLEAN_METHODS = frozenset({"includes", "startsWith", "endsWith", "test"})
_STRING_METHODS = frozenset(
    {
        "slice",
        "substr",
        "substring",
        "trim",
        "toString",
        "toLowerCase",
        "toUpperCase",
        "replace",
        "split",
        "padStart",
        "padEnd",
        "concat",
        "repeat",
    }
)
_COMPARISON_OPERATORS = frozenset({"==", "===", "!=", "!==", "<", ">", "<=", ">="})


class StateVariablesExtractionError(ValueError):
    """Raised when state variable definitions are malformed beyond recovery."""


def extract_state_variables(
    parsed: ParsedModule,
) -> tuple[StateVariablesSection, ReviewReport]:
    """Build state_variables from setVariableDefinitions() and infer types."""
    definitions = _collect_definitions(parsed)
    if not definitions:
        return StateVariablesSection(), ReviewReport()

    candidates = _collect_type_candidates(parsed, {var_id for var_id, _ in definitions})
    state_variables: dict[str, StateVariableEntry] = {}
    flags: list[ReviewFlag] = []

    for variable_id, label in definitions:
        final_type, evidence = _resolve_type(variable_id, candidates)
        state_variables[variable_id] = StateVariableEntry(label=label, type=final_type)
        flags.append(
            ReviewFlag(
                code=ReviewCode.INFERRED_STATE_TYPE,
                field=f"state_variables.{variable_id}",
                message=(
                    f"Type for state variable '{variable_id}' was inferred as '{final_type}'."
                ),
                details={
                    "variable_id": variable_id,
                    "inferred_type": final_type,
                    "evidence": evidence,
                },
            )
        )

    return StateVariablesSection(state_variables=state_variables), ReviewReport(flags=tuple(flags))


def _collect_definitions(parsed: ParsedModule) -> list[tuple[str, str]]:
    matches = find_calls(parsed, "setVariableDefinitions", include_methods=True)
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
    object_nodes: list[Node] = []
    if arg.type == "array":
        object_nodes = [child for child in arg.named_children if child.type == "object"]
    elif arg.type == "identifier":
        resolved = resolve_array_via_pushes(
            source=source,
            identifier_node=arg,
            call_node=match.node,
        )
        if resolved is not None:
            object_nodes = resolved

    definitions: list[tuple[str, str]] = []
    for obj in object_nodes:
        raw = decode_object(obj, source)
        if raw is UNRESOLVED:
            continue
        field = cast(dict[str, object], raw)
        variable_id = field.get("variableId")
        if not isinstance(variable_id, str):
            continue
        name = field.get("name")
        label = name if isinstance(name, str) and name else variable_id
        definitions.append((variable_id, label))
    return definitions


def _collect_type_candidates(
    parsed: ParsedModule,
    known_ids: set[str],
) -> dict[str, list[tuple[StateVariableType, str]]]:
    candidates: dict[str, list[tuple[StateVariableType, str]]] = {
        var_id: [] for var_id in known_ids
    }
    for match in find_calls(parsed, "setVariableValues", include_methods=True):
        source = parsed.sources[match.rel_path]
        if match.args_node is None:
            continue
        arg_nodes = list(match.args_node.named_children)
        if not arg_nodes or arg_nodes[0].type != "object":
            continue
        for pair in arg_nodes[0].named_children:
            if pair.type != "pair":
                continue
            key = pair_key(pair, source)
            if key is None or key not in known_ids:
                continue
            value_node = pair.child_by_field_name("value")
            if value_node is None:
                continue
            candidate_type, evidence = _classify_value(value_node, source)
            if candidate_type is not None:
                candidates[key].append((candidate_type, evidence))
    return candidates


def _resolve_type(
    variable_id: str,
    candidates: dict[str, list[tuple[StateVariableType, str]]],
) -> tuple[StateVariableType, str]:
    hits = candidates.get(variable_id, [])
    if not hits:
        return "string", "fallback"

    types_present = {candidate_type for candidate_type, _ in hits}
    if "integer" in types_present and "number" in types_present:
        types_present.discard("integer")

    for preferred in _TYPE_PRECEDENCE:
        if preferred in types_present:
            evidence = next(
                evidence for candidate_type, evidence in hits if candidate_type == preferred
            )
            return preferred, evidence
    return "string", "fallback"


def _classify_value(node: Node, source: str) -> tuple[StateVariableType | None, str]:
    if node.type == "true" or node.type == "false":
        return "boolean", "literal"
    if node.type == "number":
        text = node_text(node, source)
        if "." in text or "e" in text.lower():
            return "number", "literal"
        return "integer", "literal"
    if node.type in {"string", "template_string"}:
        return "string", "literal"
    if node.type == "unary_expression":
        inner = node.named_children[0] if node.named_children else None
        if inner is not None and inner.type == "number":
            text = node_text(node, source)
            if "." in text or "e" in text.lower():
                return "number", "literal"
            return "integer", "literal"
    if node.type == "call_expression":
        return _classify_call(node, source)
    if node.type == "binary_expression":
        operator = node.child_by_field_name("operator")
        if operator is not None and node_text(operator, source) in _COMPARISON_OPERATORS:
            return "boolean", "comparison"
    if node.type == "subscript_expression":
        obj = node.child_by_field_name("object")
        if obj is not None and obj.type == "call_expression":
            call_type, evidence = _classify_call(obj, source)
            if call_type == "string":
                return "string", evidence
    return None, ""


def _classify_call(node: Node, source: str) -> tuple[StateVariableType | None, str]:
    function = node.child_by_field_name("function")
    if function is None:
        return None, ""

    if function.type == "identifier":
        name = node_text(function, source)
        if name == "parseInt":
            return "integer", "call"
        if name == "parseFloat":
            return "number", "call"
        if name == "Number":
            args = node.child_by_field_name("arguments")
            if args is not None and args.named_child_count == 1:
                arg = args.named_children[0]
                if arg.type == "number":
                    text = node_text(arg, source)
                    if "." in text or "e" in text.lower():
                        return "number", "call"
                    return "integer", "call"
            return "number", "call"

    if function.type == "member_expression":
        prop = function.child_by_field_name("property")
        if prop is None:
            return None, ""
        method = node_text(prop, source)
        if method in _BOOLEAN_METHODS:
            return "boolean", "call"
        if method in _STRING_METHODS:
            return "string", "call"

    return None, ""
