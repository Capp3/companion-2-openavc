"""Golden snapshots for M4 manifest metadata extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_manifest


def _snapshot_payload(root: Path) -> dict[str, Any]:
    section, report = extract_manifest(root)
    return {
        "manifest": section.model_dump(),
        "review_flags": tuple(flag.model_dump() for flag in report.flags),
    }


def test_dummy_manifest_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_manifest_golden(bmd_webpresenter: Path, snapshot: Any) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot
