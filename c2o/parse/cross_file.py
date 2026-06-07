"""Conservative cross-file JavaScript resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit

from tree_sitter import Node

from c2o.parse.js import ParsedModule, node_text
from c2o.parse.literals import decode_js_string
from c2o.parse.send_template import resolve_string_expression


@dataclass(frozen=True)
class DefinitionObject:
    """A definition object resolved from a Companion factory function."""

    key: str
    node: Node
    source: str


@dataclass(frozen=True)
class ResolvedArrayConstant:
    """An exported array constant and the source text that owns its AST node."""

    node: Node
    source: str


@dataclass(frozen=True)
class SendHelperTemplate:
    """URL shape for a simple Companion HTTP send helper."""

    path_template: str


@dataclass(frozen=True)
class ResolvedSendHelper:
    """A statically resolved HTTP helper call."""

    path: str
    query_params: dict[str, str] | None = None


@dataclass(frozen=True)
class ResolvedFunction:
    """A statically resolved JavaScript function declaration."""

    rel_path: str
    node: Node
    body: Node
    source: str


SEND_HELPERS: dict[str, SendHelperTemplate] = {
    "sendPTZ": SendHelperTemplate(path_template="/cgi-bin/aw_ptz?cmd=%23{cmd}&res=1"),
    "sendCam": SendHelperTemplate(path_template="/cgi-bin/aw_cam?cmd={cmd}&res=1"),
    "sendWeb": SendHelperTemplate(path_template="/cgi-bin/{cmd}"),
}


def resolve_factory_call_definitions(
    arg_node: Node,
    parsed: ParsedModule,
    *,
    source: str,
) -> list[DefinitionObject] | None:
    """Resolve ``set*Definitions(factory(this))`` into definition object nodes."""
    callee = _call_identifier(arg_node, source)
    if callee is None:
        return None

    function = _find_single_function(parsed, callee)
    if function is None:
        return None

    rel_path, function_node, body = function
    source = parsed.sources[rel_path]
    returned = _returned_identifier(body, source)
    if returned is None:
        return None

    declarator = _find_empty_declarator(body, source, returned)
    if declarator is None:
        return None

    value = declarator.child_by_field_name("value")
    if value is None:
        return None

    if value.type == "object":
        pairs = _collect_object_assignments(
            body,
            source,
            returned,
            after_byte=declarator.end_byte,
        )
        return [DefinitionObject(key=key, node=node, source=source) for key, node in pairs]

    if value.type == "array":
        objects = _collect_array_push_objects(
            body,
            source,
            returned,
            after_byte=declarator.end_byte,
        )
        definitions: list[DefinitionObject] = []
        for node in objects:
            key = _object_literal_string_field(node, source, "variableId")
            if key is not None:
                definitions.append(DefinitionObject(key=key, node=node, source=source))
        return definitions

    return None


def resolve_exported_array_constant(
    name: str,
    declaring_rel: str,
    parsed: ParsedModule,
) -> ResolvedArrayConstant | None:
    """Resolve an imported/exported array constant used by ``return NAME``."""
    same_file = _find_exported_array(parsed, declaring_rel, name)
    if same_file is not None:
        return same_file

    source = parsed.sources.get(declaring_rel)
    tree = parsed.trees.get(declaring_rel)
    if source is None or tree is None:
        return None

    imported_rel = _resolve_named_import(source, tree.root_node, declaring_rel, name)
    if imported_rel is None:
        return None
    return _find_exported_array(parsed, imported_rel, name)


def resolve_single_function(parsed: ParsedModule, name: str) -> ResolvedFunction | None:
    """Resolve a single function declaration by name across parsed files."""
    function = _find_single_function(parsed, name)
    if function is None:
        return None
    rel_path, node, body = function
    return ResolvedFunction(
        rel_path=rel_path,
        node=node,
        body=body,
        source=parsed.sources[rel_path],
    )


def resolve_send_helper_call(
    body: Node,
    source: str,
    known_param_ids: set[str],
) -> ResolvedSendHelper | None:
    """Resolve the first static ``sendPTZ``/``sendCam``/``sendWeb`` helper call."""
    for call in _iter_nodes(body):
        if call.type != "call_expression":
            continue
        function = call.child_by_field_name("function")
        if function is None or function.type != "identifier":
            continue
        helper_name = node_text(function, source)
        helper = SEND_HELPERS.get(helper_name)
        if helper is None:
            continue
        args = call.child_by_field_name("arguments")
        if args is None or len(args.named_children) < 2:
            continue
        payload = resolve_string_expression(
            args.named_children[1],
            scope=body,
            source=source,
            known_param_ids=known_param_ids,
        )
        if payload is None:
            continue
        raw_path = helper.path_template.replace("{cmd}", payload)
        path, query_params = _decompose_path(raw_path)
        return ResolvedSendHelper(path=path, query_params=query_params or None)
    return None


def call_body_contains_send_helper(body: Node, source: str) -> bool:
    """Return True when a callback contains a known HTTP send-helper call."""
    for node in _iter_nodes(body):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is not None and function.type == "identifier":
            if node_text(function, source) in SEND_HELPERS:
                return True
    return False


def _call_identifier(node: Node, source: str) -> str | None:
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None
    return node_text(function, source)


def _find_single_function(
    parsed: ParsedModule,
    name: str,
) -> tuple[str, Node, Node] | None:
    matches: list[tuple[str, Node, Node]] = []
    for rel_path, tree in parsed.trees.items():
        source = parsed.sources[rel_path]
        for node in _iter_nodes(tree.root_node):
            function = _function_declaration_node(node)
            if function is None:
                continue
            name_node = function.child_by_field_name("name")
            body = function.child_by_field_name("body")
            if name_node is None or body is None:
                continue
            if node_text(name_node, source) == name:
                matches.append((rel_path, function, body))
    return matches[0] if len(matches) == 1 else None


def _function_declaration_node(node: Node) -> Node | None:
    if node.type == "function_declaration":
        if node.parent is not None and node.parent.type == "export_statement":
            return None
        return node
    if node.type != "export_statement":
        return None
    for child in node.named_children:
        if child.type == "function_declaration":
            return child
    return None


def _returned_identifier(body: Node, source: str) -> str | None:
    returned: str | None = None
    for node in _iter_nodes(body):
        if node.type != "return_statement":
            continue
        named = list(node.named_children)
        if len(named) != 1 or named[0].type != "identifier":
            continue
        returned = node_text(named[0], source)
    return returned


def _find_empty_declarator(body: Node, source: str, identifier: str) -> Node | None:
    found: Node | None = None
    for node in _iter_nodes(body):
        if node.type != "variable_declarator":
            continue
        name_node = node.child_by_field_name("name")
        value = node.child_by_field_name("value")
        if name_node is None or value is None:
            continue
        if node_text(name_node, source) != identifier:
            continue
        if value.type not in {"object", "array"} or value.named_child_count != 0:
            continue
        if found is None or node.start_byte > found.start_byte:
            found = node
    return found


def _collect_object_assignments(
    body: Node,
    source: str,
    identifier: str,
    *,
    after_byte: int,
) -> list[tuple[str, Node]]:
    pairs: list[tuple[str, Node]] = []
    for node in _iter_nodes(body):
        if node.type != "assignment_expression" or node.start_byte <= after_byte:
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or right.type != "object":
            continue
        key = _assignment_object_key(left, source, identifier)
        if key is not None:
            pairs.append((key, right))
    return pairs


def _collect_array_push_objects(
    body: Node,
    source: str,
    identifier: str,
    *,
    after_byte: int,
) -> list[Node]:
    objects: list[Node] = []
    for node in _iter_nodes(body):
        if node.type != "call_expression" or node.start_byte <= after_byte:
            continue
        function = node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            continue
        obj = function.child_by_field_name("object")
        prop = function.child_by_field_name("property")
        if obj is None or prop is None:
            continue
        if node_text(obj, source) != identifier or node_text(prop, source) != "push":
            continue
        args = node.child_by_field_name("arguments")
        if args is None:
            continue
        for arg in args.named_children:
            if arg.type == "object":
                objects.append(arg)
    return objects


def _assignment_object_key(left: Node, source: str, identifier: str) -> str | None:
    if left.type == "subscript_expression":
        obj = left.child_by_field_name("object")
        index = left.child_by_field_name("index")
        if obj is None or index is None:
            return None
        if node_text(obj, source) != identifier or index.type != "string":
            return None
        return decode_js_string(node_text(index, source))

    if left.type == "member_expression":
        obj = left.child_by_field_name("object")
        prop = left.child_by_field_name("property")
        if obj is None or prop is None:
            return None
        if node_text(obj, source) != identifier:
            return None
        return node_text(prop, source)

    return None


def _object_literal_string_field(node: Node, source: str, field: str) -> str | None:
    if node.type != "object":
        return None
    for child in node.named_children:
        if child.type != "pair":
            continue
        key_node = child.child_by_field_name("key")
        value = child.child_by_field_name("value")
        if key_node is None or value is None:
            continue
        key = node_text(key_node, source)
        if key_node.type == "string":
            key = decode_js_string(key)
        if key != field or value.type != "string":
            continue
        return decode_js_string(node_text(value, source))
    return None


def _find_exported_array(
    parsed: ParsedModule,
    rel_path: str,
    name: str,
) -> ResolvedArrayConstant | None:
    tree = parsed.trees.get(rel_path)
    source = parsed.sources.get(rel_path)
    if tree is None or source is None:
        return None
    for node in _iter_nodes(tree.root_node):
        if node.type != "variable_declarator":
            continue
        name_node = node.child_by_field_name("name")
        value = node.child_by_field_name("value")
        if name_node is None or value is None or value.type != "array":
            continue
        if node_text(name_node, source) == name:
            return ResolvedArrayConstant(node=value, source=source)
    return None


def _resolve_named_import(
    source: str,
    root: Node,
    declaring_rel: str,
    imported_name: str,
) -> str | None:
    for node in _iter_nodes(root):
        if node.type != "import_statement":
            continue
        text = node_text(node, source)
        if imported_name not in text:
            continue
        import_path = _import_path_from_statement(node, source)
        if import_path is None:
            continue
        return _resolve_relative_import(declaring_rel, import_path)
    return None


def _import_path_from_statement(node: Node, source: str) -> str | None:
    for child in node.children:
        if child.type == "string":
            return decode_js_string(node_text(child, source))
    return None


def _resolve_relative_import(declaring_rel: str, import_path: str) -> str | None:
    if not import_path.startswith("."):
        return None
    base_parts = declaring_rel.split("/")[:-1]
    parts: list[str] = []
    for part in [*base_parts, *import_path.split("/")]:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    rel = "/".join(parts)
    return rel if rel.endswith(".js") else f"{rel}.js"


def _decompose_path(raw_path: str) -> tuple[str, dict[str, str]]:
    parts = urlsplit(raw_path)
    path = parts.path or "/"
    query_params: dict[str, str] = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key not in query_params:
            query_params[key] = value
    return path, query_params


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes
