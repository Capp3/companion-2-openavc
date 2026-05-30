"""Unit tests for response pattern helpers."""

from __future__ import annotations

from c2o.extract.response_patterns import (
    anchor_pattern,
    build_boolean_map_entry,
    build_fan_out_entry,
    build_prefix_capture_entry,
    compile_check,
    fan_out_match,
)
from c2o.model.driver import ResponseEntry


def test_anchor_pattern_adds_carets_when_missing() -> None:
    assert anchor_pattern(r"INPUT=(\d+)") == r"^INPUT=(\d+)$"


def test_anchor_pattern_preserves_existing_anchors() -> None:
    assert anchor_pattern(r"^MUTE=(ON|OFF)$") == r"^MUTE=(ON|OFF)$"


def test_fan_out_match_escapes_spaces_and_metacharacters() -> None:
    assert fan_out_match("Software Release") == r"^Software\ Release:\s*(.+)$"


def test_compile_check_rejects_invalid_regex() -> None:
    assert compile_check(r"^valid$") is True
    assert compile_check(r"(unclosed") is False


def test_build_prefix_capture_entry() -> None:
    entry = build_prefix_capture_entry("LABEL=", "device_label")
    assert entry == ResponseEntry(match=r"^LABEL=(.+)$", set={"device_label": "$1"})


def test_build_boolean_map_entry() -> None:
    entry = build_boolean_map_entry("MUTE=", "mute_state")
    assert entry is not None
    assert entry.match == r"^MUTE=(ON|OFF)$"
    assert entry.mappings is not None
    assert entry.mappings[0].map == {"ON": True, "OFF": False}


def test_build_fan_out_entry() -> None:
    entry = build_fan_out_entry("Label", "label")
    assert entry == ResponseEntry(match=r"^Label:\s*(.+)$", set={"label": "$1"})
