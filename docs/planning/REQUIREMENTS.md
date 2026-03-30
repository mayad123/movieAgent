# Requirements

> **Purpose:** Define functional and non-functional requirements for CineMind features, and provide acceptance criteria patterns that trace to feature docs and tests.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to... | Jump to |
|-------------|---------|
| See functional requirements | [Functional Requirements](#functional-requirements) |
| See non-functional requirements | [Non-Functional Requirements](#non-functional-requirements) |
| See acceptance criteria patterns | [Acceptance Criteria Patterns](#acceptance-criteria-patterns) |
| Map requirements to feature docs | [Traceability](#traceability) |

</details>

---

## Functional Requirements

### FR-1: Movie question answering

- The system answers movie-related questions (cast, director, release date, runtime, comparisons).
- Responses should provide sources where applicable.

Primary docs:
- Agent pipeline: [`docs/features/agent/AGENT_CORE.md`](../features/agent/AGENT_CORE.md)
- Planning: [`docs/features/planning/REQUEST_PLANNING.md`](../features/planning/REQUEST_PLANNING.md)
- Search: [`docs/features/search/SEARCH_ENGINE.md`](../features/search/SEARCH_ENGINE.md)

### FR-2: Media enrichment

- Responses may include posters/scenes and attachments where available.
- Missing images must not break message rendering.
- Posters and attachments must **only** be shown when they correspond to confidently resolved movie identities; when resolution is uncertain, media should be omitted rather than mismatched.

Primary docs:
- Media: [`docs/features/media/MEDIA_ENRICHMENT.md`](../features/media/MEDIA_ENRICHMENT.md)
- Integrations: [`docs/features/integrations/EXTERNAL_INTEGRATIONS.md`](../features/integrations/EXTERNAL_INTEGRATIONS.md)

### FR-3: Where-to-watch availability

- The UI can request streaming availability via existing endpoint(s) and render a readable list of offers/groups.
- Failures should degrade gracefully and remain contained to the watch section.

Primary docs:
- API: [`docs/features/api/API_SERVER.md`](../features/api/API_SERVER.md)
- Web: [`docs/features/web/WEB_FRONTEND.md`](../features/web/WEB_FRONTEND.md)

### FR-4: UX surfaces and views

- New views must follow the no-build frontend module pattern and be wired via callbacks in `web/js/app.js`.

Primary docs:
- Add feature patterns: [`docs/ADD_FEATURE_CONTEXT.md`](../ADD_FEATURE_CONTEXT.md)
- Frontend patterns: [`docs/practices/FRONTEND_PATTERNS.md`](../practices/FRONTEND_PATTERNS.md)

### FR-5: Projects (curated lists)

- Users can create projects and attach movie assets via the REST API; data persists to the configured JSON store path.
- List/detail/add/delete operations behave deterministically and match `src/schemas/api.py` models.
- Failures degrade gracefully (clear errors, no silent data loss).

Primary docs:
- API: [`docs/features/api/API_SERVER.md`](../features/api/API_SERVER.md)
- Config: [`docs/features/config/CONFIGURATION.md`](../features/config/CONFIGURATION.md)

## Non-Functional Requirements

### NFR-1: Reliability and graceful degradation

- External failures (keys missing, rate limiting) should not crash the app.
- The system should return a usable result in PLAYGROUND mode.

### NFR-2: Maintainability and change safety

- Changes should be localized to the owning module/file.
- Contracts should remain stable; schema changes require coordinated updates.

Primary docs:
- Change routing and dependency map: [`docs/AI_CONTEXT.md`](../AI_CONTEXT.md)

### NFR-3: UX consistency

- UI changes reuse existing typography/color/spacing tokens.
- Avoid introducing new design systems or heavy abstractions.

Primary docs:
- CSS guide: [`docs/practices/CSS_STYLE_GUIDE.md`](../practices/CSS_STYLE_GUIDE.md)

### NFR-4: Testability

- New feature work must identify which tests should be run and whether new tests are required.

Primary docs:
- Testing: [`docs/practices/TESTING_PRACTICES.md`](../practices/TESTING_PRACTICES.md)

### NFR-5: AI Response UX (Natural + Interfaceable)

- Assistant messages should be **scannable**:
  - Short paragraphs and meaningful line breaks
  - Lists for multi-item outputs (recommendations, casts, comparisons)
  - Minimal preamble; avoid “I can help…” and other machine-like filler
- Assistant messages should be **render-friendly** in the current UI:
  - Avoid wall-of-text blocks when a structured response is appropriate
  - Use predictable separators/headings that can be lightly styled in the frontend without requiring a new API schema
- Style should be **consistent with CineMind**:
  - Movie titles and years are presented consistently
  - Avoid technical pipeline terms (“dataset”, “tier”, “confidence framework”)

Primary docs:
- Prompt pipeline: [`docs/features/prompting/PROMPT_PIPELINE.md`](../features/prompting/PROMPT_PIPELINE.md)
- Web frontend: [`docs/features/web/WEB_FRONTEND.md`](../features/web/WEB_FRONTEND.md)

#### Deliverables (definition)

- **Backend prompt contract**: updated templates that reliably yield scannable responses for major intents (short paragraphs + lists, as described in `docs/features/prompting/PROMPT_PIPELINE.md`).
- **Backend guardrails**: validator rules that reduce boilerplate and enforce minimal structure.
- **Frontend render contract**: assistant text is displayed with lightweight structure (paragraphs/lists) safely (no HTML injection).
- **Regression coverage**: scenarios that prevent tone/format regressions without brittle exact-string matching.

#### Expectations (quality bar)

- **Tone**: direct, human, minimal filler; no “as an AI…” style preambles.
- **Structure**: consistent sectioning and lists for multi-item outputs.
- **Compatibility**: no API schema changes; works in PLAYGROUND and REAL_AGENT.
- **Safety**: rendering remains safe (escape/whitelist only); attachments/media strips continue to work.

### NFR-6: Poster caching resilience and observability

- Sub-context poster/hub flows should prefer cache reuse over repeat TMDB resolution for equivalent candidate sets.
- Cache behavior must remain safe under cold starts and partial cache misses; failures should degrade gracefully without breaking sub-context rendering.
- Cache layers must expose measurable hit/miss and latency telemetry for resolve, poster URL, and metadata bundle paths.
- Low-risk phases must avoid API schema churn and preserve user-visible contract behavior.

Primary docs:
- Media enrichment: [`docs/features/media/MEDIA_ENRICHMENT.md`](../features/media/MEDIA_ENRICHMENT.md)
- Integrations: [`docs/features/integrations/EXTERNAL_INTEGRATIONS.md`](../features/integrations/EXTERNAL_INTEGRATIONS.md)
- API server: [`docs/features/api/API_SERVER.md`](../features/api/API_SERVER.md)

#### Acceptance pattern (poster caching)

- **Phase 1 acceptance:** p50/p95 poster latency improves through cache tuning and observability only; no response schema or rendering contract changes.
- **Phase 2 acceptance:** duplicate TMDB resolve/enrichment work is reduced in hot paths using ID-first keying/dedupe while preserving output quality.
- **Phase 3 acceptance:** shared L2 cache improves warm-hit behavior across process restarts and multi-worker deployments.
- **Phase 4 acceptance:** follow-up sub-context hub interactions show lower time-to-first-useful-poster under realistic conversation replay.

## Acceptance Criteria Patterns

Use these patterns when writing requirements for new features:

- **Data availability**: Every optional field must have an explicit UI fallback or omission rule.
- **No empty blocks**: Do not render empty sections; hide section if no data.
- **Contract compatibility**: Prefer building from existing response payloads; only propose new endpoints if there is a documented gap.
- **Failure containment**: One feature’s failure (e.g. Watchmode) must not break other UI surfaces.
- **Test mapping**: Each requirement should list the tests to run (and where to add new tests if needed).
- **Response UX**: Prefer a structured, UI-friendly response (lists/sections) over monolithic paragraphs when multiple items are presented.
## Traceability

Map requirements to documentation and tests:

- Feature documentation index: [`docs/features/README.md`](../features/README.md)
- Feature test map: [`docs/practices/TESTING_PRACTICES.md`](../practices/TESTING_PRACTICES.md#feature-test-map)

