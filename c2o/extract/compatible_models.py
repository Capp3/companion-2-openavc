"""Extract OpenAVC compatible_models from Companion manifest products."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from c2o.model.driver import CompatibleModelEntry, CompatibleModelsSection, ManifestSection
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport


class CompatibleModelsExtractionError(ValueError):
    """Raised when compatible_models extraction encounters malformed manifest input."""


def extract_compatible_models(
    root: Path,
    manifest: ManifestSection,
) -> tuple[CompatibleModelsSection, ReviewReport]:
    """Build compatible model entries from ``manifest.json`` products."""
    manifest_data = _read_manifest(root / "companion" / "manifest.json")
    products = _string_list_unique(manifest_data.get("products"))
    if not products:
        return CompatibleModelsSection(), ReviewReport()

    section = CompatibleModelsSection(
        compatible_models=(
            CompatibleModelEntry(
                manufacturer=manifest.manufacturer,
                models=tuple(products),
                confidence="untested",
            ),
        )
    )
    return section, ReviewReport(flags=(_confidence_flag(),))


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        msg = f"Missing companion/manifest.json under {path.parent.parent}"
        raise CompatibleModelsExtractionError(msg)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {path}: {exc}"
        raise CompatibleModelsExtractionError(msg) from exc
    if not isinstance(data, dict):
        msg = f"manifest.json must contain a JSON object: {path}"
        raise CompatibleModelsExtractionError(msg)
    return data


def _string_list_unique(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _confidence_flag() -> ReviewFlag:
    return ReviewFlag(
        code=ReviewCode.COMPATIBLE_MODELS_CONFIDENCE,
        field="compatible_models",
        message=(
            "Compatible model entries are derived from Companion manifest products "
            "and default to untested confidence."
        ),
    )
