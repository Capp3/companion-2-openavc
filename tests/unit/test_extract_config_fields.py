"""Unit tests for getConfigFields extraction."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from c2o.extract import extract_config_fields
from c2o.model.driver import ConfigFieldsSection
from c2o.parse.js import ParsedModule, parse_module, parse_source


def _extract_inline(tmp_path: Path, fields_source: str) -> ConfigFieldsSection:
    source = dedent(f"""
        class Example {{
          getConfigFields() {{
            return [
              {fields_source}
            ]
          }}
        }}
        """)
    parsed = ParsedModule(
        root=tmp_path,
        sources={"index.js": source},
        trees={"index.js": parse_source(source)},
    )
    return extract_config_fields(parsed)


def test_textinput_without_hint_defaults_to_required_string(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textinput', id: 'host', label: 'Host' }",
    )

    assert section.default_config == {"host": ""}
    assert section.config_schema["host"].model_dump(exclude_none=True) == {
        "type": "string",
        "label": "Host",
        "required": True,
    }


def test_textinput_with_ip_hint_defaults_to_required_string(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textinput', id: 'host', label: 'Host', regex: Regex.IP }",
    )

    assert section.default_config == {"host": ""}
    assert section.config_schema["host"].type == "string"
    assert section.config_schema["host"].required is True


def test_textinput_with_ip_hint_and_default_is_not_required(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textinput', id: 'host', label: 'Host', regex: Regex.IP, default: '10.0.0.1' }",
    )

    assert section.default_config == {"host": "10.0.0.1"}
    assert section.config_schema["host"].required is None


def test_textinput_with_port_hint_coerces_string_default(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textinput', id: 'port', label: 'Port', regex: Regex.Port, default: '5000' }",
    )

    assert section.default_config == {"port": 5000}
    assert section.config_schema["port"].model_dump(exclude_none=True) == {
        "type": "integer",
        "label": "Port",
        "min": 1,
        "max": 65535,
    }


def test_textinput_with_number_hint_omits_numeric_default(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textinput', id: 'level', label: 'Level', regex: Regex.Number }",
    )

    assert section.default_config == {}
    assert section.config_schema["level"].type == "integer"
    assert section.config_schema["level"].required is True


def test_number_field_propagates_default_and_bounds(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'number', id: 'poll_interval', label: 'Poll interval', "
        "default: 5, min: 1, max: 60 }",
    )

    assert section.default_config == {"poll_interval": 5}
    assert section.config_schema["poll_interval"].model_dump(exclude_none=True) == {
        "type": "integer",
        "label": "Poll interval",
        "min": 1,
        "max": 60,
    }


def test_checkbox_with_default_false(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'checkbox', id: 'verbose', label: 'Verbose', default: false }",
    )

    assert section.default_config == {"verbose": False}
    assert section.config_schema["verbose"].type == "boolean"


def test_checkbox_without_default_defaults_false(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'checkbox', id: 'verbose', label: 'Verbose' }",
    )

    assert section.default_config == {"verbose": False}
    assert section.config_schema["verbose"].type == "boolean"


def test_dropdown_extracts_values_and_default(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'dropdown', id: 'mode', label: 'Mode', default: 'a', "
        "choices: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }] }",
    )

    assert section.default_config == {"mode": "a"}
    assert section.config_schema["mode"].values == ("a", "b")
    assert section.config_schema["mode"].type == "enum"


def test_dropdown_without_default_uses_first_choice(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'dropdown', id: 'mode', label: 'Mode', "
        "choices: [{ id: 'auto', label: 'Auto' }, { id: 'manual', label: 'Manual' }] }",
    )

    assert section.default_config == {"mode": "auto"}
    assert section.config_schema["mode"].values == ("auto", "manual")


def test_textarea_defaults_to_required_text(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textarea', id: 'notes', label: 'Notes' }",
    )

    assert section.default_config == {"notes": ""}
    assert section.config_schema["notes"].type == "text"
    assert section.config_schema["notes"].required is True


def test_static_text_is_dropped(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'static-text', id: 'info', label: 'Info', value: 'Hello' }",
    )

    assert section == ConfigFieldsSection()


def test_unknown_type_is_dropped(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'mystery', id: 'field', label: 'Mystery' }",
    )

    assert section == ConfigFieldsSection()


def test_unresolved_id_is_dropped(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textinput', id: dynamicId, label: 'Host' }",
    )

    assert section == ConfigFieldsSection()


def test_unresolved_field_value_is_dropped(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'textinput', id: 'host', label: dynamicLabel }",
    )

    assert section == ConfigFieldsSection()


def test_empty_dropdown_choices_are_dropped(tmp_path: Path) -> None:
    section = _extract_inline(
        tmp_path,
        "{ type: 'dropdown', id: 'mode', label: 'Mode', choices: [] }",
    )

    assert section == ConfigFieldsSection()


def test_dummy_fixture_extracts_expected_config_fields(dummy_device: Path) -> None:
    section = extract_config_fields(parse_module(dummy_device))

    assert section.default_config == {
        "host": "192.168.1.10",
        "port": 5000,
        "poll_interval": 5,
        "verbose": False,
        "mode": "auto",
    }
    assert set(section.config_schema) == {
        "host",
        "port",
        "poll_interval",
        "verbose",
        "mode",
    }
    assert section.config_schema["mode"].values == ("auto", "manual")


def test_bmd_webpresenter_fixture_extracts_expected_config_fields(
    bmd_webpresenter: Path,
) -> None:
    section = extract_config_fields(parse_module(bmd_webpresenter))

    assert section.default_config == {"host": "", "port": 9977}
    assert section.config_schema["host"].model_dump(exclude_none=True) == {
        "type": "string",
        "label": "Device IP",
        "required": True,
    }
    assert section.config_schema["port"].model_dump(exclude_none=True) == {
        "type": "integer",
        "label": "Device Port",
        "min": 1,
        "max": 65535,
    }


def test_module_without_get_config_fields_returns_empty_section(
    unknown_vendor: Path,
) -> None:
    assert extract_config_fields(parse_module(unknown_vendor)) == ConfigFieldsSection()
