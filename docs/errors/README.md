# Errors & Guardrails

This directory documents the most common regressions seen in this codebase, with a focus on:
- `Movie Hub` (sub-context genre buckets, posters, dedupe)
- `Where to Watch` (Watchmode API + UI drawer)

Use these pages before merging changes that touch parsing, prompt contracts, hub thresholds, retries, or external API wiring.

## Quick Navigation

- [Movie Hub + Sub-context Guardrails](MOVIE_HUB_AND_SUBCONTEXT.md)
- [Where to Watch Guardrails](WHERE_TO_WATCH.md)
- [Web UI Regressions](WEB_UI_REGRESSIONS.md)

## Movie Details Guardrails
The full-screen “Movie Details” modal (`Movie Details` / “More Info”) is built to degrade gracefully when TMDB is missing/unavailable.

- Keep external enrichment (TMDB) isolated from Where-to-Watch: failures/timeouts must not prevent the streaming section from loading. This mirrors the failure-isolation approach in `WHERE_TO_WATCH.md`.
- Treat the backend -> frontend payload contract as strict but optional: missing fields should trigger poster-derived fallbacks (never hard-fail and never break rendering). This mirrors the contract-stability principles in `MOVIE_HUB_AND_SUBCONTEXT.md`.
- Avoid stuck loading states: any client-side “Loading details...” UI must clear on timeout/error, and abort any in-flight fetch when the modal closes (no late re-renders into a different movie).

## Resulting behavior (current implementation)
- When the Movie Details modal opens and `tmdbId` is present, the frontend performs an on-demand fetch to `GET /api/movies/{tmdbId}/details` with a bounded timeout.
- If TMDB is disabled/unavailable or the TMDB call fails, the backend returns a minimal response containing only `tmdbId`; the frontend keeps rendering whatever poster-derived fields were already available.
- If the request succeeds, the frontend merges the enriched fields (Story/meta/credits/hero backdrop) into the currently open modal and re-renders the affected sections.
- If the modal is closed or the user opens another movie before the fetch completes, the in-flight request is aborted to prevent late re-renders.

