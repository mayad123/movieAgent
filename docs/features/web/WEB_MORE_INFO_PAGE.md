# Movie Details (“More Info”) Modal

> **See also:** [Web Frontend overview](WEB_FRONTEND.md) (module map, `movie-details.js`, `movie-details.css`).

## What it is
- A full-screen modal that shows “Story”, “Credits”, “Details”, “Related titles”, and “Where to Watch” for the currently selected movie.
- It is opened from poster actions (e.g., “More info”) in the main/sub views.

## Visibility rules
- The modal lives in `web/index.html` as `#movieDetailsView` and is toggled by adding/removing the `hidden` class.
- Opening the modal happens via `web/js/modules/movie-details.js::openMovieDetails(movie)`.
- Closing the modal happens via:
  - `#movieDetailsCloseBtn`
  - `Escape` key
  - (calls `web/js/modules/movie-details.js::closeMovieDetails()`)

## DOM structure (expected elements)
- Modal container: `#movieDetailsView`
- Poster/hero:
  - `#movieDetailsPosterWrap`
  - `#movieDetailsHeroMeta`
- Header text:
  - `#movieDetailsTitle`
  - `#movieDetailsYear`
  - `#movieDetailsTagline`
- Sections:
  - Story: `#movieDetailsStorySection`, text in `#movieDetailsStory`
  - Credits: `#movieDetailsCreditsSection`, lists in `#movieDetailsDirectorsList` and `#movieDetailsCastList`
  - Details: `#movieDetailsMetaSection`, list in `#movieDetailsMetaList`
  - Related titles: `#movieDetailsRelatedSection`, list in `#movieDetailsRelatedList`
  - Where to Watch:
    - loading: `#movieDetailsWhereToWatchLoading`
    - results: `#movieDetailsWhereToWatchResults`
    - empty: `#movieDetailsWhereToWatchEmpty`
    - error: `#movieDetailsWhereToWatchError` + `#movieDetailsWhereToWatchErrorText`

## Data flow (optimistic first, TMDB enrichment on-demand)
1. `openMovieDetails(movie)` renders immediately from the provided `movie` object (poster-derived payload).
2. If the movie includes a TMDB identifier (`movie.tmdbId` or `movie.tmdb_id`), the UI performs a non-blocking fetch:
   - `GET /api/movies/{tmdbId}/details`
3. When the fetch completes, the frontend merges the enriched fields into the currently open movie and re-renders:
   - header + hero
   - Story
   - Credits
   - Details meta rows
   - Related titles (backend data is used as enrichment; poster-derived `relatedMovies` is preferred when present)
4. The “Where to Watch” section is independent:
   - it loads via `fetchWhereToWatch()` and does not depend on the TMDB details enrichment succeeding.

## TMDB-backed contract (backend -> frontend)
- The backend returns `MovieDetailsResponse` (see `src/schemas/api.py`), which is intentionally tolerant:
  - fields are optional so the frontend can keep rendering poster-derived fallbacks
  - on TMDB failure/unavailable, the response degrades to `{"tmdbId": <id>}` and the frontend does not break rendering

## Hero readability (backdrop overlay)
- `web/css/movie-details.css` adds a backdrop-based gradient overlay behind the poster/meta when `movie.backdrop_url` exists.
- If `backdrop_url` is missing, the modal falls back to poster-only styling.

## Key errors / guardrails
- The frontend uses an `AbortController` so closing the modal (or switching movies) aborts the in-flight TMDB details fetch.
- This prevents late async results from overwriting a different movie’s modal contents.

