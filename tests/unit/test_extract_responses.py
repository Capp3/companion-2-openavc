"""Unit tests for response extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.responses import extract_responses
from c2o.parse.js import parse_module
from c2o.suitability.gate import assess_module


def test_dummy_produces_three_responses(dummy_device: Path) -> None:
    section, review = extract_responses(parse_module(dummy_device))

    assert len(section.responses) == 3
    assert review.flags == ()


def test_dummy_input_level_uses_verbose_integer(dummy_device: Path) -> None:
    section, _ = extract_responses(parse_module(dummy_device))
    entry = next(e for e in section.responses if e.match == r"^INPUT=(\d+)$")

    assert entry.mappings is not None
    assert entry.mappings[0].state == "input_level"
    assert entry.mappings[0].type == "integer"


def test_dummy_mute_uses_boolean_map(dummy_device: Path) -> None:
    section, _ = extract_responses(parse_module(dummy_device))
    entry = next(e for e in section.responses if "MUTE" in e.match)

    assert entry.mappings is not None
    assert entry.mappings[0].state == "mute_state"
    assert entry.mappings[0].map == {"ON": True, "OFF": False}


def test_dummy_label_uses_shorthand(dummy_device: Path) -> None:
    section, _ = extract_responses(parse_module(dummy_device))
    entry = next(e for e in section.responses if e.match == r"^LABEL=(.+)$")

    assert entry.set == {"device_label": "$1"}


def test_bmd_produces_fourteen_fanout_entries(bmd_webpresenter: Path) -> None:
    section, review = extract_responses(parse_module(bmd_webpresenter))

    assert len(section.responses) == 14
    assert review.flags == ()


def test_bmd_skips_substring_duration_fields(bmd_webpresenter: Path) -> None:
    section, _ = extract_responses(parse_module(bmd_webpresenter))
    states: set[str] = set()
    for entry in section.responses:
        if entry.set is not None:
            states.update(entry.set)
        if entry.mappings is not None:
            states.update(mapping.state for mapping in entry.mappings)

    assert "stream_duration_HH" not in states
    assert "stream_duration_MM" not in states
    assert "stream_duration_SS" not in states


def test_unknown_vendor_zero_responses(unknown_vendor: Path) -> None:
    section, review = extract_responses(parse_module(unknown_vendor))

    assert section.responses == ()
    assert review.flags == ()


def test_declined_responses_fixture_still_blocked(fixtures_dir: Path) -> None:
    declined = fixtures_dir / "declined-responses-not-expressible"
    gate = assess_module(parse_module(declined))

    assert gate.eligible is False
    assert any(blocker.code == "responses_not_expressible" for blocker in gate.blockers)
