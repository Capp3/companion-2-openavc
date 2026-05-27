"""Unit tests for JavaScript module parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2o.parse.js import parse_module


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
