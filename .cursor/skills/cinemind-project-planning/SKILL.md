---
name: cinemind-project-planning
description: >-
  Keeps CineMind planning artifacts coherent under docs/planning for large or cross-cutting
  work. Use when refactoring multiple areas, shifting roadmap or backlog priorities, updating
  STATE or SUMMARY, tracing requirements, defining epics, or when the user mentions
  docs/planning, program-level scope, or everything-must-align initiatives. Complements
  file-level docs rules with an end-to-end planning workflow.
---

# CineMind project planning (large / cross-cutting)

## Canonical docs (`docs/planning/`)

| File | Purpose |
|------|---------|
| [`PROJECT.md`](../../../docs/planning/PROJECT.md) | Vision, constraints, non-goals, how planning docs relate |
| [`ROADMAP.md`](../../../docs/planning/ROADMAP.md) | Phased outcomes, milestones, links to feature docs |
| [`BACKLOG.md`](../../../docs/planning/BACKLOG.md) | Prioritized items, templates, test expectations |
| [`STATE.md`](../../../docs/planning/STATE.md) | What exists today: capabilities, gaps, testing state |
| [`SUMMARY.md`](../../../docs/planning/SUMMARY.md) | At-a-glance now / next / risks / decisions |
| [`REQUIREMENTS.md`](../../../docs/planning/REQUIREMENTS.md) | Functional and non-functional requirements, traceability |
| [`archive/`](../../../docs/planning/archive/README.md) | Superseded snapshots, manifest index, archive triggers |
| [`session_logs/`](../../../docs/session_logs/README.md) | Session narratives, `depends_on`, [`MANIFEST.md`](../../../docs/session_logs/MANIFEST.md); overview: [`SESSION_LOGS.md`](../../../docs/AIbuilding/SESSION_LOGS.md) |

## Workflow

1. **Classify the change** — Vision/constraint shift vs new capability vs priority reorder vs technical refactor spanning several packages.
2. **Update the right set together** (typical patterns):
   - **Vision, scope, or non-goals** — `PROJECT.md`, then align `ROADMAP.md` / `SUMMARY.md` if narrative changed.
   - **New or materially changed capability** — `STATE.md` (capability matrix / gaps), `SUMMARY.md` (Now/Next), often `BACKLOG.md` or `ROADMAP.md` for placement; add trace rows in `REQUIREMENTS.md` when acceptance criteria matter.
   - **Priority or sequencing** — `BACKLOG.md`, `SUMMARY.md`, relevant `ROADMAP.md` sections.
   - **Milestone or phase completion** — `ROADMAP.md`, `STATE.md`, `SUMMARY.md`.
3. **Sync implementation truth** — When behavior changes, update linked docs under [`docs/features/`](../../../docs/features/) and/or [`docs/AI_CONTEXT.md`](../../../docs/AI_CONTEXT.md); keep names stable (`CineMind`, features, request types) per [`.cursor/rules/docs-planning.mdc`](../../rules/docs-planning.mdc).
4. **Archive before huge rewrites** — If edits would cross the line budget or replace entire sections, snapshot first: follow [`docs/planning/archive/README.md`](../../../docs/planning/archive/README.md) (front matter, [`MANIFEST.md`](../../../docs/planning/archive/MANIFEST.md), stub + **History** link in the live doc).
5. **Keep planning navigable** — Use existing section templates and “Quick AI Context” tables in each file; add cross-links from `PROJECT.md` planning map when introducing new canonical docs.
6. **Session log (required for substantive scoped changes)** — After large cross-cutting delivery, if touched files match tracked prefixes (for example `src/`, `web/`, or scenario YAML under `tests/fixtures/scenarios/`), run [`scripts/session_log_draft_from_signals.py`](../../../scripts/session_log_draft_from_signals.py) to draft from `.tracking/signals.jsonl`, then edit the draft into a clear narrative; create `docs/session_logs/entries/YYYY-MM-DD_<slug>.md` and append [`docs/session_logs/MANIFEST.md`](../../../docs/session_logs/MANIFEST.md). Follow [`docs/session_logs/README.md`](../../../docs/session_logs/README.md) (no secrets or raw transcript paths).

## Hooks and tests

Post-edit [`run-related-tests`](../../hooks/run-related-tests) **skips** paths under `docs/` (see [CURSOR_TEST_HOOKS.md](../../../docs/AIbuilding/CURSOR_TEST_HOOKS.md)). If the same initiative changes code, run **`make check`** and relevant tests manually before merge.

## Related

- Cursor / AIbuilding mechanisms (separate from product planning): [`cinemind-ai-building`](../cinemind-ai-building/SKILL.md), [`docs/AIbuilding/AI_BUILDING_MAINTAINER.md`](../../../docs/AIbuilding/AI_BUILDING_MAINTAINER.md)
- Markdown discipline for all `docs/**/*.md`: [`.cursor/rules/docs-planning.mdc`](../../rules/docs-planning.mdc)
- Unified query playbook (manifests, `rg`): [`docs/AIbuilding/QUERYING.md`](../../../docs/AIbuilding/QUERYING.md)
- AIbuilding index: [`docs/AIbuilding/README.md`](../../../docs/AIbuilding/README.md)
- Session logs (query + dependencies): [`docs/AIbuilding/SESSION_LOGS.md`](../../../docs/AIbuilding/SESSION_LOGS.md)
- Persona matrix: [`docs/AIbuilding/CURSOR_WORKFLOW_AGENTS.md`](../../../docs/AIbuilding/CURSOR_WORKFLOW_AGENTS.md)
