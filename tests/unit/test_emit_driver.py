"""Unit tests for .avcdriver YAML emission."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import yaml  # type: ignore[import-untyped]

from c2o.emit.driver import build_driver_payload, serialize_driver
from c2o.model.driver import (
    CommandEntry,
    CommandsSection,
    CompatibleModelsSection,
    ConfigFieldsSection,
    ConfigSchemaEntry,
    DiscoverySection,
    HelpSection,
    ManifestSection,
    OnConnectSection,
    PollingSection,
    ResponseEntry,
    ResponsesSection,
    SimulatorSection,
    StateVariableEntry,
    StateVariablesSection,
    TransportSection,
)


def _sections(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "manifest": ManifestSection(
            id="dummy_device",
            name="Dummy Device",
            manufacturer="Generic",
            category="utility",
            version="1.0.0",
            author="C2O",
            description="Fixture driver",
            source_url="https://example.test/dummy",
        ),
        "transport": TransportSection(transport="tcp", delimiter="\n"),
        "help_section": HelpSection(overview="Overview", setup="Setup"),
        "discovery": DiscoverySection(),
        "config_fields": ConfigFieldsSection(
            default_config={"host": "", "port": 1234},
            config_schema={
                "host": ConfigSchemaEntry(type="string", label="Host", required=True),
            },
        ),
        "state_variables": StateVariablesSection(
            state_variables={"power": StateVariableEntry(label="Power", type="boolean")},
        ),
        "commands": CommandsSection(
            commands={"power_on": CommandEntry(label="Power On", send="PON\n")},
        ),
        "responses": ResponsesSection(
            responses=(ResponseEntry(match="^PWR=(.+)$", set={"power": "$1"}),),
        ),
        "on_connect": OnConnectSection(),
        "polling": PollingSection(queries=("STATUS?\n",), inferred_poll_interval=5),
        "compatible_models": CompatibleModelsSection(),
        "simulator": SimulatorSection(initial_state={"power": False}),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_driver_payload_uses_locked_top_level_order() -> None:
    payload = build_driver_payload(
        _sections(
            discovery=DiscoverySection(port_open=(1234,)),
            on_connect=OnConnectSection(commands=("HELLO\n",)),
        )
    )

    assert list(payload) == [
        "id",
        "name",
        "manufacturer",
        "category",
        "version",
        "author",
        "transport",
        "description",
        "source_url",
        "delimiter",
        "help",
        "discovery",
        "default_config",
        "config_schema",
        "state_variables",
        "commands",
        "responses",
        "on_connect",
        "polling",
        "simulator",
    ]


def test_build_driver_payload_omits_empty_optional_sections() -> None:
    payload = build_driver_payload(_sections(transport=TransportSection(transport="tcp")))

    assert "delimiter" not in payload
    assert "discovery" not in payload
    assert "on_connect" not in payload
    assert "compatible_models" not in payload


def test_build_driver_payload_merges_poll_interval_into_default_config() -> None:
    payload = build_driver_payload(_sections())

    assert payload["default_config"] == {"host": "", "port": 1234, "poll_interval": 5}
    assert payload["polling"] == {"queries": ["STATUS?\n"]}


def test_serialize_driver_double_quotes_protocol_strings() -> None:
    text = serialize_driver(build_driver_payload(_sections()))

    assert 'delimiter: "\\n"' in text
    assert 'send: "PON\\n"' in text
    assert '- "STATUS?\\n"' in text
    assert text.endswith("\n")
    assert yaml.safe_load(text)["commands"]["power_on"]["send"] == "PON\n"
