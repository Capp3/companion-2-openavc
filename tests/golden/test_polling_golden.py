"""Golden snapshots for polling extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_polling
from c2o.parse.js import parse_module


def _snapshot_payload(root: Path) -> dict[str, Any]:
    section, review = extract_polling(parse_module(root))
    return {
        "polling": section.model_dump(exclude_none=True),
        "review": [flag.model_dump() for flag in review],
    }


def test_dummy_polling_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_polling_golden(bmd_webpresenter: Path, snapshot: Any) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot
