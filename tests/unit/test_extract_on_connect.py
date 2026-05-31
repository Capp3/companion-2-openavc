"""Unit tests for on_connect extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.on_connect import extract_on_connect
from c2o.parse.js import parse_module


def _write_module(root: Path, source: str) -> None:
    (root / "index.js").write_text(source, encoding="utf-8")


def test_extract_on_connect_returns_static_fixture_commands(static_on_connect: Path) -> None:
    section, review = extract_on_connect(parse_module(static_on_connect))

    assert section.commands == ("HELLO\n", "INIT\n")
    assert len(review) == 0


def test_extract_on_connect_empty_for_bmd_webpresenter(bmd_webpresenter: Path) -> None:
    section, review = extract_on_connect(parse_module(bmd_webpresenter))

    assert section.commands == ()
    assert len(review) == 0


def test_extract_on_connect_keeps_static_sends_and_drops_dynamic_sends(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        """
        class Fixture {
          init() {
            this.socket.on('connect', () => {
              this.socket.send('PING\\n')
              this.socket.send(`SET ${this.mode}\\n`)
            })
          }
        }
        """,
    )

    section, _review = extract_on_connect(parse_module(tmp_path))

    assert section.commands == ("PING\n",)


def test_extract_on_connect_collects_multiple_handlers_in_source_order(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        """
        class Fixture {
          init() {
            this.socket.on('connect', () => { this.socket.send('A\\n') })
            this.socket.on('connect', () => { this.socket.send('B\\n') })
          }
        }
        """,
    )

    section, _review = extract_on_connect(parse_module(tmp_path))

    assert section.commands == ("A\n", "B\n")
