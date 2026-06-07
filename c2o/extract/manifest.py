"""Extract OpenAVC metadata fields from Companion manifest.json."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from c2o.model.driver import AuthSection, DriverCategory, ManifestSection, TransportSection
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport

# Minimal tags derived from manifest keywords + category.
_CATEGORY_TAG_MAP: dict[str, list[str]] = {
    "camera": ["camera"],
    "projector": ["projector"],
    "display": ["display"],
    "switcher": ["switcher"],
    "audio": ["audio"],
    "video": ["video"],
    "streaming": ["streaming"],
    "lighting": ["lighting"],
    "power": ["power"],
}
_EXTRA_TAG_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("ptz", "ptz"),
    ("visca", "visca"),
    ("telnet", "telnet"),
    ("tcp", "tcp"),
    ("http", "http"),
    ("serial", "serial"),
    ("ndi", "ndi"),
    ("broadcast", "broadcast"),
    ("pjlink", "pjlink"),
    ("dante", "dante"),
    ("artnet", "artnet"),
    ("dmx", "dmx"),
)

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
_TAG_CLEANUP_PATTERN = re.compile(r"[^a-z0-9]+")


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

    author, author_defaulted = _author(manifest)
    if author_defaulted:
        flags.append(
            ReviewFlag(
                code=ReviewCode.AUTHOR_DEFAULT,
                field="author",
                message="Author defaulted to 'Community'; no maintainer name found in manifest.",
            )
        )

    tags = _derive_tags(category, keywords)

    try:
        section = ManifestSection(
            id=driver_id,
            name=_display_name(manifest, manifest_path),
            manufacturer=_require_string(manifest, "manufacturer", manifest_path),
            category=category,
            version=_require_string(manifest, "version", manifest_path),
            author=author,
            description=description,
            source_url=_source_url(manifest, source_url_hint),
            verified=False,
            simulated=False,
            ports=(),
            tags=tuple(tags),
        )
    except ValidationError as exc:
        msg = f"Invalid manifest metadata in {manifest_path}: {exc}"
        raise ManifestExtractionError(msg) from exc

    return section, ReviewReport(flags=tuple(flags))


def enrich_manifest_metadata(
    manifest: ManifestSection,
    transport: TransportSection,
    *,
    auth: AuthSection | None = None,
) -> tuple[ManifestSection, ReviewReport]:
    """Enrich metadata that depends on cross-extractor context."""
    protocol_transport = _protocol_transport_name(transport, auth)
    tags = _enrich_tags(manifest, protocol_transport)
    protocol = _protocol_slug(manifest.manufacturer, protocol_transport)
    protocols = manifest.protocols
    flags: list[ReviewFlag] = []
    if protocol is not None and protocol not in protocols:
        protocols = (*protocols, protocol)
        flags.append(
            ReviewFlag(
                code=ReviewCode.PROTOCOL_INFERRED,
                field="protocols",
                message=(
                    f"Protocol slug '{protocol}' was inferred from manufacturer "
                    f"'{manifest.manufacturer}' and transport '{protocol_transport}'."
                ),
                details={
                    "manufacturer": manifest.manufacturer,
                    "transport": protocol_transport,
                    "protocol": protocol,
                },
            )
        )

    return manifest.model_copy(update={"tags": tags, "protocols": protocols}), ReviewReport(
        flags=tuple(flags)
    )


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
    for key in ("shortName", "shortname", "label", "shortLabel"):
        value = manifest.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raw_name = _require_string(manifest, "name", manifest_path)
    # Convert hyphen-separated npm package names to human-readable form.
    # e.g. "vaddio-ptz" → "Vaddio Ptz" (further improved by shortName if available)
    if "-" in raw_name and raw_name == raw_name.lower():
        return raw_name.replace("-", " ").title()
    return raw_name


def _author(manifest: dict[str, Any]) -> tuple[str, bool]:
    maintainers = manifest.get("maintainers")
    if isinstance(maintainers, list) and maintainers:
        first = maintainers[0]
        if isinstance(first, dict):
            name = first.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip(), False
    return "Community", True


def _category_from_keywords(keywords: list[str]) -> DriverCategory | None:
    category_by_keyword = dict(CATEGORY_KEYWORDS)
    for keyword in keywords:
        category = category_by_keyword.get(keyword.lower())
        if category is not None:
            return category
    return None


def _derive_tags(category: DriverCategory, keywords: list[str]) -> list[str]:
    """Derive a minimal tag list from category and manifest keywords."""
    tags: list[str] = []
    base = _CATEGORY_TAG_MAP.get(category, [])
    for tag in base:
        if tag not in tags:
            tags.append(tag)

    all_text = " ".join(keywords).lower()
    for keyword, tag in _EXTRA_TAG_KEYWORDS:
        if keyword in all_text and tag not in tags:
            tags.append(tag)

    return tags


def _enrich_tags(manifest: ManifestSection, protocol_transport: str) -> tuple[str, ...]:
    tags: list[str] = []
    _append_tags(tags, tuple(_CATEGORY_TAG_MAP.get(manifest.category, ())))
    _append_tag(tags, _tag_slug(protocol_transport))
    _append_tags(tags, manifest.tags)
    _append_tags(tags, _brand_tags(manifest.manufacturer))
    return tuple(tags)


def _brand_tags(manufacturer: str) -> tuple[str, ...]:
    slug = _tag_slug(manufacturer)
    if slug in {"", "generic"}:
        return ()
    tags = [slug]
    head = manufacturer.strip().split(maxsplit=1)[0]
    head_slug = _tag_slug(head)
    if head_slug and head_slug != slug:
        tags.append(head_slug)
    return tuple(tags)


def _protocol_transport_name(transport: TransportSection, auth: AuthSection | None) -> str:
    if transport.transport == "tcp" and auth is not None and auth.type == "telnet_login":
        return "telnet"
    return transport.transport


def _protocol_slug(manufacturer: str, protocol_transport: str) -> str | None:
    brand = _tag_slug(manufacturer).replace("-", "_")
    if not brand or brand == "generic":
        return None
    transport_slug = _tag_slug(protocol_transport).replace("-", "_")
    return f"{brand}_{transport_slug}"


def _append_tags(tags: list[str], values: tuple[str, ...] | list[str]) -> None:
    for value in values:
        _append_tag(tags, value)


def _append_tag(tags: list[str], value: str) -> None:
    tag = _tag_slug(value)
    if tag and tag not in tags:
        tags.append(tag)


def _tag_slug(value: str) -> str:
    return _TAG_CLEANUP_PATTERN.sub("-", value.strip().lower()).strip("-")


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
