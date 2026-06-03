# Companion-2-OpenAVC (C2O)

Convert Bitfocus Companion modules into OpenAVC YAML driver definitions.

C2O is a translator, not a runtime. It statically reads Companion module source, extracts the pieces that can be represented in OpenAVC YAML, and reports anything that still needs human review.

## Status

C2O is in active development. Milestones M1-M22 have landed parser, suitability-gate, extraction, inspection, validation, logging, strict/lenient review, and Companion sibling artefact support.

Primary `.avcdriver` emission has not landed yet. Today, `c2o convert` runs the conversion pipeline and writes the reports and sibling files that are already supported:

- `.declined.json` for modules that cannot be represented as declarative YAML.
- `.review.json` in lenient mode when eligible modules still have review flags.
- `.companion-feedbacks.yml` and `.companion-presets.yml` for informational Companion UI artefacts.

Use `c2o inspect` for a read-only extraction summary and `c2o validate` to check existing `.avcdriver` files against the upstream OpenAVC validator.

## Quick Links

- [User Guide](user-guide.md) - install, CLI usage, exit codes, sidecars, and sibling artefacts.
- [Contributor Guide](contributor-guide.md) - architecture, development workflow, and extractor authoring notes.
- [Field Reference](field-reference.md) - upstream OpenAVC schema and validator links.

## Common Commands

```bash
uv sync --all-extras
uv run c2o --help
uv run pytest
make quality
make update-upstream
uv run mkdocs serve
```

## Source Of Truth

C2O does not maintain a parallel OpenAVC schema. The authoritative driver contract lives upstream:

- [open-avc/openavc-drivers/AGENTS.md](https://github.com/open-avc/openavc-drivers/blob/main/AGENTS.md)
- [open-avc/openavc-drivers/scripts/build_index.py](https://github.com/open-avc/openavc-drivers/blob/main/scripts/build_index.py)

C2O emits YAML only. If a Companion module requires UDP, binary framing, custom authentication, or another Python-driver-only capability, C2O declines it with exit code 2 and points the user toward manual OpenAVC Python driver authoring.
