# C2O — Agent Guide

This file is read by AI coding agents working on **Companion-2-OpenAVC (C2O)**. Keep it short; it points at the real sources of truth.

## What this project does

C2O is a Python CLI that converts **Bitfocus Companion** modules (Node.js) into **OpenAVC** `.avcdriver` YAML drivers. It is a translator, not a runtime — it does not execute the source module and does not implement OpenAVC's runtime semantics.

**YAML only.** C2O does **not** generate OpenAVC Python (`.py`) drivers. When a module is too complex for YAML (UDP, binary framing, non-Telnet auth, etc.), C2O **declines** and writes a `.declined.json` report (exit code 2) pointing the user to manual Python driver authoring upstream.

## Sources of truth (in priority order)

1. **Upstream OpenAVC driver spec** — [`open-avc/openavc-drivers/AGENTS.md`](https://github.com/open-avc/openavc-drivers/blob/main/AGENTS.md). The prose reference for every field C2O emits. Re-read whenever it changes upstream.
2. **Upstream JSON schema** — [`open-avc/openavc-drivers/avcdriver.schema.json`](https://github.com/open-avc/openavc-drivers/blob/main/avcdriver.schema.json). The machine-readable field contract; it wins over prose when field shape, regex, or enum values disagree.
3. **Upstream validator** — [`open-avc/openavc-drivers/scripts/build_index.py`](https://github.com/open-avc/openavc-drivers/blob/main/scripts/build_index.py). The only validation that matters. A vendored snapshot lives under `c2o/vendored/openavc_drivers/` (after M0).
4. **Upstream manufacturer registry** — `open-avc/openavc-drivers/manufacturers.json`. Every emitted driver's `manufacturer` field must resolve here.
5. **Project Brief** — [`memory-bank/projectbrief.md`](memory-bank/projectbrief.md). Scope, YAML suitability gate (§5.3), architecture, milestones, Companion → OpenAVC mapping (§15).
6. **Upstream platform (informational)** — [`open-avc/openavc`](https://github.com/open-avc/openavc). The runtime that interprets emitted drivers.

The local historical scratchpad at `docs/legacy/avcdriverbreakdown.avcdriver` is **superseded** by upstream AGENTS.md. Where they disagree, **upstream wins**.

## What you should not do

- Do not emit Python (`.py`) OpenAVC drivers — decline instead (§5.3 of the project brief).
- Do not invent schema. All field names, types, enums, and required/optional flags come from upstream AGENTS.md and `avcdriver.schema.json`.
- Do not modify the source Companion module under conversion. C2O is read-only over its input.
- Do not author a parallel OpenAVC schema in this repo. The upstream `build_index.py` is the validator.

## Canonical commands

```bash
uv sync --all-extras            # install runtime + dev
uv run c2o --help               # CLI help (once M0 lands)
uv run pytest                   # run the test suite
make update-upstream            # refresh vendored upstream snapshot (M0)
uvx mkdocs serve                # docs preview
uv build                        # build sdist + wheel
```

## Tech stack snapshot

- **Python** ≥ 3.12 · **uv** · **typer** · **tree-sitter** + **tree-sitter-javascript**
- **pydantic** v2 · **PyYAML** · **httpx** (manufacturer registry)
- **Validation:** vendored `build_index.py --check` on every golden
- **Exit codes:** 0 success · 1 strict/validation failure · **2 declined (YAML not viable)**

## Where to start

Follow milestones in `memory-bank/projectbrief.md` §10. M0 (housekeeping) is prerequisite; M3 (YAML suitability gate) must land before extractors.
