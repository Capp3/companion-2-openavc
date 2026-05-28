"""Unit tests for Companion manifest extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from c2o.extract.manifest import ManifestExtractionError, extract_manifest
from c2o.model.review import ReviewCode


def _write_manifest(tmp_path: Path, **overrides: Any) -> Path:
    root = tmp_path / "module"
    manifest_dir = root / "companion"
    manifest_dir.mkdir(parents=True)
    manifest = {
        "id": "example_device",
        "name": "Example Device Long Name",
        "shortname": "Example Device",
        "manufacturer": "Example Co",
        "keywords": ["utility"],
        "version": "1.0.0",
        "maintainers": [{"name": "Example Maintainer"}],
        "description": "Controls an example device.",
        "repository": "git+https://github.com/example/example-device.git",
    }
    manifest.update(overrides)
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_id_without_hyphen_has_no_review_flag(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, id="example_device")

    section, report = extract_manifest(root)

    assert section.id == "example_device"
    assert report.flags == ()


def test_hyphenated_id_is_coerced_with_review_flag(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, id="bmd-webpresenter")

    section, report = extract_manifest(root)

    assert section.id == "bmd_webpresenter"
    assert report.has_code(ReviewCode.ID_COERCED)
    assert report.flags[0].details == {"old": "bmd-webpresenter", "new": "bmd_webpresenter"}


def test_leading_digit_id_matches_schema_pattern(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, id="3com_switch")

    section, _report = extract_manifest(root)

    assert section.id == "3com_switch"


def test_invalid_id_raises_manifest_extraction_error(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, id="bad!id")

    with pytest.raises(ManifestExtractionError, match="manifest.json"):
        extract_manifest(root)


def test_shortname_wins_over_name(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, name="Long Name", shortname="Short Name")

    section, _report = extract_manifest(root)

    assert section.name == "Short Name"


def test_name_fallback_when_shortname_missing(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, name="Long Name", shortname="")

    section, _report = extract_manifest(root)

    assert section.name == "Long Name"


@pytest.mark.parametrize(
    ("keyword", "category"),
    [
        ("projector", "projector"),
        ("monitor", "display"),
        ("matrix", "switcher"),
        ("dsp", "audio"),
        ("ptz", "camera"),
        ("video", "video"),
        ("Streaming", "streaming"),
        ("dmx", "lighting"),
        ("pdu", "power"),
        ("utility", "utility"),
    ],
)
def test_category_keyword_mapping(tmp_path: Path, keyword: str, category: str) -> None:
    root = _write_manifest(tmp_path, keywords=[keyword])

    section, _report = extract_manifest(root)

    assert section.category == category


def test_category_mapping_uses_first_matching_keyword(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, keywords=["streaming", "audio"])

    section, _report = extract_manifest(root)

    assert section.category == "streaming"


def test_category_defaults_to_utility_with_review_flag(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, keywords=["fixture"])

    section, report = extract_manifest(root)

    assert section.category == "utility"
    assert report.has_code(ReviewCode.CATEGORY_DEFAULT)
    assert report.flags[0].details == {"keywords": "fixture"}


def test_valid_prerelease_version_passes(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, version="2.1.3-rc.1")

    section, _report = extract_manifest(root)

    assert section.version == "2.1.3-rc.1"


def test_invalid_version_raises_manifest_extraction_error(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, version="2.1")

    with pytest.raises(ManifestExtractionError, match="version"):
        extract_manifest(root)


def test_author_falls_back_to_community(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, maintainers=[])

    section, _report = extract_manifest(root)

    assert section.author == "Community"


def test_marketing_description_gets_review_flag(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, description="Industry-leading display control.")

    section, report = extract_manifest(root)

    assert section.description == "Industry-leading display control."
    assert report.has_code(ReviewCode.DESCRIPTION_MARKETING)
    assert report.flags[0].details == {"phrase": "Industry-leading"}


def test_source_url_hint_wins_over_repository(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, repository="https://github.com/example/from-manifest.git")

    section, _report = extract_manifest(
        root, source_url_hint="https://github.com/example/from-hint"
    )

    assert section.source_url == "https://github.com/example/from-hint"


def test_git_repository_source_url_is_normalized(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, repository="git+https://github.com/example/foo.git")

    section, _report = extract_manifest(root)

    assert section.source_url == "https://github.com/example/foo"


def test_plain_http_repository_source_url_passes_through(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, repository="http://github.com/example/foo")

    section, _report = extract_manifest(root)

    assert section.source_url == "http://github.com/example/foo"


def test_missing_repository_leaves_source_url_unresolved(tmp_path: Path) -> None:
    root = _write_manifest(tmp_path, repository="")

    section, _report = extract_manifest(root)

    assert section.source_url is None


def test_missing_manifest_raises_manifest_extraction_error(tmp_path: Path) -> None:
    with pytest.raises(ManifestExtractionError, match="Missing companion/manifest.json"):
        extract_manifest(tmp_path)
