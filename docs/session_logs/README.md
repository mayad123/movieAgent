# Session logs

> **Purpose:** Short, **human-written** summaries of coherent working sessions—what changed, why it mattered, and how sessions depend on each other—not raw chat transcripts.

Session logs complement [`docs/planning/`](../planning/) (product intent) and [`docs/planning/archive/`](../planning/archive/) (frozen planning **text**). They record **work narrative**, high-signal paths, optional git SHAs, and **`depends_on`** links to prior sessions.

## Layout

| Path | Role |
|------|------|
| [`MANIFEST.md`](MANIFEST.md) | Append-only index (newest first); **start here** for history |
| [`entries/`](entries/) | One markdown file per session |
| [`.tracking/signals.jsonl`](.tracking/) | **Local only** (gitignored): hook appends edited paths between drafts; see “Automated path signals” |

## Automated path signals (Cursor)

When you edit files in Cursor, a second hook ([`track-scoped-work`](../../.cursor/hooks/track-scoped-work)) may append one line per debounced save to **`docs/session_logs/.tracking/signals.jsonl`**. Prefixes and topics are configured in [`.cursor/hooks/session_track_map.json`](../../.cursor/hooks/session_track_map.json) (includes `src/`, `web/`, `tests/fixtures/scenarios/` for YAML scenarios, `docs/planning/`, `docs/session_logs/entries/`, `.cursor/rules/`, `.cursor/skills/`, `docs/AIbuilding/`).

This **does not** create a finished session log; it only queues paths for drafting.

**Agent / human follow-up:**

```bash
python scripts/session_log_draft_from_signals.py
python scripts/session_log_draft_from_signals.py --write --slug <slug>
```

Then fill in the body, append [`MANIFEST.md`](MANIFEST.md), and commit. Details: [`docs/AIbuilding/CURSOR_TEST_HOOKS.md`](../AIbuilding/CURSOR_TEST_HOOKS.md).

## When to create a log

**Do:** cross-cutting doc + code work; multi-file refactors; investigations whose conclusion future readers need; tying a planning archive event to a story.

**Do not:** single-line fixes; routine bumps—unless they unblock a logged dependency chain.

## Naming

- Pattern: `entries/YYYY-MM-DD_<slug>.md`
- Multiple sessions same day: use distinct slugs, e.g. `2026-03-24_pcache-metrics.md` and `2026-03-24_hub-parsing-fix.md`, or `2026-03-24_feature-a-2.md`

## YAML front matter (required)

Place at the top of every entry:

```yaml
---
session_slug: my-feature-slug
date: YYYY-MM-DD
depends_on: []           # session_slug or entry filename this work built on
follow_up: []            # optional later sessions (often empty; MANIFEST / rg is enough)
topics: [docs, api]
touched_paths:
  - src/api/main.py
related_commits: []      # optional SHAs
planning_refs: []        # e.g. ../planning/BACKLOG.md or ../planning/archive/snapshots/...
supersedes_session: null # optional abandoned line of work
---
```

**Privacy:** do not put secrets, tokens, or **raw Cursor transcript paths** in committed logs. Discourage “see transcript xyz” for shared repos.

## Body template (keep roughly 80–120 lines; split sessions if longer)

1. **Context** — 2–4 bullets: goal, constraints.
2. **Changes** — bullets by area (code vs docs); PR link if any.
3. **Decisions** — only if not in [`docs/planning/SUMMARY.md`](../planning/SUMMARY.md); otherwise “Recorded in SUMMARY …”.
4. **Verification** — tests run, manual checks.
5. **Links** — planning docs touched, planning archive rows, related session logs.

## After you add an entry

1. Append one row to [`MANIFEST.md`](MANIFEST.md) (newest at top).
2. Optionally run `rg "^depends_on:" entries` to validate dependency chains.

## Query cheatsheet

| Need | Where |
|------|--------|
| Recent sessions | [`MANIFEST.md`](MANIFEST.md) |
| Find dependents of a slug | `rg "depends_on:.*<slug>" docs/session_logs/entries` |
| By topic | `rg "topics:.*pcache" docs/session_logs` |
| Session by slug | `rg "session_slug: <slug>" docs/session_logs/entries` |

## Relation to planning archive

| Artifact | Holds |
|----------|--------|
| [`planning/archive/`](../planning/archive/) | Superseded **wording** removed from live planning files |
| `session_logs/` | **What we did** in a session and how it connects to other sessions/commits |

Cross-link with `planning_refs` in front matter when both apply.

## Future extension

If `entries/` grows very large, mirror planning: `session_logs/archive/` + extended manifest—document when needed.

## See also (Cursor)

- [`docs/AIbuilding/SESSION_LOGS.md`](../AIbuilding/SESSION_LOGS.md)
