.DEFAULT_GOAL := help
SHELL := /bin/bash

# Prefer .venv when it exists (create with: make venv)
PYTHON := $(shell if [ -x .venv/bin/python ]; then printf '%s' .venv/bin/python; elif command -v python3 >/dev/null 2>&1; then printf '%s' python3; else printf '%s' python; fi)

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

.PHONY: venv
venv: ## Create .venv and install requirements.txt
	@if [ ! -d .venv ]; then $(PYTHON) -m venv .venv; fi
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements.txt
	@echo "Activate: source .venv/bin/activate  (Windows: .venv\\Scripts\\activate)"

.PHONY: install
install: ## Install runtime dependencies (uses .venv/bin/python if .venv exists)
	$(PYTHON) -m pip install -e .

.PHONY: dev
dev: ## Install with dev + scripts extras (tests, linting, analysis)
	$(PYTHON) -m pip install -e ".[dev,scripts]"

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/

.PHONY: format
format: ## Auto-format with ruff
	$(PYTHON) -m ruff format src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/

.PHONY: format-check
format-check: ## Check formatting without changing files
	$(PYTHON) -m ruff format --check src/ tests/

.PHONY: typecheck
typecheck: ## Run mypy type checker
	$(PYTHON) -m mypy src/cinemind src/integrations --config-file pyproject.toml

.PHONY: check
check: lint format-check typecheck ## Run all quality checks (lint + format + types)

.PHONY: pre-commit
pre-commit: ## Run pre-commit hooks on all files
	$(PYTHON) -m pre_commit run --all-files

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run full test suite
	$(PYTHON) -m pytest tests/ -q

.PHONY: test-unit
test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/unit/ -q

.PHONY: test-integration
test-integration: ## Run integration tests only
	$(PYTHON) -m pytest tests/integration/ -q

.PHONY: test-smoke
test-smoke: ## Run smoke tests only
	$(PYTHON) -m pytest tests/smoke/ -q

.PHONY: test-contract
test-contract: ## Run contract tests only
	$(PYTHON) -m pytest tests/contract/ -q

.PHONY: test-scenarios
test-scenarios: ## Run scenario tests (gold + explore)
	$(PYTHON) -m pytest tests/test_scenarios_offline.py -q

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ --cov=src --cov-report=term-missing -q

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

.PHONY: serve
serve: ## Start the API server with auto-reload
	$(PYTHON) -m uvicorn src.api.main:app --reload --port $${PORT:-8000}

.PHONY: demo
demo: ## Start in Playground mode — no LLM keys needed (FakeLLMClient + offline Kaggle data)
	@echo ""
	@echo "  CineMind — Playground mode"
	@echo "  Responses: FakeLLMClient + offline Kaggle data (no LLM API key needed)"
	@echo "  Posters:   styled placeholders by default"
	@echo "             → add TMDB_READ_ACCESS_TOKEN to .env for real posters (free: themoviedb.org)"
	@echo "  Open http://localhost:8000"
	@echo ""
	$(PYTHON) -m uvicorn src.api.main:app --reload --port $${PORT:-8000}

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

.PHONY: docker-build
docker-build: ## Build the Docker image
	docker build -f docker/Dockerfile -t cinemind-api .

.PHONY: docker-demo
docker-demo: ## Run zero-config demo in Docker — no API keys required
	@echo ""
	@echo "  CineMind — Docker demo (Playground mode)"
	@echo "  No API keys needed. Open http://localhost:8000"
	@echo "  Stop with: make docker-demo-down"
	@echo ""
	docker compose -f docker/docker-compose.demo.yml up --build

.PHONY: docker-demo-down
docker-demo-down: ## Stop the Docker demo
	docker compose -f docker/docker-compose.demo.yml down

.PHONY: docker-up
docker-up: ## Start services via docker-compose (reads .env for API keys)
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
