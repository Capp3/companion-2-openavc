"""Golden snapshots for simulator auto-generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_commands, extract_simulator, extract_state_variables
from c2o.parse.js import parse_module


def _snapshot_payload(root: Path) -> dict[str, Any]:
    parsed = parse_module(root)
    state_variables, _state_review = extract_state_variables(parsed)
    commands, _command_review = extract_commands(parsed)
    simulator, simulator_review = extract_simulator(state_variables, commands)

    return {
        "simulator": simulator.model_dump(exclude_none=True),
        "review": [flag.model_dump() for flag in simulator_review],
    }


def test_dummy_simulator_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_simulator_golden(bmd_webpresenter: Path, snapshot: Any) -> None:
    assert _snapshot_payload(bmd_webpresenter) == snapshot


def test_http_device_simulator_golden(http_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(http_device) == snapshot
