# Engineering Best Practices

> Standards and conventions for the CineMind codebase. Follow these when making changes or adding features.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need guidance on... | Read |
|----------------------|------|
| Python module design, dataclasses, error handling | [Backend Patterns](BACKEND_PATTERNS.md) |
| JS modules, state, DOM, callbacks | [Frontend Patterns](FRONTEND_PATTERNS.md) |
| CSS naming, tokens, responsive design | [CSS Style Guide](CSS_STYLE_GUIDE.md) |
| Adding new packages, integrations, endpoints | [Directory Structure](DIRECTORY_STRUCTURE.md) |
| Writing and running tests | [Testing Practices](TESTING_PRACTICES.md) |

</details>

---

## Index


| Document                                      | Covers                                                         | When to Read                        |
| --------------------------------------------- | -------------------------------------------------------------- | ----------------------------------- |
| [Backend Patterns](BACKEND_PATTERNS.md)       | Python conventions, module design, error handling, async       | Writing or modifying Python code    |
| [Frontend Patterns](FRONTEND_PATTERNS.md)     | JS module conventions, state management, DOM patterns          | Writing or modifying frontend code  |
| [CSS Style Guide](CSS_STYLE_GUIDE.md)         | CSS architecture, naming, custom properties, responsive design | Styling changes                     |
| [Directory Structure](DIRECTORY_STRUCTURE.md) | How to create new modules, packages, and integrations          | Adding new features or sub-packages |
| [Testing Practices](TESTING_PRACTICES.md)     | Test organization, running tests, writing tests                | Writing or running tests            |
| [Code Review Playbook](code-review/README.md) | PR review checklist: coverage mapping, when-to-run, errors/violations | Making test-impacting changes        |


---

## Core Principles

These apply across the entire codebase:

1. **Deterministic before AI** — use rule-based logic first; LLM is a fallback, not a default
2. **Dependency direction** — imports flow downward: API → Workflows → Agent → Feature modules → Foundation
3. **Thin orchestration** — orchestrators (workflows, API) contain no business logic
4. **Graceful degradation** — missing API keys or failed services produce fallback behavior, not crashes
5. **Observability built-in** — every request is tracked, timed, and queryable
6. **No build step for frontend** — vanilla JS, no bundler, no transpiler

---
## External API Contract Testing (TMDB, Watchmode, etc)

External providers (TMDB, Watchmode, Kaggle, etc) can return unexpected payloads or fail intermittently. We test contracts so downstream code can rely on stable shapes.

### Methodology

For each external integration helper (for example `src/integrations/tmdb/*`):
1. **Happy-path contract**: mock the network response and assert the parsed output type/shape (lists are lists, required keys exist, truncation/ordering works).
2. **No-credentials path**: if the access token is missing/empty, helpers must return safe empty outputs (`[]` or `{}`) and not fabricate data.
3. **Failure path**: mock malformed JSON / timeouts / exceptions and assert the helper returns safe empties (never raises).
4. **Downstream compatibility**: assert the output matches what rule-based logic consumes (e.g., hub filtering expects `tmdbId`-carrying movie objects and list-of-strings for cast/genre/keywords).

For API endpoints that expose these contracts (for example `GET /api/watch/where-to-watch`):
1. Use `TestClient` and patch the underlying client/helper.
2. Assert HTTP status + normalized response keys (not full provider-specific payloads).
3. Include explicit tests for: missing keys (500), not found (404), rate limiting (429), and successful normalization (200).

### Where to Put Tests

- Integration helpers → `tests/unit/integrations/`
- Media/contract mapping logic → `tests/unit/media/`
- Endpoint wiring + normalized response shapes → `tests/unit/integrations/` or `tests/smoke/` depending on how isolated it is

