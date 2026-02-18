# src/ Reality Map and Migration Plan

Analysis-only document. **No code changes.** Use this to refactor `src/` safely.

---

## 1. Entrypoints

### 1.1 Real LLM Workflow (Production)

| Entrypoint | Location | Run command / usage |
|------------|----------|----------------------|
| **REST API** | `src/api/main.py` | `uvicorn src.api.main:app --reload` or `python -m src.api.main`. Exposes FastAPI `app`; `run_server(host, port)` for programmatic start. |
| **Agent CLI** | `src/cinemind/agent.py` | `python -m src.cinemind.agent` (interactive). Uses `CineMind` and `search_and_analyze()`. |

### 1.2 Playground (Dev / Demo)

| Entrypoint | Location | Run command / usage |
|------------|----------|----------------------|
| **Playground HTTP server** | `tests/playground_server.py` | `python -m tests.playground_server`. Exposes FastAPI `app`; mounts `web/`; `POST /query` delegates to `tests.playground_runner.run_playground`. |
| **Playground runner** | `tests/playground_runner.py` | Called by playground_server for each query. Uses `CineMind`, `FakeLLMClient`, `apply_playground_attachment_behavior`, `PLAYGROUND_ATTACHMENT_RULE_ENABLED`, `get_request_type_router`. |
| **Playground pipeline (shared)** | `src/cinemind/playground.py` | `run_playground_query(user_query, request_type)`. Used by **API** as fallback when Real Agent fails or keys missing; not used by tests/playground_server (they use tests.playground_runner directly). |

So: **Real LLM** = `src.api.main` + `src.cinemind.agent`. **Playground** = `tests.playground_server` → `tests.playground_runner` → `src.cinemind` (agent, llm_client, playground_attachments, playground, request_type_router).

---

## 2. Top-Level Modules and Dependency Graph Summary

### 2.1 API layer

- **src.api.main**  
  Imports: `cinemind.agent` (CineMind), `cinemind.agent_mode` (AgentMode, get_configured_mode, resolve_effective_mode), `cinemind.config` (REAL_AGENT_TIMEOUT_SECONDS), `cinemind.database` (Database), `cinemind.observability` (Observability), `cinemind.playground` (run_playground_query), `cinemind.tagging` (RequestTagger, OUTCOMES).

### 2.2 Core agent (real + playground)

- **cinemind.agent**  
  Imports: config, search_engine, database, observability, tagging, cache, source_policy, intent_extraction, verification, request_plan, candidate_extraction, tool_plan, prompting (PromptBuilder, EvidenceBundle, get_template), prompting.output_validator, llm_client, media_enrichment.  
  Lazy: `kaggle_retrieval_adapter.get_kaggle_adapter` inside `search_and_analyze`.

- **cinemind.playground**  
  Imports: agent (CineMind), llm_client (FakeLLMClient), playground_attachments (apply_playground_attachment_behavior).

- **cinemind.playground_attachments**  
  Imports: response_movie_extractor, attachment_intent_classifier, media_enrichment, title_extraction, wikipedia_entity_resolver, wikipedia_cache, scenes_provider.

### 2.3 Planning and routing

- **cinemind.request_plan**  
  Uses: RequestPlan, ResponseFormat, ToolType (local); ToolPlanner; lazy: request_type_router (get_request_type_router), tagging (HybridClassifier), intent_extraction (IntentExtractor).  
  RequestPlanner is constructed in agent with classifier + intent_extractor.

- **cinemind.request_type_router**  
  No cinemind imports (standalone rules).

- **cinemind.tool_plan**  
  No cinemind imports (standalone).

- **cinemind.intent_extraction**  
  No cinemind imports at top level; lazy: fuzzy_intent_matcher (get_fuzzy_matcher).

- **cinemind.tagging**  
  HybridClassifier, RequestTagger, classify_with_llm; internal only.

### 2.4 Search and retrieval

- **cinemind.search_engine**  
  SearchEngine, MovieDataAggregator. No cinemind imports (httpx, requests, os).

- **cinemind.kaggle_retrieval_adapter**  
  Lazy-imports kaggle_search (KaggleDatasetSearcher). Used only from agent.

- **cinemind.kaggle_search**  
  KaggleDatasetSearcher; uses kagglehub, pandas. No other cinemind imports.

### 2.5 Prompting and validation

- **cinemind.prompting** (package)  
  prompt_builder → request_plan, config, templates, evidence_formatter; output_validator → templates; evidence_formatter (no cinemind cross-refs); versions, templates (config only).

### 2.6 Media and enrichment

- **cinemind.media_enrichment**  
  wikipedia_entity_resolver, wikipedia_media_provider, wikipedia_cache, title_extraction; tmdb_resolver, tmdb_image_config (poster/scenes).

- **cinemind.wikipedia_entity_resolver**  
  No other cinemind imports.

- **cinemind.wikipedia_media_provider**  
  wikipedia_entity_resolver (ResolvedEntity, WIKIPEDIA_USER_AGENT).

- **cinemind.wikipedia_cache**  
  No other cinemind imports.

- **cinemind.scenes_provider**  
  get_scenes_provider; uses tmdb_image_config, tmdb_resolver (TMDB).

- **cinemind.response_movie_extractor**  
  Used by playground_attachments, attachment_intent_classifier.

- **cinemind.attachment_intent_classifier**  
  response_movie_extractor (ResponseParseResult).

### 2.7 Persistence and observability

- **cinemind.database**  
  No cinemind imports (sqlite3, psycopg2, os).

- **cinemind.observability**  
  database (Database) only.

### 2.8 Config and LLM

- **cinemind.config**  
  No cinemind imports (os, dotenv).

- **cinemind.agent_mode**  
  config only (for resolve_effective_mode, etc.).

- **cinemind.llm_client**  
  No cinemind imports (OpenAI adapter + FakeLLMClient).

### 2.9 Other

- **cinemind.cache**  
  SemanticCache; optional numpy. Used by agent.

- **cinemind.source_policy**  
  SourcePolicy, SourceMetadata, tiers. Used by agent, aggregator, verification.

- **cinemind.verification**  
  FactVerifier, VerifiedFact; takes source_policy in constructor.

- **cinemind.candidate_extraction**  
  CandidateExtractor. Used by agent.

- **cinemind.title_extraction**  
  extract_movie_titles, get_search_phrases. Used by agent, media_enrichment, playground_attachments.

- **cinemind.eval**  
  Separate CLI (`python -m cinemind.eval list-violations`). Not on API or playground path.

- **cinemind.test_results_db**  
  Used by scripts (analysis), not by API or playground.

**Dependency layers (conceptual):**  
Layer 0: config, database, llm_client, request_type_router, tool_plan, wikipedia_entity_resolver, wikipedia_cache, title_extraction, response_movie_extractor.  
Layer 1: observability(database), agent_mode(config), source_policy, tagging, intent_extraction(fuzzy_intent_matcher), verification(source_policy), cache, search_engine, kaggle_search.  
Layer 2: request_plan(request_type_router, tool_plan, tagging, intent_extraction), kaggle_retrieval_adapter(kaggle_search), media_enrichment(wikipedia_*, title_extraction), attachment_intent_classifier(response_movie_extractor), prompting(request_plan, config, templates, evidence_formatter).  
Layer 3: agent(all above), playground_attachments(media_enrichment, title_extraction, wikipedia_*, response_movie_extractor, attachment_intent_classifier, scenes_provider).  
Layer 4: playground(agent, llm_client, playground_attachments).  
API: main(agent, agent_mode, config, database, observability, playground, tagging).

---

## 3. Public Contracts (Do Not Break)

### 3.1 API routes (src.api.main)

- **GET /** → HealthResponse  
- **GET /health** → HealthResponse  
- **GET /health/diagnostic** → DiagnosticResponse  
- **POST /search** (MovieQuery) → MovieResponse  
- **POST /query** (QueryRequest) → dict (same shape as MovieResponse for UI)  
- **GET /search** (query, use_live_data) → MovieResponse  
- **POST /search/stream** (MovieQuery) → StreamingResponse  
- **GET /observability/requests/{request_id}**  
- **GET /observability/requests** (limit)  
- **GET /observability/stats** (days, request_type, outcome)  
- **GET /observability/tags** (days)  
- **PUT /observability/requests/{request_id}/outcome** (outcome)

### 3.2 API request/response schemas (Pydantic)

- **MovieQuery**: query, use_live_data, stream, request_type, outcome, requested_agent_mode (alias requestedAgentMode).  
- **MovieResponse**: agent, version, query, response, sources, timestamp, live_data_used, request_id, token_usage, cost_usd, request_type, outcome, agent_mode, actualAgentMode, requestedAgentMode, modeFallback, (optional) fallback_reason, attachments, attachment_debug, etc.  
- **QueryRequest**: user_query, request_type, requested_agent_mode (alias requestedAgentMode).  
- **HealthResponse**, **DiagnosticResponse**: as defined in main.

### 3.3 Playground server (tests) – UI contract

- **GET /health** → health status  
- **POST /query** body: `user_query`, optional `request_type`, optional `requestedAgentMode`. Response: same shape as API query response (agent_mode, response, sources, attachments, etc.).  
- **GET/POST/DELETE /api/projects** and assets: project CRUD; contracts in playground_server.

### 3.4 CineMind public surface (cinemind/__init__.py)

- **CineMind**, **SYSTEM_PROMPT**, **AGENT_NAME**, **AGENT_VERSION**, **OPENAI_MODEL**  
- **WikipediaEntityResolver**, **ResolverResult**, **ResolvedEntity**, **WikipediaMediaProvider**  
- **MediaEnrichmentResult**, **enrich**, **enrich_batch**, **attach_media_to_result**  
- **extract_movie_titles**, **get_search_phrases**, **TitleExtractionResult**  
- **WikipediaCache**, **get_default_wikipedia_cache**, **WIKIPEDIA_CACHE_OPERATIONAL_LIMITS**

### 3.5 Agent method contract

- **CineMind.search_and_analyze**(user_query, use_live_data=True, request_id=None, request_type=None, outcome=None, playground_mode=False) → Dict.  
  Returned dict must remain compatible with MovieResponse and with playground_server/API expectations (response, sources, request_id, request_type, outcome, agent_mode, attachments, attachment_debug, etc.).

### 3.6 Playground pipeline contract

- **run_playground_query**(user_query, request_type=None) → Dict (same shape as search_and_analyze result).  
- **apply_playground_attachment_behavior**(user_query, result) → None (mutates result in place).  
- **PLAYGROUND_ATTACHMENT_RULE_ENABLED** (bool) used by runner and playground.py.

---

## 4. “Do Not Break” List

### 4.1 Files and modules

- **src/api/main.py** – All routes, handlers, and Pydantic models above.  
- **src/cinemind/agent.py** – CineMind, search_and_analyze signature and return shape.  
- **src/cinemind/playground.py** – run_playground_query, PLAYGROUND_ATTACHMENT_RULE_ENABLED.  
- **src/cinemind/playground_attachments.py** – apply_playground_attachment_behavior(user_query, result).  
- **src/cinemind/llm_client.py** – LLMClient, OpenAILLMClient, FakeLLMClient (used by agent and playground).  
- **src/cinemind/config.py** – REAL_AGENT_TIMEOUT_SECONDS, OPENAI_MODEL, AGENT_NAME, AGENT_VERSION, SYSTEM_PROMPT, PROMPT_VERSION, REAL_AGENT_*, TMDB-related, dotenv loading.  
- **src/cinemind/agent_mode.py** – AgentMode, get_configured_mode, resolve_effective_mode.  
- **src/cinemind/database.py** – Database (used by API, observability).  
- **src/cinemind/observability.py** – Observability (used by API).  
- **src/cinemind/request_type_router.py** – get_request_type_router(), RequestTypeRouter.route() (playground + request_plan).  
- **src/cinemind/__init__.py** – All current exports (see 3.4).

### 4.2 Contracts (behavior/schema)

- **API**: All route paths, HTTP methods, and request/response schemas (MovieQuery, MovieResponse, QueryRequest, HealthResponse, DiagnosticResponse).  
- **Playground server**: POST /query request body (user_query, request_type, requestedAgentMode) and response shape.  
- **Agent**: search_and_analyze signature and return dict shape (including keys used by API and playground).  
- **run_playground_query** signature and return shape.  
- **apply_playground_attachment_behavior** signature and in-place mutation contract.

### 4.3 Tests and scripts (depend on src)

- **tests/playground_server.py**, **tests/playground_runner.py**, **tests/playground_projects_store.py** – depend on cinemind.agent, llm_client, playground_attachments, playground, request_type_router.  
- **web/** – consumed by playground_server; no change to src.  
- **scripts/** – observability, db, export, analysis scripts import cinemind.database, cinemind.observability, cinemind.test_results_db; paths already updated.

---

## 5. Proposed Target src/ Architecture

Goal: keep entrypoints and public contracts unchanged; group by responsibility and improve boundaries.

### 5.1 Top-level layout (preserved)

- **docker/**, **docs/**, **src/**, **web/**, **tests/** unchanged at repo top level.

### 5.2 Proposed src/ layout

```
src/
├── api/                    # HTTP layer (unchanged)
│   ├── __init__.py
│   └── main.py
└── cinemind/               # Core package (internal structure can be re-grouped)
    ├── __init__.py         # Public API surface (unchanged)
    ├── config.py
    ├── agent_mode.py
    ├── agent.py            # Orchestrator; thin over core/
    │
    ├── core/               # Request pipeline (planning, routing, execution)
    │   ├── __init__.py
    │   ├── request_plan.py
    │   ├── request_type_router.py
    │   ├── tool_plan.py
    │   ├── intent_extraction.py
    │   ├── fuzzy_intent_matcher.py
    │   ├── tagging.py
    │   ├── candidate_extraction.py
    │   ├── verification.py
    │   ├── source_policy.py
    │   └── cache.py
    │
    ├── search/             # Search and retrieval
    │   ├── __init__.py
    │   ├── search_engine.py
    │   ├── kaggle_retrieval_adapter.py
    │   └── kaggle_search.py
    │
    ├── prompting/          # (existing package, keep)
    │   ├── __init__.py
    │   ├── prompt_builder.py
    │   ├── templates.py
    │   ├── evidence_formatter.py
    │   ├── output_validator.py
    │   └── versions.py
    │
    ├── media/              # Enrichment, Wikipedia, TMDB, attachments
    │   ├── __init__.py
    │   ├── media_enrichment.py
    │   ├── wikipedia_entity_resolver.py
    │   ├── wikipedia_media_provider.py
    │   ├── wikipedia_cache.py
    │   ├── title_extraction.py
    │   ├── response_movie_extractor.py
    │   ├── attachment_intent_classifier.py
    │   ├── scenes_provider.py
    │   ├── tmdb_resolver.py
    │   └── tmdb_image_config.py
    │
    ├── llm/                # LLM abstraction (optional; can stay flat)
    │   ├── __init__.py
    │   └── llm_client.py
    │
    ├── persistence/        # DB and observability (optional grouping)
    │   ├── __init__.py
    │   ├── database.py
    │   ├── observability.py
    │   └── test_results_db.py
    │
    ├── playground.py       # Playground pipeline (unchanged location or move to run/ if desired)
    ├── playground_attachments.py
    │
    └── eval/               # CLI (unchanged)
        ├── __init__.py
        └── __main__.py
```

### 5.3 Responsibilities

- **api** – HTTP, CORS, route handlers, Pydantic models; delegates to cinemind.  
- **cinemind.agent** – Single orchestrator: config, core (planning + routing), search, prompting, llm, media, persistence; no new behavior.  
- **core** – Request planning, type routing, tool plan, intent/tagging, verification, source policy, cache.  
- **search** – Tavily/web search, Kaggle adapter, Kaggle dataset search.  
- **prompting** – Prompt building, templates, evidence formatting, output validation, versions.  
- **media** – Wikipedia/TMDB resolution, cache, title extraction, response parsing, attachment intent, scenes.  
- **llm** – LLM client interface and OpenAI/Fake implementations.  
- **persistence** – SQLite/Postgres DB, observability, test_results DB.  
- **playground** – run_playground_query and playground_attachments (playground-only behavior).  
- **eval** – Violations CLI.

---

## 6. Migration Plan (Small Refactor Steps)

Execute in order; after each step run tests and both entrypoints.

1. **Create packages, no moves**  
   Add `core/`, `search/`, `media/`, `llm/`, `persistence/` under `cinemind/` with `__init__.py`. Do not move files yet. Confirm tests and servers still run.

2. **Move search**  
   Move `search_engine.py`, `kaggle_retrieval_adapter.py`, `kaggle_search.py` into `cinemind/search/`. Update all imports (agent, any other references). Run tests and both flows.

3. **Move media**  
   Move `media_enrichment.py`, `wikipedia_entity_resolver.py`, `wikipedia_media_provider.py`, `wikipedia_cache.py`, `title_extraction.py`, `response_movie_extractor.py`, `attachment_intent_classifier.py`, `scenes_provider.py`, `tmdb_resolver.py`, `tmdb_image_config.py` into `cinemind/media/`. Update imports (agent, playground_attachments, prompting if any). Run tests and both flows.

4. **Move core**  
   Move `request_plan.py`, `request_type_router.py`, `tool_plan.py`, `intent_extraction.py`, `fuzzy_intent_matcher.py`, `tagging.py`, `candidate_extraction.py`, `verification.py`, `source_policy.py`, `cache.py` into `cinemind/core/`. Update imports in agent, request_plan (within core), prompting. Run tests and both flows.

5. **Move persistence**  
   Move `database.py`, `observability.py`, `test_results_db.py` into `cinemind/persistence/`. Update imports in api/main, agent, observability, scripts (if they import from cinemind). Run tests and both flows.

6. **Move llm (optional)**  
   Move `llm_client.py` into `cinemind/llm/`. Update agent, playground. Run tests and both flows.

7. **Re-export from cinemind/__init__.py**  
   Ensure all names currently in `cinemind/__init__.py` are still importable from `cinemind` (e.g. `from cinemind.media import ...` or keep re-exports in top-level `__init__.py`). No change to public API surface.

8. **Document and lock contracts**  
   Update BASELINE_INVENTORY and this doc with final paths. Optionally add a short CONTRACTS.md that lists routes, schemas, and function signatures that must not change.

---

## 7. Summary

- **Real LLM entrypoints:** `src.api.main` (app), `src.cinemind.agent` (CineMind CLI).  
- **Playground entrypoints:** `tests.playground_server` (app), `tests.playground_runner` (run_playground); both use `src.cinemind` (agent, llm_client, playground_attachments, playground, request_type_router).  
- **Dependency graph:** Layered from config/database/llm/routers → planning & search & media → agent → playground and API.  
- **Do-not-break:** All API routes and schemas, playground /query contract, CineMind and run_playground_query and apply_playground_attachment_behavior contracts, and the files/modules listed in §4.  
- **Target architecture:** Same top-level dirs; under `src/cinemind/` add core/, search/, media/, persistence/, and optionally llm/, with clear responsibilities.  
- **Migration:** Add empty packages → move search → media → core → persistence → llm → fix __init__ re-exports → document. No code behavior changes; refactor only.
