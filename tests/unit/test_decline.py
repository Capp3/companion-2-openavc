"""Unit tests for decline report emission."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from c2o.emit.decline import (
    build_declined_report,
    declined_json_path_for_output,
    write_declined_json,
)
from c2o.suitability.blockers import Blocker, BlockerCode


def test_declined_json_path_for_avcdriver_output() -> None:
    assert declined_json_path_for_output(Path("/tmp/foo.avcdriver")) == Path(
        "/tmp/foo.declined.json"
    )


def test_build_and_write_declined_report(tmp_path: Path) -> None:
    blocker = Blocker(
        code=BlockerCode.TRANSPORT_UDP,
        message="UDP",
        evidence="index.js:1",
        upstream_reference="AGENTS.md",
    )
    report = build_declined_report(
        source="/fixture",
        module_id="declined_udp",
        blockers=[blocker],
        declined_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    out = tmp_path / "x.declined.json"
    write_declined_json(out, report)
    text = out.read_text(encoding="utf-8")
    assert '"module_id": "declined_udp"' in text
    assert '"declined_at": "2026-01-01T00:00:00Z"' in text
