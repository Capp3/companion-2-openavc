"""Unit tests for manufacturer registry reconciliation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from c2o.model.driver import ManifestSection
from c2o.model.review import ReviewCode
from c2o.registry import VENDORED_PATH, Registry, reconcile_manufacturer


class DummyResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class BrokenJsonResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        raise json.JSONDecodeError("bad", "x", 0)


def _section(manufacturer: str) -> ManifestSection:
    return ManifestSection(
        id="dummy_device",
        name="Dummy Device",
        manufacturer=manufacturer,
        category="utility",
        version="1.0.0",
        author="C2O Fixture Bot",
        description="Fixture for manufacturer registry tests.",
        source_url="https://github.com/Capp3/companion-2-openavc",
    )


def test_registry_from_names_deduplicates_preserving_first_spelling() -> None:
    registry = Registry.from_names(["Foo", "foo", " Bar ", "BAR"], source="vendored")

    assert registry.names == ("Foo", "Bar")
    assert registry.source == "vendored"


def test_registry_contains_is_case_insensitive() -> None:
    registry = Registry.from_names(["Blackmagic Design"], source="vendored")

    assert registry.contains("blackmagic design") is True
    assert registry.contains("BLACKMAGIC DESIGN") is True
    assert registry.contains("Blackmagic Designs") is False


def test_registry_closest_returns_canonical_names() -> None:
    registry = Registry.from_names(
        ["Blackmagic Design", "Panasonic", "Sony", "Generic"],
        source="vendored",
    )

    assert registry.closest("BlackmagicDesigns")[0] == "Blackmagic Design"


def test_registry_load_uses_upstream_payload_from_response() -> None:
    registry = Registry.load(http_get=lambda _url: DummyResponse(["Foo", "Bar"]))

    assert registry.names == ("Foo", "Bar")
    assert registry.source == "upstream"


def test_registry_load_uses_direct_upstream_payload() -> None:
    registry = Registry.load(http_get=lambda _url: ["Foo", "Bar"])

    assert registry.names == ("Foo", "Bar")
    assert registry.source == "upstream"


def test_registry_load_falls_back_on_http_error(tmp_path: Path) -> None:
    vendored_path = tmp_path / "manufacturers.json"
    vendored_path.write_text('["Generic"]', encoding="utf-8")

    def raise_connect_error(_url: str) -> Any:
        raise httpx.ConnectError("boom")

    registry = Registry.load(http_get=raise_connect_error, vendored_path=vendored_path)

    assert registry.names == ("Generic",)
    assert registry.source == "vendored"


def test_registry_load_falls_back_on_invalid_shape(tmp_path: Path) -> None:
    vendored_path = tmp_path / "manufacturers.json"
    vendored_path.write_text('["Generic"]', encoding="utf-8")

    registry = Registry.load(http_get=lambda _url: {"name": "Generic"}, vendored_path=vendored_path)

    assert registry.names == ("Generic",)
    assert registry.source == "vendored"


def test_registry_load_falls_back_on_json_decode_error(tmp_path: Path) -> None:
    vendored_path = tmp_path / "manufacturers.json"
    vendored_path.write_text('["Generic"]', encoding="utf-8")

    registry = Registry.load(
        http_get=lambda _url: BrokenJsonResponse(), vendored_path=vendored_path
    )

    assert registry.names == ("Generic",)
    assert registry.source == "vendored"


def test_vendored_registry_contains_expected_names() -> None:
    registry = Registry.from_names(
        json.loads(VENDORED_PATH.read_text(encoding="utf-8")), source="vendored"
    )

    assert registry.contains("Blackmagic Design") is True
    assert registry.contains("Generic") is True


def test_reconcile_manufacturer_accepts_known_manufacturer() -> None:
    registry = Registry.from_names(["Blackmagic Design"], source="vendored")

    report = reconcile_manufacturer(_section("blackmagic design"), registry=registry)

    assert len(report) == 0


def test_reconcile_manufacturer_flags_unknown_with_suggestions() -> None:
    registry = Registry.from_names(["Blackmagic Design", "Generic"], source="vendored")

    report = reconcile_manufacturer(_section("Blackmagic Designs"), registry=registry)

    assert len(report) == 1
    flag = report.flags[0]
    assert flag.code == ReviewCode.UNKNOWN_MANUFACTURER
    assert flag.field == "manufacturer"
    assert flag.details["manufacturer"] == "Blackmagic Designs"
    assert flag.details["suggestions"] == "Blackmagic Design"
    assert flag.details["registry_source"] == "vendored"


def test_reconcile_manufacturer_flags_unknown_with_no_close_matches() -> None:
    registry = Registry.from_names(["Blackmagic Design", "Generic"], source="upstream")

    report = reconcile_manufacturer(_section("Zzzzzzzzz"), registry=registry)

    assert len(report) == 1
    flag = report.flags[0]
    assert flag.code == ReviewCode.UNKNOWN_MANUFACTURER
    assert flag.details["suggestions"] == ""
    assert flag.details["registry_source"] == "upstream"
