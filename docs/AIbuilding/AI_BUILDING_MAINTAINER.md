# AI building maintainer (persona playbook)

A **workflow persona** for improving this repo’s **Cursor mechanisms**—not CineMind’s runtime [`cinemind.agent`](../../src/cinemind/agent/). Use the project skill [`cinemind-ai-building`](../../.cursor/skills/cinemind-ai-building/SKILL.md); the matrix row is **AI building / Cursor tooling** in [CURSOR_WORKFLOW_AGENTS.md](CURSOR_WORKFLOW_AGENTS.md).

**Entry:** [README.md](README.md) (index of all AIbuilding docs).

## When to use this persona

| Situation | Use |
|-----------|-----|
| Audit or extend **`docs/AIbuilding/**`** | This playbook + skill |
| Add/change **`.cursor/rules/*.mdc`**, **`.cursor/skills/**`**, **`hooks.json`**, **`path_map.json`**, **`run-related-tests`** | This playbook + skill |
| Align docs with actual hook **skip_prefixes** / **debounce** / pytest targets | This playbook |
| **Lightweight** typo/link fixes anywhere in `docs/**` | **Docs / planning** row only—no skill required |
| **Product** roadmap, backlog, `docs/planning/**` epics + code across packages | **Program / cross-cutting planning** ([`cinemind-project-planning`](../../.cursor/skills/cinemind-project-planning/SKILL.md)); pair with this persona only when the initiative **also** changes `.cursor/` or AIbuilding docs |

## Improvement lenses

- **Globs vs reality** — Rule `globs` in [CURSOR_RULES.md](CURSOR_RULES.md) must match `.mdc` front matter; call out dead or overlapping patterns.
- **`path_map.json`** — New `src/cinemind/*` areas need entries mirroring `tests/unit/<area>/` when that is the convention ([CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md)).
- **Hook skips** — `docs/`, `.cursor/`, `data/`, etc. mean **no automatic pytest** after those edits; docs must say so and testers must run checks manually when needed.
- **Skill `description`** — Third-person, trigger-rich; enough keywords for discovery ([CURSOR_SKILLS.md](CURSOR_SKILLS.md)).
- **Cross-links** — AIbuilding pages should point to each other and to `.cursor/` paths consistently; reduce duplicate prose—link to the canonical section instead.
- **Regression to tooling propagation** — When a defect fix reveals a recurring class of mistakes, run [DEFECT_TO_TOOLING.md](DEFECT_TO_TOOLING.md) and land at least one durable mechanism update (skill/rule/errors doc/feature doc).
- **Planning / session docs** — If you change how archive or session logs work, update [PLANNING_DOCS_ARCHIVE.md](PLANNING_DOCS_ARCHIVE.md), [SESSION_LOGS.md](SESSION_LOGS.md), [QUERYING.md](QUERYING.md), and [`docs/planning/archive/README.md`](../planning/archive/README.md) / [`docs/session_logs/README.md`](../session_logs/README.md) together.

## Doc–config sync checklist

After you change the mechanisms, update the **human index** so the repo stays navigable:

1. **New rule file** → table in [CURSOR_RULES.md](CURSOR_RULES.md); if it affects workflow narrative, [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) rules table.
2. **New skill** → [CURSOR_SKILLS.md](CURSOR_SKILLS.md) table; [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) skills table + Mermaid; [CURSOR_WORKFLOW_AGENTS.md](CURSOR_WORKFLOW_AGENTS.md) if there is a new or changed persona row.
3. **Hooks / path_map / runner script** → [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md); [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) “Related paths” if new artifacts appear.
4. **This playbook or README** → [README.md](README.md) table row if you add new top-level AIbuilding docs.

## Verification

- **Hooks:** Edits under `docs/` and `.cursor/` do not trigger the related-test hook’s pytest path ([CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md)). To confirm hook behavior after changing `path_map.json`, edit a file under a mapped prefix (e.g. `src/cinemind/**`) or run the pytest command the map would produce.
- **Rules:** Open a file matching a glob and confirm the intended rule appears in context (Cursor UI).

## Custom Modes (local)

There is no committed Cursor modes file. Optional: create a Custom Mode with one instruction: follow the **AI building / Cursor tooling** row in [CURSOR_WORKFLOW_AGENTS.md](CURSOR_WORKFLOW_AGENTS.md).

## Related

- [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) — diagrams
- [QUERYING.md](QUERYING.md) — manifests and `rg` for planning archive + session logs
