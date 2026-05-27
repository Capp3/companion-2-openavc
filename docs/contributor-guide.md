# Contributor Guide

## Project brief

Architecture, milestones, and Companion → OpenAVC mapping rules live in the repository's
[project brief](https://github.com/Capp3/companion-2-openavc/blob/main/memory-bank/projectbrief.md)
(`memory-bank/projectbrief.md` — not published on this site).

## Agent guide

AI coding agents should read [`AGENTS.md`](https://github.com/Capp3/companion-2-openavc/blob/main/AGENTS.md)
at the repo root.

## Development setup

```bash
uv sync --all-extras
uv run c2o --help
uv run pytest
uv run ruff check .
uv run mypy c2o
```

## Refresh upstream validator

```bash
make update-upstream
```

This updates the vendored snapshot under `c2o/vendored/openavc_drivers/`.
