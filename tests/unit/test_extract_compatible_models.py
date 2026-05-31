"""Unit tests for compatible_models extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from c2o.extract.compatible_models import extract_compatible_models
from c2o.model.driver import ManifestSection
from c2o.model.review import ReviewCode


def _manifest_section(manufacturer: str = "Generic") -> ManifestSection:
    return ManifestSection(
        id="dummy_device",
        name="Dummy Device",
        manufacturer=manufacturer,
        category="utility",
        version="1.0.0",
        author="C2O Fixture Bot",
        description="Fixture metadata.",
        source_url="https://github.com/Capp3/companion-2-openavc",
    )


def _write_manifest(root: Path, products: object | None) -> None:
    manifest: dict[str, Any] = {
        "id": "dummy_device",
        "name": "dummy-device",
        "manufacturer": "Generic",
        "description": "Fixture metadata.",
        "version": "1.0.0",
    }
    if products is not None:
        manifest["products"] = products
    manifest_dir = root / "companion"
    manifest_dir.mkdir()
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_extract_compatible_models_from_dummy_fixture(dummy_device: Path) -> None:
    section, review = extract_compatible_models(dummy_device, _manifest_section())

    assert section.model_dump(exclude_none=True) == {
        "compatible_models": (
            {
                "manufacturer": "Generic",
                "models": ("Dummy Model A",),
                "confidence": "untested",
            },
        )
    }
    assert review.has_code(ReviewCode.COMPATIBLE_MODELS_CONFIDENCE)


def test_extract_compatible_models_missing_products_returns_empty(tmp_path: Path) -> None:
    _write_manifest(tmp_path, products=None)

    section, review = extract_compatible_models(tmp_path, _manifest_section())

    assert section.compatible_models == ()
    assert len(review) == 0


def test_extract_compatible_models_empty_products_returns_empty(tmp_path: Path) -> None:
    _write_manifest(tmp_path, products=[])

    section, review = extract_compatible_models(tmp_path, _manifest_section())

    assert section.compatible_models == ()
    assert len(review) == 0


def test_extract_compatible_models_skips_non_strings_and_deduplicates(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        products=["Model A", "", 123, "Model A", "model a", " Model B "],
    )

    section, review = extract_compatible_models(tmp_path, _manifest_section("Vendor X"))

    assert section.compatible_models[0].manufacturer == "Vendor X"
    assert section.compatible_models[0].models == ("Model A", "model a", "Model B")
    assert review.by_code(ReviewCode.COMPATIBLE_MODELS_CONFIDENCE)
