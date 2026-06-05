# GitHub Actions Workflows

This directory contains the CI, docs, dependency-update, and release automation for Companion-2-OpenAVC (C2O).

## Workflows

- `ci.yml` runs on pushes to `main` and on pull requests. It installs dependencies with `uv`, runs Ruff, isort, Black, mypy, pytest with coverage, builds the package, and smoke-checks the vendored OpenAVC validator.
- `docs.yml` runs on pushes to `main` and on pull requests. It builds the MkDocs site with `mkdocs build --strict` and uploads the generated `site/` directory as an artifact.
- `release.yml` is manual (`workflow_dispatch`). It accepts a release tag such as `v0.1.0`, runs tests, builds wheel/sdist artifacts with `uv build`, and creates a GitHub release with `dist/*` attached.
- `dependabot.yml` checks weekly for `uv` dependency updates and GitHub Actions updates.

## Release Checklist

Releases are GitHub-only for v1. Do not publish C2O to PyPI.

1. Ensure `main` is green in CI.
2. Confirm `pyproject.toml` and `c2o/__init__.py` contain the release version.
3. Confirm `CHANGELOG.md` has a dated entry for the release.
4. Run local release verification:

   ```bash
   make ci
   make docs-build
   uv build
   ```

5. Smoke-install the built wheel in a throwaway environment and verify:

   ```bash
   c2o version
   c2o --help
   ```

6. Commit and merge the release-prep changes.
7. Trigger `Release` from the GitHub Actions UI with the tag input, for example `v0.1.0`.

The release workflow creates the GitHub tag/release through `gh release create` and attaches the built wheel and sdist from `dist/`.
