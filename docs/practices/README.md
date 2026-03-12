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


---

## Core Principles

These apply across the entire codebase:

1. **Deterministic before AI** — use rule-based logic first; LLM is a fallback, not a default
2. **Dependency direction** — imports flow downward: API → Workflows → Agent → Feature modules → Foundation
3. **Thin orchestration** — orchestrators (workflows, API) contain no business logic
4. **Graceful degradation** — missing API keys or failed services produce fallback behavior, not crashes
5. **Observability built-in** — every request is tracked, timed, and queryable
6. **No build step for frontend** — vanilla JS, no bundler, no transpiler

