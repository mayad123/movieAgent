# MovieAgent Restructure Plan

> **Status:** Pre-migration analysis — no files have been moved yet.
> **Generated:** 2026-03-11

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Full Dependency Map](#2-full-dependency-map)
3. [Identified Issues](#3-identified-issues)
4. [Proposed Target Structure](#4-proposed-target-structure)
5. [Migration Phases](#5-migration-phases)
6. [Risk Register](#6-risk-register)

---

## 1. Current State Assessment

### 1.1 Repository File Tree (as-is)

```
MovieAgent/
├── .env                          # gitignored
├── README.md
├── requirements.txt              # 21 deps, flat file, no dev/prod split
├── data/
│   ├── exports/README.md
│   ├── playground_projects.json
│   └── test_results/             # 8 interactive run dirs + README
├── docker/
│   ├── Dockerfile                # python:3.11-slim, PYTHONPATH=/app
│   └── docker-compose.yml
├── docs/                         # 27 markdown files (~4,400 lines)
├── scripts/
│   ├── db/migrate_tags.py
│   ├── observability/view_observability.py
│   ├── export/export_to_csv.py
│   └── analysis/analyze_test_results.py
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py               # FastAPI app (all routes in one file)
│   ├── cinemind/                  # 28 modules + 2 sub-packages
│   │   ├── __init__.py
│   │   ├── agent.py              # core orchestrator
│   │   ├── agent_mode.py
│   │   ├── attachment_intent_classifier.py
│   │   ├── cache.py              # semantic cache (SQLite + numpy)
│   │   ├── candidate_extraction.py
│   │   ├── config.py             # re-exports from src/config
│   │   ├── database.py           # SQLite/Postgres persistence
│   │   ├── fuzzy_intent_matcher.py
│   │   ├── intent_extraction.py
│   │   ├── kaggle_retrieval_adapter.py
│   │   ├── kaggle_search.py
│   │   ├── llm_client.py         # ABC + OpenAI + Fake
│   │   ├── media_cache.py        # TTL in-memory cache
│   │   ├── media_enrichment.py   # TMDB enrichment + attachment builder
│   │   ├── media_focus.py
│   │   ├── observability.py      # logging, metrics, cost tracking
│   │   ├── playground.py         # playground entry point
│   │   ├── playground_attachments.py
│   │   ├── request_plan.py
│   │   ├── request_type_router.py
│   │   ├── response_movie_extractor.py
│   │   ├── scenes_provider.py
│   │   ├── search_engine.py      # Tavily + aggregation
│   │   ├── source_policy.py
│   │   ├── tagging.py
│   │   ├── test_results_db.py    # test infra leaked into prod code
│   │   ├── title_extraction.py
│   │   ├── tmdb_image_config.py
│   │   ├── tmdb_resolver.py
│   │   ├── tool_plan.py
│   │   ├── verification.py
│   │   ├── eval/
│   │   │   ├── __init__.py
│   │   │   └── __main__.py       # CLI for violation reports
│   │   └── prompting/
│   │       ├── __init__.py
│   │       ├── evidence_formatter.py
│   │       ├── output_validator.py
│   │       ├── prompt_builder.py
│   │       ├── templates.py
│   │       └── versions.py
│   ├── config/
│   │   └── __init__.py           # env loading, all constants
│   ├── domain/
│   │   └── __init__.py           # empty placeholder
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── watchmode.py          # Watchmode API client
│   │   └── where_to_watch_normalizer.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── api.py                # Pydantic request/response models
│   ├── services/
│   │   ├── __init__.py
│   │   └── interfaces.py         # IAgentRunner protocol
│   └── workflows/
│       ├── __init__.py
│       ├── playground_workflow.py # thin delegate to cinemind.playground
│       └── real_agent_workflow.py # timeout + fallback wrapper
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── README.md
│   ├── README_SCENARIOS.md
│   ├── PLAYGROUND_SERVER.md
│   ├── mocks.py
│   ├── parallel_runner.py
│   ├── playground_projects_store.py
│   ├── playground_runner.py
│   ├── playground_server.py
│   ├── report_generator.py
│   ├── failure_artifact_writer.py
│   ├── violation_artifact_writer.py
│   │
│   ├── test_fuzzy_intent_matcher.py     # ← misplaced (should be unit/)
│   ├── test_kaggle_retrieval_adapter.py # ← misplaced
│   ├── test_request_planner_prompt_only.py # ← misplaced
│   ├── test_request_type_router.py      # ← misplaced
│   ├── test_runner_interactive.py
│   ├── test_scenarios_offline.py
│   │
│   ├── contract/
│   │   └── test_prompt_builder_contract.py
│   ├── fixtures/
│   │   ├── loader.py
│   │   ├── scenario_loader.py
│   │   └── scenarios/            # 74 YAML scenario files (gold/ + explore/)
│   ├── integration/
│   │   ├── test_agent_offline_e2e.py
│   │   └── test_routing_mocked.py
│   ├── smoke/
│   │   ├── test_playground_smoke.py
│   │   └── test_real_workflow_smoke.py
│   ├── test_cases/               # parametrized case definitions
│   │   ├── base.py
│   │   ├── comparisons.py
│   │   ├── fact_checking.py
│   │   ├── multi_hop.py
│   │   ├── recommendations.py
│   │   ├── simple_facts.py
│   │   └── spoilers.py
│   ├── test_reports/
│   │   ├── latest.json
│   │   ├── violations_index.json
│   │   ├── failures/             # 5 JSON artifacts
│   │   └── violations/           # 3 JSON artifacts
│   └── unit/
│       └── (24 test files)
└── web/
    ├── index.html
    ├── README.md
    ├── UI_RESPONSE_CONTRACT.md
    ├── DATA_CONTRACTS.md
    ├── WHERE_TO_WATCH_CONTRACT.md
    ├── css/app.css                # 2,471 lines, single file
    └── js/
        ├── config.js
        └── app.js                 # 2,555 lines, single IIFE
```

### 1.2 Line Counts by Area

| Area | Files | Approx. Lines | Notes |
|------|------:|-------------:|-------|
| `src/cinemind/` (flat modules) | 28 | ~6,500 | Core agent logic, all in one flat package |
| `src/cinemind/prompting/` | 5 | ~900 | Well-isolated sub-package |
| `src/cinemind/eval/` | 1 | ~120 | CLI tool embedded in library |
| `src/api/main.py` | 1 | ~600 | All routes in a single file |
| `src/config/` | 1 | ~144 | Env loading + all constants |
| `src/integrations/` | 2 | ~560 | Watchmode client + normalizer |
| `src/schemas/` | 1 | ~57 | Pydantic models |
| `src/services/` | 1 | ~19 | Single protocol interface |
| `src/workflows/` | 2 | ~80 | Thin orchestration wrappers |
| `src/domain/` | 1 | ~1 | Empty placeholder |
| `tests/` (all) | ~50 | ~4,500+ | Mixed organization |
| `docs/` | 27 | ~4,400 | No clear hierarchy |
| `web/` | 4 code files | ~5,200 | Monolithic vanilla JS + CSS |

---

## 2. Full Dependency Map

### 2.1 External Dependencies (`requirements.txt`)

| Package | Purpose | Category |
|---------|---------|----------|
| `openai>=1.3.0` | LLM API client | Runtime |
| `python-dotenv>=1.0.0` | `.env` loading | Runtime |
| `requests>=2.31.0` | HTTP (sync) | Runtime |
| `httpx>=0.25.0` | HTTP (async) | Runtime |
| `beautifulsoup4>=4.12.0` | HTML parsing | Runtime |
| `lxml>=4.9.0` | XML/HTML parser backend | Runtime |
| `python-dateutil>=2.8.0` | Date parsing | Runtime |
| `tavily-python>=0.3.0` | Tavily search API | Runtime |
| `fastapi>=0.104.0` | Web framework | Runtime |
| `uvicorn[standard]>=0.24.0` | ASGI server | Runtime |
| `pydantic>=2.0.0` | Data validation | Runtime |
| `psycopg2-binary>=2.9.0` | PostgreSQL driver | Runtime (optional) |
| `matplotlib>=3.7.0` | Plotting (scripts only) | Dev/Scripts |
| `numpy>=1.24.0` | Semantic cache similarity | Runtime |
| `kagglehub[pandas-datasets]>=0.2.0` | Kaggle dataset access | Runtime |
| `pandas>=2.0.0` | Data manipulation | Runtime |
| `pytest>=7.4.0` | Testing framework | Dev |
| `pytest-mock>=3.11.0` | Mocking plugin | Dev |
| `pytest-asyncio>=0.21.0` | Async test support | Dev |
| `freezegun>=1.2.0` | Time freezing for tests | Dev |
| `pyyaml>=6.0.0` | YAML scenario files | Dev |

**Issues:**
- No separation between runtime and dev dependencies
- No `pyproject.toml` — uses legacy `requirements.txt` only
- `matplotlib` is only used by analysis scripts, not runtime
- No dependency locking (no `requirements.lock` or `pip-compile` output)
- No `.env.example` file despite being referenced in 3 docs

### 2.2 Internal Import Graph (src/cinemind/)

```
agent.py ──────────────┬── config (via cinemind.config → src/config)
  (central hub)        ├── search_engine
                       ├── database
                       ├── observability ────── database
                       ├── tagging
                       ├── cache ──────────── numpy (optional)
                       ├── source_policy
                       ├── intent_extraction
                       ├── verification
                       ├── request_plan
                       ├── candidate_extraction
                       ├── tool_plan
                       ├── prompting/ ──────── config, request_plan
                       │   ├── prompt_builder ─ templates, evidence_formatter
                       │   ├── output_validator ─ templates
                       │   ├── evidence_formatter
                       │   ├── templates
                       │   └── versions
                       ├── llm_client
                       └── media_enrichment ── media_cache, title_extraction,
                                               tmdb_image_config, tmdb_resolver (lazy)

playground.py ─────────┬── agent
                       └── playground_attachments ─┬── response_movie_extractor
                                                   ├── attachment_intent_classifier
                                                   ├── media_focus
                                                   ├── media_enrichment
                                                   ├── title_extraction
                                                   └── scenes_provider

kaggle_search.py ────── pandas, kagglehub (standalone)
kaggle_retrieval_adapter.py ── kaggle_search

search_engine.py ──────┬── requests, httpx
                       └── (tavily-python at runtime)
```

### 2.3 Cross-Package Imports

| From | To | Import |
|------|----|--------|
| `src/config/__init__.py` | `lib.env` | `find_dotenv_path` — **phantom dependency** (`lib/env.py` does not exist in repo) |
| `src/config/__init__.py` | `cinemind.prompting.versions` | `get_prompt_version` (lazy, inside function) |
| `src/cinemind/config.py` | `config` | Re-exports all symbols (backward compat shim) |
| `src/api/main.py` | `cinemind.*`, `config`, `workflows`, `schemas`, `integrations` | Uses nearly everything |
| `src/workflows/real_agent_workflow.py` | `services.interfaces` | `IAgentRunner` protocol |
| `src/workflows/playground_workflow.py` | `cinemind.playground` | Direct import |

### 2.4 Circular/Near-Circular Dependencies

| Cycle | Mitigation |
|-------|------------|
| `config` → `cinemind.prompting.versions` → (imports nothing from config) | Lazy import in `get_system_prompt()` avoids import-time cycle |
| `cinemind.__init__` re-exports from `config` and `media_enrichment` | Works but couples the package surface to config module |

### 2.5 Phantom/Broken Dependencies

| File | Import | Issue |
|------|--------|-------|
| `src/config/__init__.py` | `from lib.env import find_dotenv_path` | `lib/env.py` does not exist anywhere in the repo. Runtime must rely on `PYTHONPATH` pointing to an external location, or this import silently fails. |
| `tests/unit/test_smoke.py` | `request_plan_factory`, `evidence_bundle_factory`, `minimal_request_plan`, `minimal_evidence_bundle`, `sample_search_result`, `frozen_time` | Fixtures referenced but never defined — tests will fail |
| `tests/contract/test_prompt_builder_contract.py` | `request_plan_factory` | Same missing fixture issue |

---

## 3. Identified Issues

### 3.1 `src/cinemind/` — Flat Mega-Package

**Problem:** 28 modules in a single flat directory with no sub-package grouping. Modules span unrelated concerns: TMDB image config sits next to agent orchestration, test infrastructure (`test_results_db.py`) lives alongside production code, and caching/media/search/prompting are all peers.

**Impact:** Hard to navigate, unclear ownership boundaries, difficult to test in isolation, high coupling surface.

### 3.2 `src/` — Incomplete Layered Architecture

The repo has the skeleton of a layered architecture (`domain/`, `services/`, `workflows/`, `schemas/`) but these are mostly empty:
- `domain/__init__.py` — one-line placeholder
- `services/interfaces.py` — single 19-line protocol
- `workflows/` — two thin delegates that just call into `cinemind`

Meanwhile, all real logic lives in the `cinemind` monolith.

### 3.3 `src/config/` — Fragile Config Loading

- Imports `lib.env` which doesn't exist in the repo
- `cinemind/config.py` is a re-export shim that adds an extra hop
- Config constants are a flat namespace mixing API keys, feature flags, model settings, and timeouts
- No validation or typed settings object

### 3.4 `src/api/main.py` — Monolithic API File

All routes (~600 lines) live in a single file: health checks, search, query, streaming, observability endpoints, where-to-watch, and lifecycle hooks. No router separation.

### 3.5 `tests/` — Mixed Organization

- **4 unit test files sit at `tests/` root** instead of `tests/unit/`
- **Test infrastructure** (`mocks.py`, `parallel_runner.py`, `playground_server.py`, `report_generator.py`, etc.) lives at `tests/` root, mixed with actual test files
- **3 README/docs** inside `tests/` — should live in `docs/`
- **`test_reports/`** contains generated artifacts that probably shouldn't be committed
- **Misleading names:** `test_wikipedia_cache.py` actually tests `media_cache`
- **Missing fixtures:** `test_smoke.py` and `test_prompt_builder_contract.py` reference fixtures that don't exist
- **`test_results_db.py` in production code:** A test-only module lives in `src/cinemind/`

### 3.6 `docs/` — Flat and Redundant

27 markdown files in a flat directory with no hierarchy. Several cover overlapping topics:
- `TESTING_GUIDE.md`, `TESTING_INFRASTRUCTURE.md`, `TESTING_SETUP_SUMMARY.md`, `SCALING_TESTING.md` — 4 docs about testing
- `SMOKE_TESTS_AND_RUN_COMMANDS.md`, `VIEW_TEST_RESULT_COMMANDS.md` — more testing docs
- `SRC_REALITY_MAP_AND_MIGRATION_PLAN.md`, `SAFE_CLEANUP_PASS_DELETION_LIST.md`, `SCRIPTS_RESTRUCTURE_DELIVERABLE.md`, `BASELINE_INVENTORY_AND_PROTECTED_LIST.md` — 4 docs about restructuring/migration
- No index or navigation structure

### 3.7 `web/` — Monolithic Frontend

- `app.js` is 2,555 lines in a single IIFE — no modules, no build system
- `app.css` is 2,471 lines — no preprocessor, no component scoping
- Vanilla JS with no framework, which is fine, but the single-file approach doesn't scale
- Contract docs (`UI_RESPONSE_CONTRACT.md`, etc.) live alongside code instead of in `docs/`

### 3.8 Project Tooling Gaps

| Missing | Impact |
|---------|--------|
| `pyproject.toml` | No standard Python packaging; can't use `pip install -e .`; no tool config |
| `.env.example` | Onboarding friction; new devs must guess required vars |
| `Makefile` / task runner | No standard commands for common tasks (test, lint, format, serve) |
| CI/CD (`.github/workflows/`) | No automated testing, linting, or deployment |
| Linter/formatter config | No `ruff.toml`, `.flake8`, `black` config, `mypy.ini` |
| Pre-commit hooks | No `.pre-commit-config.yaml` |
| Dependency lock file | Non-reproducible installs |

---

## 4. Proposed Target Structure

### 4.1 `src/` — Reorganized

```
src/
├── __init__.py
├── config/
│   ├── __init__.py               # typed Settings dataclass, env loading
│   └── env.py                    # dotenv finder (currently phantom lib.env)
│
├── domain/
│   ├── __init__.py
│   └── models.py                 # shared data classes: ExtractedMovie, Candidate,
│                                 #   MediaEnrichmentResult, StructuredIntent, etc.
│
├── schemas/
│   ├── __init__.py
│   └── api.py                    # Pydantic request/response (unchanged)
│
├── services/
│   ├── __init__.py
│   └── interfaces.py             # IAgentRunner protocol (unchanged)
│
├── integrations/
│   ├── __init__.py
│   ├── watchmode/
│   │   ├── __init__.py
│   │   ├── client.py             # WatchmodeClient
│   │   └── normalizer.py         # where_to_watch_normalizer
│   └── tmdb/
│       ├── __init__.py
│       ├── image_config.py       # tmdb_image_config.py
│       ├── resolver.py           # tmdb_resolver.py
│       └── scenes.py             # scenes_provider.py
│
├── cinemind/
│   ├── __init__.py
│   │
│   ├── agent/                    # Agent orchestration
│   │   ├── __init__.py
│   │   ├── core.py               # CineMind class (from agent.py)
│   │   ├── mode.py               # AgentMode enum + resolution (agent_mode.py)
│   │   └── playground.py         # playground entry point
│   │
│   ├── extraction/               # Text/title/entity extraction
│   │   ├── __init__.py
│   │   ├── title.py              # title_extraction.py
│   │   ├── candidate.py          # candidate_extraction.py
│   │   ├── intent.py             # intent_extraction.py
│   │   ├── response_parser.py    # response_movie_extractor.py
│   │   └── fuzzy_matcher.py      # fuzzy_intent_matcher.py
│   │
│   ├── media/                    # Media enrichment + attachments
│   │   ├── __init__.py
│   │   ├── enrichment.py         # media_enrichment.py
│   │   ├── cache.py              # media_cache.py
│   │   ├── focus.py              # media_focus.py
│   │   └── attachments.py        # playground_attachments.py + attachment_intent_classifier.py
│   │
│   ├── planning/                 # Request/tool planning + routing
│   │   ├── __init__.py
│   │   ├── request_plan.py
│   │   ├── tool_plan.py
│   │   ├── request_router.py     # request_type_router.py
│   │   └── source_policy.py
│   │
│   ├── prompting/                # (keep as-is, already well-structured)
│   │   ├── __init__.py
│   │   ├── prompt_builder.py
│   │   ├── evidence_formatter.py
│   │   ├── output_validator.py
│   │   ├── templates.py
│   │   └── versions.py
│   │
│   ├── search/                   # Search + data retrieval
│   │   ├── __init__.py
│   │   ├── engine.py             # search_engine.py
│   │   ├── kaggle.py             # kaggle_search.py
│   │   └── kaggle_adapter.py     # kaggle_retrieval_adapter.py
│   │
│   ├── llm/                      # LLM client abstraction
│   │   ├── __init__.py
│   │   └── client.py             # llm_client.py
│   │
│   ├── infrastructure/           # Cross-cutting: DB, cache, observability, tagging
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── cache.py              # semantic cache
│   │   ├── observability.py
│   │   └── tagging.py
│   │
│   └── verification/
│       ├── __init__.py
│       └── fact_verifier.py      # verification.py
│
├── api/
│   ├── __init__.py
│   ├── app.py                    # FastAPI app factory, middleware, lifecycle
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py             # GET /, /health, /health/diagnostic
│   │   ├── query.py              # POST /query, /search_movies, streaming
│   │   ├── observability.py      # GET /trace, /recent-requests, /stats
│   │   └── where_to_watch.py     # GET /where-to-watch endpoints
│   └── dependencies.py           # shared FastAPI dependencies (agent, db, etc.)
│
└── workflows/
    ├── __init__.py
    ├── playground_workflow.py     # (unchanged)
    └── real_agent_workflow.py     # (unchanged)
```

### 4.2 `tests/` — Reorganized

```
tests/
├── __init__.py
├── conftest.py                   # markers, hooks, shared session fixtures
│
├── helpers/                      # test infrastructure (was at tests/ root)
│   ├── __init__.py
│   ├── mocks.py
│   ├── fixtures.py               # common fixtures (request_plan_factory, etc.)
│   ├── report_generator.py
│   ├── failure_artifact_writer.py
│   └── violation_artifact_writer.py
│
├── fixtures/
│   ├── __init__.py
│   ├── loader.py
│   ├── scenario_loader.py
│   └── scenarios/                # gold/ + explore/ YAML files
│
├── unit/                         # all unit tests (move misplaced root tests here)
│   ├── __init__.py
│   ├── extraction/
│   │   ├── test_title_extraction.py
│   │   ├── test_response_movie_extractor.py
│   │   ├── test_fuzzy_intent_matcher.py      # ← moved from tests/ root
│   │   ├── test_entity_extraction.py
│   │   └── test_candidate_extraction.py
│   ├── media/
│   │   ├── test_media_enrichment.py
│   │   ├── test_media_enrichment_dedup.py
│   │   ├── test_media_focus.py
│   │   ├── test_media_cache.py               # renamed from test_wikipedia_cache
│   │   ├── test_playground_attachments.py
│   │   ├── test_playground_attachments_invariants.py
│   │   ├── test_attachment_intent_classifier.py
│   │   └── test_scenes_provider.py
│   ├── planning/
│   │   ├── test_request_plan.py              # ← moved from tests/ root
│   │   ├── test_request_type_router.py       # ← moved from tests/ root
│   │   ├── test_tool_planner.py
│   │   └── test_source_policy.py
│   ├── search/
│   │   ├── test_kaggle_search.py
│   │   └── test_kaggle_retrieval_adapter.py  # ← moved from tests/ root
│   ├── prompting/
│   │   ├── test_evidence_formatter.py
│   │   ├── test_evidence_formatter_structured.py
│   │   └── test_output_validator.py
│   ├── integrations/
│   │   ├── test_tmdb_image_config.py
│   │   ├── test_tmdb_resolver.py
│   │   ├── test_where_to_watch_normalizer.py
│   │   └── test_where_to_watch_api.py
│   └── workflows/
│       └── test_workflows.py
│
├── contract/                     # (keep as-is)
│   └── test_prompt_builder_contract.py
│
├── integration/                  # (keep as-is)
│   ├── test_agent_offline_e2e.py
│   └── test_routing_mocked.py
│
├── smoke/                        # (keep as-is)
│   ├── test_playground_smoke.py
│   └── test_real_workflow_smoke.py
│
├── scenarios/                    # rename from test_cases + scenario harness
│   ├── __init__.py
│   ├── test_scenarios_offline.py # ← moved from tests/ root
│   ├── base.py
│   ├── comparisons.py
│   ├── fact_checking.py
│   ├── multi_hop.py
│   ├── recommendations.py
│   ├── simple_facts.py
│   └── spoilers.py
│
└── playground/                   # playground-specific test infra
    ├── __init__.py
    ├── server.py                 # playground_server.py
    ├── runner.py                 # playground_runner.py
    └── projects_store.py         # playground_projects_store.py
```

### 4.3 `docs/` — Reorganized

```
docs/
├── README.md                     # index/navigation page
│
├── getting-started/
│   ├── QUICKSTART.md
│   ├── ENV_AND_SECRETS.md
│   └── OPERATIONALIZATION.md     # deployment, Docker, Cloud Run
│
├── architecture/
│   ├── README.md                 # overview of the system
│   ├── ATTACHMENT_PIPELINE_TRACE.md
│   ├── ATTACHMENTS_SCHEMA.md
│   ├── ATTACHMENT_INTENT_CLASSIFIER.md
│   ├── BATCH_ENRICHMENT.md
│   ├── SOURCE_POLICY.md
│   ├── SEMANTIC_CACHE.md
│   ├── SKIP_TAVILY_LOGIC.md
│   ├── TITLE_EXTRACTION_CONTRACT.md
│   ├── OBSERVABILITY.md
│   ├── VIEW_OBSERVABILITY_GUIDE.md
│   ├── KAGGLE_INTEGRATION.md
│   └── WIKIPEDIA_CACHE.md
│
├── testing/
│   ├── TESTING_GUIDE.md          # consolidated from 4 overlapping docs
│   ├── INTERACTIVE_TEST_RUNNER.md
│   ├── SCALING_TESTING.md
│   ├── RUN_COMMANDS.md           # ← moved from test_reports/
│   └── RUN_COMMANDS_SCENARIOS.md # ← moved from test_reports/
│
├── api-contracts/                # UI/API contracts (moved from web/)
│   ├── UI_RESPONSE_CONTRACT.md
│   ├── DATA_CONTRACTS.md
│   └── WHERE_TO_WATCH_CONTRACT.md
│
└── migration/                    # restructuring history (keep for audit trail)
    ├── RESTRUCTURE_PLAN.md       # this document
    ├── SRC_REALITY_MAP_AND_MIGRATION_PLAN.md
    ├── BASELINE_INVENTORY_AND_PROTECTED_LIST.md
    ├── SAFE_CLEANUP_PASS_DELETION_LIST.md
    └── SCRIPTS_RESTRUCTURE_DELIVERABLE.md
```

### 4.4 Project Root — New Files Needed

```
MovieAgent/
├── pyproject.toml                # replaces requirements.txt; tool config
├── .env.example                  # documented env vars
├── Makefile                      # standard commands: test, lint, serve, docker
├── .pre-commit-config.yaml       # ruff, mypy, etc.
└── .github/
    └── workflows/
        └── ci.yml                # lint + unit tests on PR
```

---

## 5. Migration Phases

### Phase 0: Foundations (no code moves)

| Task | Details |
|------|---------|
| Create `pyproject.toml` | Migrate from `requirements.txt`. Split `[project.dependencies]` (runtime) from `[project.optional-dependencies.dev]` (pytest, freezegun, etc.) and `[project.optional-dependencies.scripts]` (matplotlib). Add `[tool.pytest.ini_options]`, `[tool.ruff]` config. |
| Create `.env.example` | Document all env vars with placeholder values and comments. |
| Fix phantom `lib.env` | Create `src/config/env.py` with the `find_dotenv_path()` function, update import in `src/config/__init__.py`. |
| Create `Makefile` | Standard targets: `install`, `dev`, `test`, `test-unit`, `test-integration`, `lint`, `format`, `serve`, `docker-build`, `docker-up`. |
| Add missing test fixtures | Define `request_plan_factory`, `evidence_bundle_factory`, etc. in `tests/conftest.py` or a shared fixtures file so `test_smoke.py` and `test_prompt_builder_contract.py` pass. |

### Phase 1: Tests Reorganization

**Why first:** Tests are the safety net. Fix them before moving source code so you can validate every subsequent phase.

| Step | Action | Validation |
|------|--------|------------|
| 1a | Move 4 misplaced root test files into `tests/unit/` | `pytest tests/unit/ -q` passes |
| 1b | Create `tests/helpers/` and move `mocks.py`, `parallel_runner.py`, `report_generator.py`, `failure_artifact_writer.py`, `violation_artifact_writer.py` | Update imports in all test files referencing them |
| 1c | Rename `test_wikipedia_cache.py` → `test_media_cache.py` | Grep for old name, ensure no references remain |
| 1d | Create `tests/playground/` and move `playground_server.py`, `playground_runner.py`, `playground_projects_store.py` | Update imports in smoke tests |
| 1e | Move `test_runner_interactive.py` to `tests/helpers/` (it's infra, not a test) | Verify it's not collected by pytest |
| 1f | Move 3 test README/doc files to `docs/testing/` | N/A |
| 1g | Sub-organize `tests/unit/` into domain-aligned folders | `pytest tests/ -q` full pass |

### Phase 2: Docs Reorganization

| Step | Action |
|------|--------|
| 2a | Create subdirectories: `getting-started/`, `architecture/`, `testing/`, `api-contracts/`, `migration/` |
| 2b | Move docs into appropriate subdirs per Section 4.3 |
| 2c | Consolidate the 4 overlapping testing docs into one `TESTING_GUIDE.md` |
| 2d | Move `web/*.md` contract docs to `docs/api-contracts/` |
| 2e | Update `docs/README.md` as a navigation index with links to all docs |
| 2f | Move `test_reports/RUN_COMMANDS*.md` to `docs/testing/` |

### Phase 3: `src/cinemind/` Sub-packaging

This is the largest and riskiest phase. Each step should be a separate commit.

| Step | Action | Files Moved |
|------|--------|-------------|
| 3a | Create `cinemind/extraction/` | `title_extraction.py`, `candidate_extraction.py`, `intent_extraction.py`, `response_movie_extractor.py`, `fuzzy_intent_matcher.py` |
| 3b | Create `cinemind/media/` | `media_enrichment.py`, `media_cache.py`, `media_focus.py`, `playground_attachments.py`, `attachment_intent_classifier.py` |
| 3c | Create `cinemind/planning/` | `request_plan.py`, `tool_plan.py`, `request_type_router.py`, `source_policy.py` |
| 3d | Create `cinemind/search/` | `search_engine.py`, `kaggle_search.py`, `kaggle_retrieval_adapter.py` |
| 3e | Create `cinemind/agent/` | `agent.py` → `core.py`, `agent_mode.py` → `mode.py`, `playground.py` |
| 3f | Create `cinemind/llm/` | `llm_client.py` → `client.py` |
| 3g | Create `cinemind/infrastructure/` | `database.py`, `cache.py`, `observability.py`, `tagging.py` |
| 3h | Create `cinemind/verification/` | `verification.py` → `fact_verifier.py` |
| 3i | Move `test_results_db.py` | Out of `src/cinemind/` → `tests/helpers/` |
| 3j | Move `cinemind/eval/` | To `scripts/eval/` or `tools/eval/` (CLI tool, not library code) |
| 3k | Delete `cinemind/config.py` shim | Update all `from cinemind.config import X` → `from config import X` |
| 3l | Update `cinemind/__init__.py` | Re-export from new sub-package paths |

**After each step:** Run `pytest tests/ -q` to verify nothing broke. Update imports across the codebase.

### Phase 4: `src/integrations/` Grouping

| Step | Action |
|------|--------|
| 4a | Create `integrations/tmdb/` with `image_config.py`, `resolver.py`, `scenes.py` |
| 4b | Create `integrations/watchmode/` with `client.py`, `normalizer.py` |
| 4c | Update all imports in `cinemind/media/`, `api/`, tests |

### Phase 5: API Route Splitting

| Step | Action |
|------|--------|
| 5a | Create `api/app.py` (app factory, middleware, lifecycle) |
| 5b | Create `api/routes/health.py`, `query.py`, `observability.py`, `where_to_watch.py` |
| 5c | Create `api/dependencies.py` (shared deps: agent instance, DB, etc.) |
| 5d | Update `api/main.py` to import from routes (or replace entirely) |
| 5e | Update Dockerfile CMD if entrypoint path changes |

### Phase 6: Tooling & CI

| Step | Action |
|------|--------|
| 6a | Add `ruff` to dev dependencies; create `[tool.ruff]` config in `pyproject.toml` |
| 6b | Add `.pre-commit-config.yaml` with ruff + mypy |
| 6c | Create `.github/workflows/ci.yml`: lint → unit tests → integration tests |
| 6d | Add type hints to public interfaces; configure `mypy` in `pyproject.toml` |

### Phase 7: Frontend Organization (optional, lower priority)

| Step | Action |
|------|--------|
| 7a | Split `app.js` into ES modules (config, api client, UI components, state management) |
| 7b | Split `app.css` into component files |
| 7c | Add a minimal build step (esbuild or similar) or keep as native ES modules |

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import breakage during Phase 3 | High | Tests fail, app won't start | One sub-package per commit; run full test suite after each step; keep backward-compat re-exports in `__init__.py` during transition |
| Docker build breaks | Medium | Can't deploy | Test `docker build` after any change to `src/` structure or `PYTHONPATH` |
| Circular imports surface | Medium | Import errors at runtime | Map all import chains before each move (Section 2.2); use lazy imports where needed |
| Test coverage gaps hidden by missing fixtures | High (already present) | False confidence | Fix `test_smoke.py` and `test_prompt_builder_contract.py` fixtures in Phase 0 |
| `PYTHONPATH` assumptions break | Medium | Imports fail in dev vs Docker vs test | Standardize with `pyproject.toml` editable install (`pip install -e .`) so imports work everywhere |
| Web frontend breaks after doc moves | Low | 404 on contract doc links | Contract docs are not served by the app; only affects developer reference |
| Merge conflicts if work continues in parallel | Medium | Painful rebases | Do restructuring on a dedicated branch; minimize concurrent feature work |

---

## Appendix A: Module Responsibility Summary

| Current Module | Responsibility | Target Location |
|---------------|---------------|-----------------|
| `agent.py` | Core agent orchestration, tool loop | `cinemind/agent/core.py` |
| `agent_mode.py` | Mode resolution (playground vs real) | `cinemind/agent/mode.py` |
| `attachment_intent_classifier.py` | Classify what attachments to show | `cinemind/media/attachments.py` |
| `cache.py` | Semantic similarity cache | `cinemind/infrastructure/cache.py` |
| `candidate_extraction.py` | Extract movie candidates from text | `cinemind/extraction/candidate.py` |
| `config.py` (cinemind) | Re-export shim | **Delete** — import `config` directly |
| `database.py` | SQLite/Postgres persistence | `cinemind/infrastructure/database.py` |
| `fuzzy_intent_matcher.py` | Fuzzy intent matching | `cinemind/extraction/fuzzy_matcher.py` |
| `intent_extraction.py` | Structured intent parsing | `cinemind/extraction/intent.py` |
| `kaggle_retrieval_adapter.py` | Kaggle dataset adapter | `cinemind/search/kaggle_adapter.py` |
| `kaggle_search.py` | Kaggle dataset search | `cinemind/search/kaggle.py` |
| `llm_client.py` | LLM abstraction layer | `cinemind/llm/client.py` |
| `media_cache.py` | In-memory TTL cache for media | `cinemind/media/cache.py` |
| `media_enrichment.py` | TMDB enrichment + attachment builder | `cinemind/media/enrichment.py` |
| `media_focus.py` | Single vs multi-movie detection | `cinemind/media/focus.py` |
| `observability.py` | Logging, metrics, cost tracking | `cinemind/infrastructure/observability.py` |
| `playground.py` | Playground query handler | `cinemind/agent/playground.py` |
| `playground_attachments.py` | Attachment behavior for playground | `cinemind/media/attachments.py` (merge) |
| `request_plan.py` | Request plan data model + planner | `cinemind/planning/request_plan.py` |
| `request_type_router.py` | Route requests by type | `cinemind/planning/request_router.py` |
| `response_movie_extractor.py` | Parse response text for movies | `cinemind/extraction/response_parser.py` |
| `scenes_provider.py` | TMDB scenes/backdrops | `integrations/tmdb/scenes.py` |
| `search_engine.py` | Tavily search + aggregation | `cinemind/search/engine.py` |
| `source_policy.py` | Source tier ranking | `cinemind/planning/source_policy.py` |
| `tagging.py` | Request classification + tagging | `cinemind/infrastructure/tagging.py` |
| `test_results_db.py` | Test result storage | `tests/helpers/test_results_db.py` |
| `title_extraction.py` | Extract titles from queries | `cinemind/extraction/title.py` |
| `tmdb_image_config.py` | TMDB image URL builder | `integrations/tmdb/image_config.py` |
| `tmdb_resolver.py` | TMDB movie resolution | `integrations/tmdb/resolver.py` |
| `tool_plan.py` | Tool selection planner | `cinemind/planning/tool_plan.py` |
| `verification.py` | Fact verification | `cinemind/verification/fact_verifier.py` |
| `eval/__main__.py` | Violation report CLI | `scripts/eval/` or `tools/eval/` |

## Appendix B: Consolidated Testing Docs

The following 6 docs should be consolidated into 2 in the target structure:

**Merge into `docs/testing/TESTING_GUIDE.md`:**
- `TESTING_GUIDE.md` (primary)
- `TESTING_INFRASTRUCTURE.md`
- `TESTING_SETUP_SUMMARY.md`
- `SMOKE_TESTS_AND_RUN_COMMANDS.md`

**Keep separate:**
- `INTERACTIVE_TEST_RUNNER.md` (distinct tool with its own usage)
- `SCALING_TESTING.md` (advanced topic)

**Move to `docs/testing/`:**
- `VIEW_TEST_RESULT_COMMANDS.md` → merge into `TESTING_GUIDE.md`
- `test_reports/RUN_COMMANDS.md` → `docs/testing/RUN_COMMANDS.md`
- `test_reports/RUN_COMMANDS_SCENARIOS.md` → `docs/testing/RUN_COMMANDS_SCENARIOS.md`
