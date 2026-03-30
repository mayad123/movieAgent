# Project

> **Purpose:** Product + engineering framing for CineMind: what we’re building, why, for whom, and what constraints shape delivery.

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need to... | Jump to |
|-------------|---------|
| Understand vision and goals | [Vision](#vision) |
| See what’s explicitly out of scope | [Non-Goals](#non-goals) |
| See success metrics | [Success Metrics](#success-metrics) |
| Understand constraints and assumptions | [Constraints & Assumptions](#constraints--assumptions) |
| Understand dependency implications | [Dependency Notes](#dependency-notes) |
| Understand how AI planning updates are recorded | [How Planning Updates Work](#how-planning-updates-work) |
| Archive long or superseded planning content | [Archiving and history](#archiving-and-history) |
| See how planning docs relate | [Planning Doc Map](#planning-doc-map) |

</details>

---

## Vision

CineMind is a movie intelligence assistant that answers questions, recommends films, and enriches responses with media and “where to watch” availability — with strong quality guardrails and graceful fallbacks.

## Target Users

- **Movie-curious users**: quick facts, cast/director, “what should I watch next?”
- **Decision-makers**: “where can I watch this?”, “is it good?”, “is it similar to…?”
- **Builders**: engineers extending features, integrations, and UI capabilities

## Non-Goals

- Becoming a general-purpose assistant (scope stays movie-centric)
- Building a heavy frontend framework or build pipeline
- Adding new backend endpoints unless required by a real capability gap

## Success Metrics

- **Answer quality**: fewer incorrect factual claims; consistent sourcing behavior
- **Latency**: fast responses in PLAYGROUND; predictable behavior in REAL_AGENT with timeouts/fallback
- **UX quality**: smooth interactions, consistent UI language, graceful missing-data behavior
- **Maintainability**: changes are localized; docs route change impact correctly

## Constraints & Assumptions

- **No-build frontend**: vanilla JS modules, HTML shell, CSS component files.
- **Contract-first API**: Pydantic models define response shape; avoid churn.
- **Fallback-first**: real agent may fail; user still receives a result.
- **External dependencies**: TMDB/Watchmode/Tavily availability varies by keys, quotas, and region.

## Dependency Notes

Use these docs to reason about impact:

- **System dependency chain**: [`docs/AI_CONTEXT.md`](../AI_CONTEXT.md) → Dependency Chain Map
- **Add vs change**: [`docs/ADD_FEATURE_CONTEXT.md`](../ADD_FEATURE_CONTEXT.md), [`docs/CHANGE_FEATURE_CONTEXT.md`](../CHANGE_FEATURE_CONTEXT.md)
- **Feature decomposition**: [`docs/features/README.md`](../features/README.md)

High-level rule: planning decisions that touch **API schema**, **media normalization**, or **search/planning taxonomy** have the widest ripple effects.

## How Planning Updates Work

When you ask for a **plan** (not immediate code changes), the resulting output should be captured in `docs/planning/` so it becomes durable project context.

- **New initiative / improvement theme** (e.g. “Improve AI response quality”) → update:
  - `ROADMAP.md`: add a theme or milestone (outcome-oriented)
  - `REQUIREMENTS.md`: add/adjust functional or non-functional requirements + acceptance patterns
  - `BACKLOG.md`: add prioritized items with dependencies and test impact
  - `STATE.md`: update the capability/gap snapshot if the plan changes what “exists today”
  - `SUMMARY.md`: reflect what is Now/Next/Later and record key risks/decisions
- **Decision made** (trade-off chosen) → record in `SUMMARY.md` → Decisions with date, reason, and impacted areas.
- **Scope or priority change** → update `ROADMAP.md` + `BACKLOG.md`, and ensure `AI_CONTEXT.md` routing still points to the right feature docs.

This keeps chat short and makes future AI work consistent: the AI reads `docs/planning/` first for intent, then `docs/features/` for implementation boundaries.

### Archiving and history

When live planning files get **too long** or a section is **fully superseded**, move content into [`archive/`](archive/README.md) instead of only deleting it.

1. **Check triggers** — line budget (~350–450 lines for `ROADMAP.md` / `BACKLOG.md`), replaced narrative, >15 decision rows in `SUMMARY.md`, or bulky delivered backlog sections. Full policy: [`archive/README.md`](archive/README.md).
2. **Snapshot** — full-file copy or section extract under `archive/snapshots/` (or `archive/delivered/` for done backlog digests) with required YAML front matter (`archive_of`, `archived_on`, `reason`, `superseded_by`, `topics`, optional `source_commit`).
3. **Manifest** — append one row to [`archive/MANIFEST.md`](archive/MANIFEST.md) (newest first).
4. **Trim the live file** — replace removed text with a short stub and **History** link to the snapshot so the chain is bidirectional.

**Query recent history:** start at [`archive/MANIFEST.md`](archive/MANIFEST.md); use `rg "archive_of: ROADMAP" docs/planning/archive` to list by source file.

## Planning Doc Map

- **`PROJECT.md`** (this file): vision, constraints, non-goals, how planning updates are recorded
- **`SUMMARY.md`**: current status at a glance (now/next/later), risks, decisions
- **`ROADMAP.md`**: phased outcomes + milestones (each phase: Outcome → Status → Focus → Dependencies → Documentation)
- **`REQUIREMENTS.md`**: functional + non-functional requirements and acceptance patterns
- **`BACKLOG.md`**: prioritized work items with dependencies and test impact
- **`STATE.md`**: capability matrix (“what exists today”) + known gaps
- **`archive/`** (this folder): superseded planning snapshots, optional delivered digests, [`MANIFEST.md`](archive/MANIFEST.md) index

---

## Related References

- Feature docs index: [`docs/features/README.md`](../features/README.md)
- Frontend patterns: [`docs/practices/FRONTEND_PATTERNS.md`](../practices/FRONTEND_PATTERNS.md)
- Backend patterns: [`docs/practices/BACKEND_PATTERNS.md`](../practices/BACKEND_PATTERNS.md)
- Testing practices: [`docs/practices/TESTING_PRACTICES.md`](../practices/TESTING_PRACTICES.md)

