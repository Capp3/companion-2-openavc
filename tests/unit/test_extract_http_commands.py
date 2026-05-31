"""Unit tests for HTTP command extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.commands import extract_commands
from c2o.parse.js import parse_module


def test_http_device_extracts_fetch_commands(http_device: Path) -> None:
    section, review = extract_commands(parse_module(http_device))

    assert review.flags == ()
    assert set(section.commands) == {"get_status", "post_event", "send_xml"}

    get_status = section.commands["get_status"]
    assert get_status.label == "Get Status"
    assert get_status.method == "GET"
    assert get_status.path == "/api/status"
    assert get_status.query_params == {"include": "{include}"}
    assert get_status.params["include"].type == "enum"
    assert get_status.params["include"].values == ("summary", "details")
    assert get_status.help == "Select status detail level."

    post_event = section.commands["post_event"]
    assert post_event.method == "POST"
    assert post_event.path == "/api/event"
    assert post_event.body == '{"name": "{name}"}'
    assert post_event.headers is None
    assert post_event.params["name"].type == "string"

    send_xml = section.commands["send_xml"]
    assert send_xml.method == "POST"
    assert send_xml.path == "/api/payload"
    assert send_xml.body == "<msg>{value}</msg>"
    assert send_xml.headers == {"Content-Type": "text/xml"}


def test_tcp_send_wins_when_callback_also_contains_fetch(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        """
        class MixedDevice {
          updateActions() {
            this.setActionDefinitions({
              mixed: {
                name: 'Mixed',
                callback: async () => {
                  this.socket.send('PING\\n')
                  await fetch('/api/status')
                },
              },
            })
          }
        }
        """,
    )

    section, _review = extract_commands(parse_module(tmp_path))

    assert set(section.commands) == {"mixed"}
    assert section.commands["mixed"].send == "PING\n"
    assert section.commands["mixed"].method is None


def test_first_static_fetch_wins(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        """
        class MultiFetchDevice {
          updateActions() {
            this.setActionDefinitions({
              multi: {
                name: 'Multi',
                callback: async () => {
                  await fetch('/api/first?x=1')
                  await fetch('/api/second?x=2')
                },
              },
            })
          }
        }
        """,
    )

    section, _review = extract_commands(parse_module(tmp_path))

    assert set(section.commands) == {"multi"}
    assert section.commands["multi"].path == "/api/first"
    assert section.commands["multi"].query_params == {"x": "1"}


def _write_module(root: Path, source: str) -> None:
    (root / "index.js").write_text(source, encoding="utf-8")
