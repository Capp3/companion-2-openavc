"""Unit tests for driver section models."""

from __future__ import annotations

from typing import Any, get_args

import pytest
from pydantic import ValidationError

from c2o.model.driver import (
    CommandEntry,
    CommandsSection,
    CompatibleModelEntry,
    CompatibleModelsSection,
    ConfigFieldsSection,
    ConfigSchemaEntry,
    DiscoverySection,
    DriverTransport,
    HelpSection,
    HttpMethod,
    ManifestSection,
    OnConnectSection,
    ParamEntry,
    PollingSection,
    ResponseEntry,
    ResponseMappingEntry,
    ResponsesSection,
    SimulatorCommandHandler,
    SimulatorControl,
    SimulatorControlType,
    SimulatorSection,
    StateVariableEntry,
    StateVariablesSection,
    StateVariableType,
    TransportSection,
)


def test_manifest_section_still_accepts_schema_aligned_metadata() -> None:
    section = ManifestSection(
        id="dummy_device",
        name="Dummy Device",
        manufacturer="Generic",
        category="utility",
        version="1.0.0",
        author="C2O Fixture Bot",
        description="Fixture metadata.",
        source_url="https://github.com/Capp3/companion-2-openavc",
    )

    assert section.id == "dummy_device"


def test_driver_transport_literal_matches_schema_values() -> None:
    assert get_args(DriverTransport) == ("tcp", "serial", "udp", "http", "osc")


def test_transport_section_defaults_delimiter_to_none() -> None:
    section = TransportSection(transport="tcp")

    assert section.transport == "tcp"
    assert section.delimiter is None


def test_transport_section_round_trips_explicit_delimiter() -> None:
    section = TransportSection(transport="tcp", delimiter="\n")

    assert section.model_dump() == {"transport": "tcp", "delimiter": "\n"}


def test_transport_section_rejects_unknown_transport() -> None:
    invalid_transport: Any = "bogus"

    with pytest.raises(ValidationError):
        TransportSection(transport=invalid_transport)


def test_transport_section_is_frozen() -> None:
    section = TransportSection(transport="tcp")

    with pytest.raises(ValidationError):
        section.delimiter = "\n"


def test_config_schema_entry_defaults_optional_fields_to_none() -> None:
    entry = ConfigSchemaEntry(type="string")

    assert entry.type == "string"
    assert entry.label is None
    assert entry.values is None
    assert entry.required is None


def test_config_schema_entry_round_trips_enum_values() -> None:
    entry = ConfigSchemaEntry(type="enum", values=("auto", "manual"))

    assert entry.model_dump(exclude_none=True) == {
        "type": "enum",
        "values": ("auto", "manual"),
    }


def test_config_schema_entry_rejects_unknown_type() -> None:
    invalid_type: Any = "bogus"

    with pytest.raises(ValidationError):
        ConfigSchemaEntry(type=invalid_type)


def test_config_schema_entry_is_frozen() -> None:
    entry = ConfigSchemaEntry(type="string")

    with pytest.raises(ValidationError):
        entry.type = "text"


def test_config_fields_section_defaults_to_empty_dicts() -> None:
    section = ConfigFieldsSection()

    assert section.default_config == {}
    assert section.config_schema == {}


def test_config_fields_section_round_trips_schema_entries() -> None:
    section = ConfigFieldsSection(
        default_config={"host": ""},
        config_schema={"host": ConfigSchemaEntry(type="string", required=True)},
    )

    assert section.model_dump(exclude_none=True) == {
        "default_config": {"host": ""},
        "config_schema": {"host": {"type": "string", "required": True}},
    }


def test_state_variable_entry_requires_label() -> None:
    with pytest.raises(ValidationError):
        StateVariableEntry(label="")


def test_state_variable_entry_accepts_optional_type() -> None:
    for var_type in get_args(StateVariableType):
        entry = StateVariableEntry(label="Example", type=var_type)
        assert entry.type == var_type


def test_state_variable_entry_rejects_unknown_type() -> None:
    invalid_type: Any = "bogus"

    with pytest.raises(ValidationError):
        StateVariableEntry(label="Example", type=invalid_type)


def test_state_variable_entry_is_frozen() -> None:
    entry = StateVariableEntry(label="Example", type="string")

    with pytest.raises(ValidationError):
        entry.label = "Other"


def test_state_variables_section_defaults_empty() -> None:
    section = StateVariablesSection()

    assert section.state_variables == {}


def test_state_variables_section_round_trip() -> None:
    section = StateVariablesSection(
        state_variables={
            "input_level": StateVariableEntry(label="Input Level", type="integer"),
        }
    )

    assert section.model_dump(exclude_none=True) == {
        "state_variables": {
            "input_level": {"label": "Input Level", "type": "integer"},
        }
    }


def test_param_entry_aliases_config_schema_entry() -> None:
    assert ParamEntry is ConfigSchemaEntry


def test_http_method_literal_matches_supported_values() -> None:
    assert get_args(HttpMethod) == ("GET", "POST", "PUT", "DELETE", "PATCH")


def test_command_entry_accepts_tcp_send_shape() -> None:
    entry = CommandEntry(label="Set Input", send="SET INPUT {input}\n")

    assert entry.params == {}
    assert entry.help is None
    assert entry.method is None


def test_command_entry_accepts_http_shape() -> None:
    entry = CommandEntry(
        label="Get Status",
        method="GET",
        path="/api/status",
        query_params={"include": "{include}"},
    )

    assert entry.model_dump(exclude_none=True, exclude_defaults=True) == {
        "label": "Get Status",
        "method": "GET",
        "path": "/api/status",
        "query_params": {"include": "{include}"},
    }


def test_command_entry_accepts_http_body_and_headers() -> None:
    entry = CommandEntry(
        label="Send XML",
        method="POST",
        path="/api/payload",
        body="<msg>{value}</msg>",
        headers={"Content-Type": "text/xml"},
    )

    assert entry.model_dump(exclude_none=True, exclude_defaults=True) == {
        "label": "Send XML",
        "method": "POST",
        "path": "/api/payload",
        "body": "<msg>{value}</msg>",
        "headers": {"Content-Type": "text/xml"},
    }


def test_command_entry_rejects_missing_command_shape() -> None:
    with pytest.raises(ValidationError):
        CommandEntry(label="Bad")


def test_command_entry_rejects_mixed_tcp_http_shape() -> None:
    with pytest.raises(ValidationError):
        CommandEntry(label="Bad", send="X", method="GET", path="/api/status")


def test_command_entry_rejects_incomplete_http_shape() -> None:
    with pytest.raises(ValidationError):
        CommandEntry(label="Bad", method="GET")

    with pytest.raises(ValidationError):
        CommandEntry(label="Bad", path="/api/status")


def test_command_entry_rejects_http_fields_on_tcp_shape() -> None:
    with pytest.raises(ValidationError):
        CommandEntry(label="Bad", send="X", headers={"Content-Type": "text/xml"})

    with pytest.raises(ValidationError):
        CommandEntry(label="Bad", send="X", query_params={"include": "details"})


def test_commands_section_round_trip() -> None:
    section = CommandsSection(
        commands={
            "set_input": CommandEntry(label="Set Input", send="SET INPUT {input}\n"),
        }
    )

    assert section.model_dump(exclude_none=True, exclude_defaults=True) == {
        "commands": {
            "set_input": {
                "label": "Set Input",
                "send": "SET INPUT {input}\n",
            },
        }
    }


def test_response_entry_requires_set_xor_mappings() -> None:
    with pytest.raises(ValidationError):
        ResponseEntry(match=r"^X$")

    with pytest.raises(ValidationError):
        ResponseEntry(
            match=r"^X$",
            set={"a": "$1"},
            mappings=(ResponseMappingEntry(group=1, state="b", type="integer"),),
        )


def test_response_entry_shorthand_round_trip() -> None:
    entry = ResponseEntry(match=r"^LABEL=(.+)$", set={"device_label": "$1"})

    assert entry.model_dump(exclude_none=True) == {
        "match": r"^LABEL=(.+)$",
        "set": {"device_label": "$1"},
    }


def test_responses_section_defaults_empty() -> None:
    section = ResponsesSection()

    assert section.responses == ()


def test_polling_section_defaults_empty() -> None:
    section = PollingSection()

    assert section.queries == ()
    assert section.inferred_poll_interval is None


def test_polling_section_round_trip() -> None:
    section = PollingSection(
        queries=("QUERY INPUT\n", "QUERY MUTE\n"),
        inferred_poll_interval=1,
    )

    assert section.model_dump(exclude_none=True) == {
        "queries": ("QUERY INPUT\n", "QUERY MUTE\n"),
        "inferred_poll_interval": 1,
    }


def test_polling_section_is_frozen() -> None:
    section = PollingSection()

    with pytest.raises(ValidationError):
        section.queries = ("X",)


def test_discovery_section_round_trip() -> None:
    section = DiscoverySection(
        port_open=(9977,),
        manufacturer_alias=("Blackmagic Design", "Blackmagic"),
    )

    assert section.model_dump(exclude_none=True) == {
        "port_open": (9977,),
        "manufacturer_alias": ("Blackmagic Design", "Blackmagic"),
    }


def test_discovery_section_defaults_empty() -> None:
    section = DiscoverySection()

    assert section.port_open == ()
    assert section.manufacturer_alias == ()


def test_compatible_models_section_round_trip() -> None:
    section = CompatibleModelsSection(
        compatible_models=(
            CompatibleModelEntry(
                manufacturer="Blackmagic Design",
                models=("WebPresenter HD", "WebPresenter 4K"),
                confidence="untested",
            ),
        )
    )

    assert section.model_dump(exclude_none=True) == {
        "compatible_models": (
            {
                "manufacturer": "Blackmagic Design",
                "models": ("WebPresenter HD", "WebPresenter 4K"),
                "confidence": "untested",
            },
        )
    }


def test_compatible_model_entry_rejects_unknown_confidence() -> None:
    invalid_confidence: Any = "bogus"

    with pytest.raises(ValidationError):
        CompatibleModelEntry(
            manufacturer="Generic",
            models=("Dummy Model A",),
            confidence=invalid_confidence,
        )


def test_on_connect_section_round_trip() -> None:
    section = OnConnectSection(commands=("HELLO\n", "INIT\n"))

    assert section.model_dump(exclude_none=True) == {
        "commands": ("HELLO\n", "INIT\n"),
    }


def test_simulator_control_type_literal_matches_auto_generated_shapes() -> None:
    assert get_args(SimulatorControlType) == ("toggle", "slider", "select", "indicator")


def test_simulator_control_round_trips_toggle() -> None:
    control = SimulatorControl(type="toggle", key="mute", label="Mute")

    assert control.model_dump(exclude_none=True) == {
        "type": "toggle",
        "key": "mute",
        "label": "Mute",
    }


def test_simulator_control_round_trips_slider() -> None:
    control = SimulatorControl(type="slider", key="volume", label="Volume", min=0, max=100, step=1)

    assert control.model_dump(exclude_none=True) == {
        "type": "slider",
        "key": "volume",
        "label": "Volume",
        "min": 0,
        "max": 100,
        "step": 1,
    }


def test_simulator_control_round_trips_select() -> None:
    control = SimulatorControl(
        type="select",
        key="input",
        label="Input",
        options=("HDMI1", "HDMI2"),
    )

    assert control.model_dump(exclude_none=True) == {
        "type": "select",
        "key": "input",
        "label": "Input",
        "options": ("HDMI1", "HDMI2"),
    }


def test_simulator_control_rejects_invalid_shape_fields() -> None:
    with pytest.raises(ValidationError):
        SimulatorControl(type="slider", key="volume", label="Volume", min=0)

    with pytest.raises(ValidationError):
        SimulatorControl(type="select", key="input", label="Input")

    with pytest.raises(ValidationError):
        SimulatorControl(type="indicator", key="label", label="Label", options=("A",))


def test_simulator_command_handler_accepts_receive_or_match_shape() -> None:
    literal = SimulatorCommandHandler(receive="STREAM START", respond="STREAM START\n")
    regex = SimulatorCommandHandler(match=r"SET INPUT (\d+)", respond="SET INPUT {1}\n")

    assert literal.model_dump(exclude_none=True) == {
        "receive": "STREAM START",
        "respond": "STREAM START\n",
    }
    assert regex.model_dump(exclude_none=True) == {
        "match": r"SET INPUT (\d+)",
        "respond": "SET INPUT {1}\n",
    }


def test_simulator_command_handler_rejects_missing_or_mixed_match_shape() -> None:
    with pytest.raises(ValidationError):
        SimulatorCommandHandler(respond="OK")

    with pytest.raises(ValidationError):
        SimulatorCommandHandler(receive="X", match="X", respond="X")


def test_simulator_section_round_trip_omits_empty_subsections() -> None:
    empty = SimulatorSection()
    populated = SimulatorSection(
        initial_state={"mute": False},
        controls=(SimulatorControl(type="toggle", key="mute", label="Mute"),),
        command_handlers=(SimulatorCommandHandler(receive="MUTE ON", respond="MUTE ON\n"),),
    )

    assert empty.model_dump(exclude_none=True) == {}
    assert populated.model_dump(exclude_none=True) == {
        "initial_state": {"mute": False},
        "controls": ({"type": "toggle", "key": "mute", "label": "Mute"},),
        "command_handlers": ({"receive": "MUTE ON", "respond": "MUTE ON\n"},),
    }


def test_help_section_requires_non_empty_fields() -> None:
    with pytest.raises(ValidationError):
        HelpSection(overview="", setup="Setup text")

    section = HelpSection(overview="Overview text", setup="Setup text")
    assert section.model_dump() == {
        "overview": "Overview text",
        "setup": "Setup text",
    }


def test_help_section_is_frozen() -> None:
    section = HelpSection(overview="Overview text", setup="Setup text")

    with pytest.raises(ValidationError):
        section.overview = "Other"
