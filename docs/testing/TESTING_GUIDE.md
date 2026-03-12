# CineMind Testing Guide

Consolidated guide for running, writing, and analyzing tests.

> **Consolidates:** the former `TESTING_GUIDE.md`, `TESTING_INFRASTRUCTURE.md`,
> `TESTING_SETUP_SUMMARY.md`, `SMOKE_TESTS_AND_RUN_COMMANDS.md`, and
> `VIEW_TEST_RESULT_COMMANDS.md`.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Test Layout](#2-test-layout)
3. [Running Tests](#3-running-tests)
4. [Smoke Tests](#4-smoke-tests)
5. [Scenario Tests](#5-scenario-tests)
6. [Writing New Tests](#6-writing-new-tests)
7. [Acceptance Criteria](#7-acceptance-criteria)
8. [Prompt Version Testing](#8-prompt-version-testing)
9. [Test Results Database](#9-test-results-database)
10. [Viewing Results and Observability](#10-viewing-results-and-observability)
11. [Parallel Execution](#11-parallel-execution)
12. [Regression Workflow](#12-regression-workflow)

---

## 1. Quick Start

All commands assume you are at the **repository root**.

```bash
# Install dev dependencies (includes pytest, freezegun, ruff, etc.)
make dev

# Run the full unit test suite
make test-unit

# Run smoke tests (fast, no API keys required)
make test-smoke

# Run everything
make test
```

## 2. Test Layout

```
tests/
├── conftest.py                 # markers, hooks, shared fixtures
├── helpers/                    # test infrastructure (not collected by pytest)
│   ├── mocks.py
│   ├── report_generator.py
│   ├── failure_artifact_writer.py
│   ├── violation_artifact_writer.py
│   ├── parallel_runner.py
│   └── interactive_runner.py
├── fixtures/
│   ├── loader.py
│   ├── scenario_loader.py
│   └── scenarios/              # YAML fixtures (gold/ + explore/)
├── unit/                       # domain-aligned unit tests
│   ├── extraction/
│   ├── media/
│   ├── planning/
│   ├── search/
│   ├── prompting/
│   ├── integrations/
│   ├── workflows/
│   └── test_smoke.py           # harness sanity check
├── contract/                   # prompt builder contracts
├── integration/                # offline E2E, mocked routing
├── smoke/                      # boot + minimal request checks
├── playground/                 # playground server, runner, project store
├── test_cases/                 # parametrized case definitions
│   ├── base.py
│   ├── simple_facts.py
│   ├── multi_hop.py
│   ├── recommendations.py
│   ├── comparisons.py
│   ├── fact_checking.py
│   └── spoilers.py
├── test_scenarios_offline.py   # scenario matrix harness
└── test_reports/               # generated JSON artifacts
```

## 3. Running Tests

### Makefile targets

| Command | What it runs |
|---------|-------------|
| `make test` | Full suite (`pytest tests/ -q`) |
| `make test-unit` | Unit tests only |
| `make test-integration` | Integration tests only |
| `make test-smoke` | Smoke tests only |
| `make test-contract` | Contract tests only |
| `make test-scenarios` | Scenario matrix tests |
| `make test-cov` | Full suite with coverage report |

### Direct pytest

```bash
# Specific file
PYTHONPATH=src pytest tests/unit/media/test_media_enrichment.py -v

# Specific test
PYTHONPATH=src pytest tests/unit/extraction/test_title_extraction.py::test_simple_title -v

# By marker
PYTHONPATH=src pytest tests/ -m gold -v
```

## 4. Smoke Tests

Minimal checks to validate the app boots and handles a basic request.
Run these **before and after** any refactor.

### Playground smoke (no env vars required)

```bash
PYTHONPATH=src pytest tests/smoke/test_playground_smoke.py -v
```

- Uses FastAPI `TestClient` — no real server process.
- Asserts: app imports, `GET /health` returns 200, `POST /query` returns expected shape.

### Real LLM smoke (requires `OPENAI_API_KEY`)

```bash
OPENAI_API_KEY=sk-... PYTHONPATH=src pytest tests/smoke/test_real_workflow_smoke.py -v
```

- Runs `CineMind.search_and_analyze` with a real OpenAI call (timeout 90 s).
- Automatically skipped if `OPENAI_API_KEY` is not set.

### Both at once

```bash
PYTHONPATH=src pytest tests/smoke/ -v
```

## 5. Scenario Tests

YAML-driven matrix tests in `tests/fixtures/scenarios/` (gold + explore).

```bash
# All scenarios
make test-scenarios

# Gold only
PYTHONPATH=src pytest tests/test_scenarios_offline.py -m gold -v

# Explore only
PYTHONPATH=src pytest tests/test_scenarios_offline.py -m explore -v
```

Each scenario defines a user query, expected request plan fields, and validator checks.
Failures write JSON artifacts to `tests/test_reports/failures/`.
Violations (even on passing tests) write to `tests/test_reports/violations/`.

## 6. Writing New Tests

### Unit test

Place the file in the matching `tests/unit/<domain>/` folder.
Name it `test_<module>.py`.

```python
from cinemind.extraction.title import extract_movie_titles  # future path

def test_extract_single_title():
    result = extract_movie_titles("Tell me about Inception")
    assert "Inception" in [t.title for t in result]
```

### Scenario (YAML)

Add a file under `tests/fixtures/scenarios/gold/` or `explore/`:

```yaml
name: my_new_scenario
query: "Who directed Prisoners?"
expected:
  request_type: info
  intent: director_info
  entities_typed:
    movies: ["Prisoners"]
  validator_checks:
    prompt_contains: ["director"]
```

### Parametrized test case (legacy)

Add to the appropriate file in `tests/test_cases/`:

```python
TestCase(
    name="my_test",
    prompt="Your test query",
    expected_type="info",
    acceptance_criteria=[
        contains_all_substrings("required", "terms"),
        min_length(100),
    ],
)
```

## 7. Acceptance Criteria

Built-in functions from `tests/test_cases/base.py`:

| Function | What it checks |
|----------|---------------|
| `contains_all_substrings(*s)` | Response contains every string |
| `contains_any_substring(*s)` | Response contains at least one |
| `contains_spoiler_warning()` | Response includes a spoiler warning |
| `min_length(n)` | Response is at least `n` characters |
| `contains_at_least_n_items(n, kw)` | At least `n` numbered/bulleted items |
| `mentions_director(name)` | Director name appears |
| `mentions_movie(title)` | Movie title appears |

## 8. Prompt Version Testing

### Compare versions

```bash
# Interactive mode
python tests/helpers/interactive_runner.py

# CLI — compare all versions, all tests
python tests/helpers/interactive_runner.py --tests all --versions all

# Specific versions and tests
python tests/helpers/interactive_runner.py --tests simple_fact_director --versions v1,v4
```

### Switch version at runtime

```bash
export PROMPT_VERSION=v4
python -m uvicorn src.api.main:app --reload
```

Or set `PROMPT_VERSION` in `.env`.

## 9. Test Results Database

Test runs are stored in `test_results.db` (SQLite).

### Schema

| Table | Content |
|-------|---------|
| `test_runs` | Summary per run (timestamp, versions, pass rates, costs) |
| `test_results` | Individual test outcomes (linked to run) |
| `criteria_results` | Per-criterion pass/fail (linked to result) |
| `test_search_results` | Search metadata (linked to result) |

### Analysis commands

```bash
# Pass rates by prompt version
python scripts/analysis/analyze_test_results.py --pass-rates

# History of a specific test
python scripts/analysis/analyze_test_results.py --test simple_fact_director

# Detect flaky tests
python scripts/analysis/analyze_test_results.py --flaky

# Compare prompt versions
python scripts/analysis/analyze_test_results.py --compare-versions v1 v4
```

### Export to CSV

```bash
python scripts/export/export_to_csv.py --table all
```

## 10. Viewing Results and Observability

### Recent requests

```bash
python scripts/observability/view_observability.py
python scripts/observability/view_observability.py --limit 20
```

### Request details (by ID)

```bash
python scripts/observability/view_observability.py --request-id <id>
```

Shows: query, classification metadata, response, sources, tokens, cost, search operations.

### Statistics

```bash
python scripts/observability/view_observability.py --stats
python scripts/observability/view_observability.py --stats --days 30 --type info
```

### Tag distribution

```bash
python scripts/observability/view_observability.py --tags
```

## 11. Parallel Execution

```bash
# Parallel with default concurrency (3)
python tests/helpers/parallel_runner.py

# Custom concurrency
python tests/helpers/parallel_runner.py --max-concurrent 5
```

Uses `asyncio.gather` with a semaphore to respect API rate limits.

## 12. Regression Workflow

1. **Baseline** — run tests and save output before changes:
   ```bash
   make test 2>&1 | tee baseline.log
   ```
2. **Make changes** — modify prompts, logic, or config.
3. **Re-run** — same command:
   ```bash
   make test 2>&1 | tee after.log
   ```
4. **Diff** — compare pass counts, look for new failures.
5. **Smoke gate** — always run `make test-smoke` before and after a refactor.
