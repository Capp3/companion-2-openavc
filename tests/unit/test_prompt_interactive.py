"""Unit tests for interactive prompt application."""

from __future__ import annotations

from dataclasses import dataclass

from c2o.model.driver import DriverCategory, ManifestSection
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport
from c2o.prompt.interactive import (
    Prompter,
    TyperPrompter,
    apply_interactive_prompts,
)


def _manifest() -> ManifestSection:
    return ManifestSection(
        id="example_device",
        name="Example Device",
        manufacturer="Exampel",
        category="utility",
        version="1.0.0",
        author="Community",
        description="Controls an example device.",
        source_url=None,
    )


def _flag(code: ReviewCode, field: str, **details: str) -> ReviewFlag:
    return ReviewFlag(
        code=code,
        field=field,
        message=f"{field} requires review.",
        details=details,
    )


@dataclass
class FakePrompter(Prompter):
    category: DriverCategory | None = None
    manufacturer: str | None = None
    author: str | None = None
    category_keywords: list[str] | None = None
    manufacturer_suggestions: tuple[str, ...] | None = None

    def prompt_category(
        self, current: DriverCategory, keywords: list[str]
    ) -> DriverCategory | None:
        self.category_keywords = keywords
        return self.category

    def prompt_manufacturer(self, current: str, suggestions: tuple[str, ...]) -> str | None:
        self.manufacturer_suggestions = suggestions
        return self.manufacturer

    def prompt_author(self, current: str) -> str | None:
        return self.author


def test_apply_interactive_prompts_updates_answered_fields_and_drops_flags() -> None:
    review = ReviewReport(
        flags=(
            _flag(ReviewCode.CATEGORY_DEFAULT, "category", keywords="fixture,control"),
            _flag(
                ReviewCode.UNKNOWN_MANUFACTURER,
                "manufacturer",
                suggestions="Example Co, Example Controls",
            ),
            _flag(ReviewCode.AUTHOR_DEFAULT, "author"),
        )
    )
    prompter = FakePrompter(
        category="video",
        manufacturer="Example Co",
        author="Example Maintainer",
    )

    manifest, updated_review = apply_interactive_prompts(_manifest(), review, prompter=prompter)

    assert manifest.category == "video"
    assert manifest.manufacturer == "Example Co"
    assert manifest.author == "Example Maintainer"
    assert updated_review.flags == ()
    assert prompter.category_keywords == ["fixture", "control"]
    assert prompter.manufacturer_suggestions == ("Example Co", "Example Controls")


def test_apply_interactive_prompts_keeps_skipped_fields_and_flags() -> None:
    review = ReviewReport(
        flags=(
            _flag(ReviewCode.CATEGORY_DEFAULT, "category", keywords="fixture"),
            _flag(ReviewCode.UNKNOWN_MANUFACTURER, "manufacturer", suggestions=""),
            _flag(ReviewCode.AUTHOR_DEFAULT, "author"),
        )
    )

    manifest, updated_review = apply_interactive_prompts(
        _manifest(), review, prompter=FakePrompter()
    )

    assert manifest == _manifest()
    assert tuple(flag.code for flag in updated_review.flags) == (
        ReviewCode.CATEGORY_DEFAULT,
        ReviewCode.UNKNOWN_MANUFACTURER,
        ReviewCode.AUTHOR_DEFAULT,
    )


def test_apply_interactive_prompts_preserves_unrelated_flags() -> None:
    unrelated = _flag(ReviewCode.DESCRIPTION_MARKETING, "description", phrase="best")
    review = ReviewReport(
        flags=(
            _flag(ReviewCode.AUTHOR_DEFAULT, "author"),
            unrelated,
        )
    )

    updated_manifest, updated_review = apply_interactive_prompts(
        _manifest(), review, prompter=FakePrompter(author="Community")
    )

    assert updated_manifest.author == "Community"
    assert updated_review.flags == (unrelated,)


def test_typer_prompter_category_choice_parsing() -> None:
    assert TyperPrompter.parse_category_choice("6") == "video"
    assert TyperPrompter.parse_category_choice("not-a-choice") is None
    assert TyperPrompter.parse_category_choice("11") is None


def test_typer_prompter_manufacturer_answer_parsing() -> None:
    suggestions = ("Example Co", "Example Controls")

    assert TyperPrompter.parse_manufacturer_answer("1", suggestions) == "Example Co"
    assert TyperPrompter.parse_manufacturer_answer("Custom Maker", suggestions) == ("Custom Maker")
    assert TyperPrompter.parse_manufacturer_answer("", suggestions) is None


def test_typer_prompter_skips_all_prompts_when_not_tty() -> None:
    prompter = TyperPrompter(is_tty=False)

    assert prompter.prompt_category("utility", []) is None
    assert prompter.prompt_manufacturer("Example", ("Example Co",)) is None
    assert prompter.prompt_author("Community") is None
