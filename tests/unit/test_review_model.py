"""Unit tests for extraction review models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport


def test_review_code_catalogue() -> None:
    assert [code.value for code in ReviewCode] == [
        "id_coerced",
        "category_default",
        "description_marketing",
        "unknown_manufacturer",
        "inferred_state_type",
        "state_dependent_branch",
        "missing_discovery_fingerprint",
        "compatible_models_confidence",
        "simulator_auto",
    ]


def test_review_flag_is_frozen() -> None:
    flag = ReviewFlag(
        code=ReviewCode.ID_COERCED,
        field="id",
        message="Driver id was coerced.",
        details={"old": "bmd-webpresenter", "new": "bmd_webpresenter"},
    )

    with pytest.raises(ValidationError):
        flag.field = "name"


def test_review_report_aggregates_flags_by_code() -> None:
    id_flag = ReviewFlag(
        code=ReviewCode.ID_COERCED,
        field="id",
        message="Driver id was coerced.",
        details={"old": "bmd-webpresenter", "new": "bmd_webpresenter"},
    )
    category_flag = ReviewFlag(
        code=ReviewCode.CATEGORY_DEFAULT,
        field="category",
        message="Category defaulted to utility.",
    )
    report = ReviewReport(flags=(id_flag, category_flag))

    assert len(report) == 2
    assert tuple(report) == (id_flag, category_flag)
    assert report.has_code(ReviewCode.ID_COERCED) is True
    assert report.has_code(ReviewCode.DESCRIPTION_MARKETING) is False
    assert report.by_code(ReviewCode.ID_COERCED) == (id_flag,)
