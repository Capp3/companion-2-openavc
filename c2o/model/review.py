"""Review flag models for lossy or heuristic extraction results."""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewCode(StrEnum):
    """Stable review flag codes emitted by extractors."""

    ID_COERCED = "id_coerced"
    CATEGORY_DEFAULT = "category_default"
    DESCRIPTION_MARKETING = "description_marketing"
    UNKNOWN_MANUFACTURER = "unknown_manufacturer"
    INFERRED_STATE_TYPE = "inferred_state_type"
    STATE_DEPENDENT_BRANCH = "state_dependent_branch"
    MISSING_DISCOVERY_FINGERPRINT = "missing_discovery_fingerprint"
    COMPATIBLE_MODELS_CONFIDENCE = "compatible_models_confidence"


class ReviewFlag(BaseModel):
    """A single extraction review flag with user-facing context."""

    model_config = ConfigDict(frozen=True)

    code: ReviewCode
    field: str
    message: str
    details: dict[str, str] = Field(default_factory=dict)


class ReviewReport(BaseModel):
    """Collection of review flags emitted while extracting one module."""

    model_config = ConfigDict(frozen=True)

    flags: tuple[ReviewFlag, ...] = ()

    def __len__(self) -> int:
        return len(self.flags)

    def __iter__(self) -> Iterator[ReviewFlag]:  # type: ignore[override]
        return iter(self.flags)

    def has_code(self, code: ReviewCode) -> bool:
        return any(flag.code == code for flag in self.flags)

    def by_code(self, code: ReviewCode) -> tuple[ReviewFlag, ...]:
        return tuple(flag for flag in self.flags if flag.code == code)
