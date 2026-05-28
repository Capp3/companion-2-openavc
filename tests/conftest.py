"""Shared pytest fixtures for C2O tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Fixed timestamp for deterministic decline snapshots (§11.4 determinism).
FROZEN_DECLINED_AT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


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


@pytest.fixture(autouse=True)
def frozen_declined_at(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin decline timestamps across CLI integration tests."""
    import c2o.cli

    monkeypatch.setattr(c2o.cli, "_declined_at_override", FROZEN_DECLINED_AT)


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
