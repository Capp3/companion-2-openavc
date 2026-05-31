"""Unit tests for remote git cloning."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import c2o.source.remote as remote
from c2o.source.errors import SourceResolutionError
from c2o.source.remote import git_clone


@pytest.fixture(autouse=True)
def reset_git_runner() -> None:
    remote._git_runner_override = None


def test_git_clone_uses_depth_one_argv(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    remote._git_runner_override = runner

    git_clone("file:///tmp/repo.git", tmp_path / "clone")

    assert calls == [["clone", "--depth", "1", "file:///tmp/repo.git", str(tmp_path / "clone")]]


def test_git_clone_propagates_stderr(tmp_path: Path) -> None:
    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=128, stdout="", stderr="nope")

    remote._git_runner_override = runner

    with pytest.raises(SourceResolutionError, match="Failed to clone .*nope"):
        git_clone("https://example.test/repo.git", tmp_path / "clone")


def test_git_clone_reports_missing_git(tmp_path: Path) -> None:
    def runner(_args: list[str]) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    remote._git_runner_override = runner

    with pytest.raises(SourceResolutionError, match="git is required"):
        git_clone("https://example.test/repo.git", tmp_path / "clone")
