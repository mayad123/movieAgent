# Cursor project rules (`.cursor/rules`)

This repo ships **Cursor Rules** under [`.cursor/rules/`](../../.cursor/rules/): small `.mdc` files whose front matter tells Cursor when to attach them to the model context. They keep backend, tests, docs, and web work aligned with project conventions.

Cursor’s own overview: [Rules | Cursor Docs](https://cursor.com/docs/context/rules).

See [CURSOR_WORKFLOW_AGENTS.md](CURSOR_WORKFLOW_AGENTS.md) for a persona-by-persona map of which rules apply alongside skills and hooks.

## Layout

| File | `description` (summary) | `globs` | `alwaysApply` |
|------|------------------------|---------|----------------|
| [`docs-planning.mdc`](../../.cursor/rules/docs-planning.mdc) | Documentation and planning update discipline | `docs/**/*.md` | `false` |
| [`python-backend.mdc`](../../.cursor/rules/python-backend.mdc) | Python backend conventions for `src` | `src/**/*.py` | `false` |
| [`testing-standards.mdc`](../../.cursor/rules/testing-standards.mdc) | Testing conventions (mirrored, deterministic) | `tests/**/*.py` | `false` |
| [`web-frontend.mdc`](../../.cursor/rules/web-frontend.mdc) | Vanilla web frontend (JS/CSS/HTML) | `web/**/*.{js,css,html}` | `false` |

All four rules use **`alwaysApply: false`**, so they load when edits or context involve matching **glob patterns**, not on every chat turn.

## What each rule is for

- **Docs and planning** — Keep feature docs in sync with `src/`, refresh planning artifacts (`ROADMAP`, `BACKLOG`, `STATE`, `SUMMARY`), stable terminology, env/config documentation. For **oversized or superseded** planning text use [`docs/planning/archive/`](../planning/archive/README.md) ([AI overview](PLANNING_DOCS_ARCHIVE.md)); for **work-session narratives** after cross-cutting delivery use [`docs/session_logs/`](../session_logs/README.md) ([SESSION_LOGS.md](SESSION_LOGS.md)). **Lookup recipes** (manifests, `rg`): [QUERYING.md](QUERYING.md).
- **Python backend** — Thin API layer, `cinemind` feature modules, typed contracts, degradation on external failures, env-based config, mirror tests when behavior changes.
- **Testing** — Mirror `src/cinemind/` in `tests/unit/`, fakes/mocks only (no live network), behavior-shaped test names, integration contract coverage, scenario updates when routing/prompting/extraction change.
- **Web frontend** — Build-free vanilla modules, `app.js` as wiring, `state.js` / `dom.js` / `api.js` patterns, safe text handling.

## Editing and extending rules

1. **Prefer a dedicated rule file** per major area (backend, tests, web, docs) so globs stay precise.
2. **Front matter** must be valid YAML between `---` lines: at minimum `description`, and for scoped rules `globs` plus `alwaysApply: false`.
3. **Body** should be short bullets; avoid duplicating long guides—link to [`docs/`](../README.md) for depth.
4. After adding a rule, update this table in **CURSOR_RULES.md** so contributors know it exists.

## Relationship to other `.cursor` config

- **Rules** (this page) inject **guidance** into the agent context for relevant files.
- **[Cursor skills](CURSOR_SKILLS.md)** are discovery-driven **role playbooks** (`SKILL.md` under `.cursor/skills/`), not glob-scoped.
- **[Cursor hooks](CURSOR_TEST_HOOKS.md)** run **commands** (e.g. related pytest) after edits; they do not replace rules. Edits under `docs/**` are typically **skipped** by the hook runner.
- **[Mechanisms flow](CURSOR_MECHANISMS_FLOW.md)** — Mermaid diagrams for how the three fit together.
- **Planning archive + session logs + querying** — [PLANNING_DOCS_ARCHIVE.md](PLANNING_DOCS_ARCHIVE.md), [SESSION_LOGS.md](SESSION_LOGS.md), [QUERYING.md](QUERYING.md) (see [README.md](README.md) § Docs history).
- **Cursor meta-tooling** — evolving `.cursor/` or AIbuilding docs: [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md), skill [`cinemind-ai-building`](../../.cursor/skills/cinemind-ai-building/SKILL.md).

See also: [README.md](README.md) for the AIbuilding doc index.
