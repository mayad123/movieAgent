# Roadmap

> **Purpose:** Phased roadmap that connects product outcomes to engineering milestones and the feature docs that describe implementation boundaries.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to... | Jump to |
|-------------|---------|
| See phases at a glance | [Phase overview](#phase-overview) |
| See milestones by phase | [Phases](#phases) |
| See cross-cutting themes | [Themes](#themes) |
| See dependency / impact reminders | [Dependency considerations](#dependency-considerations) |
| Jump from roadmap items to system docs | [Doc links](#doc-links) |

</details>

---

## Phase overview

Use this table for sequencing; each phase below uses the **same section shape**: **Outcome → Status → Focus → Dependencies → Documentation**.

| Phase | Horizon | Outcome (one line) | Status (high level) |
| ----- | ------- | ------------------ | -------------------- |
| **0** | Near-term | Reliable, readable UI and contracts; graceful fallbacks | Mostly complete; residual hub/cache tuning |
| **1** | Next | Deeper UX and hub behavior **without** new core API shapes | Ready to execute once Phase 0 exits are accepted |
| **2** | Next+ | Less robotic prompts; validator + templates aligned with chat rendering | Planned; scenario tests gate tone/structure |
| **3** | Future | Richer sub-context hub and related-title emphasis | Intent recorded; contracts TBD beyond hub MVP |

---

## Phases

Each phase follows this pattern:

1. **Outcome** — what “done” means for the product.
2. **Status** — what is already true in code/docs vs still open.
3. **Focus** — the main work themes (link to backlog IDs where useful).
4. **Dependencies** — what must stay true before sequencing more work.
5. **Documentation** — authoritative feature / practice docs.

---

### Phase 0 — Stability and UX polish (near-term)

**Outcome:** The experience is reliable, readable, and consistent across major flows; missing metadata and integration failures degrade gracefully.

**Status**

- **AI Response UX (UX‑1…UX‑4 / AIUX‑1…AIUX‑4):** Delivered — structured chat rendering, templates, `OutputValidator`, offline regression scenarios, and docs.
- **Movie Details (“More Info”) stabilization (MD‑1…MD‑3 / MDX‑1…MDX‑2):** Delivered in app — hero/backdrop composition (`web/css/movie-details.css`), Story/Credits/Meta/Related/where-to-watch (`web/js/modules/movie-details.js`), sections hidden when empty; **residual** work is optional polish and device QA.
- **Media alignment (MDX‑3):** Delivered — enrichment and UI omit media when resolution is uncertain; see `tests/unit/media/test_media_alignment.py`.
- **API contract documentation (APIDX‑1):** Delivered — `API_SERVER.md`, `CONFIGURATION.md`, and client mirrors align with `src/schemas/api.py` (including `movieHubClusters`, `MovieDetailsResponse`, and **Projects** endpoints).
- **Sub-context Movie Hub (genre MVP):** Delivered — `MovieResponse.movieHubClusters` from `POST /query` when `[[CINEMIND_HUB_CONTEXT]]` is present; strict `Genre:` + numbered `Title (Year)` contract.
- **Projects workspace (MVP):** Delivered — JSON-backed `ProjectsStore`, `/api/projects*`, `web/projects.html` + `web/js/projects-app.js`; tests `tests/unit/infrastructure/test_projects_store.py`, `tests/unit/integrations/test_projects_api.py`.
- **Poster / resolve caching (PCACHE early tranche):** In progress — in-process TMDB resolve TTL/LRU cache (`src/integrations/tmdb/resolve_cache.py`) and related tuning; PCACHE‑1…4 in backlog for metrics, ID-first keying, shared L2, and replay optimization.

**Focus**

- Close out **PCACHE‑1 / PCACHE‑2** (observability + hot-path dedupe) with no schema churn.
- Harden hub parsing and narrowing (**HUBX‑1** in [`BACKLOG.md`](BACKLOG.md)); extend scenarios as the prompt contract evolves.
- Optional: Movie Details visual QA on small viewports and accessibility pass (no new contracts).

**Dependencies**

- Baseline CSS tokens and layout patterns stay consistent; no ad-hoc one-off design systems.
- Contract-first changes only when a capability cannot ship on existing `MovieResponse` / endpoints (see Phase 2 note on schema changes).

**Documentation**

- Web: [`docs/features/web/WEB_FRONTEND.md`](../features/web/WEB_FRONTEND.md), [`docs/features/web/WEB_MORE_INFO_PAGE.md`](../features/web/WEB_MORE_INFO_PAGE.md), [`docs/features/web/WEB_SUB_CONTEXT_PAGE.md`](../features/web/WEB_SUB_CONTEXT_PAGE.md)
- API: [`docs/features/api/API_SERVER.md`](../features/api/API_SERVER.md)
- Media: [`docs/features/media/MEDIA_ENRICHMENT.md`](../features/media/MEDIA_ENRICHMENT.md)

#### Phase 0.A — Movie Details (“More Info”) stabilization (complete)

**Goal:** Full-screen Movie Details is usable, information-dense, and handles sparse data — so later phases are not blocked by layout or empty sections.

| ID | Focus | Key deliverables | Status |
|----|-------|------------------|--------|
| MD‑1 | Hero image usability | Tame hero/backdrop sizing and composition | Delivered |
| MD‑2 | Data richness | Story/Credits/Meta from `MovieResponse` + enrichment | Delivered |
| MD‑3 | Missing-data behavior | Hide sections or show explicit empty/error states | Delivered |

**Exit criteria (met):** Manageable hero, populated sections when data exists, no silent empty blocks for primary sections.

---

### Phase 1 — Feature depth using existing contracts (next)

**Outcome:** Users get more value from the **same** response shapes and endpoints — richer hub behavior, tighter integration between chat and side surfaces, and incremental watch UX — without introducing new core schema unless explicitly approved.

**Status**

- **Not started as a labeled “Phase 1 complete” milestone** — Phase 0 exit items (PCACHE‑1/2, HUBX‑1 breadth) are the practical gate for focusing here.
- **Movie Details depth** is **not** duplicated here; it ships under Phase 0.

**Focus**

- **Hub beyond genre MVP:** `tone` / `cast` cluster paths, deterministic narrowing, and parsing stability (see **HUBX‑1**; reuse `movieHubClusters` and query-driven hub where possible).
- **Actionable UI:** Buttons and flows that call existing endpoints (design tokens in `base.css`, components in `media.css`, `chat.css`, etc.); track concrete tasks in [`BACKLOG.md`](BACKLOG.md).
- **Where to watch:** Improve grouping, copy, and empty/error states using `/api/watch/where-to-watch` only.
- **Projects + chat (optional):** Wire “save to project” or context carry-over from chat into the Projects store **if** product priority confirms — still contract-compatible.

**Dependencies**

- Phase 0 **PCACHE‑1/2** and hub hardening far enough along that latency and empty-hub regressions are under control.
- No Phase 1 work should re-litigate basic Movie Details layout (that is Phase 0).

**Documentation**

- Same as Phase 0 for web/API/media; add [`docs/features/web/WEB_HOME_PAGE.md`](../features/web/WEB_HOME_PAGE.md) when home/hub layout changes.

---

### Phase 2 — Prompt pipeline quality (next+)

**Outcome:** System/developer prompts and assembled user prompts are less robotic and better aligned with what the chat UI can render (paragraphs, lists) — by changing **what we send the model** and how we validate shape, not by inventing parallel “human UI” API fields.

**Status:** Planned; implementation lands in `PromptBuilder`, `templates.py`, `output_validator.py`, and scenario tests.

**Focus**

- Tighten `ResponseTemplate` / planner copy, developer-system strings, and validators per [`docs/features/prompting/PROMPT_PIPELINE.md`](../features/prompting/PROMPT_PIPELINE.md) and [`docs/CHANGE_FEATURE_CONTEXT.md`](../CHANGE_FEATURE_CONTEXT.md).
- Keep offline + integration tests green; extend scenarios when tightening tone or structure.

**Dependencies**

- Schema / endpoint changes remain **explicit and rare**; document in `API_SERVER.md`, `CONFIGURATION.md`, and `WEB_FRONTEND.md` only when the capability cannot ship on current contracts.

**Documentation**

- [`docs/features/prompting/PROMPT_PIPELINE.md`](../features/prompting/PROMPT_PIPELINE.md)
- [`docs/features/web/WEB_FRONTEND.md`](../features/web/WEB_FRONTEND.md)

---

### Phase 3 — Sub-context and focused movie conversations (future)

**Outcome:** Sub-context (“talk more about this movie”) feels like a **movie-focused** surface: anchored title, similar/related discovery, and hub layouts that do not merely mirror main chat.

**Status:** Intent only; scope beyond the current hub shell is intentionally open for future requirements work.

**Focus**

- Tailored **Sub-context Movie Hub** layout; deeper use of `contextMovie.relatedMovies` / `similar`.
- `/api/movies/{id}/similar` exists; UI may continue to rely on query-driven hub generation — reconcile in planning when Phase 3 is active.
- Longer-term: shared cache and candidate-universe optimizations (**PCACHE‑3 / PCACHE‑4**).

**Dependencies**

- Preserve deterministic hub narrowing and stale-response protections when changing enrichment or replay.
- API stability for low-risk cache phases (PCACHE‑1/2) before shared infrastructure.

**Documentation**

- [`docs/features/web/WEB_SUB_CONTEXT_PAGE.md`](../features/web/WEB_SUB_CONTEXT_PAGE.md)
- [`docs/features/media/MEDIA_ENRICHMENT.md`](../features/media/MEDIA_ENRICHMENT.md)

#### Phase 3.A — Poster caching hardening (rollout track)

**Goal:** Improve sub-context poster reliability and latency before betting on shared infrastructure.

| ID | Risk | Focus | Outcome |
|----|------|-------|---------|
| PCACHE‑Phase‑1 | Low | Config tuning + observability | Stable poster p50/p95; no schema/UI change |
| PCACHE‑Phase‑2 | Low–medium | ID-first keying + hot-path dedupe | Fewer duplicate TMDB resolves on hub load/replay |
| PCACHE‑Phase‑3 | Medium | Shared L2 (L1 in-process + L2 shared) | Warm cache survives restart / multi-worker |
| PCACHE‑Phase‑4 | Higher | Candidate-universe narrowing + selective refresh | Faster follow-up hub turns under load |

**Dependency guardrails:** Keep contracts stable through Phase 1–2 of this track; use env toggles and safe fallbacks for shared cache.

---

## Themes

Same **Outcome / Status / Focus / Documentation** idea, organized by cross-cutting concern (these span multiple roadmap phases).

### UX quality

**Outcome:** Consistent styling and interactions; accessibility basics (keyboard close, focus, headers).

**Status:** Ongoing; Phase 0 established baseline patterns.

**Focus:** Reuse tokens and component CSS; avoid new design systems.

**Documentation:** [`docs/features/web/WEB_FRONTEND.md`](../features/web/WEB_FRONTEND.md), [`docs/practices/CSS_STYLE_GUIDE.md`](../practices/CSS_STYLE_GUIDE.md)

### AI response experience (tone + interfaceability)

**Outcome:** Assistant messages feel natural and scannable.

**Status:** Phase 0 theme **done** (UX‑1…UX‑4); Phase 2 continues prompt-level refinement.

**Focus:** Templates, `OutputValidator`, and `messages.js` rendering stay aligned; see backlog **AIUX‑\*** items for historical task IDs.

#### AI Response UX — phased deliverables (reference)

| Phase | Focus | Key deliverables | Dependencies |
|-------|-------|------------------|--------------|
| UX‑1 | Frontend readability | `web/js/modules/messages.js` safe paragraphs/lists | `normalizeMeta()`, attachments/strips unchanged |
| UX‑2 | Prompt contract | `templates.py` tuned for major intents | Planning taxonomy, `ResponseTemplate` usage |
| UX‑3 | Validator guardrails | `output_validator.py` structure/tone rules | UX‑2; prompt builder contract tests stay green |
| UX‑4 | Regression coverage | Offline structure scenarios | `tests/test_scenarios_offline.py` harness |

**Documentation:** [`docs/features/prompting/PROMPT_PIPELINE.md`](../features/prompting/PROMPT_PIPELINE.md), [`docs/features/web/WEB_FRONTEND.md`](../features/web/WEB_FRONTEND.md), [`docs/practices/FRONTEND_PATTERNS.md`](../practices/FRONTEND_PATTERNS.md)

### Reliability and fallbacks

**Outcome:** Integrations fail without breaking the UI; PLAYGROUND stays usable without keys.

**Status:** Ongoing.

**Documentation:** [`docs/features/api/API_SERVER.md`](../features/api/API_SERVER.md), [`docs/features/integrations/EXTERNAL_INTEGRATIONS.md`](../features/integrations/EXTERNAL_INTEGRATIONS.md)

### Cost / latency / observability

**Outcome:** Predictable agent behavior and measurable performance.

**Status:** TMDB resolve cache and media caches exist; PCACHE backlog carries the staged hardening plan.

**Documentation:** [`docs/features/media/MEDIA_ENRICHMENT.md`](../features/media/MEDIA_ENRICHMENT.md), [`docs/features/api/API_SERVER.md`](../features/api/API_SERVER.md)

---

## Dependency considerations

Before roadmap items touch contracts or core behavior, consult:

- Dependency chain: [`docs/AI_CONTEXT.md`](../AI_CONTEXT.md)
- Add/change patterns: [`docs/ADD_FEATURE_CONTEXT.md`](../ADD_FEATURE_CONTEXT.md), [`docs/CHANGE_FEATURE_CONTEXT.md`](../CHANGE_FEATURE_CONTEXT.md)

---

## Doc links

- Features index: [`docs/features/README.md`](../features/README.md)
- Testing: [`docs/practices/TESTING_PRACTICES.md`](../practices/TESTING_PRACTICES.md)
