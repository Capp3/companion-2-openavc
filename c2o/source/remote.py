"""Remote git source cloning."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from c2o.source.errors import SourceResolutionError

GitRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]

_git_runner_override: GitRunner | None = None


def git_clone(url: str, dest: Path, *, depth: int = 1) -> None:
    """Clone a remote git repository into dest."""
    try:
        result = _run_git(["clone", "--depth", str(depth), url, str(dest)])
    except FileNotFoundError as exc:
        raise SourceResolutionError(
            "git is required for remote sources but was not found on PATH"
        ) from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise SourceResolutionError(f"Failed to clone {url}{suffix}")


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    if _git_runner_override is not None:
        return _git_runner_override(args)
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
