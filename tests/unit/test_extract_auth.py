"""Unit tests for Companion auth extraction."""

from __future__ import annotations

from pathlib import Path

from c2o.extract.auth import extract_auth
from c2o.parse.js import parse_module


def test_extract_auth_detects_vaddio_style_telnet_prompts(tmp_path: Path) -> None:
    (tmp_path / "index.js").write_text(
        """
        import { InstanceBase, TCPHelper } from '@companion-module/base'

        export class Instance extends InstanceBase {
          init() {
            this.socket = new TCPHelper(this.config.host, this.config.port)
            this.socket.on('data', (chunk) => {
              this.receiveBuffer += chunk.toString()
              if (this.receiveBuffer.match(/[L|l]ogin:/)) {
                this.receiveBuffer = ''
                this.socket.send(this.config.username + '\\r\\n')
              } else if (this.receiveBuffer.match(/[P|p]assword:/)) {
                this.receiveBuffer = ''
                this.socket.send(this.config.password + '\\r\\n')
              } else if (this.receiveBuffer.match(/>/)) {
                this.loggedIn = true
              }
            })
          }
        }
        """,
        encoding="utf-8",
    )

    auth, report = extract_auth(parse_module(tmp_path))

    assert report.flags == ()
    assert auth is not None
    assert auth.type == "telnet_login"
    assert auth.username_prompt == "login:"
    assert auth.password_prompt == "password:"
    assert auth.success_pattern == ">"
    assert auth.username_field == "username"
    assert auth.password_field == "password"
    assert auth.line_ending == "\r\n"
