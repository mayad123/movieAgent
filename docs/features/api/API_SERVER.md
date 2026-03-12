# API Server

> **Package:** `src/api/`
> **Purpose:** FastAPI REST server that exposes CineMind's capabilities as HTTP endpoints, serves the web frontend, and provides observability dashboards.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to understand... | Jump to |
|------------------------|---------|
| All available endpoints | [Endpoint Overview](#endpoint-overview) |
| Query endpoint details | [Query Endpoints](#query-endpoints) |
| Where-to-Watch endpoint | [Where to Watch](#where-to-watch) |
| How a request flows | [Request Flow](#request-flow) |
| Response Pydantic models | [Response Schema](#response-schema) |
| What this imports | [Internal Dependencies](#internal-dependencies) |
| Which tests to run | [Test Coverage](#test-coverage) |
| What else breaks if I change this | [Change Impact Guide](#change-impact-guide) |

**Example changes and where to look:**
- "Add a new endpoint" → [Endpoint Overview](#endpoint-overview) + [Response Schema](#response-schema)
- "Change the response shape" → [Response Schema](#response-schema) + [Change Impact Guide](#change-impact-guide)
- "Understand request routing" → [Request Flow](#request-flow)

</details>

---

## Module Map

| Module | Role | Lines |
|--------|------|-------|
| `main.py` | FastAPI application with all routes | ~455 |

---

## Endpoint Overview

```mermaid
flowchart LR
    subgraph Client
        WEB["Web Frontend"]
        EXT["External Callers"]
    end

    subgraph API["FastAPI Server"]
        direction TB
        HEALTH["/health"]
        DIAG["/health/diagnostic"]
        SEARCH_POST["POST /search"]
        QUERY["POST /query"]
        STREAM["POST /search/stream"]
        SEARCH_GET["GET /search"]
        WTW["/api/watch/where-to-watch"]
        OBS_REQ["/observability/requests"]
        OBS_STATS["/observability/stats"]
        OBS_TAGS["/observability/tags"]
        STATIC["/ (web frontend)"]
    end

    WEB --> SEARCH_POST
    WEB --> WTW
    WEB --> STATIC
    EXT --> QUERY
    EXT --> STREAM
    EXT --> HEALTH
```

---

## Endpoint Details

### Health & Diagnostics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness check — returns status and agent mode |
| `/health/diagnostic` | GET | Dependency health (API keys present, DB reachable, cache status) |

### Query Endpoints

| Endpoint | Method | Description | Mode |
|----------|--------|-------------|------|
| `/search` | POST | Primary query endpoint — routes to real agent or playground | Both |
| `/query` | POST | Alias for `/search` | Both |
| `/search/stream` | POST | Server-Sent Events streaming response | REAL_AGENT |
| `/search` | GET | Simple query via URL param `?q=...` | Both |

### Where to Watch

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/watch/where-to-watch` | GET | Streaming availability via Watchmode API |
| `/api/where-to-watch` | GET | Legacy endpoint (returns 501) |

### Observability

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/observability/requests/{id}` | GET | Single request details |
| `/observability/requests` | GET | Paginated request history |
| `/observability/stats` | GET | Aggregated statistics |
| `/observability/tags` | GET | Tag distribution |
| `/observability/requests/{id}/outcome` | PUT | Update request outcome |

---

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Mode as AgentMode
    participant RealWF as real_agent_workflow
    participant PlayWF as playground_workflow
    participant Agent as CineMind

    Client->>API: POST /search {query}
    API->>Mode: resolve_effective_mode()

    alt REAL_AGENT
        API->>RealWF: run_real_agent_with_fallback(query, agent)
        RealWF->>Agent: search_and_analyze(query)
        Agent-->>RealWF: result
        alt Success
            RealWF-->>API: (result, None)
        else Timeout/Error
            RealWF-->>API: (None, fallback_reason)
            API->>PlayWF: run_playground(query)
            PlayWF-->>API: playground_result
        end
    else PLAYGROUND
        API->>PlayWF: run_playground(query)
        PlayWF-->>API: result
    end

    API-->>Client: MovieResponse JSON
```

---

## Response Schema

**File:** `src/schemas/api.py`

| Model | Fields | Purpose |
|-------|--------|---------|
| `MovieQuery` | `query: str` | Inbound request |
| `QueryRequest` | `query: str`, `request_type: Optional[str]` | Extended request |
| `MovieResponse` | `response`, `sources`, `request_type`, `search_metadata`, `media_strip`, `attachments` | Full response |
| `HealthResponse` | `status`, `agent_mode` | Health check |
| `DiagnosticResponse` | `status`, `checks: Dict` | Diagnostic info |

---

## Static File Serving

The API serves the web frontend from the `/web` directory:

```mermaid
flowchart LR
    REQ["GET /"] --> STATIC["StaticFiles mount"]
    STATIC --> INDEX["web/index.html"]
    STATIC --> CSS["web/css/*"]
    STATIC --> JS["web/js/*"]
```

---

## Internal Dependencies

```mermaid
graph TD
    API["api/main.py"]

    API --> SCHEMAS["schemas/api.py"]
    API --> WORKFLOWS_PG["workflows/playground_workflow"]
    API --> WORKFLOWS_RA["workflows/real_agent_workflow"]
    API --> MODE["cinemind.agent.mode"]
    API --> AGENT["cinemind.agent.core.CineMind"]
    API --> OBS["cinemind.infrastructure.observability"]
    API --> DB["cinemind.infrastructure.database"]
    API --> WM["integrations.watchmode"]
    API --> CONFIG["config.env"]
```

### External Packages

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `pydantic` | Request/response validation (via schemas) |
| `starlette` | Static files, CORS middleware |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_MODE` | `PLAYGROUND` | Pipeline selection |
| `AGENT_TIMEOUT_SECONDS` | `30` | Real agent timeout |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `CORS_ORIGINS` | `*` | Allowed origins |
| `WATCHMODE_API_KEY` | — | Where-to-Watch feature |

---

## Design Patterns & Practices

1. **Thin Controller** — endpoints contain routing logic only; business logic lives in workflows/domain
2. **Mode-Aware Routing** — `resolve_effective_mode()` determines pipeline before any domain call
3. **Fallback Chain** — real agent timeout → automatic playground fallback → client gets a response
4. **Contract-First** — Pydantic models in `schemas/api.py` define the API contract
5. **Observability Built-In** — every request is tracked, tagged, and queryable

---

## Test Coverage

### Tests to Run When Changing This Package

```bash
# API endpoint tests
python -m pytest tests/unit/integrations/test_where_to_watch_api.py -v
python -m pytest tests/smoke/test_playground_smoke.py -v

# Full pipeline (exercises API → workflow → agent)
python -m pytest tests/integration/test_agent_offline_e2e.py -v
```

| Test File | What It Covers |
|-----------|---------------|
| `tests/unit/integrations/test_where_to_watch_api.py` | `/api/watch/where-to-watch` endpoint: happy path, not found, rate limit, missing key |
| `tests/smoke/test_playground_smoke.py` | FastAPI app imports, basic `/query` request via TestClient |
| `tests/integration/test_agent_offline_e2e.py` | Full pipeline through API layer with FakeLLM |

---

## Change Impact Guide

| If you change... | Also check... |
|-----------------|---------------|
| Response schema (`MovieResponse`) | `schemas/api.py`, web frontend `js/modules/api.js`, `messages.js` |
| Endpoint paths | Frontend `js/modules/api.js`, any external integrations |
| CORS configuration | Deployment configs, Docker compose |
| Observability endpoints | `docs/architecture/VIEW_OBSERVABILITY_GUIDE.md` |
| Where-to-Watch response shape | `integrations/watchmode/normalizer.py`, frontend `where-to-watch.js` |
