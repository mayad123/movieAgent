# Baseline Inventory & "Do Not Break" Map

This document maps what must be preserved before any restructuring or deletion. **No behavior changes; no restructuring; no deletions**—inventory only.

---

## 1. Entrypoints

### 1.1 Real LLM Workflow (Production / Runtime Path)

| Entrypoint | Description | Run command (as currently implemented) |
|------------|-------------|--------------------------------------|
| **Agent CLI** | Interactive CLI for the CineMind agent (real OpenAI + Tavily). | `python -m src.cinemind.agent` |
| **REST API** | FastAPI server; real agent when `OPENAI_API_KEY` is set; falls back to playground when not. | `python -m src.api.main` **or** `uvicorn src.api.main:app --reload` (from repo root, with `src` on path). Default port: 8000 (`PORT` env). |

### 1.2 Playground Server (Dev / Demo Path)

| Entrypoint | Description | Run command (as currently implemented) |
|------------|-------------|--------------------------------------|
| **Playground HTTP server** | Offline server: serves `web/` static UI and exposes `POST /query` via offline runner (FakeLLM, no OpenAI/Tavily). | `python -m tests.playground_server` — Server: http://localhost:8000, UI: http://localhost:8000/ |
| **Playground CLI** | Same offline pipeline without HTTP; single query or interactive. | `python -m tests.playground_runner "Who directed The Matrix?"` or `python -m tests.playground_runner` (interactive) |

---

## 2. Minimum Set of Files/Folders per Path

### 2.1 Real LLM Workflow (Production / Runtime)

**Entrypoint modules:**

- `src/api/main.py` — API app and `/query`, `/search`, observability routes, fallback to `run_playground_query`.
- `src/cinemind/agent.py` — `CineMind.search_and_analyze()` and `if __name__ == "__main__"` CLI.

**Direct dependencies of `src.api.main`:**

- `src/api/__init__.py`
- `src/cinemind/agent.py` (CineMind)
- `src/cinemind/agent_mode.py` (AgentMode, get_configured_mode, resolve_effective_mode)
- `src/cinemind/config.py` (REAL_AGENT_TIMEOUT_SECONDS, env)
- `src/cinemind/database.py` (Database)
- `src/cinemind/observability.py` (Observability)
- `src/cinemind/playground.py` (run_playground_query — fallback when keys missing / timeout / error)
- `src/cinemind/tagging.py` (RequestTagger, OUTCOMES)

**Transitive dependencies (agent + playground + tagging + observability + database):**

- `src/cinemind/config.py` — SYSTEM_PROMPT, AGENT_NAME, AGENT_VERSION, OPENAI_MODEL, PROMPT_VERSION, REAL_AGENT_MAX_TOKENS, REAL_AGENT_MAX_TOOL_CALLS, REAL_AGENT_TIMEOUT_SECONDS, TMDB/config, .env loading
- `src/cinemind/search_engine.py` — SearchEngine, MovieDataAggregator
- `src/cinemind/database.py` — Database
- `src/cinemind/observability.py` — Observability, calculate_openai_cost
- `src/cinemind/tagging.py` — RequestTagger, HybridClassifier, classify_with_llm
- `src/cinemind/cache.py` — SemanticCache
- `src/cinemind/source_policy.py` — SourcePolicy
- `src/cinemind/intent_extraction.py` — IntentExtractor
- `src/cinemind/verification.py` — FactVerifier, VerifiedFact
- `src/cinemind/request_plan.py` — RequestPlanner, RequestPlan
- `src/cinemind/candidate_extraction.py` — CandidateExtractor
- `src/cinemind/tool_plan.py` — ToolPlanner, ToolPlan
- `src/cinemind/prompting/` — PromptBuilder, EvidenceBundle, get_template; prompt_builder, templates, evidence_formatter, output_validator, versions
- `src/cinemind/llm_client.py` — LLMClient, OpenAILLMClient (and FakeLLMClient for playground fallback)
- `src/cinemind/media_enrichment.py` — attach_media_to_result
- `src/cinemind/playground.py` — run_playground_query
- `src/cinemind/playground_attachments.py` — apply_playground_attachment_behavior (used by playground fallback path in API)

**Further transitive (e.g. from request_plan, media_enrichment, prompting, etc.):**

- `src/cinemind/request_type_router.py` — get_request_type_router (used by RequestPlanner)
- `src/cinemind/title_extraction.py` — get_search_phrases, extract_movie_titles
- `src/cinemind/wikipedia_entity_resolver.py` — WikipediaEntityResolver, ResolverResult, ResolvedEntity, WIKIPEDIA_USER_AGENT
- `src/cinemind/wikipedia_media_provider.py` — WikipediaMediaProvider
- `src/cinemind/wikipedia_cache.py` — get_default_wikipedia_cache, WikipediaCache, WIKIPEDIA_CACHE_OPERATIONAL_LIMITS
- `src/cinemind/scenes_provider.py` — get_scenes_provider
- `src/cinemind/tmdb_resolver.py` — (TMDB poster resolution)
- `src/cinemind/tmdb_image_config.py` — (TMDB image config)
- `src/cinemind/response_movie_extractor.py` — parse_response, ResponseParseResult
- `src/cinemind/attachment_intent_classifier.py` — (used by playground_attachments)

**Config / env:**

- `requirements.txt` — runtime deps
- `.env` (optional) — OPENAI_API_KEY, TAVILY_API_KEY, DATABASE_URL, TMDB_READ_ACCESS_TOKEN, ENABLE_TMDB_SCENES, etc.

**Summary — minimum for real LLM path:**

- `src/` (all of `src/api/` and `src/cinemind/` except `src/cinemind/eval/` which is a separate CLI).
- Root: `requirements.txt`, optional `.env`.

---

### 2.2 Playground Server (Dev / Demo Path)

**Entrypoint modules:**

- `tests/playground_server.py` — FastAPI app, `POST /query`, projects API, static mount of `web/`.
- `tests/playground_runner.py` — `run_playground()`, CLI; used by playground_server for each `/query`.

**Direct dependencies of playground server:**

- `tests/playground_runner.py` — run_playground
- `tests/playground_projects_store.py` — list_all, get_by_id, create, seed_if_needed, add_assets, remove_asset
- `web/` — directory mounted as static files (index.html, css/, js/, README.md, etc.)

**Dependencies of `playground_runner.run_playground`:**

- `src/cinemind/agent.py` — CineMind
- `src/cinemind/llm_client.py` — FakeLLMClient
- `src/cinemind/playground_attachments.py` — apply_playground_attachment_behavior
- `src/cinemind/playground.py` — PLAYGROUND_ATTACHMENT_RULE_ENABLED
- `src/cinemind/request_type_router.py` — get_request_type_router (used when request_type not provided)

**Transitive:** Same as real LLM path for the agent and playground_attachments chain (agent → config, search_engine, database, observability, tagging, cache, source_policy, intent_extraction, verification, request_plan, candidate_extraction, tool_plan, prompting, llm_client, media_enrichment; request_plan → request_type_router; playground_attachments → response_movie_extractor, attachment_intent_classifier, media_enrichment, title_extraction, wikipedia_entity_resolver, wikipedia_cache, scenes_provider; media_enrichment → wikipedia_*, title_extraction; etc.).

**Data:**

- `data/` — `playground_projects_store` uses `data/playground_projects.json` (creates `data/` if needed).

**Summary — minimum for playground path:**

- `tests/playground_server.py`, `tests/playground_runner.py`, `tests/playground_projects_store.py`
- `web/` (entire directory)
- `data/` (directory; `data/playground_projects.json` created at runtime if missing)
- All of `src/cinemind/` (and `src/api/` not required for playground server itself, but shared code lives in `src/cinemind/`)

---

## 3. Shared Dependencies Between the Two Paths

- **Core agent:** `src/cinemind/agent.py` (CineMind), `src/cinemind/config.py`, `src/cinemind/llm_client.py` (OpenAI + FakeLLM).
- **Request pipeline:** `request_plan.py`, `request_type_router.py`, `tagging.py`, `tool_plan.py`, `candidate_extraction.py`, `intent_extraction.py`, `prompting/*`, `verification.py`, `source_policy.py`, `cache.py`, `search_engine.py`.
- **Media / enrichment:** `media_enrichment.py`, `wikipedia_entity_resolver.py`, `wikipedia_media_provider.py`, `wikipedia_cache.py`, `title_extraction.py`, `scenes_provider.py`, `tmdb_resolver.py`, `tmdb_image_config.py`, `response_movie_extractor.py`, `attachment_intent_classifier.py`.
- **Playground-only (used by both API fallback and playground server):** `playground.py`, `playground_attachments.py`.

**Difference:**

- **Real path only:** `src/api/main.py`, `database.py`, `observability.py` (and optionally Tavily/OpenAI env). API uses Database/Observability for persistence and metrics; agent uses them when `enable_observability=True`.
- **Playground path only:** `tests/playground_server.py`, `tests/playground_runner.py`, `tests/playground_projects_store.py`, `web/`, and `data/` for projects.

---

## 4. Protected List (Must Not Delete)

The following must not be deleted so that both entrypaths continue to run and tests can still target the same behavior.

### 4.1 Source and API

- `src/__init__.py`
- `src/api/__init__.py`
- `src/api/main.py`
- `src/cinemind/__init__.py`
- `src/cinemind/agent.py`
- `src/cinemind/agent_mode.py`
- `src/cinemind/attachment_intent_classifier.py`
- `src/cinemind/cache.py`
- `src/cinemind/candidate_extraction.py`
- `src/cinemind/config.py`
- `src/cinemind/database.py`
- `src/cinemind/intent_extraction.py`
- `src/cinemind/llm_client.py`
- `src/cinemind/media_enrichment.py`
- `src/cinemind/observability.py`
- `src/cinemind/playground.py`
- `src/cinemind/playground_attachments.py`
- `src/cinemind/request_plan.py`
- `src/cinemind/request_type_router.py`
- `src/cinemind/response_movie_extractor.py`
- `src/cinemind/search_engine.py`
- `src/cinemind/source_policy.py`
- `src/cinemind/scenes_provider.py`
- `src/cinemind/tagging.py`
- `src/cinemind/tmdb_image_config.py`
- `src/cinemind/tmdb_resolver.py`
- `src/cinemind/title_extraction.py`
- `src/cinemind/verification.py`
- `src/cinemind/wikipedia_cache.py`
- `src/cinemind/wikipedia_entity_resolver.py`
- `src/cinemind/wikipedia_media_provider.py`
- `src/cinemind/prompting/__init__.py`
- `src/cinemind/prompting/evidence_formatter.py`
- `src/cinemind/prompting/output_validator.py`
- `src/cinemind/prompting/prompt_builder.py`
- `src/cinemind/prompting/templates.py`
- `src/cinemind/prompting/versions.py`

### 4.2 Playground (Dev/Demo) Path

- `tests/playground_server.py`
- `tests/playground_runner.py`
- `tests/playground_projects_store.py`
- `web/` (entire directory: index.html, css/, js/, README.md, DATA_CONTRACTS.md, UI_RESPONSE_CONTRACT.md)

### 4.3 Config and Environment

- `requirements.txt`
- `.env` (if present; referenced by config for API keys and DB)

### 4.4 Data and Docker (Preserve Top-Level Layout)

- `data/` — required for playground projects store (`data/playground_projects.json`); API may use default DB path (e.g. `cinemind.db` in cwd).
- `docker/` — do not modify per constraints.

### 4.5 Eval CLI (Separate Entrypoint; Optional for “production” but Part of Repo)

- `src/cinemind/eval/__init__.py`
- `src/cinemind/eval/__main__.py` — CLI: `python -m cinemind.eval list-violations`, `show-violation --scenario <name>`.

---

## 5. Optional / Auxiliary (Likely Safe to Remove Later — Do Not Delete Yet)

These are not required for the two main entrypaths above. Treat as candidates for cleanup only after the protected list is enforced and tests are green.

- **Scripts (utility, not required for API or playground server):**
  - `scripts/observability/view_observability.py`
  - `scripts/db/migrate_tags.py`
  - `scripts/export/export_to_csv.py`
  - `scripts/analysis/analyze_test_results.py`

- **Test infrastructure (needed for “tests pass,” but not for running production or playground):**
  - `tests/conftest.py`, `tests/__init__.py`, `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/fixtures/`, `tests/test_cases/`, `tests/test_runner_interactive.py`, `tests/test_request_type_router.py`, etc., `tests/report_generator.py`, `tests/parallel_runner.py`, `tests/mocks.py`, `tests/failure_artifact_writer.py`, `tests/violation_artifact_writer.py`  
  → Do not delete if the goal is “all existing tests continue to pass”; they are required for that. They are “optional” only in the sense of not being on the critical path for *running* production or playground.

- **Eval CLI:** `src/cinemind/eval/` — optional for production/playground run; keep if you want the violations CLI.

- **Docs:** `docs/` — safe to trim or reorganize later; not required for runtime.

- **Data subdirs used by scripts or test harness (not by API/playground core):**
  - `data/test_results/`, `data/prompt_comparison/`, `data/exports/` — used by scripts or test runs; not required for API or playground server to start.

- **Duplicate or one-off configs:** Any duplicate env or config files (if present) could be consolidated later; do not delete until confirmed unused.

---

## 6. Run Commands Summary

| Path | Run command |
|------|-------------|
| **Real agent (CLI)** | `python -m src.cinemind.agent` |
| **Real API** | `python -m src.api.main` or `uvicorn src.api.main:app --reload` |
| **Playground server** | `python -m tests.playground_server` |
| **Playground CLI** | `python -m tests.playground_runner "query"` or `python -m tests.playground_runner` |
| **Eval CLI** | `python -m cinemind.eval list-violations` / `python -m cinemind.eval show-violation --scenario <name>` |

All commands assume repo root as cwd and `src` on `PYTHONPATH` (or equivalent) where required.
