---
name: cinemind-api-contracts
description: >-
  Aligns FastAPI routes and Pydantic schemas with integration tests and web clients.
  Use when editing src/api/, src/schemas/, JSON response shapes, endpoint URLs, error
  bodies, or OpenAPI-visible behavior. Prefer verifying contracts against a running
  server and the live web client (online); pytest covers offline-backed contracts.
---

# CineMind API and schema contracts

## Canonical references

- **API behavior and structure:** [`docs/features/api/API_SERVER.md`](../../../docs/features/api/API_SERVER.md)
- **What tests cover:** [`docs/practices/code-review/TEST_COVERAGE_MAP.md`](../../../docs/practices/code-review/TEST_COVERAGE_MAP.md) — API / integrations sections
- **Post-edit pytest mapping:** [`docs/AIbuilding/CURSOR_TEST_HOOKS.md`](../../../docs/AIbuilding/CURSOR_TEST_HOOKS.md) — `src/api/` and `src/schemas/` → unit integrations + integration tests

## Code touchpoints

- **Routes and app wiring:** [`src/api/`](../../../src/api/) (e.g. `main.py` patterns)
- **Shared models:** [`src/schemas/`](../../../src/schemas/)
- **Web client:** [`web/js/modules/api.js`](../../../web/js/modules/api.js) — must stay consistent with paths, query params, and JSON field names exposed to the UI

## Workflow

1. **Identify contract surface** — Request/response models, status codes, and error shapes consumers rely on (`api.js`, integration tests).
2. **Change schemas first** — Update Pydantic models and any `response_model` / validation paths; avoid silent field renames without updating clients.
3. **Update tests** — [`tests/unit/integrations/`](../../../tests/unit/integrations/) for FastAPI-level contracts; [`tests/integration/`](../../../tests/integration/) where offline agent/API wiring is exercised.
4. **Update docs** — API_SERVER.md or feature docs when endpoints or env requirements change.
5. **Verify online** — Hit endpoints from [`web/js/modules/api.js`](../../../web/js/modules/api.js) flows or manual calls with a running API; confirm status codes and payload shapes.
6. **Run focused pytest** — `make test-unit` on touched integration test files, or full `tests/integration/` when routing behavior spans modules (offline CI).

## Coordination

Media and “movie hub” JSON shapes may also be covered under `tests/unit/media/`; check TEST_COVERAGE_MAP when responses include enrichment payloads.
