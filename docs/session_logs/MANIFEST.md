# Session logs manifest

> **Append-only** index of session log entries. Add **one row per new entry**; keep **newest first**.

## Columns

| Column | Meaning |
|--------|---------|
| **Date** | `YYYY-MM-DD` (matches entry `date` in front matter) |
| **Slug** | `session_slug` from the entry |
| **Entry** | Path: `entries/YYYY-MM-DD_<slug>.md` |
| **Topics** | Short signal (comma-separated or mirror `topics` from front matter) |
| **Depends on** | Prior sessions this builds on (slugs or filenames); `—` if none |
| **Commits** | Optional git SHAs |
| **Planning refs** | Optional: live or archive planning paths touched |

## Entries

| Date | Slug | Entry | Topics | Depends on | Commits | Planning refs |
|------|------|-------|--------|------------|---------|---------------|

*No rows yet. Append a row for each new file under `entries/`.*
