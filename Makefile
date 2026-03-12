.DEFAULT_GOAL := help
SHELL := /bin/bash

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

.PHONY: install
install: ## Install runtime dependencies
	pip install -e .

.PHONY: dev
dev: ## Install with dev + scripts extras (tests, linting, analysis)
	pip install -e ".[dev,scripts]"

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff linter
	ruff check src/ tests/

.PHONY: format
format: ## Auto-format with ruff
	ruff format src/ tests/
	ruff check --fix src/ tests/

.PHONY: format-check
format-check: ## Check formatting without changing files
	ruff format --check src/ tests/

.PHONY: typecheck
typecheck: ## Run mypy type checker
	mypy src/cinemind src/integrations --config-file pyproject.toml

.PHONY: check
check: lint format-check typecheck ## Run all quality checks (lint + format + types)

.PHONY: pre-commit
pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run full test suite
	pytest tests/ -q

.PHONY: test-unit
test-unit: ## Run unit tests only
	pytest tests/unit/ -q

.PHONY: test-integration
test-integration: ## Run integration tests only
	pytest tests/integration/ -q

.PHONY: test-smoke
test-smoke: ## Run smoke tests only
	pytest tests/smoke/ -q

.PHONY: test-contract
test-contract: ## Run contract tests only
	pytest tests/contract/ -q

.PHONY: test-scenarios
test-scenarios: ## Run scenario tests (gold + explore)
	pytest tests/test_scenarios_offline.py -q

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	pytest tests/ --cov=src --cov-report=term-missing -q

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

.PHONY: serve
serve: ## Start the API server with auto-reload
	python -m uvicorn src.api.main:app --reload --port $${PORT:-8000}

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

.PHONY: docker-build
docker-build: ## Build the Docker image
	docker build -f docker/Dockerfile -t cinemind-api .

.PHONY: docker-up
docker-up: ## Start services via docker-compose
	docker compose -f docker/docker-compose.yml up -d

.PHONY: docker-down
docker-down: ## Stop docker-compose services
	docker compose -f docker/docker-compose.yml down

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts, caches, and .pyc files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .eggs/

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'
