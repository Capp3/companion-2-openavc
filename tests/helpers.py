"""Shared helpers for CLI integration tests."""

from __future__ import annotations

import re
from typing import Protocol

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


class _CliResult(Protocol):
    @property
    def stdout(self) -> str: ...

    @property
    def stderr(self) -> str: ...


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from Typer/Rich CLI output."""
    return _ANSI_ESCAPE.sub("", text)


def cli_stdout(result: _CliResult) -> str:
    """Return normalized stdout from a CliRunner result."""
    return strip_ansi(result.stdout)


def cli_stderr(result: _CliResult) -> str:
    """Return normalized stderr from a CliRunner result."""
    return strip_ansi(result.stderr)


def cli_output(result: _CliResult) -> str:
    """Return combined normalized stdout and stderr from a CliRunner result."""
    return cli_stdout(result) + cli_stderr(result)
