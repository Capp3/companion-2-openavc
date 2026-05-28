"""Unit tests for JavaScript module parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2o.parse.js import (
    CallMatch,
    ParsedModule,
    collect_inline_object_pairs,
    find_method_definitions,
    parse_module,
    parse_source,
    resolve_array_via_pushes,
    resolve_object_via_assignments,
)


@pytest.mark.parametrize(
    ("fixture_name", "min_files"),
    [
        ("dummy-device", 4),
        ("declined-udp", 1),
        ("external/bmd-webpresenter", 4),
    ],
)
def test_parse_module_fixtures(
    fixtures_dir: Path,
    fixture_name: str,
    min_files: int,
) -> None:
    root = fixtures_dir / fixture_name
    parsed = parse_module(root)
    assert parsed.root == root.resolve()
    assert len(parsed.sources) >= min_files
    assert len(parsed.trees) == len(parsed.sources)
    for rel, tree in parsed.trees.items():
        assert tree.root_node.type == "program"
        assert rel in parsed.sources


def test_find_method_definitions_finds_dummy_config_fields(dummy_device: Path) -> None:
    parsed = parse_module(dummy_device)

    matches = find_method_definitions(parsed, "getConfigFields")

    assert len(matches) == 1
    assert matches[0].rel_path == "index.js"
    assert matches[0].name == "getConfigFields"
    assert matches[0].body is not None


def test_find_method_definitions_finds_bmd_config_fields(bmd_webpresenter: Path) -> None:
    parsed = parse_module(bmd_webpresenter)

    matches = find_method_definitions(parsed, "getConfigFields")

    assert len(matches) == 1
    assert matches[0].rel_path == "index.js"
    assert matches[0].name == "getConfigFields"
    assert matches[0].body is not None


def test_find_method_definitions_returns_empty_for_missing_method(tmp_path: Path) -> None:
    source = "class Example { init() { return [] } }\n"
    parsed = ParsedModule(
        root=tmp_path,
        sources={"index.js": source},
        trees={"index.js": parse_source(source)},
    )

    assert find_method_definitions(parsed, "getConfigFields") == []


def _find_call(source: str, function_name: str) -> tuple[ParsedModule, CallMatch]:
    from c2o.parse.js import find_calls

    parsed = ParsedModule(
        root=Path("."),
        sources={"index.js": source},
        trees={"index.js": parse_source(source)},
    )
    matches = find_calls(parsed, function_name, include_methods=True)
    assert len(matches) == 1
    return parsed, matches[0]


def test_resolve_array_via_pushes_collects_object_literals() -> None:
    source = """
    export function updateVariables() {
      let xs = []
      xs.push({ variableId: 'a', name: 'A' })
      xs.push({ variableId: 'b', name: 'B' })
      this.setVariableDefinitions(xs)
    }
    """
    parsed, call = _find_call(source, "setVariableDefinitions")
    source_text = parsed.sources["index.js"]
    arg = call.args_node.named_children[0] if call.args_node else None
    assert arg is not None
    objects = resolve_array_via_pushes(
        source=source_text,
        identifier_node=arg,
        call_node=call.node,
    )
    assert objects is not None
    assert len(objects) == 2


def test_resolve_array_via_pushes_returns_none_without_declarator() -> None:
    source = """
    export function updateVariables() {
      this.setVariableDefinitions(buildVars())
    }
    """
    parsed = ParsedModule(
        root=Path("."),
        sources={"index.js": source},
        trees={"index.js": parse_source(source)},
    )
    from c2o.parse.js import find_calls

    call = find_calls(parsed, "setVariableDefinitions", include_methods=True)[0]
    arg = call.args_node.named_children[0] if call.args_node else None
    assert arg is not None
    assert (
        resolve_array_via_pushes(
            source=source,
            identifier_node=arg,
            call_node=call.node,
        )
        is None
    )


def test_resolve_array_via_pushes_rejects_non_empty_initializer() -> None:
    source = """
    export function updateVariables() {
      let xs = [{ variableId: 'seed', name: 'Seed' }]
      xs.push({ variableId: 'a', name: 'A' })
      this.setVariableDefinitions(xs)
    }
    """
    parsed = ParsedModule(
        root=Path("."),
        sources={"index.js": source},
        trees={"index.js": parse_source(source)},
    )
    from c2o.parse.js import find_calls

    call = find_calls(parsed, "setVariableDefinitions", include_methods=True)[0]
    arg = call.args_node.named_children[0] if call.args_node else None
    assert arg is not None
    assert (
        resolve_array_via_pushes(
            source=source,
            identifier_node=arg,
            call_node=call.node,
        )
        is None
    )


def test_resolve_object_via_assignments_collects_bracket_and_dot_keys() -> None:
    source = """
    export function updateActions() {
      let actions = {}
      actions['stream'] = { name: 'Stream' }
      actions.stop = { name: 'Stop' }
      this.setActionDefinitions(actions)
    }
    """
    parsed, call = _find_call(source, "setActionDefinitions")
    source_text = parsed.sources["index.js"]
    arg = call.args_node.named_children[0] if call.args_node else None
    assert arg is not None
    pairs = resolve_object_via_assignments(
        source=source_text,
        identifier_node=arg,
        call_node=call.node,
    )
    assert pairs is not None
    assert [key for key, _ in pairs] == ["stream", "stop"]


def test_collect_inline_object_pairs_reads_inline_action_keys() -> None:
    source = """
    export function updateActions() {
      this.setActionDefinitions({
        set_input: { name: 'Set Input' },
        stream: { name: 'Stream' },
      })
    }
    """
    parsed, call = _find_call(source, "setActionDefinitions")
    source_text = parsed.sources["index.js"]
    arg = call.args_node.named_children[0] if call.args_node else None
    assert arg is not None
    pairs = collect_inline_object_pairs(arg, source_text)
    assert [key for key, _ in pairs] == ["set_input", "stream"]


def test_resolve_object_via_assignments_rejects_non_empty_initializer() -> None:
    source = """
    export function updateActions() {
      let actions = { seed: {} }
      actions['stream'] = { name: 'Stream' }
      this.setActionDefinitions(actions)
    }
    """
    parsed, call = _find_call(source, "setActionDefinitions")
    arg = call.args_node.named_children[0] if call.args_node else None
    assert arg is not None
    assert (
        resolve_object_via_assignments(
            source=source,
            identifier_node=arg,
            call_node=call.node,
        )
        is None
    )
