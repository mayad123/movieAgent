# AI building notes

Internal documentation for tooling and workflows used while building CineMind with AI assistants.

## Cursor mechanisms (rules, skills, hooks)

| Doc | Purpose |
|-----|---------|
| [CURSOR_RULES.md](CURSOR_RULES.md) | Project Cursor Rules under `.cursor/rules/` (globs, purpose, how to extend) |
| [CURSOR_SKILLS.md](CURSOR_SKILLS.md) | Project Cursor Skills under `.cursor/skills/` (role playbooks vs rules vs hooks) |
| [CURSOR_WORKFLOW_AGENTS.md](CURSOR_WORKFLOW_AGENTS.md) | Persona matrix: which skill + rules + hooks apply per workflow |
| [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) | Mermaid diagrams: how rules, skills, and hooks connect end-to-end |
| [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md) | `hooks.json`, `path_map.json`, `run-related-tests`; focused pytest after edits |

**Config on disk:** [`.cursor/rules/`](../../.cursor/rules/), [`.cursor/skills/`](../../.cursor/skills/), [`.cursor/hooks.json`](../../.cursor/hooks.json).

## Maintaining Cursor tooling (meta)

| Doc | Purpose |
|-----|---------|
| [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md) | Persona playbook: when to use vs program/docs personas, sync checklist, verification |
| [DEFECT_TO_TOOLING.md](DEFECT_TO_TOOLING.md) | Defect-to-tooling loop: convert bug fixes into skill/rule/doc guardrails |
| Skill [`cinemind-ai-building`](../../.cursor/skills/cinemind-ai-building/SKILL.md) | Discovery-driven workflow for editing `.cursor/` and this folder |

## Docs history and querying (manifest + `rg`)

These complement **live** [`docs/planning/`](../planning/): frozen planning text, session narratives, and how to look them up. They attach under **`docs-planning.mdc`** (`docs/**/*.md`) like any other doc edit; pytest hooks **skip** `docs/` (see [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md)).

| Doc | Purpose |
|-----|---------|
| [PLANNING_DOCS_ARCHIVE.md](PLANNING_DOCS_ARCHIVE.md) | [`docs/planning/archive/`](../planning/archive/): when to snapshot, manifest, stubs, Cursor wiring |
| [SESSION_LOGS.md](SESSION_LOGS.md) | [`docs/session_logs/`](../session_logs/): session narratives, `depends_on`, manifest |
| [QUERYING.md](QUERYING.md) | Unified lookup: manifests, `rg` on YAML front matter, git; crosses planning + sessions |

Start with **[QUERYING.md](QUERYING.md)** when the task is “find what changed / what this depended on,” not “how Cursor runs pytest.”

---

For general testing policy and layout, see [TESTING_PRACTICES](../practices/TESTING_PRACTICES.md) and [TEST_COVERAGE_MAP](../practices/code-review/TEST_COVERAGE_MAP.md).
