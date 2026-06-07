"""Extract OpenAVC polling queries from Companion setInterval handlers."""

from __future__ import annotations

from tree_sitter import Node

from c2o.model.driver import PollingSection
from c2o.model.review import ReviewReport
from c2o.parse.cross_file import resolve_exported_array_constant
from c2o.parse.js import ParsedModule, node_text
from c2o.parse.literals import decode_js_string as _decode_js_string
from c2o.parse.polling_handlers import find_polling_handlers, infer_poll_interval_seconds
from c2o.parse.send_template import resolve_all_static_sends


class PollingExtractionError(ValueError):
    """Raised when polling extraction encounters unrecoverable malformed input."""


def extract_polling(parsed: ParsedModule) -> tuple[PollingSection, ReviewReport]:
    """Build polling queries and optional inferred poll cadence from setInterval handlers."""
    handlers = find_polling_handlers(parsed)
    queries: list[str] = []
    seen: set[str] = set()
    inferred_interval: int | None = None

    for handler in handlers:
        new_queries = resolve_all_static_sends(handler.callback_body, handler.source)
        new_queries.extend(_expand_named_array_sends(handler.callback_body, handler.source, parsed))
        for q in new_queries:
            if q not in seen:
                seen.add(q)
                queries.append(q)
        if inferred_interval is None:
            inferred_interval = infer_poll_interval_seconds(handler.delay_ms_node, handler.source)

    return (
        PollingSection(
            queries=tuple(queries),
            inferred_poll_interval=inferred_interval,
        ),
        ReviewReport(),
    )


def _expand_named_array_sends(body: Node, source: str, parsed: ParsedModule) -> list[str]:
    """Expand ``sendCommand(SomeArray[variable])`` patterns to all array elements.

    When a polling callback calls ``this.sendCommand(NamedArray[index])`` where
    ``NamedArray`` is an exported array constant (e.g. ``PollCommands``), return
    all string elements of that array as polling queries.
    """
    queries: list[str] = []
    for node in _iter_nodes(body):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None:
            continue
        # Match both bare sendCommand(…) and this.sendCommand(…)
        is_send = False
        if function.type == "identifier" and node_text(function, source) == "sendCommand":
            is_send = True
        elif function.type == "member_expression":
            prop = function.child_by_field_name("property")
            if prop is not None and node_text(prop, source) == "sendCommand":
                is_send = True
        if not is_send:
            continue
        args = node.child_by_field_name("arguments")
        if args is None or args.named_child_count == 0:
            continue
        arg = args.named_children[0]
        if arg.type != "subscript_expression":
            continue
        arr_obj = arg.child_by_field_name("object")
        if arr_obj is None or arr_obj.type != "identifier":
            continue
        array_name = node_text(arr_obj, source)
        # Try to find this array in the parsed module
        rel_path = _find_rel_path_for_node(body, parsed)
        if rel_path is None:
            continue
        resolved = resolve_exported_array_constant(array_name, rel_path, parsed)
        if resolved is None:
            continue
        queries.extend(_string_elements_of_array(resolved.node, resolved.source))
    return queries


def _string_elements_of_array(array_node: Node, source: str) -> list[str]:
    """Return string literals from an array node."""
    results: list[str] = []
    if array_node.type != "array":
        return results
    for child in array_node.named_children:
        if child.type == "string":
            raw = node_text(child, source)
            value = _decode_js_string(raw)
            if value and value not in results:
                results.append(value)
    return results


def _find_rel_path_for_node(body: Node, parsed: ParsedModule) -> str | None:
    """Return the rel_path in the parsed module whose tree contains body."""
    for rel_path, tree in parsed.trees.items():
        root = tree.root_node
        if body.start_byte >= root.start_byte and body.end_byte <= root.end_byte:
            return rel_path
    return None


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes
