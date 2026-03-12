# Infrastructure

> **Package:** `src/cinemind/infrastructure/`
> **Purpose:** Cross-cutting concerns that support the entire agent pipeline — semantic caching, database persistence, observability/metrics, and request classification/tagging.

---

## Module Map

| Module | Role | Lines |
|--------|------|-------|
| `cache.py` | Two-tier semantic cache (hash + embedding) | ~857 |
| `database.py` | SQLite/PostgreSQL persistence layer | ~413 |
| `observability.py` | Request tracking, timing, and cost calculation | ~339 |
| `tagging.py` | Hybrid request classifier (rules → LLM → guardrails) | ~382 |

---

## System Overview

```mermaid
flowchart TD
    subgraph Pipeline["Agent Pipeline"]
        CORE["CineMind"]
    end

    subgraph infra["cinemind.infrastructure"]
        CACHE["SemanticCache<br/>Two-tier lookup"]
        DB["Database<br/>SQLite / Postgres"]
        OBS["Observability<br/>Tracking & metrics"]
        TAG["Tagging<br/>Classification"]
    end

    CORE -->|"1. cache check"| CACHE
    CORE -->|"2. log request"| OBS
    CORE -->|"3. classify"| TAG
    CORE -->|"4. persist"| DB

    CACHE --> DB
    OBS --> DB
    TAG -.->|optional LLM| LLM["cinemind.llm.LLMClient"]
```

---

## Semantic Cache (`cache.py`)

A two-tier cache that avoids redundant LLM calls for similar queries.

### Two-Tier Architecture

```mermaid
flowchart TD
    QUERY["Incoming Query"]
    QUERY --> NORMALIZE["PromptNormalizer<br/>Canonicalize query"]
    NORMALIZE --> HASH["Tier 1: Exact Hash<br/>SHA-256 of normalized query"]
    HASH -->|Hit| FRESHNESS{"Fresh enough?"}
    FRESHNESS -->|Yes| RETURN["Return cached result"]
    FRESHNESS -->|No| TIER2
    HASH -->|Miss| TIER2["Tier 2: Embedding Similarity<br/>Cosine similarity ≥ threshold"]
    TIER2 -->|Hit| FRESHNESS2{"Fresh enough?"}
    FRESHNESS2 -->|Yes| RETURN
    FRESHNESS2 -->|No| MISS["Cache miss → run pipeline"]
    TIER2 -->|Miss| MISS

    style RETURN fill:#d4edda
    style MISS fill:#f8d7da
```

### Freshness Rules

| Intent Type | TTL | Reason |
|------------|-----|--------|
| Award queries | Short (hours) | Awards change during season |
| Release/streaming info | Medium (days) | Availability changes |
| Historical facts | Long (weeks) | Director of a 1994 film won't change |
| Default | Configurable | `CACHE_DEFAULT_TTL_HOURS` env var |

### PromptNormalizer

Canonicalizes queries before hashing to improve cache hit rates:

| Normalization | Example |
|--------------|---------|
| Lowercase | "Who Directed INCEPTION" → "who directed inception" |
| Whitespace collapse | "who  directed  inception" → "who directed inception" |
| Intent signature | Groups similar phrasings into same key |

### Key Types

| Type | Fields |
|------|--------|
| `CacheEntry` | `key`, `result`, `timestamp`, `ttl_hours`, `intent`, `hit_count` |
| `SemanticCache` | Two-tier lookup with freshness gating |

### Key Methods

| Method | Purpose |
|--------|---------|
| `lookup(query, intent)` | Two-tier cache check with freshness |
| `store(query, intent, result, ttl)` | Cache a new result |
| `invalidate(query)` | Remove a specific entry |
| `stats()` | Hit/miss ratios, entry counts |

---

## Database (`database.py`)

Persistence layer supporting both SQLite (development) and PostgreSQL (production).

### Schema

```mermaid
erDiagram
    REQUESTS {
        string request_id PK
        string query
        string request_type
        string outcome
        timestamp created_at
    }

    RESPONSES {
        string response_id PK
        string request_id FK
        string response_text
        string model
        int prompt_tokens
        int completion_tokens
        float cost
    }

    METRICS {
        string metric_id PK
        string request_id FK
        string metric_name
        float metric_value
        timestamp recorded_at
    }

    SEARCH_OPS {
        string search_id PK
        string request_id FK
        string source
        string query
        int result_count
        float latency_ms
    }

    REQUESTS ||--o{ RESPONSES : has
    REQUESTS ||--o{ METRICS : has
    REQUESTS ||--o{ SEARCH_OPS : has
```

### Key Methods

| Method | Purpose |
|--------|---------|
| `log_request(...)` | Record a new request |
| `log_response(...)` | Record the agent's response |
| `log_metric(...)` | Record a performance metric |
| `log_search(...)` | Record a search operation |
| `get_request(id)` | Retrieve request details |
| `get_requests(limit, offset)` | Paginated request history |
| `get_stats()` | Aggregated statistics |
| `update_outcome(id, outcome)` | Set request outcome |

### Database Selection

```mermaid
flowchart LR
    ENV{"DATABASE_URL set?"}
    ENV -->|Yes| PG["PostgreSQL"]
    ENV -->|No| SQLITE["SQLite<br/>(cinemind.db)"]
```

---

## Observability (`observability.py`)

Structured tracking for every request through the pipeline.

### Components

```mermaid
flowchart LR
    subgraph Observability
        RT["RequestTracker<br/>Per-request context"]
        OT["OperationTimer<br/>Stage timing"]
        COST["calculate_openai_cost()<br/>Token → dollar"]
        OBS["Observability<br/>Aggregation"]
    end

    PIPELINE["Agent Pipeline"] --> RT
    RT --> OT
    RT --> COST
    OT --> OBS
    COST --> OBS
    OBS --> DB["Database"]
    OBS --> LOG["Structured Logs"]
```

### RequestTracker

Tracks a single request through all pipeline stages:

| Tracked Data | Source |
|-------------|--------|
| Request ID | Generated or provided |
| Stage timings | `OperationTimer` context manager |
| Token usage | LLM response |
| Cost | `calculate_openai_cost()` |
| Search operations | Search engine callbacks |
| Cache hits/misses | Semantic cache |

### OperationTimer

Context manager for timing individual pipeline stages:

```python
with OperationTimer("tavily_search") as timer:
    results = await search_engine.search(query)
# timer.elapsed_ms now available
```

### Cost Calculation

| Model | Input (per 1K tokens) | Output (per 1K tokens) |
|-------|----------------------|----------------------|
| `gpt-4o` | Configured rate | Configured rate |
| `gpt-4o-mini` | Configured rate | Configured rate |

---

## Request Tagging (`tagging.py`)

Classifies requests for analytics, routing, and quality tracking.

### Hybrid Classification

```mermaid
flowchart TD
    QUERY["Query"] --> RULES["Rule-based classifier<br/>(high-confidence patterns)"]
    RULES --> CONF{"Confidence ≥ threshold?"}
    CONF -->|Yes| TAG["Classification result"]
    CONF -->|No| LLM_CLASS["LLM classifier<br/>(optional)"]
    LLM_CLASS --> GUARD["Guardrail check"]
    GUARD --> TAG

    style RULES fill:#d4edda
    style LLM_CLASS fill:#fff3cd
    style GUARD fill:#cce5ff
```

### Classification Types

**Request Types** (`REQUEST_TYPES`):

| Type | Example |
|------|---------|
| `director_info` | "Who directed Inception?" |
| `cast_info` | "Cast of The Matrix" |
| `recommendation` | "Movies like Interstellar" |
| `comparison` | "Compare Alien vs Aliens" |
| `award_info` | "Best Picture 2024" |
| `off_topic` | "What's the weather?" |
| *(more)* | See `request_type_router.py` |

**Outcomes** (`OUTCOMES`):

| Outcome | Meaning |
|---------|---------|
| `success` | User satisfied |
| `partial` | Partially answered |
| `failure` | Could not answer |
| `off_topic` | Non-movie query |

### Key Types

| Type | Fields |
|------|--------|
| `ClassificationResult` | `request_type`, `confidence`, `method` (`"rule"` or `"llm"`) |
| `RequestTagger` | Tags requests with type + metadata |
| `HybridClassifier` | Rules → LLM → guardrails pipeline |

---

## Cross-Module Dependencies

```mermaid
graph TD
    subgraph infra["cinemind.infrastructure"]
        CACHE["cache"]
        DB["database"]
        OBS["observability"]
        TAG["tagging"]
    end

    TAG -.->|optional| LLM["cinemind.llm.LLMClient"]
    CACHE --> DB

    subgraph consumers["Consumers"]
        CORE["cinemind.agent.core"]
        API["api/main.py"]
    end

    CORE --> CACHE
    CORE --> OBS
    CORE --> TAG
    CORE --> DB
    API --> OBS
    API --> DB
```

### External Packages

| Package | Used In | Purpose |
|---------|---------|---------|
| `sqlite3` | `database.py` | SQLite backend |
| `psycopg2` | `database.py` | PostgreSQL backend (optional) |
| `hashlib` | `cache.py` | SHA-256 hashing |
| `numpy` | `cache.py` | Embedding similarity (optional) |
| `logging` | All modules | Structured logging |
| `time` | `observability.py` | Timing operations |
| `threading` | `cache.py` | Thread-safe cache |
| `uuid` | `observability.py` | Request ID generation |

### Environment Variables

| Variable | Default | Used By |
|----------|---------|---------|
| `DATABASE_URL` | — | `database.py` (Postgres) |
| `SQLITE_PATH` | `cinemind.db` | `database.py` (SQLite) |
| `CACHE_DEFAULT_TTL_HOURS` | `24` | `cache.py` |
| `CACHE_EMBEDDING_THRESHOLD` | `0.92` | `cache.py` |
| `CACHE_MAX_ENTRIES` | `10000` | `cache.py` |

---

## Design Patterns & Practices

1. **Layered Cache** — exact hash (fast, precise) before embedding similarity (slower, fuzzy)
2. **Freshness-Aware Caching** — TTL varies by intent type, preventing stale answers for time-sensitive queries
3. **Database Abstraction** — same interface for SQLite and PostgreSQL; selected by env var
4. **Context Manager Timing** — `OperationTimer` makes stage timing natural and exception-safe
5. **Hybrid Classification** — deterministic rules handle common cases; LLM handles edge cases; guardrails catch misclassification
6. **Cost Tracking** — every LLM call is costed and persisted for budget monitoring
7. **Structured Logging** — all operations include request IDs for distributed tracing

---

## Change Impact Guide

| If you change... | Also check... |
|-----------------|---------------|
| Cache TTL logic | Response freshness, test fixtures with time mocking |
| Database schema | Migration scripts, all `Database` methods, observability endpoints |
| `ClassificationResult` fields | `RequestPlanner`, observability analytics |
| Cost calculation rates | Budget alerts, dashboard reports |
| Cache key normalization | Cache hit rates, deduplication behavior |
| `REQUEST_TYPES` or `OUTCOMES` | `RequestTypeRouter`, `ResponseTemplate`, frontend analytics |
