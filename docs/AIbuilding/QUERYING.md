# Querying planning history and session logs

How to **look up** archived planning text and session work using the same habits: **manifest first**, **`rg` on YAML front matter**, then **git** when correlating with code.

## Mental model

| Layer | Role | First open |
|-------|------|------------|
| **Manifest** | Human-curated index (newest rows on top) | `MANIFEST.md` in each tree |s
| **Entries / snapshots** | Markdown files with **YAML between `---`** | Grep fields below |
| **Git** | When a change landed, who touched `snapshots/` | `git log -- path` |

YAML is **embedded in `.md` files**, not separate `.yaml` configs. Query patterns assume [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) from the repo root.

## Planning archive (`docs/planning/archive/`)

**Policy and field definitions:** [`docs/planning/archive/README.md`](../planning/archive/README.md).

| Goal | Start here | Command / note |
|------|------------|------------------|
| What was archived recently | [`docs/planning/archive/MANIFEST.md`](../planning/archive/MANIFEST.md) | Scan **Source** / **Archive path** columns |
| Snapshots sourced from `ROADMAP.md` | — | `rg "archive_of: ROADMAP" docs/planning/archive` |
| Broaden to any planning file | — | `rg "^archive_of:" docs/planning/archive` |
| By topic token (front matter `topics:`) | — | `rg "topics:.*pcache" docs/planning/archive` |
| Find where a snapshot points today | Open the `.md` file | Read `superseded_by:` in front matter |
| Time-ordered file changes | — | `git log --oneline -- docs/planning/archive/snapshots/` |

**Front matter keys to grep:** `archive_of`, `archived_on`, `reason`, `superseded_by`, `topics`, `source_commit`.

**Live doc back-reference:** after an archive, the canonical file may include `**History:**` with a link into `archive/snapshots/`. Search stubs with:

`rg "archive/snapshots/" docs/planning`

## Session logs (`docs/session_logs/`)

**Policy and field definitions:** [`docs/session_logs/README.md`](../session_logs/README.md).

| Goal | Start here | Command / note |
|------|------------|------------------|
| Recent sessions | [`docs/session_logs/MANIFEST.md`](../session_logs/MANIFEST.md) | Slug, topics, depends-on columns |
| Sessions that depend on slug `x` | — | `rg "depends_on:.*x" docs/session_logs/entries` |
| List all dependency edges | — | `rg "^depends_on:" docs/session_logs/entries` |
| By topic | — | `rg "topics:.*api" docs/session_logs` |
| One session by slug | — | `rg "session_slug: my-slug" docs/session_logs/entries` |

**Front matter keys to grep:** `session_slug`, `date`, `depends_on`, `follow_up`, `topics`, `touched_paths`, `related_commits`, `planning_refs`, `supersedes_session`.

## Crossing planning and sessions

Session entries may list planning paths in **`planning_refs`** (live or archive). Search:

`rg "planning_refs:" docs/session_logs/entries`

`rg "planning/archive" docs/session_logs/entries`

After a **planning archive** event, optionally add a **session log** that cites the snapshot path so narrative and frozen text stay linked.

## Tips for assistants

- Prefer **`MANIFEST.md`** for “what happened lately” before deep `rg`.
- Use **anchored keys** (`^archive_of:`, `^depends_on:`) to reduce noise when keys might appear in prose.
- Run **`rg` from repo root** so paths in tables match documentation.
- **Manifest tables are markdown**, not YAML—filter with search in-editor or `rg "\\| ROADMAP" docs/planning/archive/MANIFEST.md` once rows exist.

## Related

- [README.md](README.md) — AIbuilding index (mechanisms vs docs history)
- [AI_BUILDING_MAINTAINER.md](AI_BUILDING_MAINTAINER.md) — maintaining `.cursor/` and query doc consistency
- [PLANNING_DOCS_ARCHIVE.md](PLANNING_DOCS_ARCHIVE.md) — archive workflow + Cursor wiring
- [SESSION_LOGS.md](SESSION_LOGS.md) — session logs overview
- [CURSOR_MECHANISMS_FLOW.md](CURSOR_MECHANISMS_FLOW.md) — where rules/skills apply
- [CURSOR_RULES.md](CURSOR_RULES.md) — `docs-planning.mdc` (`docs/**/*.md`)
