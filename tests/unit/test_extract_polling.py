"""Unit tests for polling extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.polling import extract_polling
from c2o.parse.js import parse_module


def test_dummy_produces_two_queries(dummy_device: Path) -> None:
    section, review = extract_polling(parse_module(dummy_device))

    assert section.queries == ("QUERY INPUT\n", "QUERY MUTE\n")
    assert section.inferred_poll_interval is None
    assert review.flags == ()


def test_bmd_produces_single_query_and_inferred_interval(bmd_webpresenter: Path) -> None:
    section, review = extract_polling(parse_module(bmd_webpresenter))

    assert section.queries == ("STREAM STATE:\n\n",)
    assert section.inferred_poll_interval == 1
    assert review.flags == ()


def test_unknown_vendor_has_empty_polling(unknown_vendor: Path) -> None:
    section, review = extract_polling(parse_module(unknown_vendor))

    assert section.queries == ()
    assert section.inferred_poll_interval is None
    assert review.flags == ()


def test_polling_section_dump_never_contains_interval_key(bmd_webpresenter: Path) -> None:
    section, _ = extract_polling(parse_module(bmd_webpresenter))
    dumped = section.model_dump(exclude_none=True)

    assert "interval" not in dumped
