# Companion-2-OpenAVC (C2O)

Convert **Bitfocus Companion** modules into **OpenAVC** `.avcdriver` YAML driver definitions.

## Status

Pre-implementation bootstrap (**M0**). The CLI entrypoint is wired; extractors land in milestones M1–M24.

## Quick links

- [User Guide](user-guide.md) — how to run `c2o convert` (stub until M23)
- [Contributor Guide](contributor-guide.md) — architecture and development setup
- [Field Reference](field-reference.md) — links to the upstream OpenAVC driver spec

## Canonical commands

```bash
uv sync --all-extras
uv run c2o --help
uv run pytest
make update-upstream
uv run mkdocs serve
```

## Source of truth

The authoritative OpenAVC driver schema is maintained upstream:

- [open-avc/openavc-drivers/AGENTS.md](https://github.com/open-avc/openavc-drivers/blob/main/AGENTS.md)

C2O emits **YAML only**. Modules too complex for declarative YAML receive a `.declined.json` report (exit code 2).
