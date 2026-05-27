"""C2O Typer CLI entrypoint."""

from __future__ import annotations

import typer

from c2o import __version__

app = typer.Typer(
    name="c2o",
    help="Convert Bitfocus Companion modules into OpenAVC .avcdriver YAML drivers.",
    no_args_is_help=True,
)


def _not_implemented(name: str) -> None:
    typer.echo(f"{name}: not implemented yet (see milestones M1+ in memory-bank/projectbrief.md)")
    raise typer.Exit(code=1)


@app.command()
def convert(
    source: str = typer.Argument(help="Local path, GitHub URL, or bare module ID."),
    output: str = typer.Option(..., "-o", "--output", help="Output .avcdriver path."),
) -> None:
    """Convert a Companion module to an OpenAVC .avcdriver file."""
    _not_implemented("convert")


@app.command()
def inspect(
    source: str = typer.Argument(help="Local path, GitHub URL, or bare module ID."),
) -> None:
    """Show suitability gate result and extraction summary without writing files."""
    _not_implemented("inspect")


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
