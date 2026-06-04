"""Structured .review.json sidecar emission for lenient conversions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from c2o.model.review import ReviewFlag, ReviewReport

# Injectable clock for tests (monkeypatch this attribute).
_review_at_override: datetime | None = None


class ReviewSidecarReport(BaseModel):
    """Machine-readable review report for lenient eligible conversions."""

    model_config = ConfigDict(populate_by_name=True)

    source: str
    module_id: str
    generated_at: str
    flags: list[ReviewFlag]


def _to_utc_iso(when: datetime) -> str:
    return when.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sorted_flags(review: ReviewReport) -> list[ReviewFlag]:
    return sorted(review.flags, key=lambda flag: (flag.code.value, flag.field))


def build_review_sidecar(
    *,
    source: str,
    module_id: str,
    review: ReviewReport,
    generated_at: datetime | None = None,
) -> ReviewSidecarReport:
    """Build a review sidecar report with deterministic flag ordering."""
    when = generated_at or _review_at_override or datetime.now(tz=UTC)
    return ReviewSidecarReport(
        source=source,
        module_id=module_id,
        generated_at=_to_utc_iso(when),
        flags=_sorted_flags(review),
    )


def write_review_json(path: Path, report: ReviewSidecarReport) -> None:
    """Write review JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json", exclude_none=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def review_json_path_for_output(output: Path) -> Path:
    """Map `-o foo.avcdriver` -> `foo.review.json` in the same directory."""
    if output.suffix == ".avcdriver":
        return output.with_suffix(".review.json")
    return output.parent / f"{output.name}.review.json"
