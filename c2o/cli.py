"""C2O Typer CLI entrypoint."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from c2o import __version__
from c2o.emit.decline import (
    build_declined_report,
    declined_json_path_for_output,
    write_declined_json,
)
from c2o.extract import (
    CommandsExtractionError,
    CompatibleModelsExtractionError,
    ConfigFieldsExtractionError,
    DiscoveryExtractionError,
    HelpExtractionError,
    ManifestExtractionError,
    OnConnectExtractionError,
    PollingExtractionError,
    ResponsesExtractionError,
    SimulatorExtractionError,
    StateVariablesExtractionError,
    TransportExtractionError,
    extract_commands,
    extract_compatible_models,
    extract_config_fields,
    extract_discovery,
    extract_help,
    extract_manifest,
    extract_on_connect,
    extract_polling,
    extract_responses,
    extract_simulator,
    extract_state_variables,
    extract_transport,
)
from c2o.model.driver import ConfigFieldsSection, PollingSection
from c2o.model.review import ReviewCode, ReviewReport
from c2o.parse.js import ParsedModule, parse_module
from c2o.registry import Registry, reconcile_manufacturer
from c2o.source import SourceResolutionError, read_module_id, resolve_source
from c2o.suitability.blockers import Blocker
from c2o.suitability.gate import GateResult, assess_module

app = typer.Typer(
    name="c2o",
    help="Convert Bitfocus Companion modules into OpenAVC .avcdriver YAML drivers.",
    no_args_is_help=True,
)

# Injectable clock for tests (monkeypatch this attribute).
_declined_at_override: datetime | None = None

# Injectable registry for tests; production uses the live upstream-with-vendored-fallback loader.
_registry_override: Registry | None = None

_UNSET = object()


def _not_implemented(name: str) -> None:
    typer.echo(f"{name}: not implemented yet (see milestones in memory-bank/projectbrief.md)")
    raise typer.Exit(code=1)


def _decline_stderr(module_id: str, blockers: tuple[Blocker, ...]) -> None:
    typer.echo(
        f"Conversion declined for module '{module_id}' ({len(blockers)} blocker(s)):",
        err=True,
    )
    for blocker in blockers:
        typer.echo(f"  - [{blocker.code}] {blocker.message}", err=True)
    typer.echo(
        "Recommendation: author an OpenAVC Python driver per upstream AGENTS.md §3.",
        err=True,
    )


def _assess_root(root: Path) -> tuple[str, ParsedModule, GateResult]:
    module_id = read_module_id(root)
    parsed = parse_module(root)
    return module_id, parsed, assess_module(parsed)


def _source_resolution_exit(exc: SourceResolutionError) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=1) from exc


def _load_registry() -> Registry:
    return _registry_override if _registry_override is not None else Registry.load()


def _escape_delimiter(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")


def _render_default(value: object) -> str:
    return json.dumps(value)


def _escape_query_preview(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
    return escaped.replace("\t", "\\t")


def _render_poll_interval_line(
    config_fields: ConfigFieldsSection,
    polling: PollingSection,
) -> None:
    if "poll_interval" in config_fields.default_config:
        typer.echo(f"  poll_interval: {config_fields.default_config['poll_interval']} (config)")
    elif polling.inferred_poll_interval is not None:
        typer.echo(f"  poll_interval: {polling.inferred_poll_interval} (inferred)")


def _preview_text(text: str, limit: int = 80) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _render_string_list(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def _render_int_list(values: tuple[int, ...]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def _render_simulator_handler_preview(receive: str | None, match: str | None) -> str:
    if receive is not None:
        preview = receive if len(receive) <= 40 else receive[:37] + "..."
        return f'receive "{_escape_query_preview(preview)}"'
    if match is not None:
        preview = match if len(match) <= 40 else match[:37] + "..."
        return f"match {preview}"
    return "<empty>"


def _plural(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def _render_inspect(root: Path, module_id: str, parsed: ParsedModule, gate: GateResult) -> None:
    if gate.eligible:
        typer.echo("Eligibility: eligible")
        typer.echo(f"Module: {module_id}")
        typer.echo("Ready for extraction: yes")
        try:
            manifest, review = extract_manifest(root)
        except ManifestExtractionError as exc:
            typer.echo(f"Manifest extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        registry_report = reconcile_manufacturer(manifest, registry=_load_registry())
        review = ReviewReport(flags=review.flags + registry_report.flags)
        try:
            compatible_models, cm_review = extract_compatible_models(root, manifest)
        except CompatibleModelsExtractionError as exc:
            typer.echo(f"Compatible models extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        review = ReviewReport(flags=review.flags + cm_review.flags)
        typer.echo("Metadata:")
        typer.echo(f"  id: {manifest.id}")
        typer.echo(f"  name: {manifest.name}")
        typer.echo(f"  manufacturer: {manifest.manufacturer}")
        typer.echo(f"  category: {manifest.category}")
        typer.echo(f"  version: {manifest.version}")
        typer.echo(f"  author: {manifest.author}")
        typer.echo(f"  description: {manifest.description}")
        typer.echo(f"  source_url: {manifest.source_url or '<unresolved>'}")
        manufacturer_flags = registry_report.by_code(ReviewCode.UNKNOWN_MANUFACTURER)
        if manufacturer_flags:
            suggestions = manufacturer_flags[0].details.get("suggestions", "")
            suffix = f" (suggestions: {suggestions})" if suggestions else " (no close matches)"
            typer.echo(f"Manufacturer match: unknown{suffix}")
        else:
            typer.echo("Manufacturer match: ok")
        try:
            transport = extract_transport(parsed)
        except TransportExtractionError as exc:
            typer.echo(f"Transport extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Transport: {transport.transport}")
        if transport.delimiter is None:
            typer.echo('Delimiter: <default ("\\r")>')
        else:
            typer.echo(f'Delimiter: "{_escape_delimiter(transport.delimiter)}"')
        try:
            config_fields = extract_config_fields(parsed)
        except ConfigFieldsExtractionError as exc:
            typer.echo(f"Config fields extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Config fields: {len(config_fields.config_schema)}")
        for key, entry in list(config_fields.config_schema.items())[:3]:
            default = config_fields.default_config.get(key, _UNSET)
            suffix = "" if default is _UNSET else f" (default: {_render_default(default)})"
            typer.echo(f"  {key}: {entry.type}{suffix}")
        try:
            state_variables, sv_review = extract_state_variables(parsed)
        except StateVariablesExtractionError as exc:
            typer.echo(f"State variables extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        review = ReviewReport(flags=review.flags + sv_review.flags)
        typer.echo(f"State variables: {len(state_variables.state_variables)}")
        for var_id, var_entry in list(state_variables.state_variables.items())[:3]:
            inferred = var_entry.type or "string"
            typer.echo(f'  {var_id}: {inferred} ("{var_entry.label}")')
        try:
            commands, cmd_review = extract_commands(parsed)
        except CommandsExtractionError as exc:
            typer.echo(f"Commands extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        review = ReviewReport(flags=review.flags + cmd_review.flags)
        typer.echo(f"Commands: {len(commands.commands)}")
        for cmd_key, cmd_entry in list(commands.commands.items())[:3]:
            if cmd_entry.send is not None:
                preview = (
                    cmd_entry.send if len(cmd_entry.send) <= 40 else cmd_entry.send[:37] + "..."
                )
                typer.echo(f'  {cmd_key}: "{preview}"')
            elif cmd_entry.method is not None and cmd_entry.path is not None:
                typer.echo(f"  {cmd_key}: {cmd_entry.method} {cmd_entry.path}")
        try:
            responses, _resp_review = extract_responses(parsed)
        except ResponsesExtractionError as exc:
            typer.echo(f"Responses extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Responses: {len(responses.responses)}")
        for resp_entry in responses.responses[:3]:
            preview = (
                resp_entry.match if len(resp_entry.match) <= 40 else resp_entry.match[:37] + "..."
            )
            typer.echo(f"  {preview}")
        try:
            polling, _poll_review = extract_polling(parsed)
        except PollingExtractionError as exc:
            typer.echo(f"Polling extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Polling: {len(polling.queries)} queries")
        _render_poll_interval_line(config_fields, polling)
        for query in polling.queries[:3]:
            preview = query if len(query) <= 40 else query[:37] + "..."
            typer.echo(f'  "{_escape_query_preview(preview)}"')
        try:
            discovery, discovery_review = extract_discovery(
                manifest,
                config_fields,
                compatible_models,
            )
        except DiscoveryExtractionError as exc:
            typer.echo(f"Discovery extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        review = ReviewReport(flags=review.flags + discovery_review.flags)
        typer.echo("Discovery:")
        typer.echo(f"  port_open: {_render_int_list(discovery.port_open)}")
        typer.echo(f"  manufacturer_alias: {_render_string_list(discovery.manufacturer_alias)}")
        try:
            on_connect, on_connect_review = extract_on_connect(parsed)
        except OnConnectExtractionError as exc:
            typer.echo(f"On-connect extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        review = ReviewReport(flags=review.flags + on_connect_review.flags)
        typer.echo(f"On-connect: {len(on_connect.commands)} commands")
        for command in on_connect.commands[:3]:
            typer.echo(f'  "{_escape_query_preview(command)}"')
        entry_count = len(compatible_models.compatible_models)
        typer.echo(f"Compatible models: {entry_count} {_plural(entry_count, 'entry', 'entries')}")
        for compatible_entry in compatible_models.compatible_models[:3]:
            typer.echo(
                f"  {compatible_entry.manufacturer}: "
                f"{_render_string_list(compatible_entry.models)} "
                f"({compatible_entry.confidence})"
            )
        try:
            help_section, _help_review = extract_help(
                root,
                parsed,
                manifest_description=manifest.description,
            )
        except HelpExtractionError as exc:
            typer.echo(f"Help extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo("Help:")
        typer.echo(f"  overview: {_preview_text(help_section.overview)}")
        typer.echo(f"  setup: {_preview_text(help_section.setup)}")
        try:
            simulator, simulator_review = extract_simulator(state_variables, commands)
        except SimulatorExtractionError as exc:
            typer.echo(f"Simulator extraction failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        review = ReviewReport(flags=review.flags + simulator_review.flags)
        initial_state_count = len(simulator.initial_state or {})
        controls_count = len(simulator.controls or ())
        handlers_count = len(simulator.command_handlers or ())
        typer.echo("Simulator:")
        typer.echo(f"  initial_state: {initial_state_count} entries")
        typer.echo(f"  controls: {controls_count}")
        typer.echo(f"  command_handlers: {handlers_count}")
        for handler in (simulator.command_handlers or ())[:3]:
            typer.echo(
                "  "
                + _render_simulator_handler_preview(
                    receive=handler.receive,
                    match=handler.match,
                )
            )
        typer.echo(f"Review flags: {len(review)}")
        for flag in review.flags[:3]:
            typer.echo(f"  [{flag.code.value}] {flag.field} - {flag.message}")
        return

    typer.echo("Eligibility: declined")
    typer.echo(f"Module: {module_id}")
    typer.echo(f"Blockers: {len(gate.blockers)}")
    typer.echo("Code | Message | Evidence")
    typer.echo("--- | --- | ---")
    for blocker in gate.blockers:
        typer.echo(f"{blocker.code} | {blocker.message} | {blocker.evidence}")


@app.command()
def convert(
    source: str = typer.Argument(help="Local path, GitHub URL, or bare module ID."),
    output: str = typer.Option(..., "-o", "--output", help="Output .avcdriver path."),
    lenient: bool = typer.Option(
        False,
        "--lenient",
        "-l",
        help="Relax review handling for eligible modules; never overrides a decline.",
    ),
    keep_temp: bool = typer.Option(
        False,
        "--keep-temp",
        help="Preserve cloned remote sources after the run for debugging.",
    ),
) -> None:
    """Convert a Companion module to an OpenAVC .avcdriver file."""
    _ = lenient
    try:
        with resolve_source(source, keep_temp=keep_temp) as resolved:
            root = resolved.root
            module_id, _parsed, gate = _assess_root(root)

            if not gate.eligible:
                out_path = Path(output)
                decline_path = declined_json_path_for_output(out_path)
                report = build_declined_report(
                    source=str(root),
                    module_id=module_id,
                    blockers=list(gate.blockers),
                    declined_at=_declined_at_override,
                )
                write_declined_json(decline_path, report)
                _decline_stderr(module_id, gate.blockers)
                raise typer.Exit(code=2)
    except SourceResolutionError as exc:
        _source_resolution_exit(exc)

    typer.echo(
        "Warning: module is eligible for YAML conversion, but extractors are "
        "not implemented yet (M4+). No .avcdriver was written.",
        err=True,
    )


@app.command()
def inspect(
    source: str = typer.Argument(help="Local path, GitHub URL, or bare module ID."),
    keep_temp: bool = typer.Option(
        False,
        "--keep-temp",
        help="Preserve cloned remote sources after the run for debugging.",
    ),
) -> None:
    """Show suitability gate result and extraction summary without writing files."""
    try:
        with resolve_source(source, keep_temp=keep_temp) as resolved:
            root = resolved.root
            module_id, parsed, gate = _assess_root(root)
            _render_inspect(root, module_id, parsed, gate)
    except SourceResolutionError as exc:
        _source_resolution_exit(exc)


@app.command()
def validate(
    driver: str = typer.Argument(help="Path to an existing .avcdriver file."),
) -> None:
    """Validate a driver against the upstream openavc-drivers rules."""
    _not_implemented("validate")


@app.command()
def version() -> None:
    """Print the C2O version."""
    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
