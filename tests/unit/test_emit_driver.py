"""Unit tests for .avcdriver YAML emission."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import yaml  # type: ignore[import-untyped]

from c2o.emit.driver import annotate_driver_yaml, build_driver_payload, serialize_driver
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
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport


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
        "review": ReviewReport(),
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

    # Core order; verified is always present, simulated/ports appear when non-empty.
    keys = list(payload)
    assert keys[0] == "id"
    assert keys[1] == "name"
    assert keys[2] == "manufacturer"
    assert keys[3] == "category"
    assert keys[4] == "version"
    assert keys[5] == "author"
    assert keys[6] == "transport"
    assert keys[7] == "description"
    assert "verified" in keys
    assert "source_url" in keys
    assert "delimiter" in keys
    assert "help" in keys
    assert "discovery" in keys
    assert "default_config" in keys
    assert "config_schema" in keys
    assert "state_variables" in keys
    assert "commands" in keys
    assert "responses" in keys
    assert "on_connect" in keys
    assert "polling" in keys
    assert "simulator" in keys
    # verified comes before help
    assert keys.index("verified") < keys.index("help")
    # source_url before help
    assert keys.index("source_url") < keys.index("help")
    # on_connect before polling before simulator
    assert keys.index("on_connect") < keys.index("polling") < keys.index("simulator")


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


def test_build_driver_payload_emits_ports_from_normalized_config_port() -> None:
    payload = build_driver_payload(
        _sections(
            config_fields=ConfigFieldsSection(
                default_config={"host": "", "port": 80},
                config_schema={
                    "host": ConfigSchemaEntry(type="string", label="Host", required=True),
                    "port": ConfigSchemaEntry(type="integer", label="Port", min=1, max=65535),
                },
            ),
            discovery=DiscoverySection(),
        )
    )

    assert payload["ports"] == [80]


def test_build_driver_payload_emits_protocols_after_tags() -> None:
    payload = build_driver_payload(
        _sections(
            manifest=ManifestSection(
                id="panasonic_ptz",
                name="Panasonic PTZ",
                manufacturer="Panasonic",
                category="camera",
                version="1.0.0",
                author="C2O",
                description="Fixture driver",
                tags=("camera", "ptz", "panasonic"),
                protocols=("panasonic_http",),
            )
        )
    )

    assert payload["protocols"] == ["panasonic_http"]
    assert list(payload).index("tags") < list(payload).index("protocols")


def test_serialize_driver_double_quotes_protocol_strings() -> None:
    text = serialize_driver(build_driver_payload(_sections()))

    assert 'delimiter: "\\n"' in text
    assert 'send: "PON\\n"' in text
    assert '- "STATUS?\\n"' in text
    assert text.endswith("\n")
    assert yaml.safe_load(text)["commands"]["power_on"]["send"] == "PON\n"


def test_annotate_driver_yaml_inserts_top_level_todo_before_field() -> None:
    plain = "id: bmd_webpresenter\nname: BMD Web Presenter\n"
    review = ReviewReport(
        flags=(
            ReviewFlag(
                code=ReviewCode.ID_COERCED,
                field="id",
                message="Driver id was coerced.",
                details={"old": "bmd-webpresenter", "new": "bmd_webpresenter"},
            ),
        )
    )

    annotated = annotate_driver_yaml(plain, review)

    assert annotated.startswith(
        "#TODO\n"
        "#\n"
        "# companion/manifest.json:[Unknown]\n"
        "#\n"
        "# { new=bmd_webpresenter, old=bmd-webpresenter }\n"
        "# Driver id was coerced.\n"
        "id: bmd_webpresenter\n"
    )
    assert yaml.safe_load(annotated) == yaml.safe_load(plain)


def test_annotate_driver_yaml_inserts_nested_todo_with_indent() -> None:
    plain = (
        "state_variables:\n"
        "  power:\n"
        "    label: Power\n"
        "    type: boolean\n"
        "simulator: {}\n"
    )
    review = ReviewReport(
        flags=(
            ReviewFlag(
                code=ReviewCode.INFERRED_STATE_TYPE,
                field="state_variables.power",
                message="Type for state variable 'power' was inferred as 'boolean'.",
                details={"variable_id": "power", "inferred_type": "boolean"},
            ),
        )
    )

    annotated = annotate_driver_yaml(plain, review)

    assert (
        "state_variables:\n"
        "  #TODO\n"
        "  #\n"
        "  # [Unknown]:[Unknown]\n"
        "  #\n"
        "  # { inferred_type=boolean, variable_id=power }\n"
        "  # Type for state variable 'power' was inferred as 'boolean'.\n"
        "  power:\n"
    ) in annotated
    assert yaml.safe_load(annotated) == yaml.safe_load(plain)


def test_annotate_driver_yaml_places_orphan_flags_in_header() -> None:
    plain = "id: dummy_device\nsimulator: {}\n"
    review = ReviewReport(
        flags=(
            ReviewFlag(
                code=ReviewCode.MISSING_DISCOVERY_FINGERPRINT,
                field="discovery",
                message="Discovery fingerprints require review.",
            ),
        )
    )

    annotated = annotate_driver_yaml(plain, review)

    assert annotated.startswith(
        "#TODO\n"
        "#\n"
        "# [Unknown]:[Unknown]\n"
        "#\n"
        "# { [Empty] }\n"
        "# Discovery fingerprints require review.\n"
        "id: dummy_device\n"
    )
    assert yaml.safe_load(annotated) == yaml.safe_load(plain)


def test_annotate_driver_yaml_uses_explicit_source_reference() -> None:
    plain = "simulator: {}\n"
    review = ReviewReport(
        flags=(
            ReviewFlag(
                code=ReviewCode.SIMULATOR_AUTO,
                field="simulator",
                message="Simulator requires review.",
                source_path="index.js",
                source_line=42,
            ),
        )
    )

    annotated = annotate_driver_yaml(plain, review)

    assert "# index.js:42\n" in annotated
    assert yaml.safe_load(annotated) == yaml.safe_load(plain)
