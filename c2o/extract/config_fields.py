"""Extract OpenAVC config fields from Companion getConfigFields()."""

from __future__ import annotations

import re
from typing import Any, Final, cast

from tree_sitter import Node

from c2o.extract.param_schema import (
    coerce_numeric,
    extract_static_choice_values,
    infer_option_type,
)
from c2o.model.driver import (
    AuthSection,
    ConfigFieldsSection,
    ConfigFieldType,
    ConfigSchemaEntry,
)
from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport
from c2o.parse.cross_file import resolve_exported_array_constant
from c2o.parse.js import ParsedModule, find_method_definitions, node_text
from c2o.parse.literals import UNRESOLVED, decode_object

_NO_DEFAULT: Final[object] = object()

# Default Telnet port, synthesized when telnet_login auth is detected but the
# module never exposes a port config field.
_TELNET_DEFAULT_PORT: Final[int] = 23

# Module-internal UI field IDs that should never appear in the OpenAVC driver schema.
# These are Companion-specific preferences with no connection/transport semantics.
_MODULE_UI_FIELD_IDS: Final[frozenset[str]] = frozenset(
    {
        "autoConnect",
        "auto_connect",
        "autoTCP",
        "debug",
        "debugLevel",
        "debug_level",
        "enableTCP",
        "enable_tcp",
        "pollingOn",
        "polling_on",
        "storeWithoutSpeed",
        "store_without_speed",
        "tcpPort",
        "tcp_port",
    }
)

_FIELD_ID_ALIASES: Final[dict[str, str | None]] = {
    "httpPort": "port",
    "pollInterval": "poll_interval",
    "pollingInterval": "poll_interval",
    "polling_interval": "poll_interval",
    "tcpPort": None,
}

# Field IDs whose values should be treated as secrets (masked in UI).
_SECRET_FIELD_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)password|passwd|secret|token|api[_]?key|auth[_]?key"
)


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

    source = parsed.sources[matches[0].rel_path]
    resolved = _find_return_array(
        body,
        source=source,
        rel_path=matches[0].rel_path,
        parsed=parsed,
    )
    if resolved is None:
        return ConfigFieldsSection()

    array, array_source = resolved
    default_config: dict[str, Any] = {}
    config_schema: dict[str, ConfigSchemaEntry] = {}
    for child in array.named_children:
        if child.type == "object":
            _consume_field(child, array_source, default_config, config_schema)

    # P1-3: Remove non-transport boolean/checkbox fields that are module-UI-only.
    _filter_non_transport_fields(default_config, config_schema)

    return ConfigFieldsSection(
        default_config=default_config,
        config_schema=config_schema,
    )


def ensure_auth_config_fields(
    section: ConfigFieldsSection,
    auth: AuthSection | None,
) -> ConfigFieldsSection:
    """Add credential config entries required by detected telnet auth."""
    if auth is None:
        return section

    default_config = dict(section.default_config)
    config_schema = dict(section.config_schema)

    _ensure_auth_field(
        auth.username_field,
        label="Username",
        secret=False,
        default_config=default_config,
        config_schema=config_schema,
    )
    _ensure_auth_field(
        auth.password_field,
        label="Password",
        secret=True,
        default_config=default_config,
        config_schema=config_schema,
    )

    return ConfigFieldsSection(default_config=default_config, config_schema=config_schema)


def ensure_telnet_default_port(
    section: ConfigFieldsSection,
    auth: AuthSection | None,
) -> tuple[ConfigFieldsSection, ReviewReport]:
    """Synthesize a Telnet default port when telnet auth is detected.

    OpenAVC drivers surface the connection port via ``config_schema.port`` /
    ``default_config.port`` (and the emitter's top-level ``ports`` list). Many
    Companion Telnet modules hard-code port 23 and never expose a port field, so
    C2O infers it. The synthesized value is review-flagged.
    """
    if auth is None or auth.type != "telnet_login":
        return section, ReviewReport()
    if "port" in section.default_config or "port" in section.config_schema:
        return section, ReviewReport()

    default_config = dict(section.default_config)
    config_schema = dict(section.config_schema)
    default_config["port"] = _TELNET_DEFAULT_PORT
    config_schema["port"] = ConfigSchemaEntry(
        type="integer",
        label="Telnet Port",
        default=_TELNET_DEFAULT_PORT,
    )
    flag = ReviewFlag(
        code=ReviewCode.CONFIG_DEFAULT_PORT_INFERRED,
        field="config_schema.port",
        message=(
            "Telnet auth was detected but no port field was declared; "
            f"defaulted port to {_TELNET_DEFAULT_PORT}."
        ),
        details={"port": str(_TELNET_DEFAULT_PORT), "transport": "telnet"},
    )
    return (
        ConfigFieldsSection(default_config=default_config, config_schema=config_schema),
        ReviewReport(flags=(flag,)),
    )


def _ensure_auth_field(
    field_id: str | None,
    *,
    label: str,
    secret: bool,
    default_config: dict[str, Any],
    config_schema: dict[str, ConfigSchemaEntry],
) -> None:
    if field_id is None:
        return
    if field_id not in default_config:
        default_config[field_id] = ""
    if field_id not in config_schema:
        config_schema[field_id] = ConfigSchemaEntry(
            type="string",
            label=label,
            required=True,
            secret=True if secret else None,
        )


def _find_return_array(
    node: Node,
    *,
    source: str,
    rel_path: str,
    parsed: ParsedModule,
) -> tuple[Node, str] | None:
    if node.type == "return_statement":
        for child in node.named_children:
            if child.type == "array":
                return child, source
            if child.type == "identifier":
                resolved = resolve_exported_array_constant(
                    node_text(child, source),
                    rel_path,
                    parsed,
                )
                if resolved is not None:
                    return resolved.node, resolved.source
    for child in node.named_children:
        result = _find_return_array(
            child,
            source=source,
            rel_path=rel_path,
            parsed=parsed,
        )
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
    aliased_field_id = _FIELD_ID_ALIASES.get(field_id, field_id)
    if aliased_field_id is None:
        return
    field_id = aliased_field_id
    if field_id in _MODULE_UI_FIELD_IDS:
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

    # P1-4: Mark password-type fields as secret.
    is_secret = bool(_SECRET_FIELD_PATTERN.search(field_id)) or None

    config_schema[field_id] = ConfigSchemaEntry(
        type=inferred_type,
        label=field.get("label") if isinstance(field.get("label"), str) else None,
        required=_required_for(inferred_type, has_default),
        values=values,
        min=schema_min,
        max=schema_max,
        secret=is_secret if is_secret else None,
    )


def _filter_non_transport_fields(
    default_config: dict[str, Any],
    config_schema: dict[str, ConfigSchemaEntry],
) -> None:
    """Remove known module-internal UI fields that are not connection parameters.

    Only well-known Companion-specific IDs (e.g. ``pollingOn``,
    ``storeWithoutSpeed``) are removed. Generic connection parameters should be
    normalized before reaching this pass.
    """
    to_remove = [fid for fid in config_schema if fid in _MODULE_UI_FIELD_IDS]
    for field_id in to_remove:
        config_schema.pop(field_id, None)
        default_config.pop(field_id, None)


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
