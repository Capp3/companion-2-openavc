"""Structured .declined.json sidecar emission (§5.3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from c2o.suitability.blockers import Blocker

_RECOMMENDATION = (
    "This Companion module cannot be converted to a .avcdriver by C2O. "
    "Author an OpenAVC Python driver manually per upstream AGENTS.md §3 "
    "(https://github.com/open-avc/openavc-drivers/blob/main/AGENTS.md#3-python-driver-api)."
)


class DeclinedReport(BaseModel):
    """Machine-readable decline report matching brief §5.3."""

    model_config = ConfigDict(populate_by_name=True)

    eligible: bool = False
    source: str
    module_id: str
    declined_at: str
    blockers: list[Blocker]
    recommendation: str = _RECOMMENDATION


def build_declined_report(
    *,
    source: str,
    module_id: str,
    blockers: list[Blocker],
    declined_at: datetime | None = None,
) -> DeclinedReport:
    """Build a decline report; `declined_at` is injectable for deterministic tests."""
    when = declined_at or datetime.now(tz=UTC)
    iso = when.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return DeclinedReport(
        source=source,
        module_id=module_id,
        declined_at=iso,
        blockers=blockers,
    )


def write_declined_json(path: Path, report: DeclinedReport) -> None:
    """Write decline JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def declined_json_path_for_output(output: Path) -> Path:
    """Map `-o foo.avcdriver` → `foo.declined.json` in the same directory."""
    if output.suffix == ".avcdriver":
        return output.with_suffix(".declined.json")
    return output.parent / f"{output.name}.declined.json"
