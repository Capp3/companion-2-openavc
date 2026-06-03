"""Shared pytest fixtures for C2O tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Fixed timestamp for deterministic decline snapshots (§11.4 determinism).
FROZEN_DECLINED_AT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
FROZEN_LOG_AT = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def dummy_device(fixtures_dir: Path) -> Path:
    return fixtures_dir / "dummy-device"


@pytest.fixture
def declined_udp(fixtures_dir: Path) -> Path:
    return fixtures_dir / "declined-udp"


@pytest.fixture
def bmd_webpresenter(fixtures_dir: Path) -> Path:
    return fixtures_dir / "external" / "bmd-webpresenter"


@pytest.fixture
def unknown_vendor(fixtures_dir: Path) -> Path:
    return fixtures_dir / "unknown-vendor"


@pytest.fixture
def static_on_connect(fixtures_dir: Path) -> Path:
    return fixtures_dir / "static-on-connect"


@pytest.fixture
def http_device(fixtures_dir: Path) -> Path:
    return fixtures_dir / "http-device"


@pytest.fixture(scope="session")
def dummy_device_git_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Build a bare git mirror of dummy-device and return a file:// URL."""
    if shutil.which("git") is None:
        pytest.skip("git is required for source-resolution smoke tests")

    root = tmp_path_factory.mktemp("dummy-device-git")
    worktree = root / "worktree"
    bare_repo = root / "dummy-device.git"
    shutil.copytree(FIXTURES_DIR / "dummy-device", worktree)

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "c2o",
        "GIT_AUTHOR_EMAIL": "c2o@test",
        "GIT_COMMITTER_NAME": "c2o",
        "GIT_COMMITTER_EMAIL": "c2o@test",
    }

    def run_git(args: list[str], *, cwd: Path | None = None) -> None:
        subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    run_git(["init"], cwd=worktree)
    run_git(["checkout", "-b", "main"], cwd=worktree)
    run_git(["add", "-A"], cwd=worktree)
    run_git(["commit", "-m", "Add dummy fixture"], cwd=worktree)
    run_git(["init", "--bare", str(bare_repo)])
    run_git(["remote", "add", "origin", str(bare_repo)], cwd=worktree)
    run_git(["push", "origin", "HEAD:main"], cwd=worktree)

    return bare_repo.as_uri()


@pytest.fixture(autouse=True)
def frozen_declined_at(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin decline timestamps across CLI integration tests."""
    import c2o.cli

    monkeypatch.setattr(c2o.cli, "_declined_at_override", FROZEN_DECLINED_AT)


@pytest.fixture(autouse=True)
def frozen_log_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin structured log timestamps across CLI integration tests."""
    import c2o.log

    monkeypatch.setattr(c2o.log, "_clock_override", lambda: FROZEN_LOG_AT)


@pytest.fixture(autouse=True)
def patched_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the CLI registry across tests to the vendored snapshot."""
    import c2o.cli
    from c2o.registry import VENDORED_PATH, Registry

    registry = Registry.from_names(
        json.loads(VENDORED_PATH.read_text(encoding="utf-8")),
        source="vendored",
    )
    monkeypatch.setattr(c2o.cli, "_registry_override", registry)
