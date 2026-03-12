# Request Planning

> **Package:** `src/cinemind/planning/`
> **Purpose:** Decides *how* to answer a query before any search or LLM call — classifying request type, selecting tools, applying source policies, and producing a structured execution plan.

---

## Module Map

| Module | Role | Lines |
|--------|------|-------|
| `request_plan.py` | `RequestPlanner` — orchestrates plan creation | ~324 |
| `request_type_router.py` | Deterministic request classification | ~239 |
| `source_policy.py` | Source tier ranking and domain filtering | ~354 |
| `tool_plan.py` | Tool selection (Kaggle, Tavily, freshness) | ~244 |

---

## Planning Pipeline

```mermaid
flowchart TD
    QUERY["User Query"]

    subgraph Planning["cinemind.planning"]
        ROUTER["RequestTypeRouter<br/>Classify request type"]
        INTENT["IntentExtractor<br/>(from extraction)"]
        TOOL["ToolPlanner<br/>Select tools"]
        SOURCE["SourcePolicy<br/>Rank sources"]
        PLAN["RequestPlanner<br/>Assemble RequestPlan"]
    end

    QUERY --> PLAN
    PLAN --> ROUTER
    PLAN --> INTENT
    ROUTER --> PLAN
    INTENT --> TOOL
    TOOL --> PLAN
    SOURCE -.->|consulted by| PLAN

    PLAN --> OUTPUT["RequestPlan"]
    OUTPUT --> CORE["CineMind.search_and_analyze()"]
```

---

## Request Type Router (`request_type_router.py`)

Classifies the user query into a known `request_type` using layered deterministic rules — no LLM required.

### Classification Tiers

```mermaid
flowchart TD
    Q["Query"] --> GUARD{"Guardrail patterns?"}
    GUARD -->|Yes| REJECT["OFF_TOPIC / GUARDRAIL"]
    GUARD -->|No| HIGH{"High-confidence patterns?"}
    HIGH -->|Yes| TYPE_H["director_info, cast_info,<br/>recommendation, etc."]
    HIGH -->|No| MED{"Medium-confidence patterns?"}
    MED -->|Yes| TYPE_M["comparison, trivia, etc."]
    MED -->|No| LOW{"Low-confidence heuristics?"}
    LOW -->|Yes| TYPE_L["general_movie_question"]
    LOW -->|No| DEFAULT["general_movie_question<br/>(default)"]
```

### Request Types

| Type | Example Query |
|------|--------------|
| `director_info` | "Who directed Inception?" |
| `cast_info` | "Who stars in The Matrix?" |
| `recommendation` | "Movies like Interstellar" |
| `comparison` | "Compare The Godfather and Goodfellas" |
| `award_info` | "Best Picture 2024" |
| `release_info` | "When did Oppenheimer come out?" |
| `scene_info` | "Famous scenes in Pulp Fiction" |
| `streaming_info` | "Where can I watch Dune?" |
| `trivia` | "Fun facts about Jaws" |
| `general_movie_question` | Fallback for anything movie-related |
| `off_topic` | Non-movie queries |

### Key Types

| Type | Fields |
|------|--------|
| `RequestTypeResult` | `request_type`, `confidence`, `matched_pattern` |

---

## Request Planner (`request_plan.py`)

Orchestrates the full planning stage — combines router, intent extractor, and tool planner into a single `RequestPlan`.

### RequestPlan Structure

```mermaid
classDiagram
    class RequestPlan {
        +str request_type
        +StructuredIntent intent
        +ToolPlan tool_plan
        +ResponseFormat response_format
        +float confidence
    }

    class ToolPlan {
        +List~ToolAction~ actions
        +bool use_kaggle
        +bool use_tavily
        +bool use_freshness_override
    }

    class StructuredIntent {
        +str intent
        +Dict entities
        +Dict constraints
        +float confidence
        +bool need_freshness
    }

    RequestPlan --> ToolPlan
    RequestPlan --> StructuredIntent
```

### ResponseFormat & ToolType Enums

| Enum | Values |
|------|--------|
| `ResponseFormat` | `PARAGRAPH`, `LIST`, `TABLE`, `COMPARISON` |
| `ToolType` | `KAGGLE`, `TAVILY`, `CACHE`, `NONE` |

---

## Tool Planner (`tool_plan.py`)

Decides which search tools to invoke based on intent, freshness requirements, and available data.

### Decision Logic

```mermaid
flowchart TD
    INTENT["StructuredIntent"] --> FRESH{"need_freshness?"}
    FRESH -->|Yes| TAVILY_YES["Tavily: REQUIRED"]
    FRESH -->|No| KAGGLE_CHECK{"Kaggle can answer?"}
    KAGGLE_CHECK -->|Yes| KAGGLE["Kaggle only<br/>(skip Tavily)"]
    KAGGLE_CHECK -->|No| BOTH["Kaggle + Tavily"]

    TAVILY_YES --> PLAN["ToolPlan"]
    KAGGLE --> PLAN
    BOTH --> PLAN
```

### Tavily Skip Logic

Tavily (web search) is skipped when:
1. The tool plan explicitly says `use_tavily = False`
2. Kaggle data is highly correlated (confidence ≥ threshold)
3. The query is about historical/static facts (no freshness needed)

### Key Types

| Type | Fields |
|------|--------|
| `ToolPlan` | `actions`, `use_kaggle`, `use_tavily`, `use_freshness_override` |
| `ToolAction` | `tool_type`, `priority`, `reason` |

---

## Source Policy (`source_policy.py`)

Governs which sources are trusted for which types of information. Implements a tiered trust model.

### Source Tiers

```mermaid
graph LR
    subgraph TierA["Tier A — Authoritative"]
        IMDB["IMDb"]
        WIKI["Wikipedia"]
        WIKIDATA["Wikidata"]
        TMDB["TMDB"]
    end

    subgraph TierB["Tier B — Reliable"]
        ROTTEN["Rotten Tomatoes"]
        METACRITIC["Metacritic"]
        BOXOFFICE["Box Office Mojo"]
        AFI["AFI"]
    end

    subgraph TierC["Tier C — Supplementary"]
        BLOGS["Film blogs"]
        NEWS["News sites"]
        FORUMS["Forums"]
    end

    TierA ---|"Trusted for facts"| VERIFY["Verification"]
    TierB ---|"Trusted for opinions"| ENRICH["Enrichment"]
    TierC ---|"Context only"| CONTEXT["Background"]
```

### Source Policy Capabilities

| Method | Purpose |
|--------|---------|
| `get_tier(url)` | Classify a URL into Tier A/B/C |
| `rank_sources(results)` | Sort search results by tier |
| `filter_by_tier(results, min_tier)` | Keep only sources above a threshold |
| `get_domain_metadata(url)` | Retrieve source metadata |

### Key Types

| Type | Fields |
|------|--------|
| `SourceTier` | Enum: `A`, `B`, `C`, `UNKNOWN` |
| `SourceMetadata` | `domain`, `tier`, `name`, `specialization` |
| `SourceConstraints` | `min_tier`, `required_domains`, `blocked_domains` |

---

## Cross-Module Dependencies

```mermaid
graph TD
    subgraph planning["cinemind.planning"]
        RP["request_plan.py"]
        RTR["request_type_router.py"]
        SP["source_policy.py"]
        TP["tool_plan.py"]
    end

    subgraph extraction["cinemind.extraction"]
        IE["intent_extraction"]
    end

    RP --> RTR
    RP --> IE
    RP --> TP
    TP --> IE

    subgraph consumers["Consumers"]
        CORE["cinemind.agent.core"]
        PROMPT["cinemind.prompting.prompt_builder"]
        VERIFY["cinemind.verification.fact_verifier"]
        SEARCH["cinemind.search.search_engine"]
    end

    CORE --> RP
    CORE --> SP
    PROMPT --> RP
    VERIFY --> SP
    SEARCH --> SP
```

### External Packages

| Package | Used In | Purpose |
|---------|---------|---------|
| `re` | `request_type_router.py` | Pattern matching |
| `urllib.parse` | `source_policy.py` | Domain extraction from URLs |
| `dataclasses` | All modules | Data structures |
| `enum` | `request_plan.py`, `source_policy.py` | Enums |

---

## Design Patterns & Practices

1. **Separation of Concerns** — routing, tool selection, and source trust are independent modules composed by `RequestPlanner`
2. **Deterministic by Default** — no LLM calls in the planning stage; all decisions are rule-based
3. **Layered Classification** — guardrails → high confidence → medium → low → default prevents misclassification
4. **Policy Object** — `SourcePolicy` encapsulates trust decisions, easily testable in isolation
5. **Plan as Data** — `RequestPlan` is a plain dataclass, serializable and inspectable

---

## Change Impact Guide

| If you change... | Also check... |
|-----------------|---------------|
| Request type taxonomy | `RequestTypeRouter` patterns, `ResponseTemplate` mappings, `HybridClassifier` |
| `RequestPlan` fields | `CineMind.search_and_analyze()`, `PromptBuilder.build()` |
| Source tier domains | `FactVerifier` (relies on Tier A for verification) |
| Tavily skip logic | `SearchEngine`, integration tests with live data |
| `ToolPlan` structure | `CineMind` tool execution logic |
