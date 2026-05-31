"""Unit tests for socket connect handler discovery."""

from __future__ import annotations

from pathlib import Path

from c2o.parse.connect_handlers import find_socket_connect_handlers
from c2o.parse.js import node_text, parse_module


def _write_module(root: Path, source: str) -> None:
    (root / "index.js").write_text(source, encoding="utf-8")


def test_find_socket_connect_handlers_extracts_callback_body(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        """
        class Fixture {
          init() {
            this.socket.on('connect', () => {
              this.socket.send('HELLO\\n')
            })
          }
        }
        """,
    )

    handlers = find_socket_connect_handlers(parse_module(tmp_path))

    assert len(handlers) == 1
    assert "HELLO" in node_text(handlers[0].callback_body, handlers[0].source)


def test_find_socket_connect_handlers_ignores_other_events_and_missing_callbacks(
    tmp_path: Path,
) -> None:
    _write_module(
        tmp_path,
        """
        class Fixture {
          init() {
            this.socket.on('data', () => {})
            this.socket.on(eventName, () => {})
            this.socket.on('connect')
          }
        }
        """,
    )

    assert find_socket_connect_handlers(parse_module(tmp_path)) == []
