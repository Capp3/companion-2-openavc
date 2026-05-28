"""Extract OpenAVC config fields from Companion getConfigFields()."""

from __future__ import annotations

from typing import Any, Final, cast

from tree_sitter import Node

from c2o.extract.param_schema import (
    coerce_numeric,
    extract_static_choice_values,
    infer_option_type,
)
from c2o.model.driver import ConfigFieldsSection, ConfigFieldType, ConfigSchemaEntry
from c2o.parse.js import ParsedModule, find_method_definitions
from c2o.parse.literals import UNRESOLVED, decode_object

_NO_DEFAULT: Final[object] = object()


class ConfigFieldsExtractionError(ValueError):
    """Raised when getConfigFields cannot be statically interpreted."""


def extract_config_fields(parsed: ParsedModule) -> ConfigFieldsSection:
    """Build default_config + config_schema from getConfigFields()."""
    matches = find_method_definitions(parsed, "getConfigFields")
    if not matches:
        return ConfigFieldsSection()

    body = matches[0].body
    if body is None:
        return ConfigFieldsSection()

    array = _find_return_array(body)
    if array is None:
        return ConfigFieldsSection()

    source = parsed.sources[matches[0].rel_path]
    default_config: dict[str, Any] = {}
    config_schema: dict[str, ConfigSchemaEntry] = {}
    for child in array.named_children:
        if child.type == "object":
            _consume_field(child, source, default_config, config_schema)

    return ConfigFieldsSection(
        default_config=default_config,
        config_schema=config_schema,
    )


def _find_return_array(node: Node) -> Node | None:
    if node.type == "return_statement":
        for child in node.named_children:
            if child.type == "array":
                return child
    for child in node.named_children:
        result = _find_return_array(child)
        if result is not None:
            return result
    return None


def _consume_field(
    node: Node,
    source: str,
    default_config: dict[str, Any],
    config_schema: dict[str, ConfigSchemaEntry],
) -> None:
    raw_field = decode_object(node, source)
    if raw_field is UNRESOLVED:
        return
    field = cast(dict[str, Any], raw_field)

    field_id = field.get("id")
    companion_type = field.get("type")
    if not isinstance(field_id, str) or not isinstance(companion_type, str):
        return
    if companion_type == "static-text":
        return

    inferred_type, min_value, max_value = infer_option_type(field)
    if inferred_type is None:
        return

    values = extract_static_choice_values(field.get("choices")) if inferred_type == "enum" else None
    if inferred_type == "enum" and values is None:
        return

    has_default = "default" in field
    default_value = _default_for(inferred_type, field.get("default", _NO_DEFAULT), values)
    if default_value is not _NO_DEFAULT:
        default_config[field_id] = default_value

    schema_min = coerce_numeric(field.get("min", min_value), inferred_type)
    schema_max = coerce_numeric(field.get("max", max_value), inferred_type)

    config_schema[field_id] = ConfigSchemaEntry(
        type=inferred_type,
        label=field.get("label") if isinstance(field.get("label"), str) else None,
        required=_required_for(inferred_type, has_default),
        values=values,
        min=schema_min,
        max=schema_max,
    )


def _default_for(
    field_type: ConfigFieldType,
    companion_default: Any,
    values: tuple[str, ...] | None,
) -> Any:
    if companion_default is not _NO_DEFAULT:
        return _coerce_default(companion_default, field_type)

    if field_type in {"string", "text"}:
        return ""
    if field_type == "boolean":
        return False
    if field_type == "enum" and values:
        return values[0]
    return _NO_DEFAULT


def _required_for(field_type: ConfigFieldType, has_default: bool) -> bool | None:
    if not has_default and field_type in {"string", "text", "integer"}:
        return True
    return None


def _coerce_default(value: Any, field_type: ConfigFieldType) -> Any:
    if field_type == "integer":
        number = coerce_numeric(value, field_type)
        return number if number is not None else value
    if field_type in {"number", "float"}:
        number = coerce_numeric(value, field_type)
        return number if number is not None else value
    return value
