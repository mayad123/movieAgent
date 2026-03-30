# CineMind Documentation

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I want to... | Start with |
|-------------|-----------|
| Use AI to modify code | [AI_CONTEXT.md](AI_CONTEXT.md) |
| Add a new feature | [ADD_FEATURE_CONTEXT.md](ADD_FEATURE_CONTEXT.md) |
| Fix / change existing code | [CHANGE_FEATURE_CONTEXT.md](CHANGE_FEATURE_CONTEXT.md) |
| Understand a specific feature | [features/README.md](features/README.md) |
| Follow coding conventions | [practices/README.md](practices/README.md) |
| Set up the project | [getting-started/QUICKSTART.md](getting-started/QUICKSTART.md) |
| Trace cross-cutting work sessions (narrative + dependencies) | [session_logs/README.md](session_logs/README.md) |
| Maintain Cursor rules, skills, hooks, or `docs/AIbuilding/` | [AIbuilding/README.md](AIbuilding/README.md) · [AIbuilding/AI_BUILDING_MAINTAINER.md](AIbuilding/AI_BUILDING_MAINTAINER.md) |

</details>

## Documentation Structure

```
docs/
├── README.md                   ← You are here
├── AI_CONTEXT.md               ← Start here when using AI assistance
├── ADD_FEATURE_CONTEXT.md      ← AI context for adding new features
├── CHANGE_FEATURE_CONTEXT.md   ← AI context for modifying existing code
├── errors/                     ← Guardrails for common regressions
├── AIbuilding/                 ← Cursor rules/skills/hooks docs + meta-tooling playbook
├── session_logs/               ← Session work summaries (manifest + entries; queryable)
├── planning/                   ← Project planning (roadmap, requirements, backlog)
│   ├── PROJECT.md
│   ├── SUMMARY.md
│   ├── ROADMAP.md
│   ├── REQUIREMENTS.md
│   ├── BACKLOG.md
│   └── STATE.md
├── getting-started/            ← Setup & deployment
│   ├── QUICKSTART.md
│   ├── ENV_AND_SECRETS.md
│   └── OPERATIONALIZATION.md
├── features/                   ← Feature documentation (by domain)
│   ├── README.md               ← Index + system architecture diagram
│   ├── agent/                  ← Agent core, modes, pipeline
│   ├── api/                    ← REST API endpoints
│   ├── config/                 ← Configuration, schemas, env vars
│   ├── extraction/             ← NLP extraction pipeline
│   ├── infrastructure/         ← Cache, DB, observability, tagging
│   ├── integrations/           ← TMDB, Watchmode
│   ├── llm/                    ← LLM client abstraction
│   ├── media/                  ← Media enrichment & attachments
│   ├── planning/               ← Request planning & routing
│   ├── prompting/              ← Prompt building & validation
│   ├── search/                 ← Search engine & data retrieval
│   ├── verification/           ← Fact verification
│   ├── web/                    ← Frontend architecture
│   └── workflows/              ← Orchestration layer
├── practices/                  ← Engineering best practices
│   ├── README.md               ← Index
│   ├── BACKEND_PATTERNS.md     ← Python/backend conventions
│   ├── FRONTEND_PATTERNS.md    ← JS/CSS/HTML conventions
│   ├── CSS_STYLE_GUIDE.md      ← CSS architecture & naming
│   ├── DIRECTORY_STRUCTURE.md  ← How to add new modules
│   └── TESTING_PRACTICES.md    ← Testing conventions
```

## Quick Navigation

| I want to... | Go to |
|-------------|-------|
| Set up the project | [Getting Started](getting-started/QUICKSTART.md) |
| Understand project scope & direction | [Planning: Project](planning/PROJECT.md) |
| See current status (now/next/later) | [Planning: Summary](planning/SUMMARY.md) |
| See milestones and phases | [Planning: Roadmap](planning/ROADMAP.md) |
| See functional/non-functional requirements | [Planning: Requirements](planning/REQUIREMENTS.md) |
| See prioritized work items | [Planning: Backlog](planning/BACKLOG.md) |
| See current capability snapshot | [Planning: State](planning/STATE.md) |
| Trace session-scoped work history | [Session logs](session_logs/README.md) |
| Understand the system | [Feature Docs Index](features/README.md) |
| Use AI to make changes | [AI Context Guide](AI_CONTEXT.md) |
| Use AI to **add** a feature | [AI_CONTEXT.md](AI_CONTEXT.md) + [ADD_FEATURE_CONTEXT.md](ADD_FEATURE_CONTEXT.md) |
| Use AI to **modify** existing code | [AI_CONTEXT.md](AI_CONTEXT.md) + [CHANGE_FEATURE_CONTEXT.md](CHANGE_FEATURE_CONTEXT.md) |
| Follow coding standards | [Best Practices](practices/README.md) |
| Understand a specific feature | [Feature Docs](features/README.md#documentation-index) |
| Add a new module | [Directory Structure Guide](practices/DIRECTORY_STRUCTURE.md) |
| Avoid common regressions | [Errors & Guardrails](errors/README.md) |
| Map `src/` → docs → tests | [AI_CONTEXT: Navigate from `src/`](AI_CONTEXT.md#navigate-from-src-canonical-map) · [features/README: mapping](features/README.md#source--documentation-mapping) |
| See what’s recently in scope for docs/code | [Planning: Summary](planning/SUMMARY.md) · [Documentation scope](#documentation-scope--maintenance) |

---

## Documentation scope & maintenance

Feature docs under `docs/features/` are **maintained alongside `src/`**: when behavior, contracts, or env vars change, update the matching feature markdown (each has a **Change Impact Guide** and **Test Coverage** section). High-churn areas recently aligned include:

- **API & schemas** — `POST /query` (Movie Hub marker, `hubConversationHistory`), similar/details endpoints → [`features/api/API_SERVER.md`](features/api/API_SERVER.md)
- **Extraction** — intents, response parsing, dual `normalize_title` behaviors → [`features/extraction/EXTRACTION_PIPELINE.md`](features/extraction/EXTRACTION_PIPELINE.md)
- **Prompting** — two-message prompts, templates, validator, cache env vars → [`features/prompting/PROMPT_PIPELINE.md`](features/prompting/PROMPT_PIPELINE.md)
- **Media** — enrichment, hub parsing/filtering, similar clusters, cache TTLs → [`features/media/MEDIA_ENRICHMENT.md`](features/media/MEDIA_ENRICHMENT.md)
- **Web** — chat, sub-context hub, home/more-info flows → [`features/web/`](features/web/) (see [`web/README.md`](features/web/README.md))

**Regression notes** for hub / where-to-watch / movie details live in [`docs/errors/`](errors/README.md).

---

## How to navigate docs (for AI assistants & contributors)

1. **Goal** — What are you changing? Use [`AI_CONTEXT.md`](AI_CONTEXT.md) **Change Routing Table** + companion docs ([`ADD_FEATURE_CONTEXT.md`](ADD_FEATURE_CONTEXT.md) / [`CHANGE_FEATURE_CONTEXT.md`](CHANGE_FEATURE_CONTEXT.md)).
2. **Location** — Find the **`src/` package** → open the matching row in [`AI_CONTEXT.md` § Navigate from `src/`](AI_CONTEXT.md#navigate-from-src-canonical-map) or [`features/README.md` § Source ↔ Documentation](features/README.md#source--documentation-mapping).
3. **Depth** — Read the **feature doc** end-to-end for contracts, dependencies, and tests; follow **Cross-Cutting** / **Dependency Chain** diagrams in [`AI_CONTEXT.md`](AI_CONTEXT.md) if the change spans layers.
4. **Safety** — Check [`errors/README.md`](errors/README.md) when touching hub parsing, Watchmode, or movie-details contracts.
5. **Verify** — Use [`practices/code-review/`](practices/code-review/README.md) and the **Test Coverage** section inside the feature doc you edited.

**Rule of thumb:** one primary feature doc per `src/cinemind/*` package; `src/api/` and `web/` each have their own top-level feature doc; `src/config/` + `src/schemas/` share [`CONFIGURATION.md`](features/config/CONFIGURATION.md).
