"""Unit tests for shared param schema inference."""

from __future__ import annotations

from c2o.extract.param_schema import (
    build_params_from_options,
    infer_option_type,
    option_to_param_entry,
)


def test_infer_option_type_maps_number_to_integer() -> None:
    inferred, min_value, max_value = infer_option_type({"type": "number", "id": "input"})

    assert inferred == "integer"
    assert min_value is None
    assert max_value is None


def test_option_to_param_entry_maps_dropdown_to_enum() -> None:
    entry = option_to_param_entry(
        {
            "type": "dropdown",
            "id": "mode",
            "label": "Mode",
            "choices": [{"id": "auto"}, {"id": "manual"}],
        }
    )

    assert entry is not None
    assert entry.type == "enum"
    assert entry.values == ("auto", "manual")


def test_option_to_param_entry_skips_dynamic_dropdown() -> None:
    entry = option_to_param_entry(
        {
            "type": "dropdown",
            "id": "video_mode",
            "choices": "this.formats",
        }
    )

    assert entry is None


def test_build_params_from_options_skips_static_text() -> None:
    params = build_params_from_options(
        [
            {"type": "static-text", "id": "info", "label": "Info"},
            {"type": "textinput", "id": "label", "label": "Label"},
        ]
    )

    assert list(params) == ["label"]
    assert params["label"].type == "string"
