# Planning archive manifest

> **Append-only index** of archived planning artifacts. Add **one row per snapshot** when archiving; **newest first**.

## Columns

| Column | Meaning |
|--------|---------|
| **Archived** | `YYYY-MM-DD` (when the snapshot was captured) |
| **Source** | Canonical file: `ROADMAP.md`, `BACKLOG.md`, etc. |
| **Archive path** | Path under `archive/` (e.g. `snapshots/2026-03-24_roadmap__example.md`) |
| **Reason** | Short note (matches `reason` in snapshot front matter) |
| **Commit** | Optional git SHA of repo state when snapshot was taken |

## Entries

| Archived | Source | Archive path | Reason | Commit |
|----------|--------|--------------|--------|--------|

*No rows yet. Append one row per archive event (newest first). If `docs/planning/*.md` has never been committed, there is no git bootstrap snapshot—start here on the first archive.*

## Snapshots directory

Binary or non-markdown artifacts should not live here; only `.md` snapshots. See [README.md](README.md) for policy.
