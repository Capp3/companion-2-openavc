"""Golden snapshots for discovery extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import (
    extract_compatible_models,
    extract_config_fields,
    extract_discovery,
    extract_manifest,
)
from c2o.parse.js import parse_module


def _snapshot_payload(root: Path) -> dict[str, Any]:
    parsed = parse_module(root)
    manifest, _manifest_review = extract_manifest(root)
    config_fields = extract_config_fields(parsed)
    compatible_models, _compatible_review = extract_compatible_models(root, manifest)
    section, review = extract_discovery(manifest, config_fields, compatible_models)
    return {
        "discovery": section.model_dump(exclude_none=True),
        "review": [flag.model_dump() for flag in review],
    }


def test_dummy_discovery_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_discovery_golden(bmd_webpresenter: Path, snapshot: Any) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot


def test_static_on_connect_discovery_golden(static_on_connect: Path, snapshot: Any) -> None:
    assert _snapshot_payload(static_on_connect) == snapshot
