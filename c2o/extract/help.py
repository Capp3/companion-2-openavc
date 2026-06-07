"""Extract OpenAVC help from Companion HELP.md with manifest/config fallbacks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from c2o.extract.config_fields import _find_return_array
from c2o.extract.help_markdown import parse_help_markdown
from c2o.model.driver import HelpSection
from c2o.model.review import ReviewReport
from c2o.parse.js import ParsedModule, find_method_definitions
from c2o.parse.literals import UNRESOLVED, decode_object


class HelpExtractionError(ValueError):
    """Raised when help extraction cannot produce required overview and setup text."""


def extract_help(
    root: Path,
    parsed: ParsedModule,
    *,
    manifest_description: str | None = None,
) -> tuple[HelpSection, ReviewReport]:
    """Build help overview and setup from HELP.md or manifest/config fallbacks."""
    help_path = root / "companion" / "HELP.md"
    if help_path.is_file():
        text = help_path.read_text(encoding="utf-8")
        if text.strip():
            parsed_help = parse_help_markdown(text)
            if parsed_help is not None:
                help_overview, help_setup = parsed_help
                if help_overview and help_setup:
                    return (
                        HelpSection(overview=help_overview, setup=help_setup),
                        ReviewReport(),
                    )

    description = manifest_description or _read_manifest_description(root)
    static_text = _first_static_text_value(parsed)
    overview = static_text or description
    setup = description

    if not overview or not setup:
        msg = f"{root}: could not derive non-empty help overview and setup"
        raise HelpExtractionError(msg)

    return HelpSection(overview=overview, setup=setup), ReviewReport()


def _read_manifest_description(root: Path) -> str | None:
    manifest_path = root / "companion" / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    description = manifest.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    return None


def _first_static_text_value(parsed: ParsedModule) -> str | None:
    matches = find_method_definitions(parsed, "getConfigFields")
    if not matches or matches[0].body is None:
        return None

    source = parsed.sources[matches[0].rel_path]
    resolved = _find_return_array(
        matches[0].body,
        source=source,
        rel_path=matches[0].rel_path,
        parsed=parsed,
    )
    if resolved is None:
        return None

    array, array_source = resolved
    for child in array.named_children:
        if child.type != "object":
            continue
        raw_field = decode_object(child, array_source)
        if raw_field is UNRESOLVED:
            continue
        field = cast(dict[str, Any], raw_field)
        if field.get("type") != "static-text":
            continue
        value = field.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
