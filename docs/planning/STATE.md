# State

> **Purpose:** Describe the current system capabilities and known gaps. This is the “what exists today” snapshot to keep planning grounded in the codebase.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to... | Jump to |
|-------------|---------|
| See current capabilities | [Capability matrix](#capability-matrix) |
| See known gaps | [Known gaps](#known-gaps) |
| Understand testing coverage state | [Testing state](#testing-state) |
| Jump to feature docs | [Feature doc index](#feature-doc-index) |

</details>

---

## Capability Matrix


| Area | Current capability | Notes |
| ---- | ------------------ | ----- |
| Query answering | Implemented via agent pipeline | [`docs/features/agent/AGENT_CORE.md`](../features/agent/AGENT_CORE.md) |
| Request planning | Routing, tool planning, source policy | [`docs/features/planning/REQUEST_PLANNING.md`](../features/planning/REQUEST_PLANNING.md) |
| Search | Kaggle + Tavily + fallback | [`docs/features/search/SEARCH_ENGINE.md`](../features/search/SEARCH_ENGINE.md) |
| Prompting | Builder, templates, validator, versioning | [`docs/features/prompting/PROMPT_PIPELINE.md`](../features/prompting/PROMPT_PIPELINE.md) |
| Media enrichment | Posters, scenes, attachments, hub clusters | [`docs/features/media/MEDIA_ENRICHMENT.md`](../features/media/MEDIA_ENRICHMENT.md) |
| External integrations | TMDB, Watchmode | [`docs/features/integrations/EXTERNAL_INTEGRATIONS.md`](../features/integrations/EXTERNAL_INTEGRATIONS.md) |
| API server | FastAPI, static web, where-to-watch, projects | [`docs/features/api/API_SERVER.md`](../features/api/API_SERVER.md) |
| Web frontend | No-build modular JS/CSS, chat + details + projects page | [`docs/features/web/WEB_FRONTEND.md`](../features/web/WEB_FRONTEND.md) |
| Projects | JSON-backed store + `/api/projects*` + `web/projects.html` | `src/cinemind/infrastructure/projects_store.py`, Pydantic models in `src/schemas/api.py` |
| Poster / resolve caching | L1 in-process TTL/LRU resolve cache + media memoization | `src/integrations/tmdb/resolve_cache.py`; shared L2 and replay memo (**PCACHE‑3/4**) not implemented |


## Known Gaps

These are missing guardrails, polish, or infrastructure — not an exhaustive bug list.

- **Movie Details**: optional responsive/accessibility QA; no further Phase 0 scope unless product reopens layout
- **Sub-context Movie Hub**: `tone` / `cast` paths and narrowing beyond genre MVP; **HUBX‑1** tracks parsing + filter stability
- **Poster cache keying and reuse**: text-keyed paths still cause miss amplification in some turns (**PCACHE‑2**)
- **Cache durability / multi-worker**: in-process caches drop on restart; shared L2 is future (**PCACHE‑3**)
- **Sub-context replay**: candidate-universe memoization for follow-ups is incomplete (**PCACHE‑4**)
- **Projects**: single-file JSON store is dev/simple-deployment friendly; scaling, auth, and chat integration are not first-class yet
- **Unit test coverage** gaps in some backend areas (verification/infrastructure)
- **Frontend automated tests** remain light (smoke + manual workflows)
- **External dependency variability** (keys, quotas, region) needs ongoing fallback review

## Testing State

Use:

- Feature docs’ `Test Coverage` section in each file under `docs/features/`
- Testing guide: [`docs/practices/TESTING_PRACTICES.md`](../practices/TESTING_PRACTICES.md)

## Feature doc index

- [`docs/features/README.md`](../features/README.md)
- [`docs/AI_CONTEXT.md`](../AI_CONTEXT.md)

