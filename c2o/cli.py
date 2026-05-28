"""C2O Typer CLI entrypoint."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer

from c2o import __version__
from c2o.emit.decline import (
    build_declined_report,
    declined_json_path_for_output,
    write_declined_json,
)
from c2o.parse.js import parse_module
from c2o.source.local import read_module_id, resolve_local
from c2o.suitability.blockers import Blocker
from c2o.suitability.gate import GateResult, assess_module

app = typer.Typer(
    name="c2o",
    help="Convert Bitfocus Companion modules into OpenAVC .avcdriver YAML drivers.",
    no_args_is_help=True,
)

# Injectable clock for tests (monkeypatch this attribute).
_declined_at_override: datetime | None = None


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


def _resolve_local_input(source: str) -> Path:
    source_path = Path(source)
    if not source_path.is_dir():
        typer.echo(
            "Only local directory sources are supported before M13 (URL/bare ID resolution).",
            err=True,
        )
        raise typer.Exit(code=1)
    return resolve_local(source)


def _assess_local_source(source: str) -> tuple[Path, str, GateResult]:
    root = _resolve_local_input(source)
    module_id = read_module_id(root)
    parsed = parse_module(root)
    return root, module_id, assess_module(parsed)


def _render_inspect(module_id: str, gate: GateResult) -> None:
    if gate.eligible:
        typer.echo("Eligibility: eligible")
        typer.echo(f"Module: {module_id}")
        typer.echo("Ready for extraction: yes")
        typer.echo("Note: extraction is not implemented until M4+.")
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
) -> None:
    """Convert a Companion module to an OpenAVC .avcdriver file."""
    _ = lenient
    root, module_id, gate = _assess_local_source(source)

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

    typer.echo(
        "Warning: module is eligible for YAML conversion, but extractors are "
        "not implemented yet (M4+). No .avcdriver was written.",
        err=True,
    )


@app.command()
def inspect(
    source: str = typer.Argument(help="Local path, GitHub URL, or bare module ID."),
) -> None:
    """Show suitability gate result and extraction summary without writing files."""
    _root, module_id, gate = _assess_local_source(source)
    _render_inspect(module_id, gate)


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
