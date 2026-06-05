# User Guide

This guide describes the current C2O CLI surface. `convert` runs the extraction pipeline, writes an OpenAVC `.avcdriver` for eligible modules, and emits machine-readable sidecar reports when a module is declined or needs review.

## Install

Requirements:

- Python 3.12 or newer.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync --all-extras
uv run c2o --help
```

## Source Inputs

Commands that accept a Companion module source support three forms:

- Local path: `./companion-module-bmd-webpresenter`
- GitHub URL: `https://github.com/bitfocus/companion-module-bmd-webpresenter`
- Bare module ID: `bmd-webpresenter`

Remote sources are cloned fresh with `--depth 1` into a temporary directory. Temporary clones are removed after the run unless `--keep-temp` is passed.

## Inspect A Module

`inspect` is the safest first command. It does not write files.

```bash
uv run c2o inspect ./companion-module-bmd-webpresenter
uv run c2o inspect bmd-webpresenter
uv run c2o inspect bmd-webpresenter --keep-temp
```

The output starts with the YAML suitability gate result. Eligible modules then show extraction summaries for metadata, manufacturer reconciliation, transport, config fields, state variables, commands, responses, polling, help, discovery, compatible models, on-connect sends, simulator hints, and review-flag counts.

Declined modules show blocker codes and recommendations instead.

## Convert A Module

`convert` performs the conversion pipeline and writes the generated OpenAVC `.avcdriver` for eligible modules.

```bash
uv run c2o convert ./companion-module-bmd-webpresenter -o out/bmd-webpresenter.avcdriver
uv run c2o convert bmd-webpresenter --output-root out/drivers
```

Options:

- `-o, --output PATH` - explicit output `.avcdriver` path. The path stem is used for sidecar and sibling filenames. Mutually exclusive with `--output-root`.
- `--output-root DIR` - derive `<category>/<id>.avcdriver` under `DIR`. **Defaults to `./out`** if neither flag is given.
- `--strict` - opt into strict review handling. Eligible modules with unresolved review flags exit 1 and no `.avcdriver` is written.
- `--lenient`, `-l` - write `.review.json` for unresolved review flags and exit 0 for eligible modules.
- `--todo`, `-todo` - default review policy. Same policy as `--lenient`, plus `#TODO` comments in the `.avcdriver` before flagged YAML fields.
- `--interactive/--no-interactive` - prompt for metadata fields C2O cannot safely infer.
- `--keep-temp` - preserve cloned remote sources for debugging.

`--strict`, `--lenient`, and `--todo` are mutually exclusive. Passing more than one exits before source resolution.

### Files Written By Convert

For declined modules:

- `<stem>.declined.json` - machine-readable blocker report.
- Exit code 2.
- No sibling files.

For eligible modules with Companion feedbacks or presets:

- `<stem>.avcdriver` - generated OpenAVC YAML driver.
- `<stem>.companion-feedbacks.yml` - informational feedback definitions from `setFeedbackDefinitions(...)`.
- `<stem>.companion-presets.yml` - informational preset definitions from `setPresetDefinitions(...)`.

These sibling YAML files are not part of the OpenAVC catalog and are ignored by the upstream validator.

For eligible modules with review flags in lenient mode:

- `<stem>.avcdriver` - best-effort generated driver.
- `<stem>.review.json` - machine-readable review flags.
- Exit code 0.

For eligible modules with review flags in default todo mode:

- `<stem>.avcdriver` - best-effort generated driver with comment-only `#TODO` review blocks.
- `<stem>.review.json` - machine-readable review flags.
- Exit code 0.

Todo comments do not change YAML data and are ignored by validation. Source references are best-effort: manifest-derived flags point to `companion/manifest.json:[Unknown]`; other flags use `[Unknown]:[Unknown]` until extractor-level line tracking lands.

For eligible modules with review flags in strict mode:

- Exit code 1.
- Review flags are listed on stderr.
- No `.avcdriver` is written.
- Sibling YAMLs are still written when available.

## Validate A Driver

`validate` checks an existing `.avcdriver` file against the vendored upstream OpenAVC rules.

```bash
uv run c2o validate ./drivers/generic/example.avcdriver
```

Internally, C2O stages the single driver into an isolated OpenAVC-style catalog and runs the vendored `build_index.py --check` validator. Validation errors preserve upstream stderr lines.

## Version

```bash
uv run c2o version
```

## Logging

Root logging options come before the subcommand:

```bash
uv run c2o -v inspect bmd-webpresenter
uv run c2o -vv --log-format json inspect bmd-webpresenter
```

- `-v` enables INFO logs.
- `-vv` enables DEBUG logs.
- `--log-format text` is the default.
- `--log-format json` emits one JSON object per line with `ts`, `level`, `event`, `module`, and `details`.

## Exit Codes

| Code | Meaning |
| --- | --- |
| 0 | Success, including default todo and lenient eligible conversions with `.avcdriver` and review sidecars. |
| 1 | Strict-mode review failure, validation failure, or general input/runtime failure. |
| 2 | YAML suitability decline. Declines are not overridden by `--lenient` or `--todo`. |

## Current Limits

C2O does not generate OpenAVC Python drivers. Modules requiring UDP, binary framing, custom authentication, or other Python-driver-only behaviour are declined with a `.declined.json` report.
