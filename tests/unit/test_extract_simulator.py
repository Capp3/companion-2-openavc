"""Unit tests for simulator auto-generation."""

from __future__ import annotations

import c2o.extract as extract
from c2o.extract.simulator import SimulatorExtractionError, extract_simulator
from c2o.model.driver import (
    CommandEntry,
    CommandsSection,
    ConfigSchemaEntry,
    StateVariableEntry,
    StateVariablesSection,
)
from c2o.model.review import ReviewCode


def test_extract_simulator_defaults_initial_state_by_type() -> None:
    section, _review = extract_simulator(
        StateVariablesSection(
            state_variables={
                "enabled": StateVariableEntry(label="Enabled", type="boolean"),
                "count": StateVariableEntry(label="Count", type="integer"),
                "gain": StateVariableEntry(label="Gain", type="number"),
                "ratio": StateVariableEntry(label="Ratio", type="float"),
                "label": StateVariableEntry(label="Label", type="string"),
                "mode": StateVariableEntry(label="Mode", type="enum", values=("auto", "manual")),
                "explicit": StateVariableEntry(label="Explicit", type="string", default="ready"),
            }
        ),
        CommandsSection(),
    )

    assert section.initial_state == {
        "enabled": False,
        "count": 0,
        "gain": 0,
        "ratio": 0.0,
        "label": "",
        "mode": "auto",
        "explicit": "ready",
    }


def test_extract_simulator_maps_state_variables_to_controls() -> None:
    section, _review = extract_simulator(
        StateVariablesSection(
            state_variables={
                "mute": StateVariableEntry(label="Mute", type="boolean"),
                "volume": StateVariableEntry(label="Volume", type="integer", min=0, max=100),
                "gain": StateVariableEntry(label="Gain", type="float", min=-12.5, max=12.5),
                "level": StateVariableEntry(label="Level", type="integer"),
                "mode": StateVariableEntry(label="Mode", type="enum", values=("auto", "manual")),
                "quality": StateVariableEntry(
                    label="Quality",
                    type="string",
                    values=("low", "high"),
                ),
                "name": StateVariableEntry(label="Name", type="string"),
            }
        ),
        CommandsSection(),
    )

    assert [control.model_dump(exclude_none=True) for control in section.controls or ()] == [
        {"type": "toggle", "key": "mute", "label": "Mute"},
        {"type": "slider", "key": "volume", "label": "Volume", "min": 0, "max": 100, "step": 1},
        {"type": "slider", "key": "gain", "label": "Gain", "min": -12.5, "max": 12.5},
        {"type": "indicator", "key": "level", "label": "Level"},
        {"type": "select", "key": "mode", "label": "Mode", "options": ("auto", "manual")},
        {"type": "select", "key": "quality", "label": "Quality", "options": ("low", "high")},
        {"type": "indicator", "key": "name", "label": "Name"},
    ]


def test_extract_simulator_generates_tcp_literal_echo_handler() -> None:
    section, _review = extract_simulator(
        StateVariablesSection(),
        CommandsSection(
            commands={
                "stream_start": CommandEntry(label="Stream Start", send="STREAM START\r\n"),
            }
        ),
    )

    handlers = [handler.model_dump(exclude_none=True) for handler in section.command_handlers or ()]
    assert handlers == [
        {"receive": "STREAM START", "respond": "STREAM START\r\n"},
    ]


def test_extract_simulator_generates_tcp_parameterized_echo_handler() -> None:
    section, _review = extract_simulator(
        StateVariablesSection(),
        CommandsSection(
            commands={
                "configure": CommandEntry(
                    label="Configure",
                    send="CFG {mode} {label}\r\n",
                    params={
                        "mode": ConfigSchemaEntry(type="enum"),
                        "label": ConfigSchemaEntry(type="string"),
                    },
                ),
                "set_input": CommandEntry(
                    label="Set Input",
                    send="SET INPUT {input}\r\n",
                    params={"input": ConfigSchemaEntry(type="integer")},
                ),
                "set_mute": CommandEntry(
                    label="Set Mute",
                    send="MUTE {enabled}\r\n",
                    params={"enabled": ConfigSchemaEntry(type="boolean")},
                ),
            }
        ),
    )

    handlers = [handler.model_dump(exclude_none=True) for handler in section.command_handlers or ()]
    assert handlers == [
        {"match": r"CFG (\S+) (\S+)", "respond": "CFG {1} {2}\r\n"},
        {"match": r"SET INPUT (\d+)", "respond": "SET INPUT {1}\r\n"},
        {"match": r"MUTE (true|false)", "respond": "MUTE {1}\r\n"},
    ]


def test_extract_simulator_skips_multiline_tcp_commands() -> None:
    section, _review = extract_simulator(
        StateVariablesSection(),
        CommandsSection(
            commands={
                "multi": CommandEntry(
                    label="Multi",
                    send="STREAM STATE:\nAction: Start\n\n",
                ),
                "single": CommandEntry(label="Single", send="PING\n"),
            }
        ),
    )

    handlers = [handler.model_dump(exclude_none=True) for handler in section.command_handlers or ()]
    assert handlers == [
        {"receive": "PING", "respond": "PING\n"},
    ]


def test_extract_simulator_generates_http_handlers_with_tail_consumer() -> None:
    section, _review = extract_simulator(
        StateVariablesSection(),
        CommandsSection(
            commands={
                "get_status": CommandEntry(
                    label="Get Status",
                    method="GET",
                    path="/api/status",
                    query_params={"include": "{include}"},
                ),
                "power_on": CommandEntry(
                    label="Power On",
                    method="GET",
                    path="/cgi-bin/aw_ptz",
                    query_params={"cmd": "#O1", "res": "1"},
                ),
                "post_event": CommandEntry(
                    label="Post Event",
                    method="POST",
                    path="/api/device/{id}/event",
                    body='{"name": "{name}"}',
                    params={"id": ConfigSchemaEntry(type="integer")},
                ),
            }
        ),
    )

    handlers = [handler.model_dump(exclude_none=True) for handler in section.command_handlers or ()]
    assert handlers == [
        {"match": r"GET /api/status\?include=[^&]*.*", "respond": "{}"},
        {"match": r"GET /cgi\-bin/aw_ptz\?cmd=%23O1&res=1.*", "respond": "{}"},
        {"match": r"POST /api/device/([^?|]*)/event.*", "respond": '{"ok": true}'},
    ]


def test_extract_simulator_keeps_placeholder_query_commands_distinct() -> None:
    section, _review = extract_simulator(
        StateVariablesSection(),
        CommandsSection(
            commands={
                "iris": CommandEntry(
                    label="Iris",
                    method="GET",
                    path="/cgi-bin/aw_ptz",
                    query_params={"cmd": "#I{val}", "res": "1"},
                ),
                "scene": CommandEntry(
                    label="Scene",
                    method="GET",
                    path="/cgi-bin/aw_ptz",
                    query_params={"cmd": "#S{val}", "res": "1"},
                ),
            }
        ),
    )

    matches = sorted(
        handler.match for handler in section.command_handlers or () if handler.match is not None
    )
    assert matches == [
        r"GET /cgi\-bin/aw_ptz\?cmd=%23I[^&]*&res=1.*",
        r"GET /cgi\-bin/aw_ptz\?cmd=%23S[^&]*&res=1.*",
    ]


def test_extract_simulator_emits_one_umbrella_review_flag_for_non_empty_section() -> None:
    _section, review = extract_simulator(
        StateVariablesSection(
            state_variables={"mute": StateVariableEntry(label="Mute", type="boolean")},
        ),
        CommandsSection(),
    )

    assert len(review) == 1
    assert review.flags[0].code == ReviewCode.SIMULATOR_AUTO
    assert review.flags[0].field == "simulator"


def test_extract_simulator_empty_inputs_return_empty_section_without_review_flags() -> None:
    section, review = extract_simulator(StateVariablesSection(), CommandsSection())

    assert section.model_dump(exclude_none=True) == {}
    assert len(review) == 0


def test_simulator_symbols_are_exported_from_extract_package() -> None:
    assert extract.extract_simulator is extract_simulator
    assert extract.SimulatorExtractionError is SimulatorExtractionError
    assert extract.SimulatorSection.__name__ == "SimulatorSection"
    assert extract.SimulatorControl.__name__ == "SimulatorControl"
    assert extract.SimulatorCommandHandler.__name__ == "SimulatorCommandHandler"
