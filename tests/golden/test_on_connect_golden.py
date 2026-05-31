"""Golden snapshots for on_connect extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_on_connect
from c2o.parse.js import parse_module


def _snapshot_payload(root: Path) -> dict[str, Any]:
    section, review = extract_on_connect(parse_module(root))
    return {
        "on_connect": section.model_dump(exclude_none=True),
        "review": [flag.model_dump() for flag in review],
    }


def test_dummy_on_connect_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_on_connect_golden(bmd_webpresenter: Path, snapshot: Any) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot


def test_static_on_connect_on_connect_golden(static_on_connect: Path, snapshot: Any) -> None:
    assert _snapshot_payload(static_on_connect) == snapshot
