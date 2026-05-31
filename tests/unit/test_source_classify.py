"""Unit tests for source input classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2o.source.classify import SourceKind, classify_source, expand_bare_id
from c2o.source.errors import SourceResolutionError


def test_classify_existing_directory_as_local(tmp_path: Path) -> None:
    kind, clone_url = classify_source(str(tmp_path))

    assert kind is SourceKind.LOCAL
    assert clone_url is None


@pytest.mark.parametrize(
    "source",
    [
        "https://github.com/bitfocus/companion-module-x",
        "http://example.test/repo.git",
        "file:///tmp/fixture.git",
        "ssh://git@example.test/repo.git",
        "git://example.test/repo.git",
        "git@github.com:bitfocus/companion-module-x.git",
    ],
)
def test_classify_url_sources(source: str) -> None:
    kind, clone_url = classify_source(source)

    assert kind is SourceKind.URL
    assert clone_url == source


def test_classify_bare_id_expands_to_bitfocus_url() -> None:
    kind, clone_url = classify_source("bmd-webpresenter")

    assert kind is SourceKind.BARE_ID
    assert clone_url == "https://github.com/bitfocus/companion-module-bmd-webpresenter"


def test_expand_bare_id_allows_underscores() -> None:
    assert (
        expand_bare_id("dummy_device")
        == "https://github.com/bitfocus/companion-module-dummy_device"
    )


def test_missing_path_with_separator_is_not_bare_id() -> None:
    with pytest.raises(SourceResolutionError, match="not a directory"):
        classify_source("not/a/dir")


@pytest.mark.parametrize("source", ["", "   ", "-bad"])
def test_invalid_source_shape_raises(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SourceResolutionError):
        classify_source(source)
