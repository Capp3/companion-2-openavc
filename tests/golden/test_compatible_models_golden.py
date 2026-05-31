"""Golden snapshots for compatible_models extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_compatible_models, extract_manifest


def _snapshot_payload(root: Path) -> dict[str, Any]:
    manifest, _manifest_review = extract_manifest(root)
    section, review = extract_compatible_models(root, manifest)
    return {
        "compatible_models": section.model_dump(exclude_none=True),
        "review": [flag.model_dump() for flag in review],
    }


def test_dummy_compatible_models_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_compatible_models_golden(
    bmd_webpresenter: Path,
    snapshot: Any,
) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot


def test_static_on_connect_compatible_models_golden(
    static_on_connect: Path,
    snapshot: Any,
) -> None:
    assert _snapshot_payload(static_on_connect) == snapshot
