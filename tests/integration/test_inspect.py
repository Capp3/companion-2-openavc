"""Integration tests for `c2o inspect`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from c2o.cli import app


def test_inspect_declined_prints_eligibility_first(declined_udp: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(declined_udp)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Eligibility: declined"
    assert "Blockers: 1" in result.stdout
    assert "transport_udp" in result.stdout
    assert "UDPHelper" in result.stdout


def test_inspect_eligible_prints_manifest_metadata(dummy_device: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(dummy_device)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Eligibility: eligible"
    assert "Ready for extraction: yes" in result.stdout
    assert "Metadata:" in result.stdout
    assert "  id: dummy_device" in result.stdout
    assert "  name: Dummy Device" in result.stdout
    assert "  manufacturer: Generic" in result.stdout
    assert "  category: utility" in result.stdout
    assert "  version: 1.0.0" in result.stdout
    assert "  author: C2O Fixture Bot" in result.stdout
    assert "  source_url: https://github.com/Capp3/companion-2-openavc" in result.stdout
    assert "Manufacturer match: ok" in result.stdout
    assert "Transport: tcp" in result.stdout
    assert 'Delimiter: "\\n"' in result.stdout
    assert "Config fields: 5" in result.stdout
    assert '  host: string (default: "192.168.1.10")' in result.stdout
    assert "  port: integer (default: 5000)" in result.stdout
    assert "  poll_interval: integer (default: 5)" in result.stdout
    assert "State variables: 3" in result.stdout
    assert '  device_label: string ("Device Label")' in result.stdout
    assert '  input_level: integer ("Input Level")' in result.stdout
    assert '  mute_state: boolean ("Mute State")' in result.stdout
    assert "Commands: 4" in result.stdout
    assert "  set_input:" in result.stdout
    assert "  stream_start:" in result.stdout
    assert "Review flags: 4" in result.stdout


def test_inspect_bmd_webpresenter_prints_id_coercion_flag(bmd_webpresenter: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(bmd_webpresenter)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "  id: bmd_webpresenter" in result.stdout
    assert "  name: WebPresenter" in result.stdout
    assert "  manufacturer: Blackmagic Design" in result.stdout
    assert "  category: streaming" in result.stdout
    assert "  version: 2.1.3" in result.stdout
    assert "  author: Peter Daniel" in result.stdout
    assert (
        "  source_url: https://github.com/bitfocus/companion-module-bmd-webpresenter"
        in result.stdout
    )
    assert "Manufacturer match: ok" in result.stdout
    assert "Transport: tcp" in result.stdout
    assert 'Delimiter: "\\n"' in result.stdout
    assert "Config fields: 2" in result.stdout
    assert '  host: string (default: "")' in result.stdout
    assert "  port: integer (default: 9977)" in result.stdout
    assert "State variables: 17" in result.stdout
    assert '  model: string ("Device Model")' in result.stdout
    assert '  label: string ("Device Label")' in result.stdout
    assert '  software: string ("Device Software")' in result.stdout
    assert "Commands: 2" in result.stdout
    assert "  stream_start:" in result.stdout
    assert "Review flags: 19" in result.stdout
    assert "[id_coerced] id -" in result.stdout


def test_inspect_unknown_vendor_emits_review_flag(unknown_vendor: Path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(unknown_vendor)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "  id: unknown_vendor_device" in result.stdout
    assert "  manufacturer: Blackmagic Designs" in result.stdout
    assert "Manufacturer match: unknown (suggestions: Blackmagic Design" in result.stdout
    assert "Transport: tcp" in result.stdout
    assert 'Delimiter: <default ("\\r")>' in result.stdout
    assert "Config fields: 0" in result.stdout
    assert "State variables: 0" in result.stdout
    assert "Commands: 0" in result.stdout
    assert "Review flags: 1" in result.stdout
    assert "[unknown_manufacturer] manufacturer -" in result.stdout


def test_inspect_tcp_fixture_without_delimiter_evidence_uses_default(tmp_path: Path) -> None:
    (tmp_path / "companion").mkdir()
    (tmp_path / "companion" / "manifest.json").write_text(
        """
        {
          "id": "default_delimiter",
          "name": "Default Delimiter",
          "shortname": "Default Delimiter",
          "description": "Fixture with no explicit delimiter evidence.",
          "version": "1.0.0",
          "manufacturer": "Generic",
          "maintainers": [{ "name": "C2O Fixture Bot" }],
          "keywords": ["utility"],
          "repository": "https://github.com/example/default-delimiter"
        }
        """,
        encoding="utf-8",
    )
    (tmp_path / "index.js").write_text(
        "import { InstanceBase, TCPHelper, runEntrypoint } from '@companion-module/base'\n"
        "class DefaultDelimiter extends InstanceBase {\n"
        "  async init(config) { this.socket = new TCPHelper(config.host, config.port) }\n"
        "}\n"
        "runEntrypoint(DefaultDelimiter)\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["inspect", str(tmp_path)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Transport: tcp" in result.stdout
    assert 'Delimiter: <default ("\\r")>' in result.stdout
    assert "Config fields: 0" in result.stdout
    assert "State variables: 0" in result.stdout
    assert "Commands: 0" in result.stdout
    assert "Review flags: 0" in result.stdout


def test_inspect_eligible_with_invalid_manifest_exits_one(tmp_path: Path) -> None:
    (tmp_path / "companion").mkdir()
    (tmp_path / "companion" / "manifest.json").write_text(
        """
        {
          "id": "bad_version",
          "name": "Bad Version",
          "shortname": "Bad Version",
          "description": "Fixture with an invalid version.",
          "version": "1",
          "manufacturer": "C2O Test Labs",
          "maintainers": [{ "name": "C2O Fixture Bot" }],
          "keywords": ["utility"],
          "repository": "https://github.com/example/bad-version"
        }
        """,
        encoding="utf-8",
    )
    (tmp_path / "index.js").write_text(
        "import { InstanceBase, TCPHelper } from '@companion-module/base'\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["inspect", str(tmp_path)])

    assert result.exit_code == 1
    assert "Manifest extraction failed" in result.stderr
    assert "manifest.json" in result.stderr


def test_inspect_rejects_non_local_source() -> None:
    result = CliRunner().invoke(
        app,
        ["inspect", "https://github.com/bitfocus/companion-module-x"],
    )

    assert result.exit_code == 1
    assert "M13" in result.stderr
