"""Extract OpenAVC metadata fields from Companion manifest.json."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from c2o.model.driver import DriverCategory, ManifestSection
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport

CATEGORY_KEYWORDS: tuple[tuple[str, DriverCategory], ...] = (
    ("projector", "projector"),
    ("display", "display"),
    ("monitor", "display"),
    ("tv", "display"),
    ("switcher", "switcher"),
    ("matrix", "switcher"),
    ("router", "switcher"),
    ("audio", "audio"),
    ("mixer", "audio"),
    ("dsp", "audio"),
    ("speaker", "audio"),
    ("microphone", "audio"),
    ("mic", "audio"),
    ("amplifier", "audio"),
    ("camera", "camera"),
    ("ptz", "camera"),
    ("visca", "camera"),
    ("video", "video"),
    ("recorder", "video"),
    ("playback", "video"),
    ("streaming", "streaming"),
    ("stream", "streaming"),
    ("encoder", "streaming"),
    ("ndi", "streaming"),
    ("rtmp", "streaming"),
    ("srt", "streaming"),
    ("lighting", "lighting"),
    ("light", "lighting"),
    ("dmx", "lighting"),
    ("artnet", "lighting"),
    ("sacn", "lighting"),
    ("power", "power"),
    ("pdu", "power"),
    ("ups", "power"),
    ("utility", "utility"),
    ("bridge", "utility"),
    ("relay", "utility"),
    ("wol", "utility"),
)

_MARKETING_PATTERN = re.compile(
    r"industry-leading|best-in-class|cutting-edge|world-class|revolutionary|"
    r"state-of-the-art|next-generation",
    re.IGNORECASE,
)
_HTTP_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


class ManifestExtractionError(ValueError):
    """Raised when Companion manifest metadata cannot be extracted."""


def extract_manifest(
    root: Path,
    *,
    source_url_hint: str | None = None,
) -> tuple[ManifestSection, ReviewReport]:
    """Extract the M4 metadata header from a Companion module root."""

    manifest_path = root / "companion" / "manifest.json"
    manifest = _read_manifest(manifest_path)
    flags: list[ReviewFlag] = []

    raw_id = _require_string(manifest, "id", manifest_path)
    driver_id = raw_id.replace("-", "_")
    if driver_id != raw_id:
        flags.append(
            ReviewFlag(
                code=ReviewCode.ID_COERCED,
                field="id",
                message=f"Driver id was coerced from '{raw_id}' to '{driver_id}'.",
                details={"old": raw_id, "new": driver_id},
            )
        )

    keywords = _string_list(manifest.get("keywords"))
    category = _category_from_keywords(keywords)
    if category is None:
        category = "utility"
        flags.append(
            ReviewFlag(
                code=ReviewCode.CATEGORY_DEFAULT,
                field="category",
                message="No manifest keyword mapped to an OpenAVC category; defaulted to utility.",
                details={"keywords": ",".join(keywords)},
            )
        )

    description = _require_string(manifest, "description", manifest_path)
    marketing_match = _MARKETING_PATTERN.search(description)
    if marketing_match is not None:
        flags.append(
            ReviewFlag(
                code=ReviewCode.DESCRIPTION_MARKETING,
                field="description",
                message="Description contains marketing language that should be reviewed.",
                details={"phrase": marketing_match.group(0)},
            )
        )

    try:
        section = ManifestSection(
            id=driver_id,
            name=_display_name(manifest, manifest_path),
            manufacturer=_require_string(manifest, "manufacturer", manifest_path),
            category=category,
            version=_require_string(manifest, "version", manifest_path),
            author=_author(manifest),
            description=description,
            source_url=_source_url(manifest, source_url_hint),
        )
    except ValidationError as exc:
        msg = f"Invalid manifest metadata in {manifest_path}: {exc}"
        raise ManifestExtractionError(msg) from exc

    return section, ReviewReport(flags=tuple(flags))


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        msg = f"Missing companion/manifest.json under {path.parent.parent}"
        raise ManifestExtractionError(msg)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {path}: {exc}"
        raise ManifestExtractionError(msg) from exc
    if not isinstance(data, dict):
        msg = f"manifest.json must contain a JSON object: {path}"
        raise ManifestExtractionError(msg)
    return data


def _require_string(manifest: dict[str, Any], field: str, manifest_path: Path) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value.strip():
        msg = f"manifest.json missing non-empty string '{field}' field: {manifest_path}"
        raise ManifestExtractionError(msg)
    return value.strip()


def _display_name(manifest: dict[str, Any], manifest_path: Path) -> str:
    shortname = manifest.get("shortname")
    if isinstance(shortname, str) and shortname.strip():
        return shortname.strip()
    return _require_string(manifest, "name", manifest_path)


def _author(manifest: dict[str, Any]) -> str:
    maintainers = manifest.get("maintainers")
    if isinstance(maintainers, list) and maintainers:
        first = maintainers[0]
        if isinstance(first, dict):
            name = first.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return "Community"


def _category_from_keywords(keywords: list[str]) -> DriverCategory | None:
    category_by_keyword = dict(CATEGORY_KEYWORDS)
    for keyword in keywords:
        category = category_by_keyword.get(keyword.lower())
        if category is not None:
            return category
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _source_url(manifest: dict[str, Any], source_url_hint: str | None) -> str | None:
    return _normalize_repository(source_url_hint) or _normalize_repository(
        manifest.get("repository")
    )


def _normalize_repository(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    repository = value.strip()
    if repository.startswith("git+"):
        repository = repository[4:]
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not _HTTP_URL_PATTERN.match(repository):
        return None
    return repository
