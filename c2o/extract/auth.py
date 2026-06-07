"""Extract OpenAVC auth block from Companion Telnet login handshake patterns."""

from __future__ import annotations

import re

from tree_sitter import Node

from c2o.model.driver import AuthSection
from c2o.model.review import ReviewReport
from c2o.parse.event_handlers import EventHandler, find_socket_event_handlers
from c2o.parse.js import ParsedModule, node_text

# Regex patterns used to detect login/password prompts and send sequences.
_LOGIN_PATTERNS = (
    re.compile(r"[Ll]ogin\s*:", re.IGNORECASE),
    re.compile(r"\[L\|l\]ogin\s*:", re.IGNORECASE),
    re.compile(r"\[Ll\]ogin\s*:", re.IGNORECASE),
    re.compile(r"[Uu]sername\s*:", re.IGNORECASE),
    re.compile(r"\[U\|u\]sername\s*:", re.IGNORECASE),
    re.compile(r"\[Uu\]sername\s*:", re.IGNORECASE),
    re.compile(r"[Uu]ser\s*:", re.IGNORECASE),
    re.compile(r"\[U\|u\]ser\s*:", re.IGNORECASE),
    re.compile(r"\[Uu\]ser\s*:", re.IGNORECASE),
)
_PASSWORD_PATTERNS = (
    re.compile(r"[Pp]assword\s*:", re.IGNORECASE),
    re.compile(r"\[P\|p\]assword\s*:", re.IGNORECASE),
    re.compile(r"\[Pp\]assword\s*:", re.IGNORECASE),
    re.compile(r"[Pp]ass\s*:", re.IGNORECASE),
    re.compile(r"\[P\|p\]ass\s*:", re.IGNORECASE),
    re.compile(r"\[Pp\]ass\s*:", re.IGNORECASE),
)
_SUCCESS_PATTERNS = (
    re.compile(r"[Ww]elcome"),
    re.compile(r"[Ss]uccess"),
    re.compile(r"[Ll]ogged\s+[Ii]n"),
    re.compile(r">"),
)

_CREDENTIAL_FIELDS = frozenset({"username", "password"})


class AuthExtractionError(ValueError):
    """Raised when auth extraction encounters unrecoverable input."""


def extract_auth(parsed: ParsedModule) -> tuple[AuthSection | None, ReviewReport]:
    """Detect a Telnet login handshake in socket.on('data', ...) handlers."""
    handlers = find_socket_event_handlers(parsed)
    for handler in handlers:
        result = _try_extract_from_handler(handler)
        if result is not None:
            return result, ReviewReport()
    return None, ReviewReport()


def _try_extract_from_handler(handler: EventHandler) -> AuthSection | None:
    """Return an AuthSection if the handler implements a telnet login handshake."""
    source = handler.source
    body = handler.callback_body

    login_prompt: str | None = None
    password_prompt: str | None = None
    success_pat: str | None = None
    username_field: str | None = None
    password_field: str | None = None
    line_ending: str | None = None

    for node in _iter_nodes(body):
        if node.type == "if_statement":
            condition = node.child_by_field_name("condition")
            if condition is None:
                continue
            prompt = _detect_prompt_match(condition, source)
            if prompt == "login":
                login_prompt = _extract_literal_from_match_arg(condition, source)
                consequent = node.child_by_field_name("consequence")
                if consequent is not None:
                    creds = _extract_send_credential(consequent, source)
                    if creds is not None:
                        username_field, line_ending = creds
            elif prompt == "password":
                password_prompt = _extract_literal_from_match_arg(condition, source)
                consequent = node.child_by_field_name("consequence")
                if consequent is not None:
                    creds = _extract_send_credential(consequent, source)
                    if creds is not None:
                        password_field, line_ending = creds
            elif prompt == "success":
                success_pat = _extract_literal_from_match_arg(condition, source)

    if login_prompt is None and password_prompt is None:
        return None

    return AuthSection(
        type="telnet_login",
        username_prompt=login_prompt,
        password_prompt=password_prompt,
        success_pattern=success_pat,
        username_field=username_field or "username",
        password_field=password_field or "password",
        skip_if_empty=False,
        timeout_seconds=10,
        line_ending=line_ending or "\r\n",
    )


def _detect_prompt_match(condition: Node, source: str) -> str | None:
    """Classify a condition node as 'login', 'password', 'success', or None."""
    text = node_text(condition, source)
    for pattern in _LOGIN_PATTERNS:
        if pattern.search(text):
            return "login"
    for pattern in _PASSWORD_PATTERNS:
        if pattern.search(text):
            return "password"
    for pattern in _SUCCESS_PATTERNS:
        if pattern.search(text):
            return "success"
    return None


def _extract_literal_from_match_arg(condition: Node, source: str) -> str | None:
    """Extract the regex literal string from a .match(/.../) call inside a condition."""
    for node in _iter_nodes(condition):
        if node.type == "regex":
            raw = node_text(node, source)
            inner = raw[1 : raw.rfind("/")]
            inner = _literalize_prompt_regex(inner)
            inner = inner.strip()
            if any(char.isalpha() for char in inner) and not inner.endswith(":"):
                inner = inner.rstrip() + ":"
            return inner if inner else None
        if node.type == "string":
            raw = node_text(node, source)
            val = raw[1:-1] if len(raw) >= 2 else raw
            return val if val else None
    return None


def _literalize_prompt_regex(pattern: str) -> str:
    """Convert simple prompt regex spelling into a readable prompt literal."""
    result = pattern.replace("\\s*", " ").replace("\\s+", " ")

    # Companion modules commonly write case-insensitive prompt chars as
    # ``/[L|l]ogin:/`` or ``/[Ll]ogin:/``. Preserve the literal char instead of
    # dropping it from the emitted prompt.
    result = re.sub(
        r"\[([A-Za-z])\|([A-Za-z])\]",
        lambda match: match.group(1).lower(),
        result,
    )
    result = re.sub(
        r"\[([A-Za-z])([A-Za-z])\]",
        lambda match: match.group(1).lower(),
        result,
    )
    return result


def _extract_send_credential(
    block: Node,
    source: str,
) -> tuple[str, str] | None:
    """Return (config_field_name, line_ending) for a credential send in a block."""
    for node in _iter_nodes(block):
        if node.type != "call_expression":
            continue
        function = node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            continue
        prop = function.child_by_field_name("property")
        if prop is None or node_text(prop, source) != "send":
            continue
        args = node.child_by_field_name("arguments")
        if args is None or args.named_child_count == 0:
            continue
        arg = args.named_children[0]
        field, ending = _parse_credential_arg(arg, source)
        if field is not None:
            return field, ending or "\r\n"
    return None


def _parse_credential_arg(node: Node, source: str) -> tuple[str | None, str | None]:
    """Try to extract (field_name, line_ending) from a credential argument expression."""
    text = node_text(node, source)

    for field in _CREDENTIAL_FIELDS:
        if (
            f"config.{field}" in text
            or f"config['{field}']" in text
            or f'config["{field}"]' in text
        ):
            ending = _detect_line_ending(text)
            return field, ending

    if node.type in {"binary_expression", "template_string"}:
        for child in _iter_nodes(node):
            if child.type == "member_expression":
                member_text = node_text(child, source)
                for field in _CREDENTIAL_FIELDS:
                    if member_text.endswith(f".{field}"):
                        ending = _detect_line_ending(text)
                        return field, ending
    return None, None


def _detect_line_ending(text: str) -> str:
    if "\\r\\n" in text or "\r\n" in text:
        return "\r\n"
    if "\\n" in text or "\n" in text:
        return "\n"
    if "\\r" in text or "\r" in text:
        return "\r"
    return "\r\n"


def _iter_nodes(root: Node) -> list[Node]:
    nodes: list[Node] = []
    stack = [root]
    while stack:
        current = stack.pop()
        nodes.append(current)
        stack.extend(reversed(current.children))
    return nodes
