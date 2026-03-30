# Backend Patterns

> Python conventions and design patterns used throughout the CineMind backend (`src/`).

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need guidance on... | Jump to |
|----------------------|---------|
| Package structure and `__init__.py` | [Module Design](#module-design) |
| How to define data structures | [Dataclass Conventions](#dataclass-conventions) |
| When to use Protocol interfaces | [Protocol Interfaces](#protocol-interfaces) |
| Error handling and fallbacks | [Error Handling](#error-handling) |
| Async patterns and timeouts | [Async Patterns](#async-patterns) |
| Constructor injection and singletons | [Dependency Injection](#dependency-injection) |
| Environment variable conventions | [Configuration Pattern](#configuration-pattern) |
| Naming rules | [Naming Conventions](#naming-conventions) |
| Import organization | [Import Organization](#import-organization) |
| What NOT to do | [Anti-Patterns to Avoid](#anti-patterns-to-avoid) |

</details>

---

## Module Design

### Package Structure

Every feature sub-package under `src/cinemind/` follows this pattern:

```
cinemind/<feature>/
├── __init__.py      # Public API — re-exports only what consumers need
├── <primary>.py     # Main implementation
├── <secondary>.py   # Supporting modules
└── ...
```

**The `__init__.py` is the public interface.** Consumers import from the package, never from internal modules:

```python
# GOOD — import from the package
from cinemind.extraction import IntentExtractor, StructuredIntent

# BAD — import from internal module
from cinemind.extraction.intent_extraction import IntentExtractor
```

### Single Responsibility

Each module has one job:

| Pattern | Example |
|---------|---------|
| One class per concern | `CandidateExtractor` does extraction only, not verification |
| Pure functions for transforms | `normalize_title()` takes input, returns output, no side effects |
| Orchestrators don't compute | `CineMind.search_and_analyze()` calls subsystems; logic lives in them |

---

## Dataclass Conventions

Use `@dataclass` for all data structures. Never use plain dicts for structured data crossing module boundaries.

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VerifiedFact:
    fact_type: str
    value: str
    verified: bool
    source_url: str
    confidence: float
    conflicts: List[str] = None

    def __post_init__(self) -> None:
        if self.conflicts is None:
            self.conflicts = []
```

### Rules

- All fields have type annotations
- Mutable defaults use `None` + `__post_init__`
- Dataclasses are the contract between modules — changing fields is a breaking change

---

## Protocol Interfaces

Use `typing.Protocol` for service boundaries — not `abc.ABC`:

```python
from typing import Protocol, Dict, Any, Optional

class IAgentRunner(Protocol):
    async def search_and_analyze(
        self,
        user_query: str,
        use_live_data: bool = True,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]: ...
```

**When to use Protocols:**
- Between layers (workflows → domain)
- For test substitution (inject fakes)
- When multiple implementations exist (LLMClient)

**When NOT to use Protocols:**
- Within a single package (just import directly)
- For simple functions (use plain function signatures)

---

## Error Handling

### Principle: Degrade, Don't Crash

```python
# GOOD — graceful degradation
try:
    result = await tavily_search(query)
except Exception:
    logger.exception("Tavily search failed, falling back to DuckDuckGo")
    result = await duckduckgo_search(query)

# BAD — let it crash
result = await tavily_search(query)  # unhandled exception kills the request
```

### Structured Return Types

For operations that can partially succeed, return typed results:

```python
@dataclass
class ValidationResult:
    valid: bool
    warnings: List[str]
    auto_fixes: List[str]
    original: str
    fixed: str
```

### Logging

- Use `logging.getLogger(__name__)` per module
- Log at appropriate levels: `error` for failures, `warning` for fallbacks, `info` for key decisions, `debug` for details
- Always include context: query, request_id, timing

---

## Async Patterns

### Async Functions

All pipeline functions are `async`:

```python
async def search_and_analyze(self, user_query: str, ...) -> Dict[str, Any]:
    # Cache check (sync, fast)
    cached = self.cache.lookup(user_query)
    if cached:
        return cached

    # Async operations
    plan = await self.planner.plan(user_query)
    results = await self.search_engine.search(user_query, plan.tool_plan)
    ...
```

### Timeout Wrapping

```python
import asyncio

try:
    result = await asyncio.wait_for(
        agent.search_and_analyze(query),
        timeout=timeout_seconds,
    )
except asyncio.TimeoutError:
    logger.error("Agent timed out after %.0fs", timeout_seconds)
    return None, "Request timed out"
```

---

## Dependency Injection

### Constructor Injection

```python
class CineMind:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or HttpChatLLMClient(...)  # from CINEMIND_LLM_* in production
        self.search = SearchEngine()
        self.planner = RequestPlanner(
            router=RequestTypeRouter(),
            intent_extractor=IntentExtractor(),
            tool_planner=ToolPlanner(),
        )
```

### Factory Functions for Singletons

```python
_default_cache: Optional[MediaCache] = None

def get_default_media_cache() -> MediaCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = MediaCache()
    return _default_cache

def set_default_media_cache(cache: MediaCache) -> None:
    """For testing — inject a mock."""
    global _default_cache
    _default_cache = cache
```

---

## Configuration Pattern

### Environment Variables

All configuration comes from environment variables, read via `os.environ.get()`:

```python
import os

KAGGLE_ENABLED = os.environ.get("KAGGLE_ENABLED", "true").lower() == "true"
CACHE_TTL_HOURS = int(os.environ.get("CACHE_DEFAULT_TTL_HOURS", "24"))
```

### Rules

- Always provide a sensible default
- Parse to the correct type immediately
- Document every env var in `docs/features/config/CONFIGURATION.md`
- Add to `.env.example` with a comment

---

## Naming Conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| Packages | `snake_case` | `cinemind/extraction/` |
| Modules | `snake_case` | `candidate_extraction.py` |
| Classes | `PascalCase` | `CandidateExtractor` |
| Functions | `snake_case` | `extract_movie_titles()` |
| Constants | `UPPER_SNAKE_CASE` | `MEDIA_FOCUS_SINGLE` |
| Dataclass fields | `snake_case` | `source_tier` |
| Type aliases | `PascalCase` | `SearchDecision` |
| Private methods | `_leading_underscore` | `_score_candidate()` |

---

## Import Organization

```python
# 1. Standard library
import re
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass

# 2. Third-party packages
from fastapi import FastAPI
import httpx

# 3. Internal packages (absolute imports)
from cinemind.extraction import IntentExtractor
from cinemind.planning import SourcePolicy
```

Never use relative imports across packages. Within a package, relative imports are acceptable in `__init__.py`:

```python
# In cinemind/extraction/__init__.py
from .title_extraction import extract_movie_titles
from .intent_extraction import IntentExtractor
```

---

## Anti-Patterns to Avoid

| Anti-Pattern | Instead Do |
|-------------|-----------|
| Dict as data contract | Use `@dataclass` |
| Catching `Exception` silently | Log the error, then degrade |
| Business logic in `api/main.py` | Put it in a feature module, call from workflow |
| Direct `import cinemind.agent.core` in workflows | Use `IAgentRunner` Protocol |
| Hardcoding URLs or API keys | Use environment variables |
| `print()` for debugging | Use `logging.getLogger(__name__)` |
| Global mutable state | Use factory functions with `get_`/`set_` pattern |
