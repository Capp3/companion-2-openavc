"""Unit tests for upstream validation staging and parsing."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from c2o.validate import upstream
from c2o.validate.upstream import validate_upstream

FIXTURES = Path(__file__).parents[1] / "fixtures" / "validate"
VALID_DRIVER = FIXTURES / "minimal-valid.avcdriver"
INVALID_DRIVER = FIXTURES / "tampered-invalid.avcdriver"


def test_category_to_dir_matches_upstream_categories() -> None:
    assert upstream.CATEGORY_TO_DIR == {
        "projector": "projectors",
        "display": "displays",
        "switcher": "switchers",
        "audio": "audio",
        "camera": "cameras",
        "video": "video",
        "streaming": "streaming",
        "lighting": "lighting",
        "power": "power",
        "utility": "utility",
    }


def test_stage_driver_island_copies_driver_and_manufacturers() -> None:
    with upstream._stage_driver_island(VALID_DRIVER) as repo_root:
        staged_driver = repo_root / "utility" / VALID_DRIVER.name

        assert (repo_root / "manufacturers.json").is_file()
        assert staged_driver.read_text(encoding="utf-8") == VALID_DRIVER.read_text(encoding="utf-8")

    assert not repo_root.exists()


def test_parse_upstream_errors_extracts_failed_bullets() -> None:
    stderr = """
FAILED: 2 validation error(s):

  - utility/foo.avcdriver: version: String should match pattern
  - utility/foo.avcdriver: source_url: String should match pattern
"""

    assert upstream._parse_upstream_errors(stderr) == [
        "utility/foo.avcdriver: version: String should match pattern",
        "utility/foo.avcdriver: source_url: String should match pattern",
    ]


def test_errors_to_pointers_extracts_field_locations() -> None:
    assert upstream._errors_to_pointers(
        [
            "utility/foo.avcdriver: version: String should match pattern",
            "utility/foo.avcdriver: commands.power.label: Field required",
            "utility/foo.avcdriver: manufacturer 'Nope' not in manufacturers.json",
        ]
    ) == ["/version", "/commands/power/label"]


def test_validate_upstream_returns_subprocess_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(repo_root: Path) -> subprocess.CompletedProcess[str]:
        assert (repo_root / "utility" / VALID_DRIVER.name).is_file()
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Validated 1 driver(s), 0 device(s).\n",
            stderr="",
        )

    monkeypatch.setattr(upstream, "_run_build_index_check", fake_run)

    result = validate_upstream(VALID_DRIVER)

    assert result.passed is True
    assert result.exit_code == 0
    assert result.stdout == "Validated 1 driver(s), 0 device(s).\n"
    assert result.errors == []
    assert result.pointers == []


def test_validate_upstream_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_upstream(tmp_path / "missing.avcdriver")


def test_validate_upstream_rejects_wrong_suffix(tmp_path: Path) -> None:
    path = tmp_path / "driver.yaml"
    path.write_text("id: wrong_suffix\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\.avcdriver"):
        validate_upstream(path)


def test_validate_upstream_runs_real_vendored_validator() -> None:
    result = validate_upstream(INVALID_DRIVER)

    assert result.passed is False
    assert result.exit_code == 1
    assert "FAILED: 1 validation error(s):" in result.stderr
    assert "utility/tampered-invalid.avcdriver: version:" in result.stderr
    assert result.pointers == ["/version"]
