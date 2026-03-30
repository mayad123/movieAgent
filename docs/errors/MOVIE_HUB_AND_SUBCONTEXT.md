# Movie Hub + Sub-context Guardrails

## Key errors to watch out for

- **Similar-movies API fallback (`GET /api/movies/{id}/similar`):** After LLM hub auto-load retries are exhausted, `layout.maybeAutoLoadMovieHubClusters` calls `fetchSimilarMovies` with the anchor’s `tmdbId` when possible, plus `title` / `year` / `mediaType` query params so `build_similar_movie_clusters` gets correct cluster labels and can resolve TMDB id when the path uses a non-numeric placeholder (`_`) and only `title`+`year` are known. If TMDB is disabled or the API returns empty clusters, the UI falls back to `updateMovieHub` (mini-hero only, no hub row).
- **Parent “candidate universe” vs anchor movie:** In chat attachments, `posters.js` may attach the same `relatedMovies` list (the whole main-reply candidate set) to every poster card so the UI had a bounded universe for filtering. That list is **not** “movies similar to the clicked title.” Do **not** copy `movie.relatedMovies` into `sub.contextMovie` when opening a sub-conversation — the hub must be populated from LLM auto-load and/or TMDB similar for the **selected** `tmdbId`. Otherwise the sub hub incorrectly shows the parent query’s movies (e.g. Inception-style picks when the user opened Interstellar).
- `movieHubClusters` contract mismatch: frontend expects an array of clusters shaped as `{ kind, label, movies[] }` where each movie has `{ title, year?, primary_image_url?, page_url?, tmdbId?, mediaType? }`.
- Prompt contract drift: the hub parsing logic relies on deterministic `Genre: <GenreName>` headers plus `1. Title (Year)`-style lines; if the LLM output format changes, parsing can silently degrade to fallback extraction.
- Candidate-title filtering stability: when the UI sends `candidateTitles` in `[[CINEMIND_HUB_CONTEXT]]`, the backend overwrites `movieHubClusters` using deterministic TMDB-backed constraints (instead of relying on fragile structured parsing). This avoids poster under-renders caused by contract/parsing drift.
- “Numbering leaks into poster titles”: list markers like `1.` or `• 1.` can end up inside extracted titles if parsing doesn’t strip leading list markers.
- Fallback extraction pulls titles from narrative prose: fallback regexes must be restricted to list-like lines, otherwise unrelated titles get extracted and rendered in the sub-context.
- Threshold misalignment: backend parsing/enrichment thresholds and frontend gated-loading thresholds must stay consistent (`min_total_items` vs `minRequiredGenreMovies`) or the UI can get stuck or render too early/too little.
- Re-entrancy bugs: hub auto-load must be guarded with `_hubClustersLoading`, `_hubClustersLoaded`, and “stale result” checks against `activeSubConversationId`, otherwise you get repeated fetches and inconsistent rendering.
- Duplicate posters: repeated candidate titles that resolve to the same `tmdbId` should not repeatedly keep `primary_image_url` set (dedupe rule must remain intact end-to-end).

## What to test (minimum)

Run these unit tests when you touch:
- hub parsing (`movie_hub_genre_parsing.py`)
- title normalization (`response_movie_extractor.py`)
- hub contract mapping (`src/api/main.py` marker handling)
- hub rendering thresholds (`web/js/modules/layout.js`)

Commands:
- `python3 -m pytest -q tests/unit/media/test_movie_hub_genre_parsing.py`
- `python3 -m pytest -q tests/unit/media/test_movie_hub_filtering.py`
- `python3 -m pytest -q tests/unit/media/test_movie_hub_deduping.py`
- `python3 -m pytest -q tests/unit/extraction/test_response_movie_extractor.py`

## What to consider when changing behavior

- `PLAYGROUND` vs `REAL_AGENT`:
  - If you rely on strict formatting, validate that the chosen agent mode actually follows the required output format.
  - If `PLAYGROUND` output is not contract-compliant, keep the gated-loading principle but add a retry strategy that switches modes (without endlessly retrying).
- Keep retries bounded:
  - Retries should improve variety/robustness without starving other UI work (notably the main page “Where to Watch” drawer).
- Don’t let parsing failure become “stuck loading”:
  - Always ensure there is an exit path (empty/partial-results state) once enrichment attempts are exhausted.

