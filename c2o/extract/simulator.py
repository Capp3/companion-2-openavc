"""Auto-generate Level 0+ OpenAVC simulator sections."""

from __future__ import annotations

import re
from typing import Any

from c2o.model.driver import (
    CommandEntry,
    CommandsSection,
    ConfigSchemaEntry,
    SimulatorCommandHandler,
    SimulatorControl,
    SimulatorSection,
    StateVariableEntry,
    StateVariablesSection,
)
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_TRAILING_DELIMITER_RE = re.compile(r"[\r\n]+$")


class SimulatorExtractionError(ValueError):
    """Raised when simulator extraction encounters malformed section input."""


def extract_simulator(
    state_variables: StateVariablesSection,
    commands: CommandsSection,
) -> tuple[SimulatorSection, ReviewReport]:
    """Build a best-effort simulator from extracted state variables and commands."""
    initial_state = _build_initial_state(state_variables)
    controls = _build_controls(state_variables)
    command_handlers = _build_command_handlers(commands)

    section = SimulatorSection(
        initial_state=initial_state or None,
        controls=tuple(controls) or None,
        command_handlers=tuple(command_handlers) or None,
    )
    flags = (_simulator_auto_flag(),) if _section_has_content(section) else ()
    return section, ReviewReport(flags=flags)


def _build_initial_state(state_variables: StateVariablesSection) -> dict[str, Any]:
    return {
        key: _default_state_value(entry) for key, entry in state_variables.state_variables.items()
    }


def _default_state_value(entry: StateVariableEntry) -> Any:
    if entry.default is not None:
        return entry.default
    if entry.values:
        return entry.values[0]
    if entry.type == "boolean":
        return False
    if entry.type in {"integer", "number"}:
        return 0
    if entry.type == "float":
        return 0.0
    return ""


def _build_controls(state_variables: StateVariablesSection) -> list[SimulatorControl]:
    return [
        _control_for_state_variable(key, entry)
        for key, entry in state_variables.state_variables.items()
    ]


def _control_for_state_variable(key: str, entry: StateVariableEntry) -> SimulatorControl:
    if entry.values:
        return SimulatorControl(
            type="select",
            key=key,
            label=entry.label,
            options=tuple(entry.values),
        )

    if entry.type == "boolean":
        return SimulatorControl(type="toggle", key=key, label=entry.label)

    if (
        entry.type in {"integer", "number", "float"}
        and entry.min is not None
        and entry.max is not None
    ):
        return SimulatorControl(
            type="slider",
            key=key,
            label=entry.label,
            min=entry.min,
            max=entry.max,
            step=1 if entry.type == "integer" else None,
        )

    return SimulatorControl(type="indicator", key=key, label=entry.label)


def _build_command_handlers(commands: CommandsSection) -> list[SimulatorCommandHandler]:
    handlers: list[SimulatorCommandHandler] = []
    for command in commands.commands.values():
        handler = _handler_for_command(command)
        if handler is not None:
            handlers.append(handler)
    return handlers


def _handler_for_command(command: CommandEntry) -> SimulatorCommandHandler | None:
    if command.send is not None:
        return _handler_for_tcp_command(command)
    if command.method is not None and command.path is not None:
        return _handler_for_http_command(command)
    return None


def _handler_for_tcp_command(command: CommandEntry) -> SimulatorCommandHandler | None:
    send = command.send
    if send is None:
        return None

    stripped = _strip_trailing_delimiter(send)
    if "\r" in stripped or "\n" in stripped:
        return None

    placeholders = _placeholders_in_order(stripped)
    if not placeholders:
        return SimulatorCommandHandler(receive=stripped, respond=send)

    return SimulatorCommandHandler(
        match=_template_to_match(stripped, command.params),
        respond=_template_to_response(send, placeholders),
    )


def _strip_trailing_delimiter(value: str) -> str:
    return _TRAILING_DELIMITER_RE.sub("", value)


def _placeholders_in_order(value: str) -> list[str]:
    return [match.group(1) for match in _PLACEHOLDER_RE.finditer(value)]


def _template_to_match(value: str, params: dict[str, ConfigSchemaEntry]) -> str:
    parts: list[str] = []
    cursor = 0
    for match in _PLACEHOLDER_RE.finditer(value):
        parts.append(_escape_literal_pattern(value[cursor : match.start()]))
        parts.append(_capture_group_for_param(params.get(match.group(1))))
        cursor = match.end()
    parts.append(_escape_literal_pattern(value[cursor:]))
    return "".join(parts)


def _escape_literal_pattern(value: str) -> str:
    return re.escape(value).replace(r"\ ", " ")


def _capture_group_for_param(param: ConfigSchemaEntry | None) -> str:
    if param is None:
        return r"(\S+)"
    if param.type in {"integer", "number", "float"}:
        return r"(\d+)"
    if param.type == "boolean":
        return r"(true|false)"
    return r"(\S+)"


def _template_to_response(value: str, placeholders: list[str]) -> str:
    seen: dict[str, int] = {}
    for placeholder in placeholders:
        if placeholder not in seen:
            seen[placeholder] = len(seen) + 1
    return _PLACEHOLDER_RE.sub(lambda match: "{" + str(seen[match.group(1)]) + "}", value)


def _handler_for_http_command(command: CommandEntry) -> SimulatorCommandHandler:
    method = command.method
    path = command.path
    if method is None or path is None:
        msg = "HTTP simulator handler requires command method and path"
        raise SimulatorExtractionError(msg)
    respond = "{}" if method == "GET" else '{"ok": true}'
    return SimulatorCommandHandler(
        match=f"{method} {_http_path_to_match(path)}.*",
        respond=respond,
    )


def _http_path_to_match(path: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in _PLACEHOLDER_RE.finditer(path):
        parts.append(re.escape(path[cursor : match.start()]))
        parts.append(r"([^?|]*)")
        cursor = match.end()
    parts.append(re.escape(path[cursor:]))
    return "".join(parts)


def _section_has_content(section: SimulatorSection) -> bool:
    return (
        section.initial_state is not None
        or section.controls is not None
        or section.command_handlers is not None
    )


def _simulator_auto_flag() -> ReviewFlag:
    return ReviewFlag(
        code=ReviewCode.SIMULATOR_AUTO,
        field="simulator",
        message=(
            "The simulator block was auto-generated from state variables and commands. "
            "All entries require human review before the driver is considered production-ready."
        ),
    )
