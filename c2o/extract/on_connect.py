"""Extract static OpenAVC on_connect commands."""

from __future__ import annotations

from c2o.model.driver import OnConnectSection
from c2o.model.review import ReviewReport
from c2o.parse.connect_handlers import find_socket_connect_handlers
from c2o.parse.js import ParsedModule
from c2o.parse.send_template import resolve_all_static_sends


class OnConnectExtractionError(ValueError):
    """Raised when on_connect extraction encounters unrecoverable input."""


def extract_on_connect(parsed: ParsedModule) -> tuple[OnConnectSection, ReviewReport]:
    """Build static commands sent immediately after connection."""
    commands: list[str] = []
    for handler in find_socket_connect_handlers(parsed):
        commands.extend(resolve_all_static_sends(handler.callback_body, handler.source))
    return OnConnectSection(commands=tuple(commands)), ReviewReport()
