"""C2O Typer CLI entrypoint."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated

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
from c2o.log import LogFormat, configure_logging, emit
from c2o.model.driver import (
    CommandsSection,
    CompatibleModelsSection,
    ConfigFieldsSection,
    DiscoverySection,
    HelpSection,
    ManifestSection,
    OnConnectSection,
    PollingSection,
    ResponsesSection,
    SimulatorSection,
    StateVariablesSection,
    TransportSection,
)
from c2o.model.review import ReviewCode, ReviewReport
from c2o.parse.js import ParsedModule, parse_module
from c2o.prompt import Prompter, TyperPrompter, apply_interactive_prompts
from c2o.registry import Registry, reconcile_manufacturer
from c2o.source import ResolvedSource, SourceResolutionError, read_module_id, resolve_source
from c2o.suitability.blockers import Blocker
from c2o.suitability.gate import GateResult, assess_module
from c2o.validate import UpstreamValidationResult, validate_upstream

app = typer.Typer(
    name="c2o",
    help="Convert Bitfocus Companion modules into OpenAVC .avcdriver YAML drivers.",
    no_args_is_help=True,
)

# Injectable clock for tests (monkeypatch this attribute).
_declined_at_override: datetime | None = None

# Injectable registry for tests; production uses the live upstream-with-vendored-fallback loader.
_registry_override: Registry | None = None

# Injectable prompter for tests; production uses the Typer-backed implementation.
_prompter_override: Prompter | None = None

_UNSET = object()
_LOGGER = logging.getLogger("c2o")


@app.callback()
def _root_callback(
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Increase log verbosity (-v INFO, -vv DEBUG).",
        ),
    ] = 0,
    log_format: Annotated[
        LogFormat,
        typer.Option(
            "--log-format",
            help="Log output format.",
            show_default=True,
        ),
    ] = LogFormat.text,
) -> None:
    """Configure root CLI options shared by all subcommands."""
    configure_logging(verbosity=verbose, log_format=log_format)


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


def _blocker_codes(gate: GateResult) -> list[str]:
    return [blocker.code.value for blocker in gate.blockers]


def _blocker_payloads(blockers: tuple[Blocker, ...]) -> list[dict[str, object]]:
    return [blocker.model_dump(mode="json") for blocker in blockers]


def _log_source_resolution_complete(resolved: ResolvedSource) -> None:
    details: dict[str, object] = {
        "kind": resolved.kind.value,
        "root": str(resolved.root),
        "duration_ms": resolved.duration_ms,
    }
    if resolved.clone_url is not None:
        details["clone_url"] = resolved.clone_url
    emit(_LOGGER, logging.INFO, "source_resolution_complete", **details)


def _log_source_clone_preserved(resolved: ResolvedSource) -> None:
    if resolved.tempdir is not None:
        emit(_LOGGER, logging.INFO, "source_clone_preserved", path=str(resolved.tempdir))


def _log_gate_result(gate: GateResult) -> None:
    emit(
        _LOGGER,
        logging.INFO,
        "suitability_gate_result",
        eligible=gate.eligible,
        blocker_codes=_blocker_codes(gate),
    )


def _assess_root(root: Path) -> tuple[str, ParsedModule, GateResult]:
    module_id = read_module_id(root)
    parsed = parse_module(root)
    return module_id, parsed, assess_module(parsed)


def _source_resolution_exit(exc: SourceResolutionError) -> None:
    emit(_LOGGER, logging.WARNING, "source_resolution_failed", error=str(exc))
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=1) from exc


def _log_schema_validation_result(
    driver_path: Path,
    result: UpstreamValidationResult,
) -> None:
    emit(
        _LOGGER,
        logging.INFO if result.passed else logging.WARNING,
        "schema_validation_result",
        path=str(driver_path),
        passed=result.passed,
        error_count=len(result.errors),
        pointer=result.pointers[0] if result.pointers else None,
        first_error=result.errors[0] if result.errors else None,
    )


def validate_upstream_or_exit(driver_path: Path) -> UpstreamValidationResult:
    """Run upstream validation and exit the CLI process on failure."""
    emit(_LOGGER, logging.DEBUG, "schema_validation_start", path=str(driver_path))
    try:
        result = validate_upstream(driver_path)
    except (FileNotFoundError, ValueError) as exc:
        message = str(exc)
        emit(
            _LOGGER,
            logging.WARNING,
            "schema_validation_result",
            path=str(driver_path),
            passed=False,
            error_count=1,
            pointer=None,
            first_error=message,
        )
        typer.echo(f"ERROR: {message}", err=True)
        raise typer.Exit(code=1) from exc

    if result.passed:
        _log_schema_validation_result(driver_path, result)
        if result.stdout:
            typer.echo(result.stdout.rstrip("\n"))
        return result

    if result.stderr:
        sys.stderr.write(result.stderr)
        sys.stderr.flush()
    _log_schema_validation_result(driver_path, result)
    raise typer.Exit(code=1)


def _load_registry() -> Registry:
    return _registry_override if _registry_override is not None else Registry.load()


def _load_prompter() -> Prompter:
    return _prompter_override if _prompter_override is not None else TyperPrompter()


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


def _extractor_event_name(label: str) -> str:
    return label.lower().replace("-", "_").replace(" ", "_")


def _extract_or_exit[T](
    label: str,
    callback: Callable[[], T],
    *,
    summary: Callable[[T], tuple[dict[str, object], int]] | None = None,
) -> T:
    extractor = _extractor_event_name(label)
    emit(_LOGGER, logging.DEBUG, "extractor_start", extractor=extractor)
    try:
        result = callback()
    except (
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
    ) as exc:
        emit(
            _LOGGER,
            logging.WARNING,
            "extractor_failed",
            extractor=extractor,
            error=str(exc),
        )
        typer.echo(f"{label} extraction failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    fields: dict[str, object] = {}
    review_flags = 0
    if summary is not None:
        fields, review_flags = summary(result)
    emit(
        _LOGGER,
        logging.INFO,
        "extractor_complete",
        extractor=extractor,
        fields=fields,
        review_flags=review_flags,
    )
    return result


def _merge_review(left: ReviewReport, right: ReviewReport) -> ReviewReport:
    return ReviewReport(flags=left.flags + right.flags)


def _manifest_log_summary(
    result: tuple[ManifestSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    manifest, review = result
    fields: dict[str, object] = {
        "metadata": sum(
            value is not None
            for value in (
                manifest.id,
                manifest.name,
                manifest.manufacturer,
                manifest.category,
                manifest.version,
                manifest.author,
                manifest.description,
                manifest.source_url,
            )
        )
    }
    return fields, len(review)


def _compatible_models_log_summary(
    result: tuple[CompatibleModelsSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    compatible_models, review = result
    return {"compatible_models": len(compatible_models.compatible_models)}, len(review)


def _transport_log_summary(transport: TransportSection) -> tuple[dict[str, object], int]:
    return {
        "transport": str(transport.transport),
        "delimiter": transport.delimiter is not None,
    }, 0


def _config_fields_log_summary(config_fields: ConfigFieldsSection) -> tuple[dict[str, object], int]:
    return {
        "config_schema": len(config_fields.config_schema),
        "default_config": len(config_fields.default_config),
    }, 0


def _state_variables_log_summary(
    result: tuple[StateVariablesSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    state_variables, review = result
    return {"state_variables": len(state_variables.state_variables)}, len(review)


def _commands_log_summary(
    result: tuple[CommandsSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    commands, review = result
    return {"commands": len(commands.commands)}, len(review)


def _responses_log_summary(
    result: tuple[ResponsesSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    responses, review = result
    return {"responses": len(responses.responses)}, len(review)


def _polling_log_summary(
    result: tuple[PollingSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    polling, review = result
    return {
        "queries": len(polling.queries),
        "inferred_poll_interval": polling.inferred_poll_interval is not None,
    }, len(review)


def _discovery_log_summary(
    result: tuple[DiscoverySection, ReviewReport],
) -> tuple[dict[str, object], int]:
    discovery, review = result
    return {
        "port_open": len(discovery.port_open),
        "manufacturer_alias": len(discovery.manufacturer_alias),
    }, len(review)


def _on_connect_log_summary(
    result: tuple[OnConnectSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    on_connect, review = result
    return {"commands": len(on_connect.commands)}, len(review)


def _help_log_summary(result: tuple[HelpSection, ReviewReport]) -> tuple[dict[str, object], int]:
    help_section, review = result
    return {
        "overview": bool(help_section.overview),
        "setup": bool(help_section.setup),
    }, len(review)


def _simulator_log_summary(
    result: tuple[SimulatorSection, ReviewReport],
) -> tuple[dict[str, object], int]:
    simulator, review = result
    return {
        "initial_state": len(simulator.initial_state or {}),
        "controls": len(simulator.controls or ()),
        "command_handlers": len(simulator.command_handlers or ()),
    }, len(review)


def _render_metadata(manifest: ManifestSection) -> None:
    typer.echo("Metadata:")
    typer.echo(f"  id: {manifest.id}")
    typer.echo(f"  name: {manifest.name}")
    typer.echo(f"  manufacturer: {manifest.manufacturer}")
    typer.echo(f"  category: {manifest.category}")
    typer.echo(f"  version: {manifest.version}")
    typer.echo(f"  author: {manifest.author}")
    typer.echo(f"  description: {manifest.description}")
    typer.echo(f"  source_url: {manifest.source_url or '<unresolved>'}")


def _render_manufacturer_match(registry_report: ReviewReport) -> None:
    manufacturer_flags = registry_report.by_code(ReviewCode.UNKNOWN_MANUFACTURER)
    if manufacturer_flags:
        suggestions = manufacturer_flags[0].details.get("suggestions", "")
        suffix = f" (suggestions: {suggestions})" if suggestions else " (no close matches)"
        typer.echo(f"Manufacturer match: unknown{suffix}")
    else:
        typer.echo("Manufacturer match: ok")


def _render_transport_section(transport: TransportSection) -> None:
    typer.echo(f"Transport: {transport.transport}")
    if transport.delimiter is None:
        typer.echo('Delimiter: <default ("\\r")>')
    else:
        typer.echo(f'Delimiter: "{_escape_delimiter(transport.delimiter)}"')


def _render_config_fields_section(config_fields: ConfigFieldsSection) -> None:
    typer.echo(f"Config fields: {len(config_fields.config_schema)}")
    for key, entry in list(config_fields.config_schema.items())[:3]:
        default = config_fields.default_config.get(key, _UNSET)
        suffix = "" if default is _UNSET else f" (default: {_render_default(default)})"
        typer.echo(f"  {key}: {entry.type}{suffix}")


def _render_state_variables_section(state_variables: StateVariablesSection) -> None:
    typer.echo(f"State variables: {len(state_variables.state_variables)}")
    for var_id, var_entry in list(state_variables.state_variables.items())[:3]:
        inferred = var_entry.type or "string"
        typer.echo(f'  {var_id}: {inferred} ("{var_entry.label}")')


def _render_commands_section(commands: CommandsSection) -> None:
    typer.echo(f"Commands: {len(commands.commands)}")
    for cmd_key, cmd_entry in list(commands.commands.items())[:3]:
        if cmd_entry.send is not None:
            preview = cmd_entry.send if len(cmd_entry.send) <= 40 else cmd_entry.send[:37] + "..."
            typer.echo(f'  {cmd_key}: "{preview}"')
        elif cmd_entry.method is not None and cmd_entry.path is not None:
            typer.echo(f"  {cmd_key}: {cmd_entry.method} {cmd_entry.path}")


def _render_responses_section(responses: ResponsesSection) -> None:
    typer.echo(f"Responses: {len(responses.responses)}")
    for resp_entry in responses.responses[:3]:
        preview = resp_entry.match if len(resp_entry.match) <= 40 else resp_entry.match[:37] + "..."
        typer.echo(f"  {preview}")


def _render_polling_section(
    config_fields: ConfigFieldsSection,
    polling: PollingSection,
) -> None:
    typer.echo(f"Polling: {len(polling.queries)} queries")
    _render_poll_interval_line(config_fields, polling)
    for query in polling.queries[:3]:
        preview = query if len(query) <= 40 else query[:37] + "..."
        typer.echo(f'  "{_escape_query_preview(preview)}"')


def _render_discovery_section(discovery: DiscoverySection) -> None:
    typer.echo("Discovery:")
    typer.echo(f"  port_open: {_render_int_list(discovery.port_open)}")
    typer.echo(f"  manufacturer_alias: {_render_string_list(discovery.manufacturer_alias)}")


def _render_on_connect_section(on_connect: OnConnectSection) -> None:
    typer.echo(f"On-connect: {len(on_connect.commands)} commands")
    for command in on_connect.commands[:3]:
        typer.echo(f'  "{_escape_query_preview(command)}"')


def _render_compatible_models_section(compatible_models: CompatibleModelsSection) -> None:
    entry_count = len(compatible_models.compatible_models)
    typer.echo(f"Compatible models: {entry_count} {_plural(entry_count, 'entry', 'entries')}")
    for compatible_entry in compatible_models.compatible_models[:3]:
        typer.echo(
            f"  {compatible_entry.manufacturer}: "
            f"{_render_string_list(compatible_entry.models)} "
            f"({compatible_entry.confidence})"
        )


def _render_help_section(help_section: HelpSection) -> None:
    typer.echo("Help:")
    typer.echo(f"  overview: {_preview_text(help_section.overview)}")
    typer.echo(f"  setup: {_preview_text(help_section.setup)}")


def _render_simulator_section(simulator: SimulatorSection) -> None:
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


def _render_review_flags(review: ReviewReport) -> None:
    typer.echo(f"Review flags: {len(review)}")
    for flag in review.flags[:3]:
        typer.echo(f"  [{flag.code.value}] {flag.field} - {flag.message}")


def _render_eligible(root: Path, module_id: str, parsed: ParsedModule) -> None:
    typer.echo("Eligibility: eligible")
    typer.echo(f"Module: {module_id}")
    typer.echo("Ready for extraction: yes")

    manifest, review = _extract_or_exit(
        "Manifest",
        lambda: extract_manifest(root),
        summary=_manifest_log_summary,
    )
    registry_report = reconcile_manufacturer(manifest, registry=_load_registry())
    review = _merge_review(review, registry_report)

    compatible_models, cm_review = _extract_or_exit(
        "Compatible models",
        lambda: extract_compatible_models(root, manifest),
        summary=_compatible_models_log_summary,
    )
    review = _merge_review(review, cm_review)

    _render_metadata(manifest)
    _render_manufacturer_match(registry_report)

    transport = _extract_or_exit(
        "Transport",
        lambda: extract_transport(parsed),
        summary=_transport_log_summary,
    )
    _render_transport_section(transport)

    config_fields = _extract_or_exit(
        "Config fields",
        lambda: extract_config_fields(parsed),
        summary=_config_fields_log_summary,
    )
    _render_config_fields_section(config_fields)

    state_variables, sv_review = _extract_or_exit(
        "State variables",
        lambda: extract_state_variables(parsed),
        summary=_state_variables_log_summary,
    )
    review = _merge_review(review, sv_review)
    _render_state_variables_section(state_variables)

    commands, cmd_review = _extract_or_exit(
        "Commands",
        lambda: extract_commands(parsed),
        summary=_commands_log_summary,
    )
    review = _merge_review(review, cmd_review)
    _render_commands_section(commands)

    responses, _resp_review = _extract_or_exit(
        "Responses",
        lambda: extract_responses(parsed),
        summary=_responses_log_summary,
    )
    _render_responses_section(responses)

    polling, _poll_review = _extract_or_exit(
        "Polling",
        lambda: extract_polling(parsed),
        summary=_polling_log_summary,
    )
    _render_polling_section(config_fields, polling)

    discovery, discovery_review = _extract_or_exit(
        "Discovery",
        lambda: extract_discovery(
            manifest,
            config_fields,
            compatible_models,
        ),
        summary=_discovery_log_summary,
    )
    review = _merge_review(review, discovery_review)
    _render_discovery_section(discovery)

    on_connect, on_connect_review = _extract_or_exit(
        "On-connect",
        lambda: extract_on_connect(parsed),
        summary=_on_connect_log_summary,
    )
    review = _merge_review(review, on_connect_review)
    _render_on_connect_section(on_connect)
    _render_compatible_models_section(compatible_models)

    help_section, _help_review = _extract_or_exit(
        "Help",
        lambda: extract_help(
            root,
            parsed,
            manifest_description=manifest.description,
        ),
        summary=_help_log_summary,
    )
    _render_help_section(help_section)

    simulator, simulator_review = _extract_or_exit(
        "Simulator",
        lambda: extract_simulator(state_variables, commands),
        summary=_simulator_log_summary,
    )
    review = _merge_review(review, simulator_review)
    _render_simulator_section(simulator)
    _render_review_flags(review)


def _render_declined(module_id: str, gate: GateResult) -> None:
    typer.echo("Eligibility: declined")
    typer.echo(f"Module: {module_id}")
    typer.echo(f"Blockers: {len(gate.blockers)}")
    typer.echo("Code | Message | Evidence")
    typer.echo("--- | --- | ---")
    for blocker in gate.blockers:
        typer.echo(f"{blocker.code} | {blocker.message} | {blocker.evidence}")


def _render_inspect(root: Path, module_id: str, parsed: ParsedModule, gate: GateResult) -> None:
    if gate.eligible:
        _render_eligible(root, module_id, parsed)
        return

    _render_declined(module_id, gate)


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
    interactive: bool = typer.Option(
        False,
        "--interactive/--no-interactive",
        help="Prompt for metadata fields that C2O cannot safely infer.",
    ),
) -> None:
    """Convert a Companion module to an OpenAVC .avcdriver file."""
    _ = lenient
    emit(_LOGGER, logging.DEBUG, "source_resolution_start", raw=source)
    try:
        with resolve_source(source, keep_temp=keep_temp) as resolved:
            _log_source_resolution_complete(resolved)
            if keep_temp:
                _log_source_clone_preserved(resolved)
            root = resolved.root
            module_id, _parsed, gate = _assess_root(root)
            _log_gate_result(gate)

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
                emit(
                    _LOGGER,
                    logging.WARNING,
                    "conversion_declined",
                    module_id=module_id,
                    blocker_codes=_blocker_codes(gate),
                    blockers=_blocker_payloads(gate.blockers),
                )
                emit(
                    _LOGGER,
                    logging.INFO,
                    "output_write",
                    path=str(decline_path),
                    bytes=decline_path.stat().st_size,
                )
                _decline_stderr(module_id, gate.blockers)
                raise typer.Exit(code=2)

            if interactive:
                manifest, review = _extract_or_exit(
                    "Manifest",
                    lambda: extract_manifest(root),
                    summary=_manifest_log_summary,
                )
                registry_report = reconcile_manufacturer(manifest, registry=_load_registry())
                review = ReviewReport(flags=review.flags + registry_report.flags)
                manifest, review = apply_interactive_prompts(
                    manifest,
                    review,
                    prompter=_load_prompter(),
                )
                emit(
                    _LOGGER,
                    logging.INFO,
                    "interactive_prompts_applied",
                    unresolved_review_flags=len(review),
                )
                typer.echo("Interactive metadata:")
                typer.echo(f"  category: {manifest.category}")
                typer.echo(f"  manufacturer: {manifest.manufacturer}")
                typer.echo(f"  author: {manifest.author}")
                typer.echo(f"  unresolved review flags: {len(review)}")

            # M21 strict mode will call validate_upstream_or_exit before writing YAML.
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
    emit(_LOGGER, logging.DEBUG, "source_resolution_start", raw=source)
    try:
        with resolve_source(source, keep_temp=keep_temp) as resolved:
            _log_source_resolution_complete(resolved)
            if keep_temp:
                _log_source_clone_preserved(resolved)
            root = resolved.root
            module_id, parsed, gate = _assess_root(root)
            _log_gate_result(gate)
            _render_inspect(root, module_id, parsed, gate)
    except SourceResolutionError as exc:
        _source_resolution_exit(exc)


@app.command()
def validate(
    driver: str = typer.Argument(help="Path to an existing .avcdriver file."),
) -> None:
    """Validate a driver against the upstream openavc-drivers rules."""
    validate_upstream_or_exit(Path(driver).expanduser().resolve())


@app.command()
def version() -> None:
    """Print the C2O version."""
    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
