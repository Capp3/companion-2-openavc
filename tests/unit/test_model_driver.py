"""Unit tests for driver section models."""

from __future__ import annotations

from typing import Any, get_args

import pytest
from pydantic import ValidationError

from c2o.model.driver import (
    CommandEntry,
    CommandsSection,
    ConfigFieldsSection,
    ConfigSchemaEntry,
    DriverTransport,
    ManifestSection,
    ParamEntry,
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


def test_command_entry_requires_label_and_send() -> None:
    entry = CommandEntry(label="Set Input", send="SET INPUT {input}\n")

    assert entry.params == {}
    assert entry.help is None


def test_commands_section_round_trip() -> None:
    section = CommandsSection(
        commands={
            "set_input": CommandEntry(label="Set Input", send="SET INPUT {input}\n"),
        }
    )

    assert section.model_dump(exclude_none=True) == {
        "commands": {
            "set_input": {
                "label": "Set Input",
                "send": "SET INPUT {input}\n",
                "params": {},
            },
        }
    }
