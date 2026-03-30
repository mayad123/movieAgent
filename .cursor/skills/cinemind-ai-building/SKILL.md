---
name: cinemind-ai-building
description: >-
  Maintains and improves CineMind Cursor tooling: docs under docs/AIbuilding/, project rules
  (.cursor/rules/*.mdc), agent skills (.cursor/skills/**/SKILL.md), hooks (hooks.json, path_map.json,
  run-related-tests), cross-link consistency, and planning/session-query docs when that narrative
  changes. Use when adding or auditing rules, skills, hooks, path_map entries, AIbuilding prose,
  or custom-mode instructions that reference this repo’s mechanisms.
---

# CineMind AI building (Cursor meta-tooling)

Deep playbook: [`docs/AIbuilding/AI_BUILDING_MAINTAINER.md`](../../../docs/AIbuilding/AI_BUILDING_MAINTAINER.md). Index: [`docs/AIbuilding/README.md`](../../../docs/AIbuilding/README.md).

## Workflow

1. **Classify** — Rule-only, skill-only, hooks/path_map, `docs/AIbuilding` prose only, or cross-cutting (multiple layers).
2. **Read current truth** — On-disk files under [`.cursor/`](../../) plus the matching section of [CURSOR_RULES.md](../../../docs/AIbuilding/CURSOR_RULES.md), [CURSOR_SKILLS.md](../../../docs/AIbuilding/CURSOR_SKILLS.md), [CURSOR_MECHANISMS_FLOW.md](../../../docs/AIbuilding/CURSOR_MECHANISMS_FLOW.md), [CURSOR_TEST_HOOKS.md](../../../docs/AIbuilding/CURSOR_TEST_HOOKS.md).
3. **Edit** — Change config and docs in the **same change set** when possible; avoid orphan `.mdc` files not listed in CURSOR_RULES.
4. **Sync checklist** (after substantive edits):
   - New or renamed **rule** → table in [CURSOR_RULES.md](../../../docs/AIbuilding/CURSOR_RULES.md).
   - New or renamed **skill** → tables in [CURSOR_SKILLS.md](../../../docs/AIbuilding/CURSOR_SKILLS.md) and [CURSOR_MECHANISMS_FLOW.md](../../../docs/AIbuilding/CURSOR_MECHANISMS_FLOW.md); update Mermaid in MECHANISMS_FLOW if persona/skill relationships changed; add row to [CURSOR_WORKFLOW_AGENTS.md](../../../docs/AIbuilding/CURSOR_WORKFLOW_AGENTS.md) if the skill introduces a persona.
   - **Hooks / path_map** → [CURSOR_TEST_HOOKS.md](../../../docs/AIbuilding/CURSOR_TEST_HOOKS.md) + verify `skip_prefixes` / `entries` match [run-related-tests](../../hooks/run-related-tests) behavior.

5. **Propagate regression learnings** — If this change originated from a defect, run [DEFECT_TO_TOOLING.md](../../../docs/AIbuilding/DEFECT_TO_TOOLING.md) and update at least one durable mechanism artifact (skill/rule/errors doc/feature doc) in the same change or immediate follow-up.

   Session narrative requirement: for substantive scoped edits that hit tracked prefixes (including scenario YAML under `tests/fixtures/scenarios/`), run [`scripts/session_log_draft_from_signals.py`](../../../scripts/session_log_draft_from_signals.py), polish the generated entry, and append [`docs/session_logs/MANIFEST.md`](../../../docs/session_logs/MANIFEST.md). Reference [CURSOR_TEST_HOOKS.md](../../../docs/AIbuilding/CURSOR_TEST_HOOKS.md) and [`docs/session_logs/README.md`](../../../docs/session_logs/README.md).

6. **Verify** — Post-edit hooks **skip** `docs/` and `.cursor/`; validate hook behavior by editing a mapped file under `src/` or `tests/` or run pytest targets manually ([CURSOR_TEST_HOOKS.md](../../../docs/AIbuilding/CURSOR_TEST_HOOKS.md)).

7. **Required for large mechanism refactors** — Produce a session log entry under [`docs/session_logs/`](../../../docs/session_logs/README.md) and append manifest.

## Related

- Persona matrix: [`docs/AIbuilding/CURSOR_WORKFLOW_AGENTS.md`](../../../docs/AIbuilding/CURSOR_WORKFLOW_AGENTS.md)
- Program / product planning (different role): [`cinemind-project-planning`](../cinemind-project-planning/SKILL.md)
