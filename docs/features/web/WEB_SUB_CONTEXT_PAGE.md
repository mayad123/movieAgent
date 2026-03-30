# Sub-context Page (Sub-conversation Movie Hub)

> **See also:** [Web Frontend overview](WEB_FRONTEND.md) (file map, API client, message flow), [API Server](../api/API_SERVER.md) (`POST /query`, `hubConversationHistory`), [errors: Movie Hub guardrails](../../errors/MOVIE_HUB_AND_SUBCONTEXT.md).

## Design
- A dedicated “movie hub” view that appears when the user enters a sub-conversation.
- Like the rest of the UI: vanilla JS, pre-rendered DOM, and CSS classes/`hidden` toggle for view changes.

## UI Goals
- Primary goal: show a dedicated related-movie poster hub anchored to one *selected context movie*.
- Present multiple movies in a compact hub (similar/related) so the user can scan options that are still relevant to the same chosen context.
- The hub should support question-driven narrowing: a user can ask attribute/constraint questions about the related set (e.g., starring/genres/tone), and the UI should update what’s shown/emphasized to match the question.
- The user should be able to ask freely about the movie itself (not only “boxing” into pre-defined categories), while the hub remains bounded to that same context movie’s related universe.

## Features
### DOM structure (expected elements in `web/index.html`)
- `#movieHubView` (`section.movie-hub`)
  - `#movieHubRetrieving` — in-header “Updating hub…” state while a hub filter `/query` is in flight (sub-context; main chat still uses `#retrievingRow`).
  - `#movieHubFilterHistoryWrap` / `#movieHubFilterHistory` — compact **filter history** under the poster row (not a chat transcript). Same `sub.messages` power `hubConversationHistory` and replay; the thread UI is hidden in sub-view (`#messageList` is not shown).
  - `#movieHubResetBtn` — restores the hub to the **original** similar-movies set for this sub (does not delete chat messages).
  - `#movieHubSelectedMovie` / `#movieHubSelectedPoster` / `#movieHubSelectedTitle` / `#movieHubSelectedTagline`
  - `#movieHubAskBtn`
  - Cluster containers:
    - `#movieHubSimilarByGenre`
    - `#movieHubSimilarByTone`
    - `#movieHubSimilarByCast`

### Hub visibility rules
- Hub is visible only when:
  - `appState.conversationView === 'sub'`, and
  - the active sub-conversation thread has a `contextMovie` (`thread.sub.contextMovie`)
- When hub is visible:
  - `#movieHubView` is shown (visibility via `hidden` class removal)
- When hub is not visible (back to main chat):
  - `#movieHubView` is hidden
  - `#messageList` is visible again (main chat transcript)

### Selected movie + ask button behavior
- The mini-hero is populated from `contextMovie`:
  - title/year → `#movieHubSelectedTitle`
  - `imageUrl` → `#movieHubSelectedPoster`
  - optional tagline → `#movieHubSelectedTagline`
- `#movieHubAskBtn` pre-fills the composer with a question like:
  - `Tell me more about <label>`
  - then focuses `#composerInput`

### Question-driven filtering (intended UX)
- The sub-conversation defines the anchor primarily via prompt text:
  - ask-button questions include `Tell me more about <label>` so the LLM stays focused on the selected context movie.
- The JSON `[[CINEMIND_HUB_CONTEXT]]...` marker is used server-side as a parsing trigger:
  - the API strips the marker before sending the remaining question to the agent, then parses the assistant response into `movieHubClusters`.
- The user can then ask constraints in natural language, for example:
  - “Which movies star [actor]?” (filter / highlight posters where cast matches)
  - “Are there movies that aren’t scary?” (exclude horror/scary tone; keep the non-scary subset)
  - “What movies like [movie title]?” (intersect the anchored hub with TMDB-similar movies to that referenced title)
  - “Show me more like [selected movie] but with a lighter vibe.” (tone/intent constraint)
- Expected UX behavior:
  - the hub remains centered on the same context movie
  - the displayed set is narrowed/re-ranked based on the question constraints
  - the assistant response explains the selection and may reference why each movie matches the constraint

- Backend filtering is defensive:
  - if TMDB metadata is unavailable, it preserves the input hub clusters unchanged
  - if filtering would produce an empty hub, it falls back to the original anchored universe (avoids empty/dead-end hubs)

### Candidate movie set + grouping (how hub content is derived)
- Primary (local) data (fast path):
  - reuse `contextMovie.relatedMovies` / `similar` **only if** populated from a real per-movie source (e.g. TMDB-backed details). **Do not** seed the sub from the parent chat’s attachment “universe” (`item.relatedMovies` on posters is the same candidate list for every card — it is not similar titles for the clicked movie).
  - opening a sub from a poster (`addSubConversationFromPoster`) does **not** copy `movie.relatedMovies` onto `contextMovie` so the hub loads via LLM auto-load / TMDB similar for the anchor `tmdbId`.
  - the initial hub content comes from the *currently selected* `contextMovie` on the active sub-conversation (until the user asks a question and the UI applies backend narrowing).
  - if the user selects a different movie (i.e., a new sub-conversation with a different `contextMovie`), the hub should repopulate using that new selection.
- Question-driven narrowing (backend-driven):
  - when the user asks a question in the sub-conversation, the frontend prefixes the outgoing `user_query` with a context marker:
    - `[[CINEMIND_HUB_CONTEXT]]{"title":"...","year":1999,"tmdbId":123,"candidateTitles":["Title (Year)", "..."]}[[/CINEMIND_HUB_CONTEXT]]`
  - the backend strips the marker before calling the agent; after the response it parses the assistant text into genre buckets and returns it as `result.movieHubClusters`.
  - to keep the hub parseable, the LLM should respond with the same `Genre: ...` + numbered `Title (Year)` format.
  - when `candidateTitles` is present, the backend injects those currently-loaded hub titles into the agent prompt, so filtering stays aligned with the posters already shown in the hub (UI still expects the strict genre+numbered-title contract for `movieHubClusters` rendering).
  - for **follow-up** questions in the same sub-conversation, the UI also POSTs `hubConversationHistory`: prior `user` / `assistant` message texts (excluding the current turn). The API prepends a bounded history block before the current question + candidate list (see `src/api/main.py` and [API_SERVER](../api/API_SERVER.md)).
  - the frontend then replaces the rendered hub clusters with `result.movieHubClusters` after the assistant response (via `layout.applyMovieHubClusters()`).

### Multi-turn state, snapshots, and history UI
- **Per-sub state** (`thread.sub`):
  - `similarClusters` — current hub rendered in the DOM.
  - `hubOriginalClusters` — deep clone of the first non-empty hub loaded for this sub (auto-load, related movies, or first successful filter). Used for **Reset hub** and for **recomputing** after a message is removed.
- **Per-message** (`thread.sub.messages[]`):
  - each message has a stable `id` (for row actions).
  - after a hub-updating assistant response, `meta.hubSnapshot` and `meta.movieHubClusters` hold a deep clone of that turn’s clusters (for **Show this hub** preview without changing history).
- **Filter history UI** (sub view only, `web/js/modules/messages.js` — `renderSubHubFilterHistory`):
  - Hub narrowing still uses the composer; turns are stored in `sub.messages` for the API but **no chat-style bubble list** appears — only the top hub row updates, plus this compact history block under the clusters.
  - **Remove** — deletes that message and calls `layout.recomputeHubFromMessages(sub)` (replay remaining turns).
  - **Show this hub** (assistant rows with a snapshot) — `applyMovieHubClusters` with the stored snapshot only.
- **Pure helpers:** `web/js/modules/hub-history.js` (`cloneMovieHubClusters`, `buildHubConversationHistory`, `candidateTitlesFromClusters`).
- Auto-load (LLM-driven) hub clusters:
  - when a sub-conversation is created from a poster, the frontend immediately sends a hub-specific `/query` request that asks for **20 similar movies grouped by genre**.
  - the prompt instructs the LLM to emit a deterministic, parseable format:
    - `Genre: <GenreName>`
    - then 5 numbered lines formatted exactly as `Title (Year)`
  - the backend parses that text into genre buckets, enriches titles into movie cards, and returns them as `result.movieHubClusters`.
- If the structured parse is weak, the backend falls back to extracting `Title (Year)` strings from list-like lines and returns them under a single default genre bucket.
  - the frontend then replaces the rendered hub clusters with `result.movieHubClusters` after `/query` completes (via `layout.applyMovieHubClusters()`).

Performance/consistency notes:
- The auto-load uses `PLAYGROUND` mode for lower latency and deterministic parsing.
- The frontend enforces a short timeout (and retries) for the hub auto-load so transient delays don't “lock” the hub empty.
- The backend enriches posters/IDs for a prefix of titles (defaults to match the requested hub total via `HUB_ENRICH_POSTERS_LIMIT`) and returns placeholders (no image) when resolution fails, so the hub always renders the full 20 items quickly.
- De-dup hub movies before render: if multiple candidates resolve to the same canonical movie (prefer `tmdbId`; fallback `normalizedTitle + year` when ID is missing), keep only the first instance in the hub and remove later duplicates from clusters/history snapshots.
- De-dup posters by TMDB id: if duplicate candidates still slip through resolution, only the first occurrence keeps `primary_image_url`; later duplicates render with empty images to avoid showing the exact same poster repeatedly.
- Gated loading UX: on first entry, the hub shows a loading sign until it has at least 20 VALID genre movies to display (unique, TMDB-resolved items; duplicates/incomplete results do not count). Once that threshold is reached it renders the 20 items immediately (background retries are only used if fewer than 20 valid movies were retrieved). When retrying, the frontend filters out titles already returned in the previous attempt so the next 20 are different.

### Duplicate-handling contract (sub-context)
- Goal: the hub should show unique movie recommendations, not repeated entries under different clusters/labels.
- Canonical key order:
  1. `tmdbId` (authoritative when present)
  2. normalized `title` + `year`
  3. normalized `title` only (last-resort fallback)
- Dedupe points:
  - backend parse/enrichment path (preferred): normalize + dedupe before returning `result.movieHubClusters`
  - frontend safety net: re-check uniqueness before `layout.applyMovieHubClusters()` writes cluster DOM
- If dedupe drops below the target (20), continue retries/fetch with an exclusion list of already kept canonical keys so refill attempts produce genuinely new movies.

**Grouping note**
- The cluster boxes are primarily an initial grouping/rendering strategy (especially `genre` today).
- The broader UX goal is question-driven narrowing while keeping the same context anchor (so the hub doesn’t “jump” to unrelated movies).

### Cluster rendering expectations
- Cluster rendering is handled by `layout.js`’s hub helpers, and uses hero card rendering from `web/js/modules/posters.js`.
- A cluster container is hidden if it has no movies for that specific `kind` (genre/tone/cast).

### Poster icon tooltips (“Where to watch”, “More info”, etc.)
- Tooltip labels are rendered via `::after` on `.media-strip-card-action` in `web/css/media.css`.
- **Taller / shorter pill behind the text:** adjust `--media-strip-tooltip-padding-block` (and optionally `--media-strip-tooltip-padding-inline`) on `:root` in `web/css/chat.css`.

## Expectations (what must be true if the hub isn’t showing)
If you see “the same view keeps rendering” when you click into a sub-conversation, verify:
- State:
  - `appState.conversationView` becomes `'sub'`
  - `appState.activeSubConversationId` is set
  - `getActiveThread().sub.contextMovie` is non-null
- DOM toggles:
  - `web/js/modules/layout.js:updateHeaderForView()` should remove `hidden` from `#movieHubView`
  - `updateHeaderForView()` calls `updateMovieHub(thread)`, and `updateMovieHub()` should ensure the hub content is populated
- Trigger path:
  - `switchConversation(mainId, subId)` sets `conversationView = 'sub'`
  - `addSubConversationFromPoster(movie)` also sets `conversationView = 'sub'` and focuses the composer
- Data loading behavior:
  - initial hub content comes from LLM auto-load (`maybeAutoLoadMovieHubClusters`) and/or **`GET /api/movies/{id}/similar`** via `fetchSimilarMovies` when auto-load exhausts retries (see `layout.js`).
  - `updateMovieHub()` may still render from `contextMovie.relatedMovies` / `similar` when those fields are genuinely per-movie (not the parent reply’s shared candidate list — `addSubConversationFromPoster` does not copy poster `relatedMovies` onto `contextMovie`).
  - if all sources fail, the hub may show the mini-hero only with clusters hidden until a successful load.

