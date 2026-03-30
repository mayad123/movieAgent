# Backlog

> **Purpose:** Prioritized work items with clear user value, engineering scope, dependencies, and testing implications.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to... | Jump to |
|-------------|---------|
| See prioritization rubric | [Prioritization](#prioritization) |
| Add a new backlog item | [Backlog Item Template](#backlog-item-template) |
| See the current backlog list | [Items](#items) |
| Understand test impact expectations | [Testing Expectations](#testing-expectations) |

</details>

---

## Prioritization

Rank items using:

- **User value**: how much it improves outcomes or usability
- **Risk reduction**: reduces external dependency or contract brittleness
- **Scope**: how many layers/packages are impacted
- **Testability**: can we verify safely with existing tests?

## Backlog Item Template

Use this structure for each item:

```text
ID:
Title:
Problem:
User value:
Scope (frontend/backend/docs):
Primary docs to consult:
Dependencies / also-check:
Risks:
Tests to run:
Definition of done:
```

## Testing Expectations

Every item must specify at least:

- **Tests to run** from feature docs’ `Test Coverage` sections (or from `docs/practices/TESTING_PRACTICES.md`).
- **If tests are missing**, explicitly note the gap and propose where to add them.

References:
- Testing practices: [`docs/practices/TESTING_PRACTICES.md`](../practices/TESTING_PRACTICES.md)
- Feature docs index: [`docs/features/README.md`](../features/README.md)

## Items

### Projects workspace (MVP — delivered)

MVP is in production code: `ProjectsStore`, `/api/projects*`, `web/projects.html`. Track **optional** follow-ups (chat integration, auth, non-file store) as new backlog IDs when prioritized.

### Movie Details View: Hero & Data Stabilization (delivered — see roadmap Phase 0.A)

```text
ID: MDX-1
Title: Fix Movie Details hero image usability
Problem: The hero image on the full-screen Movie Details (“More Info”) page is visually awkward and hard to work with.
User value: Users can quickly recognize the movie and context without the image overwhelming the page.
Scope (frontend/backend/docs): frontend + docs
Primary docs to consult: docs/features/web/WEB_FRONTEND.md, docs/practices/CSS_STYLE_GUIDE.md
Dependencies / also-check: src/cinemind/media (media enrichment), TMDB image config sizes.
Risks: Overfitting to specific aspect ratios; layout regressions on small screens.
Tests to run: tests/smoke/test_playground_smoke.py + manual Movie Details UI checks across a few titles.
Definition of done: Hero image has a consistent, usable size across viewports; text content remains readable; no overlap with composer/sidebar.
```

```text
ID: MDX-2
Title: Increase Movie Details data richness using existing contracts
Problem: The Movie Details page shows limited metadata, blocking Phase 1 feature depth work.
User value: Users see meaningful Story/Credits/Meta sections for most movies without backend changes.
Scope (frontend/backend/docs): frontend + docs
Primary docs to consult: docs/features/web/WEB_FRONTEND.md, docs/features/media/MEDIA_ENRICHMENT.md
Dependencies / also-check: normalizeMeta() fields, MovieResponse media/enrichment data, where-to-watch integration.
Risks: Over-reliance on fields that are sparse; cluttered layout if all fields are dumped without hierarchy.
Tests to run: tests/smoke/test_playground_smoke.py + manual checks on several movies (rich vs sparse metadata).
Definition of done: Story, Credits, and Meta sections consistently show populated data when available and hide cleanly when not.
```

### AI Response UX: Natural + Interfaceable (Phase 0 delivered)

#### Prioritized implementation methods (recommended order)

1. **Frontend readability first (low risk / immediate UX win)**
   Improve rendering of assistant responses in `web/js/modules/messages.js` so paragraphs/lists are readable without changing backend contracts.
2. **Template contract next (high leverage)**
   Update `src/cinemind/prompting/templates.py` so common intents naturally produce structured, skimmable outputs.
3. **Validator guardrails (stability)**
   Extend `src/cinemind/prompting/output_validator.py` to detect/repair robotic boilerplate and structure violations.
4. **Regression scenarios (prevent drift)**
   Add a small set of offline scenarios that assert structure-level outcomes and keep the “CineMind voice” from regressing.

#### Deliverables and expectations

- **Deliverables**
  - Updated frontend message rendering (safe structure, no XSS)
  - Updated backend templates + validator rules
  - New scenario/regression coverage for response style
  - Updated docs: `docs/features/prompting/PROMPT_PIPELINE.md` and `docs/features/web/WEB_FRONTEND.md`
- **Expectations**
  - No API schema changes required
  - “Machine-like” boilerplate is materially reduced (measured by scenario assertions + spot checks)
  - Multi-item answers are scannable (lists/sections)
  - Failures remain contained (no broken attachments/media strips)

```text
ID: AIUX-1
Title: Update response templates for UI-friendly structure and tone
Problem: Responses feel machine-like and hard to scan in the chat UI.
User value: Faster comprehension, premium feel, easier interaction with multi-item answers.
Scope (frontend/backend/docs): backend + docs
Primary docs to consult: docs/features/prompting/PROMPT_PIPELINE.md, docs/features/planning/REQUEST_PLANNING.md
Dependencies / also-check: OutputValidator rules; request_type ↔ template mapping.
Risks: Over-constraining the model; regressions for edge-case intents.
Tests to run: tests/unit/prompting/ tests/contract/test_prompt_builder_contract.py tests/test_scenarios_offline.py
Definition of done: Templates produce short sections/lists; forbidden machine phrases are rare; scenarios remain green. (Status: delivered in Phase 0.)
```

```text
ID: AIUX-2
Title: Extend OutputValidator to reduce machine-like phrasing and enforce formatting rules
Problem: Even good prompts can produce robotic preambles and dense paragraphs.
User value: Consistent “CineMind voice” and predictable structure.
Scope (frontend/backend/docs): backend + docs
Primary docs to consult: docs/features/prompting/PROMPT_PIPELINE.md
Dependencies / also-check: ResponseTemplate.required_elements / structure_hints.
Risks: False positives removing legitimate content; “auto-fix” overreach.
Tests to run: tests/unit/prompting/test_output_validator.py tests/integration/test_agent_offline_e2e.py
Definition of done: Validator flags/repairs robotic boilerplate; does not break legitimate answers.
```

```text
ID: AIUX-3
Title: Improve frontend rendering for assistant messages (lightweight structure)
Problem: Chat bubble renders assistant text as a single text node (no paragraphs/lists).
User value: Better readability and interfaceability without adding a frontend framework.
Scope (frontend/backend/docs): frontend + docs
Primary docs to consult: docs/features/web/WEB_FRONTEND.md, docs/practices/FRONTEND_PATTERNS.md
Dependencies / also-check: normalizeMeta() output; message rendering flow in web/js/modules/messages.js.
Risks: HTML injection (must remain safe); inconsistent formatting across browsers.
Tests to run: tests/smoke/test_playground_smoke.py + manual UI verification via playground server
Definition of done: Assistant output renders paragraphs/lists safely; no XSS; existing movie strips/attachments still render.
```

```text
ID: AIUX-4
Title: Add “response style” regression scenarios
Problem: Tone/format regressions are hard to catch via unit tests alone.
User value: Prevents drifting back to robotic responses.
Scope (frontend/backend/docs): tests + docs
Primary docs to consult: docs/practices/TESTING_PRACTICES.md
Dependencies / also-check: Scenario harness in tests/test_scenarios_offline.py.
Risks: Brittle assertions on text.
Tests to run: tests/test_scenarios_offline.py
Definition of done: Add a small set of gold scenarios that assert high-level structure (not exact phrasing). (Status: delivered in Phase 0; extend with new scenarios as needed.)
```

### Media Alignment: Posters Match Responses

```text
ID: MDX-3
Title: Align posters/media with resolved movie identities
Problem: Sometimes the response text and poster/media do not refer to the same movie; placeholders like "Tell me more about Inception" become media titles or links with "#" urls.
User value: Users only see posters and movie cards that match what the assistant is actually talking about, or no media at all when resolution is uncertain.
Scope (frontend/backend/docs): backend (media enrichment + extraction) + frontend + docs
Primary docs to consult: docs/features/media/MEDIA_ENRICHMENT.md, docs/features/web/WEB_FRONTEND.md
Dependencies / also-check: src/cinemind/media (media_enrichment, media_focus, attachment_intent_classifier), normalizeMeta(), posters.js, tests/unit/media/test_media_alignment.py
Risks: Overly strict rules could hide useful media when data is slightly incomplete; TMDB outages reduce media frequency.
Tests to run: tests/unit/media/test_media_alignment.py, tests/unit/media/test_media_enrichment.py, tests/test_scenarios_offline.py (media-related scenarios), tests/smoke/test_playground_smoke.py
Definition of done: For representative scenarios (e.g., "Tell me more about Inception"), media_strip and attachments always match resolved movie identities; when resolution fails or is low confidence, media_strip and primary_movie sections are omitted rather than populated with query-based placeholders.
```

### Sub-context Movie Hub Hardening: Parsing Contract Stability

```text
ID: HUBX-1
Title: Harden genre-block parsing + narrowing for Sub-context Movie Hub
Problem: The Movie Hub UX relies on strict plain-text parsing of assistant output (genre blocks + numbered `Title (Year)` lines) and then enrichment/dedup; small prompt/validator drifts can break the contract or reduce the “valid TMDB-resolved titles” count.
User value: More reliable hub population (fewer empty/partial hubs), better UX continuity, and safer future prompt/LLM tuning.
Scope (frontend/backend/docs): backend parsing + API response shaping + frontend rendering/retry behavior + docs
Primary docs to consult: docs/features/web/WEB_FRONTEND.md, docs/features/api/API_SERVER.md, docs/features/media/MEDIA_ENRICHMENT.md, docs/features/web/WEB_SUB_CONTEXT_PAGE.md, docs/features/media/MEDIA_ENRICHMENT.md
Dependencies / also-check: src/cinemind/media/movie_hub_genre_parsing.py (parse_movie_hub_genre_buckets), src/cinemind/media/movie_hub_filtering.py (filter_movie_hub_clusters_by_question), TMDB helper `src/integrations/tmdb/movie_metadata.py`, and hub retry logic in web/js/modules/layout.js
Risks: Parsing false-negatives could hide valid candidates; filtering could over-prune when TMDB metadata is incomplete; stricter parsing may increase empty-state frequency under TMDB outages.
Tests to run: tests/unit/media/test_movie_hub_genre_parsing.py, tests/unit/media/test_movie_hub_filtering.py, tests/unit/media/test_movie_hub_deduping.py, tests/unit/media/test_media_alignment.py, tests/test_scenarios_offline.py (hub-related regression scenarios), tests/smoke/test_playground_smoke.py (manual UI checks)
Definition of done: Hub parsing yields stable genre buckets (>=20 valid genre movies in the common auto-load path under normal conditions); strict formatting contract is enforced with safe fallbacks; question-driven narrowing either returns a non-empty narrowed hub or preserves the anchored universe on failure (no empty hub regressions).
```

```text
ID: APIDX-1
Title: Reconcile `API_SERVER.md` with current API contracts + dependencies
Problem: `docs/features/api/API_SERVER.md` drifted from runtime behavior (endpoints, request param names, response schema fields, and dependency/wiring notes), increasing integration risk and making it harder for contributors to modify the API safely.
User value: Contributors and integrators can rely on the docs to match what the backend + frontend actually do, reducing contract brittleness.
Scope (frontend/backend/docs): docs (API server feature doc) + doc-to-code consistency validation
Primary docs to consult: docs/features/api/API_SERVER.md, src/api/main.py, src/schemas/api.py, web/js/modules/api.js, web/js/modules/movie-details.js
Dependencies / also-check: Sub-context hub marker parsing + `movieHubClusters` generation (`cinemind.media.movie_hub_genre_parsing`, `cinemind.media.movie_hub_filtering`), TMDB-backed Movie Details endpoint (`MovieDetailsResponse` contract).
Risks: Future contract changes reintroduce drift unless we keep docs as “contract-first” and validate against existing smoke/tests.
Tests to run: tests/smoke/test_playground_smoke.py + tests/unit/integrations/test_where_to_watch_api.py + tests/integration/test_agent_offline_e2e.py (and run hub/unit tests if marker/cluster logic changed recently).
Definition of done: `API_SERVER.md` accurately lists implemented endpoints and their request/response contracts; hub marker JSON + deterministic filtering behavior are documented; observability paths and query params are correct; no stale env var references remain; docs include relevant dependency/wiring notes to prevent runtime errors. (Status: addressed/delivered by syncing `API_SERVER.md`, `CONFIGURATION.md`, and frontend contract mirrors to `src/schemas/api.py`.)
```

### Poster / TMDB latency — longer bets (out of scope for initial perf pass)

```text
ID: TMDB-PERF-1
Title: Cross-process TMDB resolve cache (e.g. Redis)
Problem: In-process LRU caches do not help multi-worker deployments or cold starts.
User value: Fewer duplicate TMDB calls across users and instances.
Scope (frontend/backend/docs): backend (cache layer) + ops + docs
Primary docs to consult: docs/features/media/MEDIA_ENRICHMENT.md, docs/features/integrations/EXTERNAL_INTEGRATIONS.md
Dependencies / also-check: Resolver cache key semantics, TMDB rate limits, invalidation strategy.
Risks: Stale resolves if TTL too long; operational complexity.
Tests to run: tests/unit/integrations/test_tmdb_resolver.py + integration tests for cache behavior if added.
Definition of done: Documented deployment option; measurable hit rate; safe TTL defaults.
```

```text
ID: TMDB-PERF-2
Title: Overlap TMDB resolution with LLM generation where titles are predictable
Problem: Media enrichment currently runs after the assistant reply is fully generated.
User value: Lower perceived latency to first poster.
Scope (frontend/backend/docs): agent pipeline + API contracts + docs
Primary docs to consult: docs/features/agent/AGENT_CORE.md, docs/features/media/MEDIA_ENRICHMENT.md
Dependencies / also-check: Title extraction reliability before answer exists; race/cancellation semantics.
Risks: Wrong poster if predicted title disagrees with final answer; added complexity.
Tests to run: tests/unit/media/test_media_enrichment.py, integration/agent flows.
Definition of done: Measurable wall-clock improvement without regressing media alignment tests.
```

```text
ID: TMDB-PERF-3
Title: Progressive Movie Hub poster loading (API + web)
Problem: Large hub grids wait for all poster enrichments before users see a full grid.
User value: Faster first paint; optional fill-in for remaining cards.
Scope (frontend/backend/docs): API + web + docs
Primary docs to consult: docs/features/api/API_SERVER.md, docs/features/web/WEB_FRONTEND.md
Dependencies / also-check: HUB_ENRICH_POSTERS_LIMIT semantics, batch endpoint design.
Risks: UI flicker; duplicate TMDB load without dedupe.
Tests to run: tests/unit/media/test_movie_hub_filtering.py, web smoke/manual hub checks.
Definition of done: Documented contract for lazy or second-phase poster fetch; acceptable UX.
```

### Poster Caching Hardening (low-risk-first)

```text
ID: PCACHE-1
Title: Tune existing poster/resolve/metadata cache TTLs and add cache-path metrics
Problem: Sub-context poster latency remains inconsistent due to cache miss spikes and limited visibility into hit/miss behavior.
User value: Faster and more predictable poster loading without changing API contracts or UI behavior.
Scope (frontend/backend/docs): backend + docs
Primary docs to consult: docs/features/media/MEDIA_ENRICHMENT.md, docs/features/integrations/EXTERNAL_INTEGRATIONS.md, docs/features/api/API_SERVER.md
Dependencies / also-check: resolve cache env vars, metadata memo TTL, media cache poster retention, existing timing logs in api/main.py.
Risks: Overly long TTLs can increase stale data windows; noisy metrics can reduce signal quality.
Tests to run: tests/unit/integrations/test_tmdb_resolver.py, tests/unit/integrations/test_tmdb_movie_metadata.py, tests/unit/media/test_media_alignment.py
Definition of done: Cache knobs are documented and tuned with baseline metrics showing improved hit ratio and reduced p95 latency on sub-context hub flows, with no schema/UI regressions.
```

```text
ID: PCACHE-2
Title: Introduce ID-first poster cache keying and hot-path dedupe in hub enrichment
Problem: Title/year text variance causes avoidable misses and duplicate TMDB lookups in repeated sub-context turns.
User value: More reliable poster continuity and lower latency during follow-up questions.
Scope (frontend/backend/docs): backend + docs
Primary docs to consult: docs/features/media/MEDIA_ENRICHMENT.md, docs/features/web/WEB_SUB_CONTEXT_PAGE.md
Dependencies / also-check: src/api/main.py hub flow, media_enrichment dedupe behavior, TMDB resolve cache semantics.
Risks: Incorrect key migration could suppress valid updates; over-deduping can reduce candidate diversity.
Tests to run: tests/unit/media/test_movie_hub_filtering.py, tests/unit/media/test_media_alignment.py, tests/unit/extraction/test_response_movie_extractor.py
Definition of done: Hub enrichment paths prioritize tmdbId-based cache reuse when available and avoid duplicate resolves per request while preserving output quality.
```

```text
ID: PCACHE-3
Title: Add shared L2 cache for TMDB resolve/poster/metadata with L1 fallback
Problem: In-process caching loses warm state on restart and does not share wins across workers.
User value: Better warm performance and fewer repeated external calls in real deployments.
Scope (frontend/backend/docs): backend + ops + docs
Primary docs to consult: docs/features/integrations/EXTERNAL_INTEGRATIONS.md, docs/features/media/MEDIA_ENRICHMENT.md
Dependencies / also-check: shared cache provider selection, env-based feature toggles, invalidation/versioning and negative cache TTL policy.
Risks: Operational complexity and stale-data risks if invalidation/versioning is weak.
Tests to run: tests/unit/integrations/test_tmdb_resolver.py, tests/unit/integrations/test_tmdb_movie_metadata.py, integration tests for L1/L2 fallback behavior
Definition of done: Shared cache is optional/toggleable, preserves existing behavior when disabled, and shows measurable warm-hit improvements across restarts.
```

```text
ID: PCACHE-4
Title: Optimize sub-context follow-up narrowing using cached candidate universe first
Problem: Follow-up sub-context queries often recompute expensive poster candidate work even when the candidate universe is stable.
User value: Faster time-to-first-useful-hub for conversational narrowing in sub-context.
Scope (frontend/backend/docs): frontend + backend + docs
Primary docs to consult: docs/features/web/WEB_SUB_CONTEXT_PAGE.md, docs/features/api/API_SERVER.md, docs/features/media/MEDIA_ENRICHMENT.md
Dependencies / also-check: hub replay logic in web/js/modules/layout.js and messages.js, backend attach_movie_hub_clusters branch behavior.
Risks: Stale candidate universes could over-constrain results; replay keying must avoid serving incorrect state.
Tests to run: tests/unit/media/test_movie_hub_filtering.py, tests/test_scenarios_offline.py, tests/smoke/test_playground_smoke.py + manual sub-context replay checks
Definition of done: Follow-up narrowing reuses cached candidate universes safely, preserving deterministic behavior and stale-request safeguards while lowering median hub turnaround.
```

