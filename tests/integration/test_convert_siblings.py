"""Integration tests for Companion sibling artefact emission."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from c2o.cli import app


def test_convert_dummy_writes_sibling_yaml_before_strict_failure(
    dummy_device: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    out_avc = tmp_path / "out.avcdriver"

    result = CliRunner().invoke(app, ["convert", str(dummy_device), "-o", str(out_avc)])

    assert result.exit_code == 1, result.stdout + result.stderr
    assert not out_avc.exists()
    assert (tmp_path / "out.companion-feedbacks.yml").read_text(encoding="utf-8") == snapshot(
        name="feedbacks"
    )
    assert (tmp_path / "out.companion-presets.yml").read_text(encoding="utf-8") == snapshot(
        name="presets"
    )


def test_convert_bmd_writes_sibling_yaml_before_strict_failure(
    bmd_webpresenter: Path,
    tmp_path: Path,
    snapshot: Any,
) -> None:
    out_avc = tmp_path / "out.avcdriver"

    result = CliRunner().invoke(app, ["convert", str(bmd_webpresenter), "-o", str(out_avc)])

    assert result.exit_code == 1, result.stdout + result.stderr
    assert not out_avc.exists()
    assert (tmp_path / "out.companion-feedbacks.yml").read_text(encoding="utf-8") == snapshot(
        name="feedbacks"
    )
    assert (tmp_path / "out.companion-presets.yml").read_text(encoding="utf-8") == snapshot(
        name="presets"
    )


def test_convert_declined_writes_no_sibling_yaml(
    declined_udp: Path,
    tmp_path: Path,
) -> None:
    out_avc = tmp_path / "out.avcdriver"

    result = CliRunner().invoke(app, ["convert", str(declined_udp), "-o", str(out_avc)])

    assert result.exit_code == 2, result.stdout + result.stderr
    assert not (tmp_path / "out.companion-feedbacks.yml").exists()
    assert not (tmp_path / "out.companion-presets.yml").exists()


def test_convert_sibling_yaml_is_deterministic(
    dummy_device: Path,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first" / "out.avcdriver"
    second = tmp_path / "second" / "out.avcdriver"

    first_result = CliRunner().invoke(app, ["convert", str(dummy_device), "-o", str(first)])
    second_result = CliRunner().invoke(app, ["convert", str(dummy_device), "-o", str(second)])

    assert first_result.exit_code == 1, first_result.stdout + first_result.stderr
    assert second_result.exit_code == 1, second_result.stdout + second_result.stderr
    assert first.with_suffix(".companion-feedbacks.yml").read_text(
        encoding="utf-8"
    ) == second.with_suffix(".companion-feedbacks.yml").read_text(encoding="utf-8")
    assert first.with_suffix(".companion-presets.yml").read_text(
        encoding="utf-8"
    ) == second.with_suffix(".companion-presets.yml").read_text(encoding="utf-8")
