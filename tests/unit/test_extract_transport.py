"""Unit tests for Companion transport extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2o.extract.transport import TransportExtractionError, extract_transport
from c2o.model.driver import TransportSection
from c2o.parse.js import parse_module


def _write_module(tmp_path: Path, source: str) -> Path:
    root = tmp_path / "module"
    root.mkdir()
    (root / "index.js").write_text(source, encoding="utf-8")
    return root


def _extract_inline(tmp_path: Path, source: str) -> TransportSection:
    return extract_transport(parse_module(_write_module(tmp_path, source)))


def test_tcp_helper_extracts_tcp_transport(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n",
    )

    assert section.transport == "tcp"
    assert section.delimiter is None


def test_serial_port_extracts_serial_transport(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { SerialPort } from 'serialport'\n" "const port = new SerialPort('/dev/ttyUSB0')\n",
    )

    assert section.transport == "serial"


def test_serial_helper_extracts_serial_transport(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { SerialHelper } from '@companion-module/base'\n"
        "const port = new SerialHelper('/dev/ttyUSB0')\n",
    )

    assert section.transport == "serial"


def test_osc_import_extracts_osc_transport(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { OSC } from 'osc-js'\n" "const osc = new OSC()\n",
    )

    assert section.transport == "osc"


@pytest.mark.parametrize("hint", ["fetch", "axios", "got", "node-fetch"])
def test_http_hints_extract_http_transport(tmp_path: Path, hint: str) -> None:
    section = _extract_inline(
        tmp_path,
        f"import {hint.replace('-', '_')} from '{hint}'\n"
        f"const client = {hint.replace('-', '_')}\n",
    )

    assert section.transport == "http"


def test_transport_helper_wins_over_http_hint(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "fetch('/status')\n",
    )

    assert section.transport == "tcp"


def test_udp_helper_raises_defensive_error(tmp_path: Path) -> None:
    root = _write_module(
        tmp_path,
        "import { UDPHelper } from '@companion-module/base'\n"
        "const socket = new UDPHelper(config.host, config.port)\n",
    )

    with pytest.raises(TransportExtractionError, match="UDP"):
        extract_transport(parse_module(root))


def test_unknown_transport_raises(tmp_path: Path) -> None:
    root = _write_module(tmp_path, "const nothing = true\n")

    with pytest.raises(TransportExtractionError, match="could not be inferred"):
        extract_transport(parse_module(root))


def test_split_on_chunk_newline_extracts_newline_delimiter(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "socket.on('data', (chunk) => chunk.toString().split('\\n'))\n",
    )

    assert section.delimiter == "\n"


def test_index_of_receive_buffer_extracts_newline_delimiter(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "this.receiveBuffer = ''\n"
        "while ((i = this.receiveBuffer.indexOf('\\n', offset)) !== -1) {}\n",
    )

    assert section.delimiter == "\n"


def test_crlf_delimiter_has_highest_priority(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "data.indexOf('\\n')\n"
        "data.indexOf('\\r\\n')\n",
    )

    assert section.delimiter == "\r\n"


def test_carriage_return_delimiter_collapses_to_default_none(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "data.indexOf('\\r')\n",
    )

    assert section.delimiter is None


def test_newline_wins_over_carriage_return(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "data.indexOf('\\r')\n"
        "data.indexOf('\\n')\n",
    )

    assert section.delimiter == "\n"


def test_irrelevant_split_value_is_ignored(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "value.split(':')\n",
    )

    assert section.delimiter is None


def test_non_buffer_receiver_split_is_ignored(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "import { TCPHelper } from '@companion-module/base'\n"
        "const socket = new TCPHelper(config.host, config.port)\n"
        "obj['Available Video Modes'].split(',')\n",
    )

    assert section.delimiter is None


def test_fixture_dummy_device_extracts_newline(dummy_device: Path) -> None:
    section = extract_transport(parse_module(dummy_device))

    assert section.transport == "tcp"
    assert section.delimiter == "\n"


def test_fixture_bmd_webpresenter_extracts_newline(bmd_webpresenter: Path) -> None:
    section = extract_transport(parse_module(bmd_webpresenter))

    assert section.transport == "tcp"
    assert section.delimiter == "\n"


def test_fixture_unknown_vendor_uses_default_delimiter(unknown_vendor: Path) -> None:
    section = extract_transport(parse_module(unknown_vendor))

    assert section.transport == "tcp"
    assert section.delimiter is None
