"""Golden snapshots for config field extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_config_fields
from c2o.parse.js import parse_module


def _snapshot_payload(root: Path) -> dict[str, Any]:
    section = extract_config_fields(parse_module(root))
    return {"config_fields": section.model_dump(exclude_none=True)}


def test_dummy_config_fields_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_config_fields_golden(
    bmd_webpresenter: Path,
    snapshot: Any,
) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot
