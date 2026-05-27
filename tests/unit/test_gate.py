"""Unit tests for the YAML suitability gate."""

from __future__ import annotations

from pathlib import Path

from c2o.parse.js import parse_module
from c2o.suitability.blockers import BlockerCode
from c2o.suitability.gate import assess_module


def test_dummy_device_is_eligible(dummy_device: Path) -> None:
    gate = assess_module(parse_module(dummy_device))
    assert gate.eligible is True
    assert gate.blockers == ()


def test_declined_udp_has_transport_udp_blocker(declined_udp: Path) -> None:
    gate = assess_module(parse_module(declined_udp))
    assert gate.eligible is False
    assert len(gate.blockers) == 1
    assert gate.blockers[0].code == BlockerCode.TRANSPORT_UDP
    assert "UDPHelper" in gate.blockers[0].evidence


def test_bmd_webpresenter_is_eligible(bmd_webpresenter: Path) -> None:
    gate = assess_module(parse_module(bmd_webpresenter))
    assert gate.eligible is True
