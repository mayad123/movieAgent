# Session logs (`docs/session_logs/`)

Human-written **session summaries** for cross-cutting work: what changed, verification, and **`depends_on`** links between sessions. This is **not** a substitute for raw Cursor transcripts (too verbose, often local-only).

Canonical policy: [`docs/session_logs/README.md`](../session_logs/README.md).

## Why separate from planning?

| Store | Content |
|-------|---------|
| [`docs/planning/`](../planning/) | Product intent: roadmap, backlog, state, requirements |
| [`docs/planning/archive/`](../planning/archive/) | Frozen **text** removed from live planning |
| **`docs/session_logs/`** | **Work narrative**: implementations, paths, commits, dependency chain between sessions |

Use **`planning_refs`** in session front matter to point at live or archived planning when both matter.

## Layout

| Path | Role |
|------|------|
| [`README.md`](../session_logs/README.md) | Triggers, YAML schema, body template, privacy |
| [`MANIFEST.md`](../session_logs/MANIFEST.md) | Append-only index (newest first) |
| [`entries/`](../session_logs/entries/) | One markdown file per session |

## Query cheatsheet

| Goal | Command or file |
|------|-----------------|
| Recent work | [`MANIFEST.md`](../session_logs/MANIFEST.md) |
| Dependency edges | `rg "^depends_on:" docs/session_logs/entries` |
| Children of a slug | `rg "depends_on:.*<slug>" docs/session_logs/entries` |
| By topic | `rg "topics:.*api" docs/session_logs` |

## Agent workflow

1. While editing tracked paths in Cursor, optional **signals** accumulate under `docs/session_logs/.tracking/signals.jsonl` ([`track-scoped-work`](../../.cursor/hooks/track-scoped-work); see [CURSOR_TEST_HOOKS.md](CURSOR_TEST_HOOKS.md)).
2. Draft or write an entry from signals: `python scripts/session_log_draft_from_signals.py` or `--write --slug <slug>`.
3. After substantive **planning + code** work, ensure `entries/YYYY-MM-DD_<slug>.md` has required front matter + short body sections (hand-written or edited from the draft).
4. Append a row to [`MANIFEST.md`](../session_logs/MANIFEST.md).
5. Do not commit secrets or transcript paths.

## Cursor wiring

| Mechanism | Guidance |
|-----------|----------|
| **Rule** | [`.cursor/rules/docs-planning.mdc`](../../.cursor/rules/docs-planning.mdc) — optional session log after large doc/planning work |
| **Skill** | [`.cursor/skills/cinemind-project-planning/SKILL.md`](../../.cursor/skills/cinemind-project-planning/SKILL.md) — session log step after cross-cutting delivery |

## Related

- [README.md](README.md) — AIbuilding index
- [QUERYING.md](QUERYING.md) — full query playbook (manifests, `rg`, crossing planning + sessions)
- [PLANNING_DOCS_ARCHIVE.md](PLANNING_DOCS_ARCHIVE.md) — planning snapshots + manifest
- [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) — rules / skills / hooks
- [CURSOR_RULES.md](CURSOR_RULES.md) — `docs-planning.mdc`
