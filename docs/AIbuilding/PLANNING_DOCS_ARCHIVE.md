# Planning docs archive (`docs/planning/archive/`)

How CineMind keeps **live** planning files small and navigable while preserving **history** with bidirectional links. Canonical policy lives in `[docs/planning/archive/README.md](../planning/archive/README.md)`; this page is the AI-building overview (how it connects to Cursor rules and skills).

## Why it exists

- **Long context:** `ROADMAP.md`, `BACKLOG.md`, and `SUMMARY.md` can grow until assistants and humans lose the thread.
- **Honest history:** Large rewrites should not erase prior intent—only git blame is not enough for narrative planning.
- **Fast lookup:** One manifest + predictable filenames so `rg` and readers find “what did ROADMAP say before?”

## Layout


| Path                                                                   | Role                                                         |
| ---------------------------------------------------------------------- | ------------------------------------------------------------ |
| `[docs/planning/*.md](../planning/)`                                   | **Live** canonical planning (six files at folder root)       |
| `[docs/planning/archive/README.md](../planning/archive/README.md)`     | Triggers, naming, YAML header template, stubs                |
| `[docs/planning/archive/MANIFEST.md](../planning/archive/MANIFEST.md)` | Append-only index (newest first); **start here** for history |
| `[docs/planning/archive/snapshots/](../planning/archive/snapshots/)`   | Frozen full-file or section snapshots                        |
| `[docs/planning/archive/delivered/](../planning/archive/delivered/)`   | Optional large “done” backlog digests                        |


## When to archive (triggers)

Summarized; full table in the archive README.

- **Size:** ~**350–450 lines** for `ROADMAP.md` / `BACKLOG.md` (same idea for others if they balloon).
- **Supersede:** A section is no longer truth—snapshot what you remove.
- **Decisions:** `SUMMARY.md` **Decisions** past ~**15 rows**—roll older rows to a dated snapshot.
- **Done clutter:** Huge delivered blocks in `BACKLOG.md`—move to `archive/delivered/` with a manifest row.

**Not triggers:** typos, single-bullet status updates, link fixes.

## Agent workflow (archive-then-trim)

1. Copy content to `archive/snapshots/YYYY-MM-DD_<source>__<slug>.md` (or `delivered/` if appropriate).
2. Set YAML front matter: `archive_of`, `archived_on`, `reason`, `superseded_by`, `topics`, optional `source_commit`.
3. Append a row to `[MANIFEST.md](../planning/archive/MANIFEST.md)`.
4. Trim the live file; add **History:** link under the affected heading (bidirectional with `superseded_by`).

## Query cheatsheet


| Goal                     | Command or path                                  |
| ------------------------ | ------------------------------------------------ |
| Recent archives          | `[MANIFEST.md](../planning/archive/MANIFEST.md)` |
| All snapshots of roadmap | `rg "archive_of: ROADMAP" docs/planning/archive` |
| By topic token           | `rg "topics:.*pcache" docs/planning/archive`     |


## Cursor wiring


| Mechanism       | What to follow                                                                                                                                       |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rule**        | `[.cursor/rules/docs-planning.mdc](../../.cursor/rules/docs-planning.mdc)` — archive when over budget or superseding                                 |
| **Skill**       | `[.cursor/skills/cinemind-project-planning/SKILL.md](../../.cursor/skills/cinemind-project-planning/SKILL.md)` — step “Archive before huge rewrites” |
| **Project doc** | `[docs/planning/PROJECT.md](../planning/PROJECT.md)` — **Archiving and history** under *How Planning Updates Work*                                   |


## Related

- [README.md](README.md) — AIbuilding index
- [QUERYING.md](QUERYING.md) — unified manifest + `rg` patterns (planning archive + session logs)
- [SESSION_LOGS.md](SESSION_LOGS.md) — work-session narratives + `depends_on` (parallel manifest/query pattern)
- [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) — rules, skills, hooks map
- [CURSOR_SKILLS.md](CURSOR_SKILLS.md) — `cinemind-project-planning` skill
- [CURSOR_RULES.md](CURSOR_RULES.md) — `docs-planning.mdc` glob
- [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md) — `docs/` skipped by post-edit pytest

