"""Unit tests for review flag models."""

from __future__ import annotations

from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport


def test_m14_review_codes_round_trip_through_report() -> None:
    flags = (
        ReviewFlag(
            code=ReviewCode.MISSING_DISCOVERY_FINGERPRINT,
            field="discovery",
            message="Missing rich discovery fingerprints.",
            details={"missing": "mdns,ssdp"},
        ),
        ReviewFlag(
            code=ReviewCode.COMPATIBLE_MODELS_CONFIDENCE,
            field="compatible_models",
            message="Compatible model confidence defaults to untested.",
        ),
    )

    report = ReviewReport(flags=flags)

    assert report.has_code(ReviewCode.MISSING_DISCOVERY_FINGERPRINT)
    assert report.has_code(ReviewCode.COMPATIBLE_MODELS_CONFIDENCE)
    assert report.by_code(ReviewCode.COMPATIBLE_MODELS_CONFIDENCE) == (flags[1],)
