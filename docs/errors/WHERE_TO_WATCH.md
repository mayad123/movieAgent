# Where to Watch Guardrails (Watchmode)

## Key errors to watch out for

- Missing `WATCHMODE_API_KEY`:
  - Backend should return `500` with `error = "missing_key"`.
  - Frontend should show a readable error (normalized message) instead of failing silently.
- Wrong endpoint usage:
  - Main UI uses `GET /api/watch/where-to-watch` (TMDB-based via `tmdbId`).
  - A legacy endpoint `GET /api/where-to-watch` exists but returns `not_implemented`; ensure the UI does not point to it.
- Missing parameters:
  - Backend returns `400` when both `tmdbId` and `title` are absent, or when invalid `mediaType` is passed.
- Provider payload shape changes:
  - Frontend expects normalized response keys: `offers[]` (or `groups[]`), `region`, and `offers[n].provider.name`.
  - If the normalizer changes, validate UI rendering logic remains compatible.
- Rate limits:
  - Backend may return `429` with `error = "rate_limit_exceeded"`.
  - UI should show the error and not repeatedly retry automatically in a loop.

## What to test (minimum)

- `python3 -m pytest -q tests/unit/integrations/test_where_to_watch_api.py`

When testing UI behavior manually, validate these paths:
- Success path: clicking “Where to watch” for a poster triggers the drawer and renders groups/offers.
- Missing key path: the drawer shows the expected configured-missing message.
- 404/not found: the drawer renders empty state or “not found” state without breaking other UI.
- Rate limit path: the drawer shows a clear message.

## What to consider when changing code

- Frontend concurrency:
  - Sub-context hub auto-load retries can create extra backend load; ensure they do not starve other user actions like opening the Where-to-Watch drawer.
- Contract consistency:
  - Keep error normalization stable so the UI can show a predictable message.

