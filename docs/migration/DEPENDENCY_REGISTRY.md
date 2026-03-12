# MovieAgent Dependency Registry

> **Companion to:** [RESTRUCTURE_PLAN.md](./RESTRUCTURE_PLAN.md)
> **Generated:** 2026-03-11
> **Purpose:** Single-source reference for every dependency (external package, internal import, env var) before any files are moved.

---

## Table of Contents

1. [External Packages](#1-external-packages)
2. [Environment Variables](#2-environment-variables)
3. [Per-File Internal Dependencies](#3-per-file-internal-dependencies)
4. [Reverse Dependency Index](#4-reverse-dependency-index)
5. [Broken & Phantom Dependencies](#5-broken--phantom-dependencies)

---

## 1. External Packages

### 1.1 Runtime Dependencies

| Package | Version Constraint | Used By | Purpose |
|---------|--------------------|---------|---------|
| `openai` | `>=1.3.0` | `cinemind/agent.py`, `cinemind/llm_client.py` | LLM API (chat completions) |
| `python-dotenv` | `>=1.0.0` | `config/__init__.py` | Load `.env` file |
| `requests` | `>=2.31.0` | `cinemind/search_engine.py` | Synchronous HTTP |
| `httpx` | `>=0.25.0` | `cinemind/search_engine.py`, `integrations/watchmode.py` | Async HTTP |
| `beautifulsoup4` | `>=4.12.0` | `cinemind/search_engine.py` | HTML parsing from search results |
| `lxml` | `>=4.9.0` | (bs4 backend) | XML/HTML parser |
| `python-dateutil` | `>=2.8.0` | `cinemind/source_policy.py`, `cinemind/search_engine.py` | Date parsing |
| `tavily-python` | `>=0.3.0` | `cinemind/search_engine.py` | Tavily search API client |
| `fastapi` | `>=0.104.0` | `api/main.py` | Web framework |
| `uvicorn` | `>=0.24.0` (with `[standard]`) | `api/main.py` | ASGI server |
| `pydantic` | `>=2.0.0` | `schemas/api.py` | Request/response validation |
| `psycopg2-binary` | `>=2.9.0` | `cinemind/database.py` | PostgreSQL driver (optional — falls back to SQLite) |
| `numpy` | `>=1.24.0` | `cinemind/cache.py` | Cosine similarity for semantic cache |
| `kagglehub` | `>=0.2.0` (with `[pandas-datasets]`) | `cinemind/kaggle_search.py` | Kaggle dataset download |
| `pandas` | `>=2.0.0` | `cinemind/kaggle_search.py` | DataFrame operations on Kaggle data |

### 1.2 Dev / Test Dependencies

| Package | Version Constraint | Used By | Purpose |
|---------|--------------------|---------|---------|
| `pytest` | `>=7.4.0` | `tests/` (all) | Test runner |
| `pytest-mock` | `>=3.11.0` | Various unit/integration tests | `mocker` fixture |
| `pytest-asyncio` | `>=0.21.0` | Async tests (`test_agent_offline_e2e.py`, etc.) | Async test support |
| `freezegun` | `>=1.2.0` | `tests/unit/test_source_policy.py`, others | Freeze `datetime.now()` |
| `pyyaml` | `>=6.0.0` | `tests/fixtures/loader.py`, `tests/fixtures/scenario_loader.py` | Load YAML scenario files |

### 1.3 Scripts-Only Dependencies

| Package | Version Constraint | Used By | Purpose |
|---------|--------------------|---------|---------|
| `matplotlib` | `>=3.7.0` | `scripts/analysis/analyze_test_results.py` | Plotting test result charts |

---

## 2. Environment Variables

| Variable | Required | Default | Read By | Purpose |
|----------|----------|---------|---------|---------|
| `OPENAI_API_KEY` | Yes (real agent mode) | `""` | `config/__init__.py` | OpenAI API authentication |
| `TAVILY_API_KEY` | No | `""` | `config/__init__.py` | Tavily search API authentication |
| `WATCHMODE_API_KEY` | No | `""` | `config/__init__.py` | Watchmode Where-to-Watch API |
| `TMDB_READ_ACCESS_TOKEN` | No | `""` | `config/__init__.py` | TMDB API bearer token |
| `ENABLE_TMDB_SCENES` | No | `"false"` | `config/__init__.py` | Toggle TMDB scenes/backdrops |
| `TMDB_POSTER_MODE` | No | `"fallback_only"` | `config/__init__.py` | Poster fetch strategy |
| `OPENAI_MODEL` | No | `"gpt-3.5-turbo"` | `config/__init__.py` | Model for LLM calls |
| `PROMPT_VERSION` | No | `"v1"` | `config/__init__.py` | Prompt template version |
| `KAGGLE_CORRELATION_THRESHOLD` | No | `"0.7"` | `config/__init__.py` | Kaggle relevance threshold |
| `KAGGLE_DATASET_PATH` | No | `""` | `config/__init__.py` | Local Kaggle dataset path |
| `ENABLE_KAGGLE_SEARCH` | No | `"true"` | `config/__init__.py` | Toggle Kaggle search |
| `DATABASE_URL` | No | `"cinemind.db"` | `cinemind/database.py` | DB connection string (SQLite path or Postgres URL) |
| `CINEMIND_REAL_AGENT_TIMEOUT` | No | `"90"` | `config/__init__.py` | Real agent timeout (seconds) |
| `CINEMIND_REAL_AGENT_MAX_TOKENS` | No | `"2000"` | `config/__init__.py` | Max tokens per LLM call |
| `CINEMIND_REAL_AGENT_MAX_TOOL_CALLS` | No | `"10"` | `config/__init__.py` | Max tool calls per request |
| `PORT` | No | `8000` | `api/main.py` | API server port |

---

## 3. Per-File Internal Dependencies

Every source file, its internal imports, and the key symbols it exports.

### 3.1 `src/config/__init__.py`

| Imports From | Symbols |
|-------------|---------|
| `dotenv` | `load_dotenv` |
| `lib.env` | `find_dotenv_path` (**phantom — file missing**) |
| `cinemind.prompting.versions` (lazy) | `get_prompt_version` |

**Exports:** `OPENAI_API_KEY`, `TAVILY_API_KEY`, `get_watchmode_api_key`, `is_watchmode_configured`, `is_tmdb_enabled`, `get_tmdb_access_token`, `TMDB_POSTER_MODE`, `ENABLE_TMDB_SCENES`, `TMDB_READ_ACCESS_TOKEN`, `AGENT_NAME`, `AGENT_VERSION`, `OPENAI_MODEL`, `SEARCH_PROVIDERS`, `KAGGLE_CORRELATION_THRESHOLD`, `KAGGLE_DATASET_PATH`, `ENABLE_KAGGLE_SEARCH`, `MOVIE_DATA_SOURCES`, `PROMPT_VERSION`, `REAL_AGENT_TIMEOUT_SECONDS`, `REAL_AGENT_MAX_TOKENS`, `REAL_AGENT_MAX_TOOL_CALLS`, `get_system_prompt`, `SYSTEM_PROMPT`

---

### 3.2 `src/cinemind/` — Core Package

#### `agent.py`

| Imports From | Symbols |
|-------------|---------|
| `asyncio`, `os`, `json`, `logging`, `uuid`, `time`, `re`, `datetime` | stdlib |
| `openai` | `AsyncOpenAI` |
| `config` | `SYSTEM_PROMPT`, `AGENT_NAME`, `AGENT_VERSION`, `OPENAI_MODEL`, etc. |
| `.search_engine` | `SearchEngine`, `MovieDataAggregator` |
| `.database` | `Database` |
| `.observability` | `Observability`, `RequestTracker` |
| `.tagging` | `RequestTagger` |
| `.cache` | `SemanticCache` |
| `.source_policy` | `SourcePolicy` |
| `.intent_extraction` | `IntentExtractor` |
| `.verification` | `FactVerifier` |
| `.request_plan` | `RequestPlanner`, `RequestPlan` |
| `.candidate_extraction` | `CandidateExtractor` |
| `.tool_plan` | `ToolPlanner` |
| `.prompting` | `PromptBuilder`, `EvidenceBundle` |
| `.llm_client` | `OpenAILLMClient` |
| `.media_enrichment` | `attach_media_to_result` |

**Exports:** `CineMind` class

---

#### `agent_mode.py`

| Imports From | Symbols |
|-------------|---------|
| `os`, `logging` | stdlib |
| `enum` | `Enum` |

**Exports:** `AgentMode`, `get_configured_mode`, `resolve_effective_mode`

---

#### `attachment_intent_classifier.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `dataclasses` | stdlib |
| `.response_movie_extractor` | `ResponseParseResult`, `ParseStructure` |

**Exports:** `AttachmentIntentResult`, `classify_attachment_intent`

---

#### `cache.py`

| Imports From | Symbols |
|-------------|---------|
| `hashlib`, `json`, `re`, `logging`, `sqlite3`, `datetime`, `typing`, `dataclasses` | stdlib |
| `numpy` (optional) | cosine similarity computation |

**Exports:** `SemanticCache`, `CacheEntry`, `TTL_BY_TYPE`, `SEMANTIC_SIMILARITY_THRESHOLD`

---

#### `candidate_extraction.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `logging`, `typing`, `dataclasses` | stdlib |

**Exports:** `Candidate`, `CandidateExtractor`, `normalize_title`

---

#### `config.py` (cinemind shim)

| Imports From | Symbols |
|-------------|---------|
| `config` (top-level) | Re-exports everything |

**Exports:** Same as `src/config/__init__.py` (backward compat shim — candidate for deletion)

---

#### `database.py`

| Imports From | Symbols |
|-------------|---------|
| `os`, `sqlite3`, `json`, `datetime`, `typing`, `contextlib`, `logging` | stdlib |
| `psycopg2` (optional) | PostgreSQL driver |

**Exports:** `Database`

---

#### `fuzzy_intent_matcher.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `typing`, `dataclasses` | stdlib |

**Exports:** `FuzzyMatchResult`, `FuzzyIntentMatcher`, `get_fuzzy_matcher`

---

#### `intent_extraction.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `json`, `logging`, `typing`, `dataclasses` | stdlib |

**Exports:** `StructuredIntent`, `IntentExtractor`

---

#### `kaggle_retrieval_adapter.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `asyncio`, `typing`, `dataclasses` | stdlib |

**Exports:** `KaggleEvidenceItem`, `KaggleRetrievalResult`, `KaggleRetrievalAdapter`, `get_kaggle_adapter`

---

#### `kaggle_search.py`

| Imports From | Symbols |
|-------------|---------|
| `os`, `re`, `logging`, `typing`, `datetime`, `urllib.parse` | stdlib |
| `pandas` | DataFrame operations |

**Exports:** `KaggleDatasetSearcher`, `normalize_title`, `tokenize`

---

#### `llm_client.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `abc`, `typing`, `dataclasses` | stdlib |

**Exports:** `LLMResponse`, `LLMClient` (ABC), `FakeLLMClient`, `OpenAILLMClient`

---

#### `media_cache.py`

| Imports From | Symbols |
|-------------|---------|
| `os`, `threading`, `time`, `typing` | stdlib |

**Exports:** `TTLCache`, `MediaCache`, `get_default_media_cache`, `set_default_media_cache`

---

#### `media_enrichment.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `concurrent.futures`, `dataclasses`, `typing` | stdlib |
| `.media_cache` | `get_default_media_cache` |
| `.title_extraction` | `extract_movie_titles` |
| `config` (lazy) | `get_tmdb_access_token`, `is_tmdb_enabled` |
| `.tmdb_image_config` (lazy) | `build_image_url`, `get_config` |
| `.tmdb_resolver` (lazy) | `resolve_movie` |

**Exports:** `MediaEnrichmentResult`, `enrich`, `enrich_batch`, `build_attachments_from_media`, `attach_media_to_result`

---

#### `media_focus.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `typing` | stdlib |

**Exports:** `get_media_focus`, `MEDIA_FOCUS_SINGLE`, `MEDIA_FOCUS_MULTI`

---

#### `observability.py`

| Imports From | Symbols |
|-------------|---------|
| `time`, `uuid`, `logging`, `json`, `datetime`, `typing`, `contextlib`, `functools` | stdlib |
| `.database` | `Database` |

**Exports:** `Observability`, `RequestTracker`, `OperationTimer`, `SafeRequestFormatter`, `RequestContextFilter`, `calculate_openai_cost`

---

#### `playground.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `typing` | stdlib |
| `.agent` | `CineMind` |
| `.llm_client` | `FakeLLMClient` |
| `.playground_attachments` | `apply_playground_attachment_behavior` |

**Exports:** `run_playground_query`

---

#### `playground_attachments.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `re`, `typing` | stdlib |
| `.response_movie_extractor` | `parse_response`, `extract_titles_for_enrichment` |
| `.attachment_intent_classifier` | `classify_attachment_intent` |
| `.media_focus` | `get_media_focus` |
| `.media_enrichment` | `enrich`, `enrich_batch`, `build_attachments_from_media` |
| `.title_extraction` | `extract_movie_titles` |
| `.scenes_provider` | `get_scenes_provider` |

**Exports:** `apply_playground_attachment_behavior`, `ATTACHMENT_DEBUG_KEY`

---

#### `request_plan.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `typing`, `dataclasses`, `enum` | stdlib |

**Exports:** `ResponseFormat`, `ToolType`, `RequestPlan`, `RequestPlanner`

---

#### `request_type_router.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `logging`, `typing`, `dataclasses` | stdlib |

**Exports:** `RequestTypeResult`, `RequestTypeRouter`, `get_request_type_router`

---

#### `response_movie_extractor.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `dataclasses`, `typing` | stdlib |

**Exports:** `ExtractedMovie`, `ParseStructure`, `ParseSignals`, `ResponseParseResult`, `parse_response`, `extract_titles_for_enrichment`, `normalize_title`

---

#### `scenes_provider.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `dataclasses`, `typing` | stdlib |

**Exports:** `SceneItem`, `ScenesProvider` (Protocol), `ScenesProviderEmpty`, `ScenesProviderTMDB`, `get_scenes_provider`

---

#### `search_engine.py`

| Imports From | Symbols |
|-------------|---------|
| `os`, `re`, `typing`, `datetime`, `dataclasses`, `enum`, `logging` | stdlib |
| `requests` | Sync HTTP |
| `httpx` | Async HTTP |

**Exports:** `SearchEngine`, `MovieDataAggregator`, `TavilyOverrideReason`, `SearchDecision`

---

#### `source_policy.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `logging`, `typing`, `dataclasses`, `enum`, `urllib.parse`, `datetime` | stdlib |

**Exports:** `SourceTier`, `SourceMetadata`, `SourceConstraints`, `SourcePolicy`

---

#### `tagging.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `json`, `logging`, `typing`, `dataclasses` | stdlib |

**Exports:** `ClassificationResult`, `HybridClassifier`, `RequestTagger`, `REQUEST_TYPES`, `OUTCOMES`

---

#### `test_results_db.py`

| Imports From | Symbols |
|-------------|---------|
| `os`, `sqlite3`, `json`, `datetime`, `typing`, `contextlib`, `logging` | stdlib |

**Exports:** `TestResultsDB`

**Note:** Test infrastructure that leaked into production code. Should move to `tests/helpers/`.

---

#### `title_extraction.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `dataclasses` | stdlib |

**Exports:** `TitleExtractionResult`, `extract_movie_titles`, `get_search_phrases`

---

#### `tmdb_image_config.py`

| Imports From | Symbols |
|-------------|---------|
| `json`, `logging`, `threading`, `time`, `urllib.request`, `dataclasses`, `typing` | stdlib |

**Exports:** `TMDBImageConfig`, `fetch_config`, `get_config`, `build_image_url`, `clear_config_cache`

---

#### `tmdb_resolver.py`

| Imports From | Symbols |
|-------------|---------|
| `json`, `logging`, `math`, `re`, `urllib.parse`, `urllib.request`, `dataclasses`, `typing` | stdlib |

**Exports:** `TMDBCandidate`, `TMDBResolveResult`, `resolve_movie`

---

#### `tool_plan.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `typing`, `dataclasses`, `enum` | stdlib |

**Exports:** `ToolAction`, `ToolPlan`, `ToolPlanner`

---

#### `verification.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `logging`, `typing`, `urllib.parse` | stdlib |

**Exports:** `VerifiedFact`, `FactVerifier`

---

### 3.3 `src/cinemind/prompting/`

#### `prompt_builder.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `typing`, `dataclasses`, `datetime` | stdlib |
| `..request_plan` | `RequestPlan` |
| `config` | `AGENT_NAME`, etc. |
| `.templates` | `get_template` |
| `.evidence_formatter` | `EvidenceFormatter` |

**Exports:** `PromptArtifacts`, `EvidenceBundle`, `PromptBuilder`

---

#### `evidence_formatter.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `typing`, `urllib.parse`, `dataclasses` | stdlib |

**Exports:** `FormattedEvidenceItem`, `EvidenceFormatResult`, `EvidenceFormatter`

---

#### `output_validator.py`

| Imports From | Symbols |
|-------------|---------|
| `re`, `logging`, `typing`, `dataclasses` | stdlib |
| `.templates` | `ResponseTemplate` |

**Exports:** `ValidationResult`, `OutputValidator`

---

#### `templates.py`

| Imports From | Symbols |
|-------------|---------|
| `typing`, `dataclasses` | stdlib |

**Exports:** `ResponseTemplate`, `get_template`, `list_all_templates`, `RESPONSE_TEMPLATES`

---

#### `versions.py`

| Imports From | Symbols |
|-------------|---------|
| `typing`, `datetime` | stdlib |

**Exports:** `get_prompt_version`, `list_versions`, `compare_versions`, `PROMPT_VERSIONS`

---

### 3.4 `src/api/main.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `os`, `typing` | stdlib |
| `fastapi` | `FastAPI`, `HTTPException`, `BackgroundTasks`, `Query`, `CORSMiddleware` |
| `uvicorn` | server runner |
| `cinemind.agent` | `CineMind` |
| `cinemind.agent_mode` | `AgentMode`, `get_configured_mode`, `resolve_effective_mode` |
| `cinemind.database` | `Database` |
| `cinemind.observability` | `Observability` |
| `cinemind.tagging` | `RequestTagger` |
| `cinemind.tmdb_image_config` | — |
| `config` | Various constants |
| `workflows` | `run_real_agent_with_fallback`, `run_playground` |
| `schemas` | `MovieQuery`, `MovieResponse`, `QueryRequest`, `HealthResponse`, `DiagnosticResponse` |
| `integrations.watchmode` | `get_watchmode_client` |
| `integrations.where_to_watch_normalizer` | `normalize_where_to_watch_response` |

**Exports:** `app` (FastAPI instance), `run_server`

---

### 3.5 `src/integrations/`

#### `watchmode.py`

| Imports From | Symbols |
|-------------|---------|
| `logging`, `time`, `typing` | stdlib |
| `httpx` | Async HTTP |
| `config` (lazy, inside factory) | `get_watchmode_api_key` |

**Exports:** `WatchmodeClient`, `get_watchmode_client`

---

#### `where_to_watch_normalizer.py`

| Imports From | Symbols |
|-------------|---------|
| `datetime`, `typing` | stdlib |

**Exports:** `normalize_where_to_watch_response`

---

### 3.6 `src/schemas/api.py`

| Imports From | Symbols |
|-------------|---------|
| `typing` | stdlib |
| `pydantic` | `BaseModel`, `Field` |

**Exports:** `MovieQuery`, `MovieResponse`, `HealthResponse`, `DiagnosticResponse`, `QueryRequest`

---

### 3.7 `src/services/interfaces.py`

| Imports From | Symbols |
|-------------|---------|
| `typing` | `Any`, `Dict`, `Optional`, `Protocol` |

**Exports:** `IAgentRunner`

---

### 3.8 `src/workflows/`

#### `playground_workflow.py`

| Imports From | Symbols |
|-------------|---------|
| `typing` | stdlib |
| `cinemind.playground` | `run_playground_query` |

**Exports:** `run_playground`

---

#### `real_agent_workflow.py`

| Imports From | Symbols |
|-------------|---------|
| `asyncio`, `logging`, `typing` | stdlib |
| `services.interfaces` | `IAgentRunner` |

**Exports:** `run_real_agent_with_fallback`

---

### 3.9 `src/cinemind/__init__.py` (Package Public API)

| Re-exports From | Symbols |
|-----------------|---------|
| `.agent` | `CineMind` |
| `config` | `SYSTEM_PROMPT`, `AGENT_NAME`, `AGENT_VERSION`, `OPENAI_MODEL` |
| `.media_enrichment` | `MediaEnrichmentResult`, `enrich`, `enrich_batch`, `attach_media_to_result` |
| `.title_extraction` | `extract_movie_titles`, `get_search_phrases`, `TitleExtractionResult` |
| `.media_cache` | `MediaCache`, `get_default_media_cache` |

---

## 4. Reverse Dependency Index

"Who depends on this file?" — critical for knowing what breaks when a module moves.

| Module | Depended On By |
|--------|---------------|
| `config/__init__.py` | `cinemind/config.py`, `cinemind/agent.py`, `cinemind/media_enrichment.py` (lazy), `cinemind/prompting/prompt_builder.py`, `api/main.py`, `integrations/watchmode.py` (lazy) |
| `cinemind/agent.py` | `cinemind/__init__.py`, `cinemind/playground.py`, `api/main.py` |
| `cinemind/agent_mode.py` | `api/main.py` |
| `cinemind/attachment_intent_classifier.py` | `cinemind/playground_attachments.py` |
| `cinemind/cache.py` | `cinemind/agent.py` |
| `cinemind/candidate_extraction.py` | `cinemind/agent.py` |
| `cinemind/config.py` | (backward compat — grep codebase for `from cinemind.config import`) |
| `cinemind/database.py` | `cinemind/agent.py`, `cinemind/observability.py`, `api/main.py` |
| `cinemind/fuzzy_intent_matcher.py` | (standalone — used by tests directly) |
| `cinemind/intent_extraction.py` | `cinemind/agent.py` |
| `cinemind/kaggle_retrieval_adapter.py` | (standalone — used by agent or tests) |
| `cinemind/kaggle_search.py` | `cinemind/kaggle_retrieval_adapter.py` |
| `cinemind/llm_client.py` | `cinemind/agent.py`, `cinemind/playground.py` |
| `cinemind/media_cache.py` | `cinemind/media_enrichment.py`, `cinemind/__init__.py` |
| `cinemind/media_enrichment.py` | `cinemind/agent.py`, `cinemind/playground_attachments.py`, `cinemind/__init__.py` |
| `cinemind/media_focus.py` | `cinemind/playground_attachments.py` |
| `cinemind/observability.py` | `cinemind/agent.py`, `api/main.py` |
| `cinemind/playground.py` | `workflows/playground_workflow.py` |
| `cinemind/playground_attachments.py` | `cinemind/playground.py` |
| `cinemind/request_plan.py` | `cinemind/agent.py`, `cinemind/prompting/prompt_builder.py` |
| `cinemind/request_type_router.py` | (standalone — used by tests directly) |
| `cinemind/response_movie_extractor.py` | `cinemind/playground_attachments.py`, `cinemind/attachment_intent_classifier.py` |
| `cinemind/scenes_provider.py` | `cinemind/playground_attachments.py` |
| `cinemind/search_engine.py` | `cinemind/agent.py` |
| `cinemind/source_policy.py` | `cinemind/agent.py` |
| `cinemind/tagging.py` | `cinemind/agent.py`, `api/main.py` |
| `cinemind/test_results_db.py` | (tests only — should not be in src) |
| `cinemind/title_extraction.py` | `cinemind/media_enrichment.py`, `cinemind/playground_attachments.py`, `cinemind/__init__.py` |
| `cinemind/tmdb_image_config.py` | `cinemind/media_enrichment.py` (lazy), `api/main.py` |
| `cinemind/tmdb_resolver.py` | `cinemind/media_enrichment.py` (lazy) |
| `cinemind/tool_plan.py` | `cinemind/agent.py` |
| `cinemind/verification.py` | `cinemind/agent.py` |
| `cinemind/prompting/` (package) | `cinemind/agent.py` |
| `cinemind/prompting/templates.py` | `prompting/prompt_builder.py`, `prompting/output_validator.py` |
| `cinemind/prompting/evidence_formatter.py` | `prompting/prompt_builder.py` |
| `cinemind/prompting/versions.py` | `config/__init__.py` (lazy) |
| `schemas/api.py` | `api/main.py` |
| `services/interfaces.py` | `workflows/real_agent_workflow.py` |
| `integrations/watchmode.py` | `api/main.py` |
| `integrations/where_to_watch_normalizer.py` | `api/main.py` |
| `workflows/playground_workflow.py` | `api/main.py`, `workflows/__init__.py` |
| `workflows/real_agent_workflow.py` | `api/main.py`, `workflows/__init__.py` |

---

## 5. Broken & Phantom Dependencies

### 5.1 Missing Files

| Expected Import | Referenced In | Status |
|----------------|---------------|--------|
| `lib.env.find_dotenv_path` | `src/config/__init__.py` | **File does not exist.** No `lib/` directory anywhere in repo. Must be created at `src/config/env.py` or the import must be replaced with inline logic. |

### 5.2 Missing Test Fixtures

These fixtures are referenced in test files but never defined in any `conftest.py` or fixture module:

| Fixture Name | Referenced In | Status |
|-------------|---------------|--------|
| `request_plan_factory` | `tests/unit/test_smoke.py`, `tests/contract/test_prompt_builder_contract.py` | **Not defined** |
| `minimal_request_plan` | `tests/unit/test_smoke.py` | **Not defined** |
| `minimal_evidence_bundle` | `tests/unit/test_smoke.py` | **Not defined** |
| `evidence_bundle_factory` | `tests/unit/test_smoke.py` | **Not defined** |
| `sample_search_result` | `tests/unit/test_smoke.py` | **Not defined** |
| `frozen_time` | `tests/unit/test_smoke.py` | **Not defined** |

### 5.3 Misplaced Production Dependencies

| File | Issue |
|------|-------|
| `src/cinemind/test_results_db.py` | Test-only module in production package. Imported only by test infrastructure, never by runtime code. Should move to `tests/helpers/`. |
| `src/cinemind/eval/__main__.py` | CLI developer tool embedded inside the library package. Should move to `scripts/eval/` or `tools/eval/`. |

### 5.4 Redundant Import Shim

| File | Issue |
|------|-------|
| `src/cinemind/config.py` | Re-exports everything from `src/config/__init__.py`. Exists only for backward compatibility (`from cinemind.config import X`). Should be deleted once all callers switch to `from config import X`. |
