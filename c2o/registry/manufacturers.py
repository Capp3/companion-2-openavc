"""Manufacturer registry loading and reconciliation."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, PrivateAttr

from c2o.model.driver import ManifestSection
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport

UPSTREAM_URL = "https://raw.githubusercontent.com/open-avc/openavc-drivers/main/manufacturers.json"
VENDORED_PATH = (
    Path(__file__).resolve().parent.parent / "vendored" / "openavc_drivers" / "manufacturers.json"
)

RegistrySource = Literal["upstream", "vendored"]


class Registry(BaseModel):
    """Closed set of manufacturer names accepted by OpenAVC."""

    model_config = ConfigDict(frozen=True)

    names: tuple[str, ...]
    source: RegistrySource

    _lookup_set: frozenset[str] = PrivateAttr(default_factory=frozenset)

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "_lookup_set", frozenset(name.casefold() for name in self.names))

    @classmethod
    def from_names(cls, names: Iterable[str], *, source: RegistrySource) -> Registry:
        """Build a registry from names, preserving first-seen canonical spelling."""
        normalized: list[str] = []
        seen: set[str] = set()
        for name in names:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("manufacturer registry names must be non-empty strings")
            key = cleaned.casefold()
            if key in seen:
                continue
            normalized.append(cleaned)
            seen.add(key)
        return cls(names=tuple(normalized), source=source)

    @classmethod
    def load(
        cls,
        *,
        http_get: Callable[[str], Any] | None = None,
        vendored_path: Path | None = None,
        upstream_url: str | None = None,
    ) -> Registry:
        """Try upstream manufacturers.json, then fall back to the vendored snapshot."""
        try:
            payload = _fetch_upstream(http_get=http_get, upstream_url=upstream_url or UPSTREAM_URL)
            return cls.from_names(_names_from_payload(payload), source="upstream")
        except (httpx.HTTPError, json.JSONDecodeError, ValueError):
            return cls.from_names(
                _names_from_payload(_read_json(vendored_path or VENDORED_PATH)),
                source="vendored",
            )

    def contains(self, name: str) -> bool:
        """Return true when a manufacturer has a case-insensitive exact match."""
        return name.casefold() in self._lookup_set

    def closest(self, name: str, n: int = 3) -> tuple[str, ...]:
        """Return closest canonical manufacturer names."""
        return tuple(get_close_matches(name, self.names, n=n, cutoff=0.6))


def reconcile_manufacturer(section: ManifestSection, *, registry: Registry) -> ReviewReport:
    """Emit at most one review flag for unknown manufacturers."""
    if registry.contains(section.manufacturer):
        return ReviewReport()

    suggestions = registry.closest(section.manufacturer)
    return ReviewReport(
        flags=(
            ReviewFlag(
                code=ReviewCode.UNKNOWN_MANUFACTURER,
                field="manufacturer",
                message="Manufacturer was not found in the OpenAVC registry.",
                details={
                    "manufacturer": section.manufacturer,
                    "suggestions": ", ".join(suggestions),
                    "registry_source": registry.source,
                },
            ),
        )
    )


def _fetch_upstream(*, http_get: Callable[[str], Any] | None, upstream_url: str) -> Any:
    if http_get is None:
        response = httpx.get(upstream_url, timeout=5.0)
    else:
        response = http_get(upstream_url)

    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    if hasattr(response, "json"):
        return response.json()
    return response


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _names_from_payload(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise ValueError("manufacturer registry must be a JSON array")
    if not all(isinstance(item, str) for item in payload):
        raise ValueError("manufacturer registry values must be strings")
    return tuple(payload)
