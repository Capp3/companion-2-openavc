# =============================================================================
# Companion-2-OpenAVC Makefile
# =============================================================================

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -e -u -o pipefail -c

.DEFAULT_GOAL := help

# Quality gate (match CI coverage threshold)
COV_FAIL_UNDER ?= 85

# Python paths (exclude vendored upstream snapshot)
PY_SRC := c2o tests
MYPY_PKGS := c2o tests

.PHONY: help
.PHONY: install sync setup
.PHONY: format fix lint typecheck test test-cov quality check ci
.PHONY: build serve docs-build deploy update-upstream verify-upstream clean

help: ## Show this help message
	@echo "Companion-2-OpenAVC — common targets:"
	@fgrep -h "##" $(MAKEFILE_LIST) | grep -v fgrep | sed -e 's/\([^:]*\):[^#]*##\(.*\)/  \1|\2/' | column -t -s '|'

# -----------------------------------------------------------------------------
# Environment
# -----------------------------------------------------------------------------

install: ## Install uv (https://docs.astral.sh/uv/)
	curl -LsSf https://astral.sh/uv/install.sh | sh

sync: ## Install runtime + dev + docs dependencies
	uv sync --all-extras

setup: sync ## Alias for sync

# -----------------------------------------------------------------------------
# Formatting (apply fixes)
# -----------------------------------------------------------------------------

format: ## Auto-format: isort, black, ruff --fix
	uv run isort $(PY_SRC)
	uv run black $(PY_SRC)
	uv run ruff check --fix $(PY_SRC)

fix: format ## Alias for format

# -----------------------------------------------------------------------------
# Lint & typecheck (check only, no writes)
# -----------------------------------------------------------------------------

lint: ## Lint: ruff, isort, black (check mode)
	uv run ruff check .
	uv run isort --check $(PY_SRC)
	uv run black --check $(PY_SRC)

typecheck: ## Static typecheck with mypy
	uv run mypy $(MYPY_PKGS)

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

test: ## Run pytest
	uv run pytest

test-cov: ## Run pytest with coverage gate (COV_FAIL_UNDER=$(COV_FAIL_UNDER))
	uv run pytest --cov=c2o --cov-fail-under=$(COV_FAIL_UNDER)

# -----------------------------------------------------------------------------
# Quality gates
# -----------------------------------------------------------------------------

quality: lint typecheck test-cov ## Lint + typecheck + tests (local quality gate)

check: quality ## Alias for quality

ci: quality build verify-upstream ## Mirror CI: quality + package build + upstream validator

# -----------------------------------------------------------------------------
# Build & docs
# -----------------------------------------------------------------------------

build: ## Build Python wheel and sdist
	uv build

serve: ## Start MkDocs development server
	uv run mkdocs serve

docs-build: ## Build MkDocs static site (--strict)
	uv run mkdocs build --strict

deploy: docs-build ## Build docs for deployment
	@echo "Site built in 'site/' directory"

# -----------------------------------------------------------------------------
# Upstream vendoring
# -----------------------------------------------------------------------------

update-upstream: ## Refresh vendored openavc-drivers snapshot
	./scripts/update-upstream.sh

verify-upstream: ## Verify vendored build_index.py runs
	uv run python c2o/vendored/openavc_drivers/scripts/build_index.py --help

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------

clean: ## Remove build artefacts, caches, and temp directories
	rm -rf site/ .cache/ dist/ .pytest_cache/ .mypy_cache/ .ruff_cache/ temp/ scripts/temp/
	find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."
