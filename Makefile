# =============================================================================
# Companion-2-OpenAVC Makefile
# =============================================================================

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -e -u -o pipefail -c

.DEFAULT_GOAL := help

.PHONY: help clean install setup sync test lint serve docs-build build deploy update-upstream

help: ## Show this help message
	@echo "Available targets:"
	@fgrep -h "##" $(MAKEFILE_LIST) | grep -v fgrep | sed -e 's/\([^:]*\):[^#]*##\(.*\)/  \1|\2/' | column -t -s '|'

sync: ## Install runtime + dev dependencies with uv
	uv sync --all-extras

install: ## Install uv (https://docs.astral.sh/uv/)
	curl -LsSf https://astral.sh/uv/install.sh | sh

setup: sync ## Alias: sync dependencies

test: ## Run pytest
	uv run pytest

lint: ## Run ruff and isort checks
	uv run ruff check .
	uv run isort --check .

serve: ## Start MkDocs development server
	uv run mkdocs serve

docs-build: ## Build MkDocs static site
	uv run mkdocs build

build: ## Build Python wheel and sdist
	uv build

deploy: docs-build ## Build docs for deployment
	@echo "Site built in 'site/' directory"

update-upstream: ## Refresh vendored openavc-drivers snapshot
	./scripts/update-upstream.sh

clean: ## Remove build artefacts and temp directories
	rm -rf site/ .cache/ dist/ .pytest_cache/ .mypy_cache/ .ruff_cache/ temp/ scripts/temp/
	find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."
