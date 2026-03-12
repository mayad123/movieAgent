# Configuration, Schemas & Services

> **Packages:** `src/config/`, `src/schemas/`, `src/services/`, `src/lib/`
> **Purpose:** Foundation layer — environment resolution, API contracts, service interfaces, and shared utilities that every other package depends on.

---

## Module Map

| Package | Module | Role | Lines |
|---------|--------|------|-------|
| `config/` | `env.py` | Locate `.env` file by walking up from cwd | ~33 |
| `schemas/` | `api.py` | Pydantic models for API request/response | ~57 |
| `services/` | `interfaces.py` | Protocol interfaces for domain services | ~19 |
| `lib/` | `env.py` | Simpler `.env` finder (legacy) | ~15 |

---

## Architecture

```mermaid
graph TD
    subgraph Foundation["Foundation Layer"]
        CONFIG["config.env<br/>find_dotenv_path()"]
        SCHEMAS["schemas.api<br/>Pydantic models"]
        SERVICES["services.interfaces<br/>IAgentRunner"]
        LIB["lib.env<br/>find_dotenv_path() (legacy)"]
    end

    subgraph Consumers
        API["api/main.py"]
        WORKFLOWS["workflows/"]
        CORE["cinemind.agent.core"]
        TESTS["tests/"]
    end

    API --> SCHEMAS
    API --> CONFIG
    WORKFLOWS --> SERVICES
    CORE --> CONFIG
    TESTS --> LIB
```

---

## Environment Configuration (`config/env.py`)

Locates the `.env` file by walking up the directory tree from a starting point.

### Resolution Logic

```mermaid
flowchart TD
    START["Start directory<br/>(default: cwd)"] --> CHECK{"filename exists here?"}
    CHECK -->|Yes| FOUND["Return absolute path"]
    CHECK -->|No| UP["Move to parent"]
    UP --> DEPTH{"Depth ≤ max_depth?"}
    DEPTH -->|Yes| CHECK
    DEPTH -->|No| NONE["Return None"]
```

### Function Signature

```python
def find_dotenv_path(
    filename: str = ".env",
    start: Optional[Path] = None,
    max_depth: int = 5,
) -> Optional[str]:
```

### Note on Dual Implementation

There are two `.env` finders:

| Module | Signature | Origin |
|--------|----------|--------|
| `config.env` | `find_dotenv_path(filename, start, max_depth)` | Post-refactor canonical |
| `lib.env` | `find_dotenv_path()` | Legacy (no parameters) |

Both exist for backward compatibility. New code should use `config.env`.

---

## API Schemas (`schemas/api.py`)

Pydantic models defining the API contract between server and clients.

### Request Models

```mermaid
classDiagram
    class MovieQuery {
        +query: str
    }

    class QueryRequest {
        +query: str
        +request_type: Optional[str]
    }

    QueryRequest --|> MovieQuery : extends
```

### Response Models

```mermaid
classDiagram
    class MovieResponse {
        +response: str
        +sources: List[Dict]
        +request_type: Optional[str]
        +search_metadata: Optional[Dict]
        +media_strip: Optional[List]
        +attachments: Optional[Dict]
    }

    class HealthResponse {
        +status: str
        +agent_mode: str
    }

    class DiagnosticResponse {
        +status: str
        +checks: Dict[str, Any]
    }
```

### Model Summary

| Model | Direction | Purpose |
|-------|-----------|---------|
| `MovieQuery` | Request | Simple query input |
| `QueryRequest` | Request | Query with optional type hint |
| `MovieResponse` | Response | Full agent response with media |
| `HealthResponse` | Response | Health check output |
| `DiagnosticResponse` | Response | Dependency health |

---

## Service Interfaces (`services/interfaces.py`)

Protocol-based interfaces that decouple workflows from domain implementations.

```mermaid
classDiagram
    class IAgentRunner {
        <<Protocol>>
        +search_and_analyze(user_query, use_live_data, request_id, request_type, outcome, playground_mode) Dict
    }

    class CineMind {
        +search_and_analyze(...) Dict
    }

    IAgentRunner <|.. CineMind : structural subtype
```

**Why it exists:** The `real_agent_workflow` depends on `IAgentRunner`, not on `CineMind` directly. This allows:
- Tests to inject stub agents
- Workflows to remain ignorant of domain internals
- Future agent implementations to be swapped in

---

## Dependency Relationships

```mermaid
graph TD
    subgraph foundation["Foundation Layer"]
        CE["config.env"]
        SA["schemas.api"]
        SI["services.interfaces"]
        LE["lib.env"]
    end

    subgraph consumers["Consumers"]
        API["api/main.py"]
        WF_REAL["workflows/real_agent_workflow"]
        WF_PLAY["workflows/playground_workflow"]
        CORE["cinemind.agent.core"]
    end

    API --> SA
    API --> CE
    WF_REAL --> SI
    CORE --> CE
```

### External Packages

| Package | Used In | Purpose |
|---------|---------|---------|
| `pydantic` | `schemas/api.py` | Model validation and serialization |
| `pathlib` | `config/env.py`, `lib/env.py` | Path operations |
| `typing` | All modules | Type annotations and Protocol |

---

## Environment Variables (Full Registry)

This is the consolidated list of all environment variables used across the system:

### Core Agent

| Variable | Default | Used By |
|----------|---------|---------|
| `AGENT_MODE` | `PLAYGROUND` | `agent/mode.py` |
| `OPENAI_API_KEY` | — | `llm/client.py`, `agent/mode.py` |
| `OPENAI_MODEL` | `gpt-4o` | `llm/client.py` |
| `AGENT_TIMEOUT_SECONDS` | `30` | `api/main.py` |

### Search

| Variable | Default | Used By |
|----------|---------|---------|
| `TAVILY_API_KEY` | — | `search/search_engine.py` |
| `KAGGLE_ENABLED` | `true` | `search/kaggle_retrieval_adapter.py` |
| `KAGGLE_DATASET_PATH` | `data/imdb.csv` | `search/kaggle_search.py` |
| `KAGGLE_CORRELATION_THRESHOLD` | `0.8` | `search/kaggle_search.py` |
| `KAGGLE_SEARCH_TIMEOUT_SECONDS` | `5` | `search/kaggle_retrieval_adapter.py` |

### Media

| Variable | Default | Used By |
|----------|---------|---------|
| `TMDB_API_KEY` | — | `integrations/tmdb/*` |
| `TMDB_READ_ACCESS_TOKEN` | — | `integrations/tmdb/*` |
| `WATCHMODE_API_KEY` | — | `integrations/watchmode/client.py` |
| `MEDIA_CACHE_TTL_SECONDS` | `3600` | `media/media_cache.py` |
| `MEDIA_CACHE_MAX_ENTRIES` | `1000` | `media/media_cache.py` |

### Infrastructure

| Variable | Default | Used By |
|----------|---------|---------|
| `DATABASE_URL` | — | `infrastructure/database.py` |
| `SQLITE_PATH` | `cinemind.db` | `infrastructure/database.py` |
| `CACHE_DEFAULT_TTL_HOURS` | `24` | `infrastructure/cache.py` |
| `CACHE_EMBEDDING_THRESHOLD` | `0.92` | `infrastructure/cache.py` |
| `CACHE_MAX_ENTRIES` | `10000` | `infrastructure/cache.py` |

### Server

| Variable | Default | Used By |
|----------|---------|---------|
| `HOST` | `0.0.0.0` | `api/main.py` |
| `PORT` | `8000` | `api/main.py` |
| `CORS_ORIGINS` | `*` | `api/main.py` |

---

## Design Patterns & Practices

1. **Protocol-Based Interfaces** — `IAgentRunner` uses Python's `Protocol` for structural subtyping (no explicit inheritance required)
2. **Contract-First API** — Pydantic models define the shape of requests and responses before implementation
3. **Configuration as Discovery** — `.env` is found by walking the filesystem, not hardcoded to a path
4. **Minimal Foundation** — foundation modules have zero business logic; they're pure plumbing
5. **Single Source of Truth** — env var names and defaults documented alongside usage

---

## Change Impact Guide

| If you change... | Also check... |
|-----------------|---------------|
| `MovieResponse` fields | API endpoints, frontend `api.js`, integration tests |
| `IAgentRunner` protocol | `CineMind`, `real_agent_workflow`, all test stubs |
| `.env` variable names | `.env.example`, Docker configs, CI secrets, all modules referencing them |
| `find_dotenv_path` behavior | Any module that loads environment variables at import time |
| Pydantic model validation | API error responses, frontend error handling |
