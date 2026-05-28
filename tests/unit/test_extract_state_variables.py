"""Unit tests for setVariableDefinitions extraction."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from c2o.extract import extract_state_variables
from c2o.model.driver import StateVariablesSection
from c2o.model.review import ReviewCode, ReviewReport
from c2o.parse.js import ParsedModule, parse_module, parse_source


def _extract_inline(tmp_path: Path, body: str) -> tuple[StateVariablesSection, ReviewReport]:
    source = dedent(f"""
        class Example {{
          init() {{
            {body}
          }}
        }}
        """)
    parsed = ParsedModule(
        root=tmp_path,
        sources={"index.js": source},
        trees={"index.js": parse_source(source)},
    )
    return extract_state_variables(parsed)


def test_inline_array_definition_emits_labels(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([
          { variableId: 'device_label', name: 'Device Label' },
        ])
        """,
    )

    assert len(section.state_variables) == 1
    assert section.state_variables["device_label"].label == "Device Label"
    assert len(review) == 1


def test_push_array_definition_emits_entries_in_order(tmp_path: Path) -> None:
    section, _review = _extract_inline(
        tmp_path,
        """
        let variables = []
        variables.push(
          { variableId: 'first', name: 'First' },
          { variableId: 'second', name: 'Second' },
        )
        this.setVariableDefinitions(variables)
        """,
    )

    assert list(section.state_variables.keys()) == ["first", "second"]


def test_missing_set_variable_definitions_returns_empty(tmp_path: Path) -> None:
    section, review = _extract_inline(tmp_path, "this.initTCP()")

    assert section.state_variables == {}
    assert len(review) == 0


def test_unsupported_argument_shape_returns_empty(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        "this.setVariableDefinitions(buildVars())",
    )

    assert section.state_variables == {}
    assert len(review) == 0


def test_boolean_literal_inference(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'mute_state', name: 'Mute' }])
        this.setVariableValues({ mute_state: true })
        """,
    )

    assert section.state_variables["mute_state"].type == "boolean"
    assert review.flags[0].details["evidence"] == "literal"


def test_integer_literal_inference(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'level', name: 'Level' }])
        this.setVariableValues({ level: 42 })
        """,
    )

    assert section.state_variables["level"].type == "integer"
    assert review.flags[0].details["evidence"] == "literal"


def test_number_literal_inference(tmp_path: Path) -> None:
    section, _review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'gain', name: 'Gain' }])
        this.setVariableValues({ gain: 3.14 })
        """,
    )

    assert section.state_variables["gain"].type == "number"


def test_string_literal_inference(tmp_path: Path) -> None:
    section, _review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'label', name: 'Label' }])
        this.setVariableValues({ label: 'hello' })
        """,
    )

    assert section.state_variables["label"].type == "string"


def test_parse_int_inference(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'input_level', name: 'Input Level' }])
        this.setVariableValues({ input_level: parseInt('5', 10) })
        """,
    )

    assert section.state_variables["input_level"].type == "integer"
    assert review.flags[0].details["evidence"] == "call"


def test_parse_float_inference(tmp_path: Path) -> None:
    section, _review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'gain', name: 'Gain' }])
        this.setVariableValues({ gain: parseFloat('1.5') })
        """,
    )

    assert section.state_variables["gain"].type == "number"


def test_includes_inference(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'mute_state', name: 'Mute' }])
        this.setVariableValues({ mute_state: line.includes('ON') })
        """,
    )

    assert section.state_variables["mute_state"].type == "boolean"
    assert review.flags[0].details["evidence"] == "call"


def test_substring_inference(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'part', name: 'Part' }])
        this.setVariableValues({ part: this.duration.substring(3, 5) })
        """,
    )

    assert section.state_variables["part"].type == "string"
    assert review.flags[0].details["evidence"] == "call"


def test_comparison_inference(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'active', name: 'Active' }])
        this.setVariableValues({ active: this.streaming === 'Streaming' })
        """,
    )

    assert section.state_variables["active"].type == "boolean"
    assert review.flags[0].details["evidence"] == "comparison"


def test_member_expression_falls_back_to_string(tmp_path: Path) -> None:
    section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'label', name: 'Label' }])
        this.setVariableValues({ label: data['Label'] })
        """,
    )

    assert section.state_variables["label"].type == "string"
    assert review.flags[0].details["evidence"] == "fallback"


def test_integer_and_number_conflict_widens_to_number(tmp_path: Path) -> None:
    section, _review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'level', name: 'Level' }])
        this.setVariableValues({ level: 5 })
        this.setVariableValues({ level: 3.5 })
        """,
    )

    assert section.state_variables["level"].type == "number"


def test_review_flag_payload_shape(tmp_path: Path) -> None:
    _section, review = _extract_inline(
        tmp_path,
        """
        this.setVariableDefinitions([{ variableId: 'mute_state', name: 'Mute' }])
        this.setVariableValues({ mute_state: false })
        """,
    )

    flag = review.flags[0]
    assert flag.code == ReviewCode.INFERRED_STATE_TYPE
    assert flag.field == "state_variables.mute_state"
    assert flag.details["inferred_type"] == "boolean"
    assert flag.details["evidence"] == "literal"


def test_dummy_device_fixture(dummy_device: Path) -> None:
    section, review = extract_state_variables(parse_module(dummy_device))

    assert len(section.state_variables) == 3
    assert section.state_variables["device_label"].type == "string"
    assert section.state_variables["input_level"].type == "integer"
    assert section.state_variables["mute_state"].type == "boolean"
    assert len(review) == 3


def test_bmd_webpresenter_fixture(bmd_webpresenter: Path) -> None:
    section, review = extract_state_variables(parse_module(bmd_webpresenter))

    assert len(section.state_variables) == 17
    assert section.state_variables["model"].label == "Device Model"
    assert section.state_variables["stream_duration_HH"].type == "string"
    assert len(review) == 17
    assert all(flag.code == ReviewCode.INFERRED_STATE_TYPE for flag in review)


def test_unknown_vendor_fixture(unknown_vendor: Path) -> None:
    section, review = extract_state_variables(parse_module(unknown_vendor))

    assert section.state_variables == {}
    assert len(review) == 0
