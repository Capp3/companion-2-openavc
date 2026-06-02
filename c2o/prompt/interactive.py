"""Interactive prompt application for metadata that C2O cannot infer safely."""

from __future__ import annotations

import sys
from typing import Protocol

import typer

from c2o.model.driver import DriverCategory, ManifestSection
from c2o.model.review import ReviewCode, ReviewReport

CATEGORY_CHOICES: tuple[DriverCategory, ...] = (
    "projector",
    "display",
    "switcher",
    "audio",
    "camera",
    "video",
    "streaming",
    "lighting",
    "power",
    "utility",
)


class Prompter(Protocol):
    """Prompt provider used by CLI and tests."""

    def prompt_category(
        self, current: DriverCategory, keywords: list[str]
    ) -> DriverCategory | None:
        """Return a selected category, or None to skip."""
        ...

    def prompt_manufacturer(self, current: str, suggestions: tuple[str, ...]) -> str | None:
        """Return a confirmed/provided manufacturer, or None to skip."""
        ...

    def prompt_author(self, current: str) -> str | None:
        """Return a provided author, or None to skip."""
        ...


class TyperPrompter:
    """Typer-backed prompter for interactive CLI runs."""

    def __init__(self, *, is_tty: bool | None = None) -> None:
        self._is_tty = sys.stdin.isatty() if is_tty is None else is_tty
        self._warned_not_tty = False

    def prompt_category(
        self, current: DriverCategory, keywords: list[str]
    ) -> DriverCategory | None:
        if not self._can_prompt():
            return None

        typer.echo("Category could not be inferred safely.")
        if keywords:
            typer.echo(f"Manifest keywords: {', '.join(keywords)}")
        for index, category in enumerate(CATEGORY_CHOICES, start=1):
            typer.echo(f"  {index}. {category}")
        default = str(CATEGORY_CHOICES.index(current) + 1)
        answer = typer.prompt("Category choice", default=default)
        return self.parse_category_choice(str(answer))

    def prompt_manufacturer(self, current: str, suggestions: tuple[str, ...]) -> str | None:
        if not self._can_prompt():
            return None

        typer.echo("Manufacturer was not found in the OpenAVC registry.")
        typer.echo(f"Current manufacturer: {current}")
        if suggestions:
            typer.echo("Closest matches:")
            for index, suggestion in enumerate(suggestions, start=1):
                typer.echo(f"  {index}. {suggestion}")
        answer = typer.prompt(
            "Manufacturer name or suggestion number",
            default=current,
        )
        return self.parse_manufacturer_answer(str(answer), suggestions)

    def prompt_author(self, current: str) -> str | None:
        if not self._can_prompt():
            return None

        answer = typer.prompt("Author", default=current)
        value = str(answer).strip()
        return value or current

    @staticmethod
    def parse_category_choice(value: str) -> DriverCategory | None:
        try:
            index = int(value.strip())
        except ValueError:
            return None
        if 1 <= index <= len(CATEGORY_CHOICES):
            return CATEGORY_CHOICES[index - 1]
        return None

    @staticmethod
    def parse_manufacturer_answer(value: str, suggestions: tuple[str, ...]) -> str | None:
        answer = value.strip()
        if not answer:
            return None
        try:
            index = int(answer)
        except ValueError:
            return answer
        if 1 <= index <= len(suggestions):
            return suggestions[index - 1]
        return answer

    def _can_prompt(self) -> bool:
        if self._is_tty:
            return True
        if not self._warned_not_tty:
            typer.echo(
                "Prompts skipped: not a terminal " "(run in a TTY to enable interactive prompts).",
                err=True,
            )
            self._warned_not_tty = True
        return False


def apply_interactive_prompts(
    manifest: ManifestSection,
    review: ReviewReport,
    *,
    prompter: Prompter,
) -> tuple[ManifestSection, ReviewReport]:
    """Apply prompted metadata answers and drop flags resolved by answers."""

    updates: dict[str, str] = {}
    resolved_codes: set[ReviewCode] = set()

    if review.has_code(ReviewCode.CATEGORY_DEFAULT):
        category_flag = review.by_code(ReviewCode.CATEGORY_DEFAULT)[0]
        category_answer = prompter.prompt_category(
            manifest.category,
            _split_detail_list(category_flag.details.get("keywords", "")),
        )
        if category_answer is not None:
            updates["category"] = category_answer
            resolved_codes.add(ReviewCode.CATEGORY_DEFAULT)

    if review.has_code(ReviewCode.UNKNOWN_MANUFACTURER):
        manufacturer_flag = review.by_code(ReviewCode.UNKNOWN_MANUFACTURER)[0]
        manufacturer_answer = prompter.prompt_manufacturer(
            manifest.manufacturer,
            tuple(_split_detail_list(manufacturer_flag.details.get("suggestions", ""))),
        )
        if manufacturer_answer is not None:
            updates["manufacturer"] = manufacturer_answer
            resolved_codes.add(ReviewCode.UNKNOWN_MANUFACTURER)

    if review.has_code(ReviewCode.AUTHOR_DEFAULT):
        author_answer = prompter.prompt_author(manifest.author)
        if author_answer is not None:
            updates["author"] = author_answer
            resolved_codes.add(ReviewCode.AUTHOR_DEFAULT)

    updated_review = ReviewReport(
        flags=tuple(flag for flag in review.flags if flag.code not in resolved_codes)
    )
    if not updates:
        return manifest, updated_review
    return manifest.model_copy(update=updates), updated_review


def _split_detail_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
