"""Shared Companion option → OpenAVC param schema inference."""

from __future__ import annotations

import re
from typing import Any, Final

from c2o.model.driver import ConfigFieldType, ParamEntry

_REGEX_HINT_TYPE: Final[dict[str, tuple[ConfigFieldType, int | None, int | None]]] = {
    "Regex.IP": ("string", None, None),
    "Regex.Port": ("integer", 1, 65535),
    "Regex.Number": ("integer", None, None),
}
_TEXT_FIELD_TYPES = {"textinput", "text"}
_NUMERIC_DEFAULT_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?$")


def infer_option_type(
    field: dict[str, Any],
) -> tuple[ConfigFieldType | None, int | None, int | None]:
    """Map a Companion option object to an OpenAVC param type and bounds."""
    companion_type = field.get("type")
    regex_hint = field.get("regex")

    if companion_type in _TEXT_FIELD_TYPES:
        if isinstance(regex_hint, str) and regex_hint in _REGEX_HINT_TYPE:
            return _REGEX_HINT_TYPE[regex_hint]
        return "string", None, None

    if companion_type == "number":
        return "integer", None, None
    if companion_type == "checkbox":
        return "boolean", None, None
    if companion_type == "dropdown":
        return "enum", None, None
    if companion_type == "textarea":
        return "text", None, None

    return None, None, None


def extract_static_choice_values(choices: Any) -> tuple[str, ...] | None:
    """Return static dropdown choice ids when all are literal."""
    if not isinstance(choices, list):
        return None

    values: list[str] = []
    for choice in choices:
        if isinstance(choice, dict):
            choice_id = choice.get("id")
            if isinstance(choice_id, str):
                values.append(choice_id)
            elif isinstance(choice_id, int | float | bool):
                values.append(str(choice_id))

    return tuple(values) if values else None


def coerce_numeric(value: Any, field_type: ConfigFieldType) -> int | float | None:
    """Coerce a static numeric literal for schema min/max fields."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return int(value) if field_type == "integer" else value
    if isinstance(value, str) and _NUMERIC_DEFAULT_PATTERN.match(value):
        return int(float(value)) if field_type == "integer" else float(value)
    return None


def option_to_param_entry(field: dict[str, Any]) -> ParamEntry | None:
    """Build a single command param entry from a Companion action option."""
    companion_type = field.get("type")
    if companion_type == "static-text":
        return None

    field_id = field.get("id")
    if not isinstance(field_id, str):
        return None

    inferred_type, min_value, max_value = infer_option_type(field)
    if inferred_type is None:
        return None

    values = extract_static_choice_values(field.get("choices")) if inferred_type == "enum" else None
    if inferred_type == "enum" and values is None:
        return None

    schema_min = coerce_numeric(field.get("min", min_value), inferred_type)
    schema_max = coerce_numeric(field.get("max", max_value), inferred_type)
    label = field.get("label") if isinstance(field.get("label"), str) else None
    help_text = field.get("tooltip") if isinstance(field.get("tooltip"), str) else None

    return ParamEntry(
        type=inferred_type,
        label=label,
        values=values,
        min=schema_min,
        max=schema_max,
        help=help_text,
    )


def build_params_from_options(options: Any) -> dict[str, ParamEntry]:
    """Build command params from a decoded action ``options`` array."""
    if not isinstance(options, list):
        return {}

    params: dict[str, ParamEntry] = {}
    for option in options:
        if not isinstance(option, dict):
            continue
        field_id = option.get("id")
        entry = option_to_param_entry(option)
        if entry is None or not isinstance(field_id, str):
            continue
        params[field_id] = entry
    return params
