# Agent Core

> **Package:** `src/cinemind/agent/`
> **Purpose:** Central orchestration of the CineMind movie intelligence agent — the main entry point that wires together extraction, planning, search, prompting, and media enrichment into a coherent pipeline.

---

## Module Map

| Module | Role | Lines |
|--------|------|-------|
| `core.py` | `CineMind` class — full agent pipeline | ~1300 |
| `mode.py` | `AgentMode` enum + runtime mode resolution | ~50 |
| `playground.py` | Playground pipeline (no real LLM/Tavily) | ~80 |

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Entry["Entry Points"]
        API["API Server<br/><code>src/api/main.py</code>"]
        WF_REAL["Real Agent Workflow"]
        WF_PLAY["Playground Workflow"]
    end

    subgraph Agent["cinemind.agent"]
        MODE["AgentMode<br/>PLAYGROUND | REAL_AGENT"]
        CORE["CineMind.search_and_analyze()"]
        PLAY["run_playground_query()"]
    end

    API -->|resolve mode| MODE
    MODE -->|REAL_AGENT| WF_REAL --> CORE
    MODE -->|PLAYGROUND| WF_PLAY --> PLAY
    PLAY -->|playground_mode=True| CORE
```

---

## CineMind Pipeline (`core.py`)

The `CineMind` class is the primary orchestrator. On instantiation it wires every subsystem; on each query it executes a multi-stage pipeline.

### Constructor Dependencies

```mermaid
graph LR
    CM["CineMind"]
    CM --> LLM["LLMClient<br/>(OpenAI or Fake)"]
    CM --> SE["SearchEngine"]
    CM --> SP["SourcePolicy"]
    CM --> IE["IntentExtractor"]
    CM --> FV["FactVerifier"]
    CM --> CE["CandidateExtractor"]
    CM --> TP["ToolPlanner"]
    CM --> PB["PromptBuilder"]
    CM --> OV["OutputValidator"]
    CM --> RT["RequestTagger"]
    CM --> HC["HybridClassifier"]
    CM --> RP["RequestPlanner"]
    CM --> SC["SemanticCache"]
```

### Pipeline Stages

```mermaid
sequenceDiagram
    participant Caller
    participant CineMind
    participant Cache as SemanticCache
    participant Planner as RequestPlanner
    participant Search as SearchEngine
    participant Extract as CandidateExtractor
    participant Verify as FactVerifier
    participant Prompt as PromptBuilder
    participant LLM as LLMClient
    participant Validate as OutputValidator

    Caller->>CineMind: search_and_analyze(query)
    CineMind->>Cache: lookup(query)
    alt Cache Hit
        Cache-->>CineMind: cached result
        CineMind-->>Caller: return cached
    end
    CineMind->>Planner: plan(query)
    Note over Planner: Intent extraction + routing + tool plan
    Planner-->>CineMind: RequestPlan

    CineMind->>Search: kaggle_search(query)
    CineMind->>Search: tavily_search(query)
    Search-->>CineMind: raw results

    CineMind->>Extract: extract_movie_candidates(results)
    Extract-->>CineMind: Candidate[]

    CineMind->>Verify: verify(candidates)
    Verify-->>CineMind: VerifiedFact[]

    CineMind->>Prompt: build(plan, evidence)
    Prompt-->>CineMind: messages[]

    CineMind->>LLM: chat(messages)
    LLM-->>CineMind: response

    CineMind->>Validate: validate(response, template)
    Validate-->>CineMind: ValidationResult

    CineMind-->>Caller: structured result
```

### Key Methods

| Method | Description |
|--------|-------------|
| `search_and_analyze(query, ...)` | Full pipeline: cache → plan → search → extract → verify → prompt → LLM → validate |
| `stream_response(query)` | Streaming variant via async generator |
| `close()` | Cleanup resources (DB connections, etc.) |

---

## Agent Mode (`mode.py`)

Two execution modes control which pipeline runs:

| Mode | LLM | Web Search | Media Source | Use Case |
|------|-----|-----------|-------------|----------|
| `PLAYGROUND` | `FakeLLMClient` | Disabled | TMDB only | Development, demos, testing |
| `REAL_AGENT` | `OpenAILLMClient` | Tavily + DuckDuckGo | TMDB | Production |

**Resolution logic:**

```mermaid
flowchart TD
    ENV["Read AGENT_MODE env var"]
    ENV -->|"REAL_AGENT"| CHECK["OPENAI_API_KEY present?"]
    ENV -->|"PLAYGROUND" or unset| PG["→ PLAYGROUND"]
    CHECK -->|Yes| RA["→ REAL_AGENT"]
    CHECK -->|No| FALLBACK["→ PLAYGROUND (fallback)"]
```

- `get_configured_mode()` — reads `AGENT_MODE` env var (default: `PLAYGROUND`)
- `resolve_effective_mode()` — applies safety fallback when API key is missing

---

## Playground Pipeline (`playground.py`)

A lightweight pipeline for offline/demo use that bypasses real LLM and web search.

| Feature | Behavior |
|---------|----------|
| LLM | `FakeLLMClient` (deterministic canned responses) |
| Search | Kaggle dataset only, no Tavily |
| Media | TMDB posters and scenes |
| Attachments | Rule-based: single movie → poster + scenes; multiple → posters only |

**Key function:** `run_playground_query(user_query, request_type=None)`

**Attachment rule** (toggled by `PLAYGROUND_ATTACHMENT_RULE_ENABLED`):

```mermaid
flowchart LR
    Q["Query"] --> PARSE["Parse response"]
    PARSE --> COUNT{"Movie count?"}
    COUNT -->|"1"| SINGLE["Poster + Scenes"]
    COUNT -->|"2+"| MULTI["Posters only"]
    COUNT -->|"0"| NONE["No attachments"]
```

---

## Internal Dependencies

```mermaid
graph TD
    subgraph agent["cinemind.agent"]
        core["core.py"]
        mode["mode.py"]
        playground["playground.py"]
    end

    subgraph deps["Direct Dependencies"]
        extraction["cinemind.extraction"]
        planning["cinemind.planning"]
        search["cinemind.search"]
        prompting["cinemind.prompting"]
        verification["cinemind.verification"]
        media["cinemind.media"]
        infrastructure["cinemind.infrastructure"]
        llm["cinemind.llm"]
    end

    core --> extraction
    core --> planning
    core --> search
    core --> prompting
    core --> verification
    core --> media
    core --> infrastructure
    core --> llm

    playground --> core
    playground --> media
    playground --> llm

    mode -.->|env only| core
```

### External Packages

| Package | Used In | Purpose |
|---------|---------|---------|
| `openai` | `core.py` (via `llm.client`) | LLM API calls |
| `tavily` | `core.py` (via `search.search_engine`) | Web search |
| `logging` | All modules | Structured logging |
| `asyncio` | `core.py` | Async pipeline execution |

---

## Environment Variables

| Variable | Default | Used By |
|----------|---------|---------|
| `AGENT_MODE` | `PLAYGROUND` | `mode.py` — selects pipeline |
| `OPENAI_API_KEY` | — | `mode.py` — fallback check; `llm/client.py` — API auth |
| `OPENAI_MODEL` | `gpt-4o` | `core.py` — model selection |

---

## Design Patterns & Practices

1. **Strategy Pattern** — `AgentMode` selects between `FakeLLMClient` and `OpenAILLMClient` at runtime
2. **Pipeline Pattern** — `search_and_analyze` chains stages with early exits (cache hit)
3. **Graceful Degradation** — missing API key auto-downgrades to playground mode
4. **Dependency Injection** — `CineMind` accepts an optional `llm_client` parameter; tests inject fakes
5. **Single Responsibility** — `core.py` orchestrates only; domain logic lives in dedicated packages

---

## Change Impact Guide

| If you change... | Also check... |
|-----------------|---------------|
| `CineMind.__init__` signature | `api/main.py`, `playground.py`, all tests creating `CineMind` |
| Pipeline stage order | Integration tests, `search_and_analyze` callers |
| `AgentMode` values | `mode.py`, `api/main.py`, workflow files |
| `run_playground_query` | `workflows/playground_workflow.py`, playground tests |
