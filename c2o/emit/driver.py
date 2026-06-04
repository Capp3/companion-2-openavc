"""OpenAVC .avcdriver YAML emission."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from c2o.validate import UpstreamValidationResult, validate_upstream


class _DriverDumper(yaml.SafeDumper):  # type: ignore[misc]
    """Safe dumper with stable, driver-specific formatting."""

    def ignore_aliases(self, data: object) -> bool:
        return True


def _represent_protocol_string(dumper: _DriverDumper, data: str) -> yaml.ScalarNode:
    style = '"' if any(char in data for char in ("\n", "\r", "\t")) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_DriverDumper.add_representer(str, _represent_protocol_string)


def build_driver_payload(sections: Any) -> dict[str, Any]:
    """Build a key-ordered OpenAVC driver payload from extracted sections."""
    manifest = sections.manifest
    transport = sections.transport

    payload: dict[str, Any] = {
        "id": manifest.id,
        "name": manifest.name,
        "manufacturer": manifest.manufacturer,
        "category": manifest.category,
        "version": manifest.version,
        "author": manifest.author,
        "transport": transport.transport,
        "description": manifest.description,
    }

    if manifest.source_url is not None:
        payload["source_url"] = manifest.source_url
    if transport.delimiter is not None:
        payload["delimiter"] = transport.delimiter

    payload["help"] = sections.help_section.model_dump(mode="json")

    discovery = _non_empty_items(_model_payload(sections.discovery))
    if discovery:
        payload["discovery"] = discovery

    payload["default_config"] = _default_config_payload(sections)
    payload["config_schema"] = _model_payload(sections.config_fields).get("config_schema", {})
    payload["state_variables"] = _model_payload(sections.state_variables).get("state_variables", {})
    payload["commands"] = _model_payload(sections.commands).get("commands", {})
    payload["responses"] = _model_payload(sections.responses).get("responses", [])

    on_connect = tuple(sections.on_connect.commands)
    if on_connect:
        payload["on_connect"] = list(on_connect)

    polling_queries = tuple(sections.polling.queries)
    if polling_queries:
        payload["polling"] = {"queries": list(polling_queries)}

    compatible_models = tuple(sections.compatible_models.compatible_models)
    if compatible_models:
        payload["compatible_models"] = _model_payload(sections.compatible_models)[
            "compatible_models"
        ]

    payload["simulator"] = _model_payload(sections.simulator)

    return payload


def serialize_driver(payload: dict[str, Any]) -> str:
    """Serialize an OpenAVC driver payload as clean YAML."""
    text = yaml.dump(
        payload,
        Dumper=_DriverDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )
    return text if text.endswith("\n") else f"{text}\n"


def write_avcdriver(path: Path, sections: Any) -> None:
    """Write a driver directly to the requested path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_driver(build_driver_payload(sections)), encoding="utf-8")


def write_avcdriver_validated(path: Path, sections: Any) -> UpstreamValidationResult:
    """Validate a temporary driver, then atomically move it to the requested path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{path.stem}.", dir=path.parent) as tmp_dir:
        tmp_path = Path(tmp_dir) / path.name
        write_avcdriver(tmp_path, sections)
        result = validate_upstream(tmp_path)
        if result.passed:
            shutil.move(str(tmp_path), path)
        return result


def _model_payload(model: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", model.model_dump(mode="json", exclude_none=True))


def _non_empty_items(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in ([], {}, None)}


def _default_config_payload(sections: Any) -> dict[str, Any]:
    payload = dict(sections.config_fields.default_config)
    if sections.polling.inferred_poll_interval is not None:
        payload["poll_interval"] = sections.polling.inferred_poll_interval
    return payload
