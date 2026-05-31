"""Classify C2O source arguments."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

from c2o.source.errors import SourceResolutionError

BITFOCUS_GITHUB_ORG = "bitfocus"
BITFOCUS_REPO_PREFIX = "companion-module-"

_BARE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CLONE_SCHEMES = frozenset({"http", "https", "file", "ssh", "git"})
_GIT_SCP_RE = re.compile(r"^[^@\s/\\]+@[^@\s/\\]+:.+")


class SourceKind(StrEnum):
    """Supported source input shapes."""

    LOCAL = "local"
    URL = "url"
    BARE_ID = "bare_id"


def expand_bare_id(module_id: str) -> str:
    """Expand a bare Companion module id to the Bitfocus GitHub URL."""
    return f"https://github.com/{BITFOCUS_GITHUB_ORG}/{BITFOCUS_REPO_PREFIX}{module_id}"


def classify_source(raw: str) -> tuple[SourceKind, str | None]:
    """Classify a CLI source string.

    Returns the source kind and the clone URL for remote sources.
    """
    source = raw.strip()
    if not source:
        raise SourceResolutionError("Source must not be empty")

    path = Path(source).expanduser()
    if path.is_dir():
        return SourceKind.LOCAL, None

    if _looks_like_clone_url(source):
        return SourceKind.URL, source

    if "/" in source or "\\" in source:
        raise SourceResolutionError(f"Source is not a directory: {source}")

    if not _BARE_ID_RE.fullmatch(source):
        raise SourceResolutionError(f"Invalid source: {source!r}")

    return SourceKind.BARE_ID, expand_bare_id(source)


def _looks_like_clone_url(source: str) -> bool:
    scheme = urlparse(source).scheme
    if scheme in _CLONE_SCHEMES:
        return True
    return _GIT_SCP_RE.fullmatch(source) is not None
