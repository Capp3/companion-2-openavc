"""Unit tests for local source resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from c2o.source.local import read_module_id, resolve_local


def test_resolve_local_requires_directory(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(ValueError, match="not a directory"):
        resolve_local(str(missing))


def test_read_module_id_missing_manifest(dummy_device: Path) -> None:
    manifest = dummy_device / "companion" / "manifest.json"
    backup = manifest.read_text(encoding="utf-8")
    manifest.unlink()
    try:
        with pytest.raises(ValueError, match="Missing companion/manifest.json"):
            read_module_id(dummy_device)
    finally:
        manifest.write_text(backup, encoding="utf-8")


def test_read_module_id_invalid_manifest(dummy_device: Path) -> None:
    manifest = dummy_device / "companion" / "manifest.json"
    backup = manifest.read_text(encoding="utf-8")
    manifest.write_text(json.dumps({"name": "no-id"}), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="missing string 'id'"):
            read_module_id(dummy_device)
    finally:
        manifest.write_text(backup, encoding="utf-8")
