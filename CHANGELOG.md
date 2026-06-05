# Changelog

All notable changes to **Companion-2-OpenAVC (C2O)** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-04

### Added

- Typer CLI with `convert`, `inspect`, `validate`, and `version` commands.
- Source resolution for local directories, GitHub URLs, and bare Bitfocus Companion module IDs.
- YAML suitability gate with structured `.declined.json` reports and exit code 2 for modules that require manual OpenAVC Python drivers.
- Static extractors for manifest metadata, manufacturer registry reconciliation, transport/delimiter, config fields, state variables, TCP/serial commands, HTTP commands, responses, polling, help, discovery, compatible models, on-connect sends, and simulator hints.
- Primary `.avcdriver` YAML emission for eligible Companion modules, including deterministic key ordering and upstream validator integration.
- Default todo review mode: bare `c2o convert` writes best-effort YAML with inline `#TODO` comments plus `.review.json` for unresolved review flags.
- Explicit `--strict`, `--lenient`, `--todo` / `-todo`, and `--interactive` conversion modes.
- Informational Companion sibling artefacts: `.companion-feedbacks.yml` and `.companion-presets.yml`.
- `c2o validate` command backed by the vendored `open-avc/openavc-drivers` `build_index.py --check` validator.
- Structured logging with `-v`, `-vv`, and `--log-format {text,json}`.
- MkDocs documentation site with Home, User Guide, Contributor Guide, and Field Reference pages.
- GitHub Actions CI, docs build, manual GitHub release, and Dependabot workflows.

### Known Limitations

- C2O emits YAML `.avcdriver` files only. It never generates OpenAVC Python drivers.
- Modules requiring UDP, binary framing, custom authentication, or other Python-only runtime behavior are declined with `.declined.json`.
- Discovery fingerprints and TODO source references are best-effort until richer extractor-level line tracking lands.
- v0.1.0 is distributed through GitHub release artifacts only; there is no PyPI publication.
