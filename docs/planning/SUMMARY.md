# Planning Summary

> **Purpose:** “At a glance” project status for CineMind — what’s stable, what’s in progress, what’s next, and what’s risky.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to... | Jump to |
|-------------|---------|
| See what’s happening now | [Now](#now) |
| See what’s next | [Next](#next) |
| See longer-term ideas | [Later](#later) |
| Understand active risks | [Risks](#risks) |
| Track recent decisions | [Decisions](#decisions) |
| Understand where plans should be recorded | [How to Use Planning Docs](#how-to-use-planning-docs) |
| Find the authoritative roadmap/backlog | [Pointers](#pointers) |

</details>

---

## Now

- **Finish Phase 0 exit hygiene:** poster/resolve **PCACHE‑1 / PCACHE‑2** (metrics + ID-first dedupe / hot-path behavior) and **HUBX‑1** hub parsing/narrowing stability — without API schema churn
- **Documentation-as-code** remains the primary navigation for safe changes (`docs/features/*`, `docs/planning/*`)
- **Keep AI response UX** from regressing (templates, validator, structured chat rendering)
- **Operate Projects MVP** (JSON store + `/api/projects*` + `web/projects.html`) and keep contract docs aligned when the surface evolves

### Phase 0 Snapshot

- ✅ **AI Response UX**: Frontend paragraphs/lists, tuned templates, validator guardrails, offline regression scenarios
- ✅ **Movie Details (“More Info”)**: Hero/backdrop, Story/Credits/Meta/Related/where-to-watch, empty-section hiding — **optional** residual device/accessibility QA only
- ✅ **Media alignment**: Omit mismatched media when resolution is uncertain
- ✅ **Sub-context Movie Hub MVP**: `movieHubClusters` + strict `Genre:` / `Title (Year)` contract; auto-load/retry behavior in sub-context
- ✅ **API + config docs**: `API_SERVER.md` / `CONFIGURATION.md` / client mirrors match `src/schemas/api.py` (hub fields, movie details, **Projects**)
- ✅ **Projects workspace**: `ProjectsStore`, REST routes, dedicated web page; unit tests for store + API
- ⏳ **Poster caching hardening (early tranches)**: In-process resolve cache exists; staged PCACHE work (metrics, dedupe, future L2) is active planning focus

## Next

- **Phase 1 execution:** hub expansion (tone/cast, narrowing), richer action affordances, watch presentation polish — all on **existing** contracts unless explicitly approved otherwise
- **Phase 2 (when prioritized):** prompt pipeline and validator work for less robotic, more UI-mappable model output
- Tighten tests where code changes touch verification/infrastructure gaps

## Later

- **Phase 3** sub-context depth (layout + related-title emphasis beyond current hub shell)
- **PCACHE‑3 / PCACHE‑4**: shared L2 cache and candidate-universe-first narrowing under toggles
- Broader UI automation (still respecting no-build constraints)

## Risks

- **External API variability**: keys/quotas/regions can break UX; require graceful fallbacks
- **Contract drift**: frontend depends on `MovieResponse` shape; avoid breaking changes
- **Hub parsing sensitivity**: strict, plain-text genre-block parsing can fail if prompts/validators drift; scenario coverage must track the contract
- **Coverage gaps**: some packages lack dedicated unit tests; mitigate with integration/scenarios

## Decisions

Use this section for durable “we chose X because Y” notes.

- Decision log entries should include:
  - **Date**
  - **Decision**
  - **Reason**
  - **Affected docs/features**

- **Date:** 2026-03-22
  **Decision:** Sequence poster caching improvements as low-risk-first (config/observability, then keying/dedupe) before shared-cache infrastructure.
  **Reason:** Current sub-context pain is dominated by miss amplification and visibility gaps that can be improved safely without schema or UX contract changes.
  **Affected docs/features:** `docs/planning/ROADMAP.md`, `docs/planning/REQUIREMENTS.md`, `docs/planning/BACKLOG.md`, `docs/planning/STATE.md`, `docs/features/media/MEDIA_ENRICHMENT.md`, `docs/features/web/WEB_SUB_CONTEXT_PAGE.md`

## How to Use Planning Docs

Use `docs/planning/` as the home for durable planning context.

- If you ask: **“Plan out how to improve AI response to user queries”**
  Then updates should land in:
  - `ROADMAP.md` (milestones/outcomes)
  - `REQUIREMENTS.md` (quality requirements + acceptance criteria)
  - `BACKLOG.md` (work items and ordering)
  - `STATE.md` (current gaps and what becomes true after delivery)
  - This file (`SUMMARY.md`) for Now/Next/Later + risks/decisions
- If you ask to implement immediately, the work should be driven primarily by:
  - `docs/AI_CONTEXT.md` routing + relevant `docs/features/*` docs
  - and the planning docs should be updated *after* implementation to reflect the new state

## Pointers

- Project framing: [`PROJECT.md`](PROJECT.md)
- Roadmap (phases/milestones): [`ROADMAP.md`](ROADMAP.md)
- Requirements (acceptance patterns): [`REQUIREMENTS.md`](REQUIREMENTS.md)
- Backlog (prioritized list): [`BACKLOG.md`](BACKLOG.md)
- Current capability state: [`STATE.md`](STATE.md)

