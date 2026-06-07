"""OpenAVC .avcdriver YAML emission."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from c2o.model.review import ReviewCode, ReviewFlag, ReviewReport
from c2o.validate import UpstreamValidationResult, validate_upstream

_UNKNOWN_SOURCE = "[Unknown]"
_MANIFEST_SOURCE_CODES = {
    ReviewCode.ID_COERCED,
    ReviewCode.CATEGORY_DEFAULT,
    ReviewCode.DESCRIPTION_MARKETING,
    ReviewCode.UNKNOWN_MANUFACTURER,
    ReviewCode.COMPATIBLE_MODELS_CONFIDENCE,
    ReviewCode.AUTHOR_DEFAULT,
}


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

    # Determine simulated flag from simulator content.
    sim = sections.simulator
    has_simulator = bool(sim.initial_state or sim.controls or sim.command_handlers)

    payload: dict[str, Any] = {
        "id": manifest.id,
        "name": manifest.name,
        "manufacturer": manifest.manufacturer,
        "category": manifest.category,
        "version": manifest.version,
        "author": manifest.author,
        "transport": transport.transport,
        "description": manifest.description,
        "verified": False,
    }

    if has_simulator:
        payload["simulated"] = True

    # Ports: use discovery port_open hints or config_fields port default.
    ports = _collect_ports(sections)
    if ports:
        payload["ports"] = list(ports)

    if manifest.tags:
        payload["tags"] = list(manifest.tags)

    if manifest.protocols:
        payload["protocols"] = list(manifest.protocols)

    if manifest.source_url is not None:
        payload["source_url"] = manifest.source_url
    if transport.delimiter is not None:
        payload["delimiter"] = transport.delimiter

    auth = getattr(sections, "auth", None)
    if auth is not None:
        payload["auth"] = _non_empty_items(auth.model_dump(mode="json", exclude_none=True))

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


def serialize_driver_todo(payload: dict[str, Any], review: ReviewReport) -> str:
    """Serialize an OpenAVC driver payload with review TODO comments."""
    return annotate_driver_yaml(serialize_driver(payload), review)


def annotate_driver_yaml(text: str, review: ReviewReport) -> str:
    """Insert review TODO comments before the YAML fields they annotate."""
    flags = sorted(review.flags, key=lambda flag: (flag.code.value, flag.field))
    if not flags:
        return text

    lines = text.rstrip("\n").splitlines()
    anchor_blocks: dict[int, list[list[str]]] = {}
    header_blocks: list[list[str]] = []

    for flag in flags:
        anchor = _resolve_comment_anchor(lines, flag.field)
        block = _todo_comment_block(flag, indent=anchor.indent)
        if anchor.line_index is None:
            header_blocks.append(block)
        else:
            anchor_blocks.setdefault(anchor.line_index, []).append(block)

    out: list[str] = []
    for block in header_blocks:
        out.extend(block)
    for index, line in enumerate(lines):
        for block in anchor_blocks.get(index, []):
            out.extend(block)
        out.append(line)
    return "\n".join(out) + "\n"


def write_avcdriver(path: Path, sections: Any) -> None:
    """Write a driver directly to the requested path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_driver(build_driver_payload(sections)), encoding="utf-8")


def write_avcdriver_todo(path: Path, sections: Any) -> None:
    """Write a driver with review TODO comments directly to the requested path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_driver_payload(sections)
    path.write_text(serialize_driver_todo(payload, sections.review), encoding="utf-8")


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


def _collect_ports(sections: Any) -> list[int]:
    """Collect port numbers from discovery hints and config defaults."""
    ports: list[int] = []
    # Ports from config_fields default_config
    raw_port = sections.config_fields.default_config.get("port")
    if isinstance(raw_port, int) and 1 <= raw_port <= 65535:
        ports.append(raw_port)
    # Ports from discovery section
    for p in getattr(sections.discovery, "port_open", ()):
        if isinstance(p, int) and p not in ports:
            ports.append(p)
    return ports


def _non_empty_items(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in ([], {}, None)}


def _default_config_payload(sections: Any) -> dict[str, Any]:
    payload = dict(sections.config_fields.default_config)
    if sections.polling.inferred_poll_interval is not None:
        payload["poll_interval"] = sections.polling.inferred_poll_interval
    return payload


class _CommentAnchor:
    def __init__(self, line_index: int | None, indent: int) -> None:
        self.line_index = line_index
        self.indent = indent


def _resolve_comment_anchor(lines: list[str], field: str) -> _CommentAnchor:
    parts = field.split(".", maxsplit=1)
    if len(parts) == 1:
        line_index = _find_key_line(lines, field, indent=0)
        return _CommentAnchor(line_index, 0) if line_index is not None else _CommentAnchor(None, 0)

    section, key = parts
    section_index = _find_key_line(lines, section, indent=0)
    if section_index is None:
        return _CommentAnchor(None, 0)

    next_top_level = _find_next_top_level_line(lines, section_index + 1)
    search_end = next_top_level if next_top_level is not None else len(lines)
    nested_index = _find_key_line(lines, key, indent=2, start=section_index + 1, end=search_end)
    if nested_index is not None:
        return _CommentAnchor(nested_index, 2)
    return _CommentAnchor(section_index, 0)


def _find_key_line(
    lines: list[str],
    key: str,
    *,
    indent: int,
    start: int = 0,
    end: int | None = None,
) -> int | None:
    prefix = f"{' ' * indent}{key}:"
    for index in range(start, len(lines) if end is None else end):
        if lines[index].startswith(prefix):
            return index
    return None


def _find_next_top_level_line(lines: list[str], start: int) -> int | None:
    for index in range(start, len(lines)):
        line = lines[index]
        if line and not line.startswith(" "):
            return index
    return None


def _todo_comment_block(flag: ReviewFlag, *, indent: int) -> list[str]:
    prefix = " " * indent
    return [
        f"{prefix}#TODO",
        f"{prefix}#",
        f"{prefix}# {_source_reference(flag)}",
        f"{prefix}#",
        f"{prefix}# {{ {_details_text(flag)} }}",
        f"{prefix}# {_comment_text(flag.message)}",
    ]


def _source_reference(flag: ReviewFlag) -> str:
    source_path = flag.source_path or _inferred_source_path(flag) or _UNKNOWN_SOURCE
    source_line = str(flag.source_line) if flag.source_line is not None else _UNKNOWN_SOURCE
    return f"{source_path}:{source_line}"


def _inferred_source_path(flag: ReviewFlag) -> str | None:
    if flag.code in _MANIFEST_SOURCE_CODES:
        return "companion/manifest.json"
    return None


def _details_text(flag: ReviewFlag) -> str:
    if not flag.details:
        return "[Empty]"
    return ", ".join(f"{key}={_comment_text(value)}" for key, value in sorted(flag.details.items()))


def _comment_text(value: str) -> str:
    return value.replace("\r", "\\r").replace("\n", "\\n")
