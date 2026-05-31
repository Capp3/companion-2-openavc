"""Unit tests for source resolver lifecycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import c2o.source.remote as remote
from c2o.source.errors import SourceResolutionError
from c2o.source.resolver import resolve_source


@pytest.fixture(autouse=True)
def reset_git_runner() -> None:
    remote._git_runner_override = None


def test_resolve_source_local_yields_absolute_root(tmp_path: Path) -> None:
    with resolve_source(str(tmp_path)) as resolved:
        assert resolved.root == tmp_path.resolve()
        assert resolved.tempdir is None
        assert resolved.clone_url is None


def test_resolve_source_removes_tempdir_after_context() -> None:
    seen_tempdir: Path | None = None

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal seen_tempdir
        seen_tempdir = Path(args[-1])
        (seen_tempdir / "marker").write_text("ok", encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    remote._git_runner_override = runner

    with resolve_source("file:///tmp/repo.git") as resolved:
        assert resolved.tempdir is not None
        assert resolved.root == resolved.tempdir
        assert (resolved.root / "marker").is_file()

    assert seen_tempdir is not None
    assert not seen_tempdir.exists()


def test_resolve_source_keeps_tempdir_when_requested(capsys: pytest.CaptureFixture[str]) -> None:
    seen_tempdir: Path | None = None

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal seen_tempdir
        seen_tempdir = Path(args[-1])
        (seen_tempdir / "marker").write_text("ok", encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    remote._git_runner_override = runner

    with resolve_source("file:///tmp/repo.git", keep_temp=True) as resolved:
        assert resolved.tempdir is not None

    assert seen_tempdir is not None
    assert seen_tempdir.is_dir()
    assert "Preserved clone at:" in capsys.readouterr().err

    # Test owns cleanup for preserved tempdirs.
    for child in seen_tempdir.iterdir():
        child.unlink()
    seen_tempdir.rmdir()


def test_resolve_source_cleans_partial_tempdir_after_clone_failure() -> None:
    seen_tempdir: Path | None = None

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal seen_tempdir
        seen_tempdir = Path(args[-1])
        (seen_tempdir / "partial").write_text("leftover", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=args,
            returncode=128,
            stdout="",
            stderr="clone failed",
        )

    remote._git_runner_override = runner

    with pytest.raises(SourceResolutionError, match="clone failed"):
        with resolve_source("file:///tmp/repo.git"):
            pass

    assert seen_tempdir is not None
    assert not seen_tempdir.exists()
