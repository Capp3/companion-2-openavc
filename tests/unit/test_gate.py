"""Unit tests for the YAML suitability gate."""

from __future__ import annotations

from pathlib import Path

from c2o.parse.js import parse_module
from c2o.suitability.blockers import BlockerCode
from c2o.suitability.gate import assess_module


def test_blocker_code_catalogue_matches_brief() -> None:
    assert [code.value for code in BlockerCode] == [
        "transport_udp",
        "binary_framing",
        "auth_non_telnet",
        "transport_unknown",
        "transport_not_implemented",
        "commands_not_static",
        "responses_not_expressible",
    ]


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


def test_gate_aggregates_blockers_in_catalogue_order(tmp_path: Path) -> None:
    (tmp_path / "index.js").write_text(
        "import { InstanceBase, UDPHelper } from '@companion-module/base'\n"
        "const frame = Buffer.alloc(4)\n",
        encoding="utf-8",
    )
    gate = assess_module(parse_module(tmp_path))
    assert [blocker.code for blocker in gate.blockers] == [
        BlockerCode.TRANSPORT_UDP,
        BlockerCode.BINARY_FRAMING,
    ]


def test_declined_binary_framing_has_binary_framing_blocker(fixtures_dir: Path) -> None:
    gate = assess_module(parse_module(fixtures_dir / "declined-binary-framing"))
    assert gate.eligible is False
    assert [blocker.code for blocker in gate.blockers] == [BlockerCode.BINARY_FRAMING]
    assert "Buffer.alloc" in gate.blockers[0].evidence


def test_declined_auth_non_telnet_has_auth_blocker(fixtures_dir: Path) -> None:
    gate = assess_module(parse_module(fixtures_dir / "declined-auth-non-telnet"))
    assert gate.eligible is False
    assert [blocker.code for blocker in gate.blockers] == [BlockerCode.AUTH_NON_TELNET]
    assert "LOGIN" in gate.blockers[0].evidence


def test_declined_transport_unknown_has_unknown_transport_blocker(fixtures_dir: Path) -> None:
    gate = assess_module(parse_module(fixtures_dir / "declined-transport-unknown"))
    assert gate.eligible is False
    assert [blocker.code for blocker in gate.blockers] == [BlockerCode.TRANSPORT_UNKNOWN]
    assert "no recognised transport helper" in gate.blockers[0].evidence


def test_declined_osc_has_transport_not_implemented_blocker(tmp_path: Path) -> None:
    (tmp_path / "index.js").write_text(
        "import { InstanceBase } from '@companion-module/base'\n"
        "import OSC from 'osc-js'\n"
        "export class Instance extends InstanceBase {\n"
        "  updateActions() { this.oscSend('/eos/key/go', 1) }\n"
        "}\n",
        encoding="utf-8",
    )
    gate = assess_module(parse_module(tmp_path))
    assert gate.eligible is False
    assert [blocker.code for blocker in gate.blockers] == [
        BlockerCode.TRANSPORT_NOT_IMPLEMENTED
    ]
    assert "osc-js" in gate.blockers[0].evidence


def test_declined_commands_not_static_has_commands_blocker(fixtures_dir: Path) -> None:
    gate = assess_module(parse_module(fixtures_dir / "declined-commands-not-static"))
    assert gate.eligible is False
    assert [blocker.code for blocker in gate.blockers] == [BlockerCode.COMMANDS_NOT_STATIC]
    assert "Date.now" in gate.blockers[0].evidence


def test_declined_responses_not_expressible_has_responses_blocker(fixtures_dir: Path) -> None:
    gate = assess_module(parse_module(fixtures_dir / "declined-responses-not-expressible"))
    assert gate.eligible is False
    assert [blocker.code for blocker in gate.blockers] == [BlockerCode.RESPONSES_NOT_EXPRESSIBLE]
    assert "switch (this.parserState)" in gate.blockers[0].evidence


def test_bmd_webpresenter_is_eligible(bmd_webpresenter: Path) -> None:
    gate = assess_module(parse_module(bmd_webpresenter))
    assert gate.eligible is True


def test_unknown_vendor_is_eligible(unknown_vendor: Path) -> None:
    gate = assess_module(parse_module(unknown_vendor))
    assert gate.eligible is True
    assert gate.blockers == ()


def test_http_device_is_eligible(http_device: Path) -> None:
    gate = assess_module(parse_module(http_device))
    assert gate.eligible is True
    assert gate.blockers == ()


def test_panasonic_ptz_is_eligible(panasonic_ptz: Path) -> None:
    """Panasonic PTZ uses got.get() HTTP and src/ layout — must be eligible."""
    gate = assess_module(parse_module(panasonic_ptz))
    assert gate.eligible is True
    assert gate.blockers == ()
