"""Extract static OpenAVC on_connect commands."""

from __future__ import annotations

from tree_sitter import Node

from c2o.model.driver import OnConnectSection
from c2o.model.review import ReviewReport
from c2o.parse.connect_handlers import find_socket_connect_handlers
from c2o.parse.event_handlers import find_socket_event_handlers
from c2o.parse.js import ParsedModule, node_text
from c2o.parse.send_template import resolve_all_static_sends

# Prompts that signal the device is ready for commands (post-auth).
_PROMPT_PATTERNS = frozenset({">", "# ", "$ ", "cmd>"})


class OnConnectExtractionError(ValueError):
    """Raised when on_connect extraction encounters unrecoverable input."""


def extract_on_connect(parsed: ParsedModule) -> tuple[OnConnectSection, ReviewReport]:
    """Build static commands sent immediately after connection.

    Checks two sources:
    1. ``socket.on('connect', ...)`` callback bodies — the canonical location.
    2. ``socket.on('data', ...)`` handlers where a ``>`` (or similar CLI prompt)
       is matched in the receive buffer, indicating the device is ready for
       commands after a Telnet handshake.
    """
    commands: list[str] = []
    seen: set[str] = set()

    for handler in find_socket_connect_handlers(parsed):
        for cmd in resolve_all_static_sends(handler.callback_body, handler.source):
            if cmd not in seen:
                seen.add(cmd)
                commands.append(cmd)

    # Also scan data handlers for prompt-triggered send patterns.
    for event_handler in find_socket_event_handlers(parsed):
        for cmd in _prompt_triggered_sends(event_handler.callback_body, event_handler.source):
            if cmd not in seen:
                seen.add(cmd)
                commands.append(cmd)

    return OnConnectSection(commands=tuple(commands)), ReviewReport()


def _prompt_triggered_sends(body: Node, source: str) -> list[str]:
    """Return static send payloads inside prompt-detection guards."""
    sends: list[str] = []
    for node in _iter_nodes(body):
        if node.type != "if_statement":
            continue
        condition = node.child_by_field_name("condition")
        if condition is None or not _is_prompt_match(condition, source):
            continue
        consequent = node.child_by_field_name("consequence")
        if consequent is None:
            continue
        sends.extend(resolve_all_static_sends(consequent, source))
    return sends


def _is_prompt_match(condition: Node, source: str) -> bool:
    """Return True when a condition is a prompt-detection match like `buf.match(/>/)`."""
    text = node_text(condition, source)
    for prompt in _PROMPT_PATTERNS:
        if prompt in text:
            return True
    return "match" in text and any(
        p in text for p in ("/>", "/>/", "prompt", "ready", "READY", "cmd")
    )


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes
