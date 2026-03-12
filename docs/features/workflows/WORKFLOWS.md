# Workflows

> **Package:** `src/workflows/`
> **Purpose:** Thin orchestration layer that decouples API endpoints from domain logic. Workflows depend on service interfaces, not on concrete implementations.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to understand... | Jump to |
|------------------------|---------|
| What files are in this package | [Module Map](#module-map) |
| How API calls the agent | [Architecture](#architecture) |
| Playground workflow details | [Playground Workflow](#playground-workflow) |
| Timeout and fallback logic | [Timeout & Fallback Logic](#timeout--fallback-logic) |
| The IAgentRunner protocol | [Service Interface](#service-interface) |
| Which tests to run | [Test Coverage](#test-coverage) |
| What else breaks if I change this | [Change Impact Guide](#change-impact-guide) |

**Example changes and where to look:**
- "Change the timeout duration" → [Timeout & Fallback Logic](#timeout--fallback-logic)
- "Add a new workflow variant" → [Architecture](#architecture) + [Service Interface](#service-interface)
- "Change how fallback works" → [Real Agent Workflow](#real-agent-workflow)

</details>

---

## Module Map

| Module | Role | Lines |
|--------|------|-------|
| `playground_workflow.py` | Delegates to `cinemind.agent.playground` | ~27 |
| `real_agent_workflow.py` | Runs real agent with timeout + fallback | ~52 |

---

## Architecture

```mermaid
flowchart TD
    subgraph API["API Layer"]
        MAIN["api/main.py<br/>FastAPI endpoints"]
    end

    subgraph Workflows["Workflow Layer"]
        PG_WF["playground_workflow<br/><code>run_playground()</code>"]
        RA_WF["real_agent_workflow<br/><code>run_real_agent_with_fallback()</code>"]
    end

    subgraph Services["Service Interfaces"]
        IAGENT["IAgentRunner Protocol"]
    end

    subgraph Domain["Domain Layer"]
        PG_IMPL["cinemind.agent.playground<br/><code>run_playground_query()</code>"]
        CINEMIND["CineMind<br/>implements IAgentRunner"]
    end

    MAIN --> PG_WF
    MAIN --> RA_WF
    RA_WF -->|depends on| IAGENT
    IAGENT -.->|implemented by| CINEMIND
    PG_WF --> PG_IMPL
```

---

## Playground Workflow

**File:** `src/workflows/playground_workflow.py`

A pure pass-through to `cinemind.agent.playground.run_playground_query()`. Exists so callers (API, tests) import from `workflows` and never directly from `cinemind`.

```python
async def run_playground(
    user_query: str,
    request_type: Optional[str] = None,
) -> Dict[str, Any]:
```

**Dependencies:** `cinemind.agent.playground` only.

---

## Real Agent Workflow

**File:** `src/workflows/real_agent_workflow.py`

Wraps the real LLM agent with timeout and structured error handling. The caller (API) supplies the concrete `IAgentRunner` — the workflow never imports `CineMind` directly.

```python
async def run_real_agent_with_fallback(
    user_query: str,
    request_type: Optional[str],
    use_live_data: bool,
    timeout_seconds: float,
    agent_runner: IAgentRunner,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
```

### Timeout & Fallback Logic

```mermaid
flowchart TD
    START["run_real_agent_with_fallback()"]
    START --> TRY["asyncio.wait_for(agent.search_and_analyze(), timeout)"]
    TRY -->|Success| OK["return (result, None)"]
    TRY -->|TimeoutError| TO["return (None, 'Request timed out')"]
    TRY -->|Exception| ERR["return (None, str(error))"]

    style OK fill:#d4edda
    style TO fill:#fff3cd
    style ERR fill:#f8d7da
```

The API layer receives the `(result, fallback_reason)` tuple and switches to Playground if `fallback_reason` is set.

---

## Service Interface

**File:** `src/services/interfaces.py`

```python
class IAgentRunner(Protocol):
    async def search_and_analyze(
        self,
        user_query: str,
        use_live_data: bool = True,
        request_id: Optional[str] = None,
        request_type: Optional[str] = None,
        outcome: Optional[str] = None,
        playground_mode: bool = False,
    ) -> Dict[str, Any]: ...
```

This protocol enables:
- **Testability** — tests inject stubs without importing `CineMind`
- **Decoupling** — workflows never import domain classes
- **Substitutability** — any class satisfying the protocol works

---

## Dependency Graph

```mermaid
graph LR
    subgraph workflows
        PG["playground_workflow"]
        RA["real_agent_workflow"]
    end

    subgraph services
        IF["interfaces.IAgentRunner"]
    end

    subgraph cinemind
        AGENT["agent.playground"]
        CORE["agent.core.CineMind"]
    end

    PG --> AGENT
    RA --> IF
    IF -.->|structural subtype| CORE

    style IF stroke-dasharray: 5 5
```

### External Packages

| Package | Used In | Purpose |
|---------|---------|---------|
| `asyncio` | `real_agent_workflow.py` | `wait_for` timeout |
| `logging` | `real_agent_workflow.py` | Error logging |

---

## Design Patterns & Practices

1. **Dependency Inversion** — workflows depend on `IAgentRunner` protocol, not `CineMind`
2. **Thin Orchestration** — no business logic in workflows; they wire inputs to domain functions
3. **Structured Error Propagation** — `(result, fallback_reason)` tuple avoids silent failures
4. **Single Import Direction** — API → Workflows → Domain (never reverse)

---

## Test Coverage

### Tests to Run When Changing This Package

```bash
# Direct unit tests
python -m pytest tests/unit/workflows/test_workflows.py -v

# Smoke tests (exercise full workflow paths)
python -m pytest tests/smoke/test_playground_smoke.py -v
python -m pytest tests/smoke/test_real_workflow_smoke.py -v
```

| Test File | What It Covers |
|-----------|---------------|
| `tests/unit/workflows/test_workflows.py` | `run_real_agent_with_fallback`: timeout, error fallback, success path |
| `tests/smoke/test_playground_smoke.py` | Playground workflow via FastAPI |
| `tests/smoke/test_real_workflow_smoke.py` | Real agent workflow (requires API key) |

---

## Change Impact Guide

| If you change... | Also check... |
|-----------------|---------------|
| `IAgentRunner` signature | `CineMind.search_and_analyze`, `real_agent_workflow.py`, all test stubs |
| `run_playground` signature | `api/main.py`, playground tests |
| Timeout behavior | `api/main.py` (reads `AGENT_TIMEOUT_SECONDS` env var) |
| Fallback reason format | Frontend error display logic |
