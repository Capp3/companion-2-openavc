# Contributing to Companion-2-OpenAVC

Thanks for helping improve Companion-2-OpenAVC (C2O). C2O is a Python CLI that converts Bitfocus Companion modules into OpenAVC `.avcdriver` YAML, and declines modules that require manual OpenAVC Python drivers.

## Useful Contributions

- **Bug reports** for incorrect conversion output, unexpected declines, crashes, or validation failures.
- **Fixture coverage** for additional Companion modules, especially modules that exercise extractor edge cases.
- **Extractor improvements** for metadata, config fields, commands, responses, polling, discovery, simulator hints, feedbacks, and presets.
- **Documentation updates** for CLI usage, release process, or contributor workflows.
- **Tests** that lock in conversion behavior, decline behavior, and upstream validation compatibility.

## Getting Started

Requirements:

- Python 3.12 or newer.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- Git.

Clone and set up the project:

```bash
git clone https://github.com/Capp3/companion-2-openavc.git
cd companion-2-openavc
uv sync --all-extras
uv run c2o --help
```

## Development Workflow

Create a focused branch for each change:

```bash
git checkout -b feature/your-change
```

Before opening a pull request, run the local quality gate:

```bash
make quality
```

Useful narrower commands:

```bash
uv run pytest
uv run ruff check .
uv run mypy c2o tests
make docs-build
uv build
```

## Project Rules

- C2O emits YAML `.avcdriver` files only. Do not add OpenAVC Python driver generation.
- The upstream OpenAVC driver spec and validator are the source of truth for emitted fields and validation behavior.
- Do not modify the source Companion module during conversion; C2O is read-only over its input.
- Declined modules should produce structured `.declined.json` reports and exit code 2.
- Generated review sidecars and TODO YAML comments should remain deterministic so snapshots stay useful.

## Tests And Fixtures

- Add or update tests with every behavior change.
- Prefer focused fixtures that demonstrate the Companion pattern being extracted or declined.
- Keep golden snapshots intentional. If a snapshot changes, explain why in the PR.
- Run vendored upstream validation for emitted `.avcdriver` outputs when changing YAML emission.

## Pull Requests

Before submitting:

- Ensure `make quality` passes.
- Update docs or changelog entries when user-facing behavior changes.
- Keep commits focused and describe the reason for the change.
- Include the relevant commands you ran in the PR description.

## Releases

Releases are GitHub-only for v1. See `.github/workflows/README.md` for the release checklist and workflow details.

## License

By contributing, you agree that your contributions are licensed under this project's MIT license.
