"""Unit tests for .review.json sidecar emission."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from c2o.emit.review import (
    build_review_sidecar,
    review_json_path_for_output,
    write_review_json,
)
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport


def test_review_json_path_for_avcdriver_output() -> None:
    assert review_json_path_for_output(Path("drivers/foo.avcdriver")) == Path(
        "drivers/foo.review.json"
    )


def test_review_json_path_for_non_avcdriver_output() -> None:
    assert review_json_path_for_output(Path("drivers/foo")) == Path("drivers/foo.review.json")


def test_build_review_sidecar_sorts_flags_and_formats_timestamp() -> None:
    review = ReviewReport(
        flags=(
            ReviewFlag(
                code=ReviewCode.SIMULATOR_AUTO,
                field="simulator",
                message="Simulator generated heuristically.",
            ),
            ReviewFlag(
                code=ReviewCode.ID_COERCED,
                field="id",
                message="Driver id was coerced.",
                details={"old": "dummy-device", "new": "dummy_device"},
            ),
        )
    )

    report = build_review_sidecar(
        source="/fixtures/dummy-device",
        module_id="dummy_device",
        review=review,
        generated_at=datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=UTC),
    )

    assert report.generated_at == "2026-01-01T00:00:00Z"
    assert [flag.code for flag in report.flags] == [
        ReviewCode.ID_COERCED,
        ReviewCode.SIMULATOR_AUTO,
    ]


def test_write_review_json_uses_stable_format(tmp_path: Path) -> None:
    report = build_review_sidecar(
        source="/fixtures/dummy-device",
        module_id="dummy_device",
        review=ReviewReport(
            flags=(
                ReviewFlag(
                    code=ReviewCode.ID_COERCED,
                    field="id",
                    message="Driver id was coerced.",
                    details={"old": "dummy-device", "new": "dummy_device"},
                ),
            )
        ),
        generated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
    )
    out_path = tmp_path / "nested" / "out.review.json"

    write_review_json(out_path, report)

    text = out_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == {
        "source": "/fixtures/dummy-device",
        "module_id": "dummy_device",
        "generated_at": "2026-01-01T00:00:00Z",
        "flags": [
            {
                "code": "id_coerced",
                "field": "id",
                "message": "Driver id was coerced.",
                "details": {"old": "dummy-device", "new": "dummy_device"},
            }
        ],
    }
