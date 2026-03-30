# Cursor project skills (`.cursor/skills/`)

This repo defines **Agent Skills**: directories with a `SKILL.md` file (YAML `name` + `description` + workflow body). The agent uses **`description`** to decide when the skill applies—good for role-based, multi-step work that spans several files.

**Scenario and prompt work is online-first:** project skills treat **online** evaluation (real stack, [`tests/test_cases/`](../../tests/test_cases/), [`tests/helpers/interactive_runner.py`](../../tests/helpers/interactive_runner.py) / [`parallel_runner.py`](../../tests/helpers/parallel_runner.py)) as the primary definition of scenario quality. Offline YAML + `tests/test_scenarios_offline.py` remain for deterministic CI—see [TEST_COVERAGE_MAP](../practices/code-review/TEST_COVERAGE_MAP.md).

Post-edit **hooks** still run narrow **pytest** slices for fast feedback; they do not replace online scenario passes when a skill calls for them.

For how each skill fits with **rules** and **hooks** by persona, see [CURSOR_WORKFLOW_AGENTS.md](CURSOR_WORKFLOW_AGENTS.md).

Official overview: [Skills | Cursor Docs](https://cursor.com/docs/context/skills).

**Do not** add skills under `~/.cursor/skills-cursor/` (reserved for Cursor). Optional **personal** skills can live in `~/.cursor/skills/` (e.g. individual design taste); **project** skills below are shared with anyone using this repository.

## Project skills

| Directory | Role |
|-----------|------|
| [`.cursor/skills/cinemind-ux-web/`](../../.cursor/skills/cinemind-ux-web/SKILL.md) | UX / visual consistency for vanilla `web/` (CSS tokens, layout, accessibility) |
| [`.cursor/skills/cinemind-prompt-engineer/`](../../.cursor/skills/cinemind-prompt-engineer/SKILL.md) | Prompt pipeline: builder, templates, evidence formatter, validator, versioning |
| [`.cursor/skills/cinemind-scenario-qa/`](../../.cursor/skills/cinemind-scenario-qa/SKILL.md) | Online scenarios: `tests/test_cases/`, interactive/parallel runners, acceptance criteria |
| [`.cursor/skills/cinemind-api-contracts/`](../../.cursor/skills/cinemind-api-contracts/SKILL.md) | FastAPI + Pydantic schemas aligned with tests and `web/js/modules/api.js` |
| [`.cursor/skills/cinemind-project-planning/`](../../.cursor/skills/cinemind-project-planning/SKILL.md) | Large / cross-cutting work; [`docs/planning/`](../planning/), [`docs/planning/archive/`](../planning/archive/README.md) ([PLANNING_DOCS_ARCHIVE.md](PLANNING_DOCS_ARCHIVE.md)), [`docs/session_logs/`](../session_logs/README.md) ([SESSION_LOGS.md](SESSION_LOGS.md)); lookup: [QUERYING.md](QUERYING.md) |
| [`.cursor/skills/cinemind-ai-building/`](../../.cursor/skills/cinemind-ai-building/SKILL.md) | Cursor meta-tooling: [`docs/AIbuilding/`](README.md), [`.cursor/rules/`](../../.cursor/rules/), [`.cursor/skills/`](../../.cursor/skills/), hooks; playbook [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md) |

## Rules vs skills vs hooks

| Mechanism | Path | What it does |
|-----------|------|----------------|
| **Rules** | [`.cursor/rules/*.mdc`](../../.cursor/rules/) | Glob-scoped guardrails attached when you edit matching files. |
| **Skills** | [`.cursor/skills/*/SKILL.md`](../../.cursor/skills/) | Discovery-driven playbooks for whole workflows (UX, prompts, scenarios, API, meta-tooling). |
| **Hooks** | [`.cursor/hooks.json`](../../.cursor/hooks.json) | Runs commands (e.g. related pytest) after edits—see [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md). |

Use **rules** for “always when touching `web/**/*`,” **skills** for “I’m acting as prompt engineer this session,” and **hooks** for automated narrow test feedback.

## Adding or changing a skill

1. Create `.cursor/skills/<kebab-name>/SKILL.md`.
2. Set `name` (lowercase, hyphens) and a third-person **`description`** that states **what** the skill does and **when** to use it (trigger keywords).
3. Keep the body short; link to [`docs/`](../README.md) for depth.
4. Add a row to the table above.
5. Update [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) (skills table + Mermaid if persona links change). If the skill defines a **new persona**, add a row to [CURSOR_WORKFLOW_AGENTS.md](CURSOR_WORKFLOW_AGENTS.md). For **meta-tooling** edits, follow [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md).

See also: [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) (diagrams), [CURSOR_RULES.md](CURSOR_RULES.md), [QUERYING.md](QUERYING.md) (planning archive + session logs), [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md), [README.md](README.md).
