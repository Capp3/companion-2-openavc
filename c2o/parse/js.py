"""Tree-sitter JavaScript parser bootstrap for Companion module sources."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Node, Parser, Query, QueryCursor, Tree

_JS_LANGUAGE = Language(tsjs.language())
_PARSER = Parser(_JS_LANGUAGE)
_QUERIES_PACKAGE = "c2o.parse.queries"

# Companion modules typically keep logic in these root-level files.
_DEFAULT_JS_FILES = (
    "index.js",
    "actions.js",
    "variables.js",
    "feedback.js",
    "presets.js",
    "upgrades.js",
)


@dataclass
class ParsedModule:
    """Parsed JavaScript sources for a Companion module directory."""

    root: Path
    sources: dict[str, str] = field(default_factory=dict)
    trees: dict[str, Tree] = field(default_factory=dict)


@dataclass(frozen=True)
class CallMatch:
    """A JavaScript call expression matched in a parsed module."""

    rel_path: str
    function_text: str
    node: Node
    args_node: Node | None


@dataclass(frozen=True)
class MethodMatch:
    """A JavaScript class method definition matched in a parsed module."""

    rel_path: str
    name: str
    node: Node
    body: Node | None


@dataclass(frozen=True)
class StringTemplate:
    """A simple string-concat expression represented as a template."""

    template: str
    placeholders: list[str]


@dataclass(frozen=True)
class RegexLiteral:
    """A JavaScript regex literal matched in a parsed module."""

    rel_path: str
    pattern: str
    flags: str
    node: Node


def get_parser() -> Parser:
    """Return a tree-sitter parser configured for JavaScript."""
    return Parser(_JS_LANGUAGE)


@cache
def _load_query(name: str) -> Query:
    """Load and compile a tree-sitter query from `c2o/parse/queries`."""
    query_name = name if name.endswith(".scm") else f"{name}.scm"
    query_source = (
        resources.files(_QUERIES_PACKAGE).joinpath(query_name).read_text(encoding="utf-8")
    )
    return Query(_JS_LANGUAGE, query_source)


def node_text(node: Node, source: str) -> str:
    """Return source text covered by a tree-sitter node."""
    return source.encode("utf-8")[node.start_byte : node.end_byte].decode("utf-8")


def parse_source(source: str, *, path: str = "<string>") -> Tree:
    """Parse JavaScript source text into a syntax tree."""
    data = source.encode("utf-8")
    tree = _PARSER.parse(data)
    if tree.root_node.has_error:
        msg = f"{path}: JavaScript parse tree contains syntax errors"
        raise ValueError(msg)
    return tree


def iter_js_files(root: Path) -> list[Path]:
    """List parseable `.js` files at the module root."""
    files: list[Path] = []
    for name in _DEFAULT_JS_FILES:
        path = root / name
        if path.is_file():
            files.append(path)
    return files


def parse_module(root: Path) -> ParsedModule:
    """Parse all standard JS files under a Companion module root."""
    root = root.resolve()
    parsed = ParsedModule(root=root)
    for path in iter_js_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        parsed.sources[rel] = text
        parsed.trees[rel] = parse_source(text, path=str(path))
    if not parsed.sources:
        msg = f"{root}: no JavaScript source files found"
        raise ValueError(msg)
    return parsed


def find_calls(
    parsed: ParsedModule,
    function_name: str,
    *,
    include_methods: bool = True,
) -> list[CallMatch]:
    """Find calls to `function_name(...)` or, optionally, `*.function_name(...)`."""
    query = _load_query("call_expression")
    hits: list[CallMatch] = []
    for rel, tree in parsed.trees.items():
        source = parsed.sources[rel]
        for _, captures in QueryCursor(query).matches(tree.root_node):
            direct_names = captures.get("function.name", [])
            property_names = captures.get("function.property", [])
            member_nodes = captures.get("function.member", [])
            call_nodes = captures.get("call", [])
            args_nodes = captures.get("function.arguments", [])
            if not call_nodes:
                continue

            function_text: str | None = None
            if direct_names and node_text(direct_names[0], source) == function_name:
                function_text = node_text(direct_names[0], source)
            elif include_methods and property_names and member_nodes:
                if node_text(property_names[0], source) == function_name:
                    function_text = node_text(member_nodes[0], source)

            if function_text is None:
                continue

            args_node = args_nodes[0] if args_nodes else None
            hits.append(
                CallMatch(
                    rel_path=rel,
                    function_text=function_text,
                    node=call_nodes[0],
                    args_node=args_node,
                )
            )
    return hits


def find_method_definitions(parsed: ParsedModule, name: str) -> list[MethodMatch]:
    """Find class method definitions named `name`."""
    return [match for match in find_all_method_definitions(parsed) if match.name == name]


def find_all_method_definitions(parsed: ParsedModule) -> list[MethodMatch]:
    """Find every class method definition in a parsed module."""
    query = _load_query("method_definition")
    hits: list[MethodMatch] = []
    for rel, tree in parsed.trees.items():
        source = parsed.sources[rel]
        for _, captures in QueryCursor(query).matches(tree.root_node):
            name_nodes = captures.get("method.name", [])
            method_nodes = captures.get("method", [])
            body_nodes = captures.get("method.body", [])
            if not name_nodes or not method_nodes:
                continue
            method_name = node_text(name_nodes[0], source)
            hits.append(
                MethodMatch(
                    rel_path=rel,
                    name=method_name,
                    node=method_nodes[0],
                    body=body_nodes[0] if body_nodes else None,
                )
            )
    return hits


def resolve_array_via_pushes(
    *,
    source: str,
    identifier_node: Node,
    call_node: Node,
) -> list[Node] | None:
    """Resolve an identifier referencing an array literal built via `.push()` calls.

    Walks the nearest enclosing function body and returns object-literal nodes
    pushed onto the identifier. Returns ``None`` when the binding cannot be
    resolved statically.
    """
    if identifier_node.type != "identifier":
        return None

    identifier = node_text(identifier_node, source)
    scope_body = _enclosing_function_body(call_node)
    if scope_body is None:
        return None

    declarator = _find_empty_array_declarator(
        scope_body,
        source,
        identifier,
        before_byte=call_node.start_byte,
    )
    if declarator is None:
        return None

    return _collect_push_objects(
        scope_body,
        source,
        identifier,
        after_byte=declarator.end_byte,
        before_byte=call_node.start_byte,
    )


def _enclosing_function_body(node: Node) -> Node | None:
    current: Node | None = node
    while current is not None:
        if current.type == "statement_block":
            parent = current.parent
            if parent is not None and parent.type in {
                "function_declaration",
                "method_definition",
                "arrow_function",
                "function_expression",
                "function",
            }:
                return current
        current = current.parent
    return None


def _find_empty_array_declarator(
    body: Node,
    source: str,
    identifier: str,
    *,
    before_byte: int,
) -> Node | None:
    found: Node | None = None
    for node in _walk_nodes(body):
        if node.type != "variable_declarator":
            continue
        if node.start_byte >= before_byte:
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None or node_text(name_node, source) != identifier:
            continue
        value = node.child_by_field_name("value")
        if value is None or value.type != "array" or value.named_child_count != 0:
            continue
        if found is None or node.start_byte > found.start_byte:
            found = node
    return found


def _collect_push_objects(
    body: Node,
    source: str,
    identifier: str,
    *,
    after_byte: int,
    before_byte: int,
) -> list[Node]:
    objects: list[Node] = []
    for node in _walk_nodes(body):
        if node.type != "call_expression":
            continue
        if not (after_byte <= node.start_byte < before_byte):
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


def resolve_object_via_assignments(
    *,
    source: str,
    identifier_node: Node,
    call_node: Node,
) -> list[tuple[str, Node]] | None:
    """Resolve an identifier referencing an object built via property assignments.

    Walks the nearest enclosing function body and returns ``(key, object_node)``
    pairs assigned onto the identifier before the call. Returns ``None`` when
    the binding cannot be resolved statically.
    """
    if identifier_node.type != "identifier":
        return None

    identifier = node_text(identifier_node, source)
    scope_body = _enclosing_function_body(call_node)
    if scope_body is None:
        return None

    declarator = _find_empty_object_declarator(
        scope_body,
        source,
        identifier,
        before_byte=call_node.start_byte,
    )
    if declarator is None:
        return None

    return _collect_object_assignments(
        scope_body,
        source,
        identifier,
        after_byte=declarator.end_byte,
        before_byte=call_node.start_byte,
    )


def collect_inline_object_pairs(arg_node: Node, source: str) -> list[tuple[str, Node]]:
    """Collect ``(key, object_node)`` pairs from an inline object literal argument."""
    from c2o.parse.literals import pair_key

    if arg_node.type != "object":
        return []

    pairs: list[tuple[str, Node]] = []
    for child in arg_node.named_children:
        if child.type != "pair":
            continue
        key = pair_key(child, source)
        if key is None:
            continue
        value = child.child_by_field_name("value")
        if value is not None and value.type == "object":
            pairs.append((key, value))
    return pairs


def _find_empty_object_declarator(
    body: Node,
    source: str,
    identifier: str,
    *,
    before_byte: int,
) -> Node | None:
    found: Node | None = None
    for node in _walk_nodes(body):
        if node.type != "variable_declarator":
            continue
        if node.start_byte >= before_byte:
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None or node_text(name_node, source) != identifier:
            continue
        value = node.child_by_field_name("value")
        if value is None or value.type != "object" or value.named_child_count != 0:
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
    before_byte: int,
) -> list[tuple[str, Node]]:
    pairs: list[tuple[str, Node]] = []
    for node in _walk_nodes(body):
        if node.type != "assignment_expression":
            continue
        if not (after_byte <= node.start_byte < before_byte):
            continue
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or right.type != "object":
            continue
        key = _assignment_object_key(left, source, identifier)
        if key is None:
            continue
        pairs.append((key, right))
    return pairs


def _assignment_object_key(left: Node, source: str, identifier: str) -> str | None:
    if left.type == "subscript_expression":
        obj = left.child_by_field_name("object")
        index = left.child_by_field_name("index")
        if obj is None or index is None:
            return None
        if node_text(obj, source) != identifier:
            return None
        if index.type == "string":
            return _decode_js_string(node_text(index, source))
        return None

    if left.type == "member_expression":
        obj = left.child_by_field_name("object")
        prop = left.child_by_field_name("property")
        if obj is None or prop is None:
            return None
        if node_text(obj, source) != identifier:
            return None
        return node_text(prop, source)

    return None


def _walk_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes


def extract_string_concat(node: Node, source: str) -> StringTemplate | None:
    """Flatten a simple `+` string concat expression into a template.

    Identifiers and member expressions become placeholders. Complex operands
    such as function calls are intentionally rejected until an extractor needs
    wider JavaScript expression support.
    """
    parts = _flatten_concat_parts(node, source)
    if parts is None:
        return None

    template_parts: list[str] = []
    placeholders: list[str] = []
    for kind, value in parts:
        if kind == "text":
            template_parts.append(value)
        else:
            template_parts.append(f"{{{value}}}")
            placeholders.append(value)
    return StringTemplate(template="".join(template_parts), placeholders=placeholders)


def find_regex_literals(parsed: ParsedModule) -> list[RegexLiteral]:
    """Find every JavaScript `/pattern/flags` literal in a parsed module."""
    query = _load_query("regex_literal")
    hits: list[RegexLiteral] = []
    for rel, tree in parsed.trees.items():
        source = parsed.sources[rel]
        for _, captures in QueryCursor(query).matches(tree.root_node):
            regex_nodes = captures.get("regex", [])
            pattern_nodes = captures.get("regex.pattern", [])
            if not regex_nodes or not pattern_nodes:
                continue
            flags_nodes = captures.get("regex.flags", [])
            hits.append(
                RegexLiteral(
                    rel_path=rel,
                    pattern=node_text(pattern_nodes[0], source),
                    flags=node_text(flags_nodes[0], source) if flags_nodes else "",
                    node=regex_nodes[0],
                )
            )
    return hits


def collect_import_binding_names(tree: Tree, source: str) -> set[str]:
    """Collect identifiers introduced by import declarations."""
    names: set[str] = set[str]()
    _walk_imports(tree.root_node, source, names)
    return names


def _flatten_concat_parts(node: Node, source: str) -> list[tuple[str, str]] | None:
    if node.type == "parenthesized_expression" and node.named_child_count == 1:
        return _flatten_concat_parts(node.named_children[0], source)

    if node.type == "binary_expression":
        operator = node.child_by_field_name("operator")
        if operator is None or node_text(operator, source) != "+":
            return None
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return None
        left_parts = _flatten_concat_parts(left, source)
        right_parts = _flatten_concat_parts(right, source)
        if left_parts is None or right_parts is None:
            return None
        return [*left_parts, *right_parts]

    if node.type == "string":
        return [("text", _decode_js_string(node_text(node, source)))]

    if node.type in {"identifier", "member_expression"}:
        return [("placeholder", node_text(node, source))]

    return None


def _decode_js_string(raw: str) -> str:
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw[1:-1] if len(raw) >= 2 else raw
    if isinstance(value, str):
        return value
    return raw[1:-1] if len(raw) >= 2 else raw


def _walk_imports(node: Node, source: str, names: set[str]) -> None:
    if node.type == "import_statement":
        for child in node.children:
            if child.type == "import_clause":
                _collect_clause_bindings(child, source, names)
    for child in node.children:
        _walk_imports(child, source, names)


def _collect_clause_bindings(node: Node, source: str, names: set[str]) -> None:
    if node.type in {"identifier", "shorthand_property_identifier_pattern"}:
        names.add(source[node.start_byte : node.end_byte])
    for child in node.children:
        _collect_clause_bindings(child, source, names)


def find_symbol_references(
    parsed: ParsedModule,
    symbol: str,
) -> list[tuple[str, str]]:
    """Find static references to a symbol; returns (relative_path, evidence) pairs."""
    hits: list[tuple[str, str]] = []
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    for rel, text in parsed.sources.items():
        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                evidence = f"{rel}:{line_no} — {line.strip()}"
                hits.append((rel, evidence))
                break
    return hits
