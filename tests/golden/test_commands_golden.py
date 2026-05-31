"""Golden snapshots for command extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from c2o.extract import extract_commands
from c2o.model.review import ReviewCode
from c2o.parse.js import parse_module


def _snapshot_payload(root: Path, *, bmd_subset: bool = False) -> dict[str, Any]:
    section, review = extract_commands(parse_module(root))
    commands = section.model_dump(exclude_none=True)
    flags = [flag.model_dump() for flag in review]

    if bmd_subset:
        commands["commands"] = {
            key: value
            for key, value in commands.get("commands", {}).items()
            if key in {"stream_start", "stream_stop"}
        }
        flags = [
            flag
            for flag in flags
            if flag["code"] == ReviewCode.STATE_DEPENDENT_BRANCH
            and flag["field"] == "commands.stream"
        ]

    return {"commands": commands, "review": flags}


def test_dummy_commands_golden(dummy_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(dummy_device) == snapshot


def test_bmd_webpresenter_stream_commands_golden(
    bmd_webpresenter: Path,
    snapshot: Any,
) -> None:
    assert _snapshot_payload(bmd_webpresenter, bmd_subset=True) == snapshot


def test_http_device_commands_golden(http_device: Path, snapshot: Any) -> None:
    assert _snapshot_payload(http_device) == snapshot
