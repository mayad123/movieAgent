# Planning archive

> **Purpose:** Frozen planning content that is no longer the live source of truth, with **bidirectional links** to current docs and a **manifest** for lookup.

## Canonical live docs

These stay at [`docs/planning/`](../) root and remain the first place contributors and tooling read:

| File | Role |
|------|------|
| `PROJECT.md` | Vision, constraints, update + archive workflow |
| `ROADMAP.md` | Phased outcomes |
| `BACKLOG.md` | Prioritized work |
| `STATE.md` | Capabilities + gaps |
| `SUMMARY.md` | Now / next / decisions |
| `REQUIREMENTS.md` | Requirements + acceptance patterns |

Everything under **`archive/`** is historical or extracted detail.

## When to archive (triggers)

Archive when **any** of the following is true (not all required):

| Trigger | Guideline |
|---------|-----------|
| **Size** | A canonical file exceeds **~350–450 lines** (`ROADMAP.md`, `BACKLOG.md` first). Apply the same budget to other planning files if they grow large. |
| **Supersede** | A whole section or narrative is **replaced**; do not rely on git history alone—snapshot what you remove. |
| **Decision volume** | `SUMMARY.md` **Decisions** grows past **~15 rows**; move older rows to a dated snapshot and leave a stub in the live file. |
| **Delivered clutter** | Large **done** blocks in `BACKLOG.md` obscure active work; move to [`delivered/`](delivered/) (optional) + manifest row. |

**Not a trigger:** typos, single-bullet status updates, link fixes—edit in place.

## Archive shapes

1. **Full-file snapshot** — Copy the entire canonical file before a major rewrite; trim the live file; link stub in live doc if helpful.
2. **Section extract** — Move one oversized heading block into `snapshots/`; replace live section with a **stub** (3–6 lines) + link.

## Naming

Place files in:

- **`snapshots/`** — general snapshots and section extracts  
  Pattern: `YYYY-MM-DD_<source>__<slug>.md`  
  Examples: `2026-03-24_roadmap__phase0-restructure.md`, `2026-04-01_summary__decisions-through-2025.md`

**`source`** (lowercase): `roadmap`, `backlog`, `summary`, `state`, `requirements`, `project`.

- **`delivered/`** (optional) — Completed backlog narratives or large “done” digests  
  Same date + slug pattern; note `archive_of: BACKLOG.md` in front matter.

## Mandatory snapshot header

First lines of every archived markdown file must be YAML front matter:

```yaml
---
archive_of: ROADMAP.md
archived_on: YYYY-MM-DD
reason: Short human-readable reason
superseded_by: ../ROADMAP.md#phase-overview
source_commit: <optional git SHA>
topics: [roadmap, phase-0]
---
```

- **`archive_of`:** canonical filename only (e.g. `ROADMAP.md`).
- **`superseded_by`:** relative path from this file to the **live** doc (and optional `#anchor` for the replacing section).
- **`topics`:** lowercase tokens for `rg "^topics:"` and quick filtering.

Body follows after the closing `---`.

## Bidirectional back-references

1. **Archive → live:** set `superseded_by` in front matter (required).
2. **Live → archive:** after archiving, add under the affected heading (or at file bottom if whole-file):

   `**History:** Prior narrative: [YYYY-MM-DD snapshot](archive/snapshots/YYYY-MM-DD_source__slug.md).`

## Manifest

Every archive event gets one row in [`MANIFEST.md`](MANIFEST.md) (append-only, newest rows at top).

## Query cheatsheet

| Need | Where |
|------|--------|
| What was archived recently? | [`MANIFEST.md`](MANIFEST.md) |
| All roadmap snapshots | `rg 'archive_of: ROADMAP' docs/planning/archive` |
| By topic | `rg 'topics:.*pcache' docs/planning/archive` |
| Correlate with code | `git log -- docs/planning/archive/snapshots/` |

**First-time repos:** If canonical planning files were never in `git log`, skip a “bootstrap” snapshot; the first [`MANIFEST.md`](MANIFEST.md) row happens on the first real archive.

## See also (AI tooling)

- Cursor-oriented overview (rules, skills, query cheatsheet): [`docs/AIbuilding/PLANNING_DOCS_ARCHIVE.md`](../../AIbuilding/PLANNING_DOCS_ARCHIVE.md)
