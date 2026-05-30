"""Parse Companion companion/HELP.md into overview and setup text."""

from __future__ import annotations

import re

_VERSION_HEADING = re.compile(r"(?m)^## Version \d")


def parse_help_markdown(text: str) -> tuple[str, str] | None:
    """Return overview and setup from HELP markdown, or None when unparseable."""
    body = _strip_changelog(text)
    body = _strip_title(body)
    if not body.strip():
        return None

    blocks = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
    if not blocks:
        return None

    overview = _collapse_whitespace(blocks[0])
    if not overview:
        return None

    setup = "\n\n".join(blocks[1:]).strip() if len(blocks) > 1 else ""
    return overview, setup


def _strip_changelog(text: str) -> str:
    return _VERSION_HEADING.split(text, maxsplit=1)[0]


def _strip_title(body: str) -> str:
    lines = body.lstrip("\ufeff").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())
