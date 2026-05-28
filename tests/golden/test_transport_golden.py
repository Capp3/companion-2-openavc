"""Golden snapshots for M6 transport extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_transport
from c2o.parse.js import parse_module


def _snapshot_payload(root: Path) -> dict[str, Any]:
    section = extract_transport(parse_module(root))
    return {"transport": section.model_dump()}


def test_dummy_transport_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_transport_golden(bmd_webpresenter: Path, snapshot: Any) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot
