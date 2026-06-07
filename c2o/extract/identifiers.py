"""Shared identifier normalization for extracted OpenAVC names.

Companion modules name variables, state, and actions in mixed conventions
(camelCase, kebab-case, spaced). OpenAVC drivers use stable ``snake_case``
identifiers. Normalizing through one function keeps cross-references consistent
(e.g. response setters target the same state-variable ids that
``state_variables`` emits, and polling references match normalized command ids).
"""

from __future__ import annotations

import re
from typing import Final

_CAMEL_BOUNDARY_1: Final[re.Pattern[str]] = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2: Final[re.Pattern[str]] = re.compile(r"([a-z0-9])([A-Z])")
_NON_IDENTIFIER_CHARS: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9_]+")
_MULTI_UNDERSCORE: Final[re.Pattern[str]] = re.compile(r"_+")


def normalize_identifier(identifier: str) -> str:
    """Convert a Companion identifier to a stable snake_case OpenAVC id.

    Falls back to the original string if normalization would yield an empty id.
    """
    candidate = identifier.strip()
    candidate = _CAMEL_BOUNDARY_1.sub(r"\1_\2", candidate)
    candidate = _CAMEL_BOUNDARY_2.sub(r"\1_\2", candidate)
    candidate = candidate.replace("-", "_").replace(" ", "_")
    candidate = _NON_IDENTIFIER_CHARS.sub("_", candidate.lower())
    candidate = _MULTI_UNDERSCORE.sub("_", candidate).strip("_")
    return candidate or identifier
