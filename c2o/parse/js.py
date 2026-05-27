"""Tree-sitter JavaScript parser bootstrap for Companion module sources."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Node, Parser, Tree

_JS_LANGUAGE = Language(tsjs.language())
_PARSER = Parser(_JS_LANGUAGE)

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


def get_parser() -> Parser:
    """Return a tree-sitter parser configured for JavaScript."""
    return Parser(_JS_LANGUAGE)


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


def collect_import_binding_names(tree: Tree, source: str) -> set[str]:
    """Collect identifiers introduced by import declarations."""
    names: set[str] = set[str]()
    _walk_imports(tree.root_node, source, names)
    return names


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
