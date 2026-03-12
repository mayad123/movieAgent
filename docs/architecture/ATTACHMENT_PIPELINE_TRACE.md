# Movie Attachment Pipeline: Architecture Trace & Invariants

## 1. Call graph: how movie titles become attachments

```
playground.py
  run_playground_query(user_query, request_type?)
    → agent.search_and_analyze(user_query, use_live_data=False, request_type=?, playground_mode=True)
    → apply_playground_attachment_behavior(user_query, result)

agent.py (non-playground)
  search_and_analyze(user_query, ..., playground_mode=False)
    → (no media attachment in body when cache hit)
    → attach_media_to_result(user_query, result)   # when not playground_mode
  search_and_analyze(...) [normal flow]
    → result["recommended_movies"] = meta["similar_movies"]  # from LLM metadata
    → attach_media_to_result(user_query, result)   # when not playground_mode
```

**Title production (playground path):**

```
playground_attachments.apply_playground_attachment_behavior(user_query, result)
  ├─ extract_movie_titles(user_query_normalized)     # title_extraction.py → 2+ titles → multi
  ├─ or parse_response(user_query_stripped)        # response_movie_extractor.parse_response
  │     → ExtractedMovie(title, year?, confidence)
  ├─ get_search_phrases(user_query) / get_search_phrases(agent_response)  # title_extraction.get_search_phrases
  ├─ classify_attachment_intent(parsed, user_query_title=?)  # attachment_intent_classifier
  │     → AttachmentIntentResult(intent, titles[], rationale)
  └─ Branch:
        multi (≥2 titles):
          enrich_batch(titles)                      # media_enrichment
        single (1 title):
          enrich(user_query, fallback_title=single_title, fallback_from_result=result)  # media_enrichment
```

**Title production (non-playground path):**

```
attach_media_to_result(user_query, result)         # media_enrichment.py
  ├─ batch_titles = result.get("recommended_movies") or extract_movie_titles(user_query).titles (if compare & ≥2)
  └─ If batch_titles and len > 1: enrich_batch(batch_titles)
     Else: enrich() is NOT called here; enrich() is only used from playground_attachments.
     (So non-playground single-movie path uses get_search_phrases(user_query) inside attach_media_to_result
      via extract_movie_titles(user_query) when batch_titles is empty or len<=1.)
```

**TMDB resolution:**

```
media_enrichment.enrich(user_query, fallback_title?, fallback_from_result?)
  ├─ _fallback_title_value() uses: fallback_title → fallback_from_result["query"] or sources[0].title → user_query
  ├─ get_search_phrases(user_query)                # title_extraction.py → list of search strings
  ├─ for search_text in get_search_phrases(user_query):
  │     tmdb_resolver.resolve_movie(search_text, year=None, access_token=token)
  │       → TMDBResolveResult(status, movie_id?, poster_path?, confidence, candidates[])
  │     _build_strip_from_tmdb(tr, search_text, token, cache)   → media_strip (from tr.candidates[0] or movie_id)
  │     payloads = [_build_candidate_from_tmdb(c, token) for c in tr.candidates[:MAX_GALLERY_CANDIDATES]]
  │     show_gallery = _should_show_gallery_tmdb(tr)  # status=="ambiguous" and len(candidates)>1
  │     media_candidates = payloads if show_gallery else []
  └─ return MediaEnrichmentResult(media_strip, media_candidates, poster_debug)

media_enrichment.enrich_batch(titles)
  └─ for each title: _enrich_one_title_tmdb(title, token, cache) → resolve_movie(title) → _build_strip_from_tmdb → card
     Returns list of cards (no did_you_mean; each title → one card).
```

**Attachments from enrichment:**

```
playground_attachments (single-movie branch):
  strip = enrichment.media_strip
  result["media_strip"] = strip
  result["media_candidates"] = list(enrichment.media_candidates)
  sections = [primary_movie with items=[_movie_card_item(strip), ...scenes], did_you_mean with items=[_movie_card_item(c) for c in media_candidates]]

media_enrichment.build_attachments_from_media(result)
  sections = [primary_movie from media_strip] + [did_you_mean or movie_list from media_candidates]
  Each item built via _movie_card_item(card) → { title, year?, imageUrl?, sourceUrl?, tmdbId? }
```

---

## 2. Where duplication happens (hero vs did_you_mean)

**Exact location:** `media_enrichment.enrich()` (lines 225–246).

**Cause:** When TMDB returns `status == "ambiguous"` and multiple candidates:

1. `media_strip` is built from the **first** candidate via `_build_strip_from_tmdb(tr, ...)`, which uses `tr.candidates[0]` for title, year, and `movie_id` (lines 65–74).
2. `payloads` is built as **all** candidates: `[_build_candidate_from_tmdb(c, token) for c in (tr.candidates or [])[:MAX_GALLERY_CANDIDATES]]` (line 235).
3. `_should_show_gallery_tmdb(tr)` is True when `tr.status == "ambiguous"` and `len(tr.candidates) > 1` (line 120).
4. So `media_candidates = payloads` includes the same movie as `media_strip` (the first candidate appears in both).

**Relevant functions and fields:**

| File | Function / location | Role in duplication |
|------|----------------------|----------------------|
| `media_enrichment.py` | `enrich()` ~L225–246 | Sets `media_strip` from first candidate and `media_candidates = payloads` (all candidates). Hero = candidates[0], did_you_mean list includes candidates[0]. |
| `media_enrichment.py` | `_build_strip_from_tmdb()` L65–74 | Builds strip from `tr.candidates[0]` (and `tr.movie_id` when resolved). |
| `media_enrichment.py` | `_build_candidate_from_tmdb()` L97–116 | Builds one card per candidate; does **not** set `tmdb_id` on the card (only `page_url` from `c.id`), so dedup by `tmdb_id` requires adding `tmdb_id` to candidate cards. |
| `playground_attachments.py` | Single-movie branch L199–236 | Puts `strip` in primary_movie and `result["media_candidates"]` in did_you_mean without removing the hero from candidates. |

**Result:** The same movie (same TMDB id / same normalized identity) can appear as both the hero and the first “Did you mean?” option. Invariant “hero.tmdb_id must not appear in did_you_mean[*].tmdb_id” is currently violated when TMDB returns ambiguous with multiple candidates.

---

## 3. Invariants (must always hold)

1. **No hero in did_you_mean:** `hero.tmdb_id` must not appear in `did_you_mean[*].tmdb_id`. If `tmdb_id` is missing, treat as (normalized title + year) and require hero’s (title, year) not appear in did_you_mean list.
2. **Uniqueness of attachments:** Every movie attachment (hero + all did_you_mean / movie_list items) is unique by `tmdb_id` when present; when `tmdb_id` is absent, by normalized (title, year).
3. **Non-playground: no user_query as title seed when response data exists:** In non-playground runs, do not use `user_query` as the title seed/fallback when `result` already has title-bearing data (e.g. `recommended_movies`, or response-derived titles used by attachment logic). User query may be used only when there is no such data.
4. **Playground: user_query as only title seed:** In playground runs, treat `user_query` as the only source for title seeds (parsed as response text and/or via `get_search_phrases(user_query)` / `extract_movie_titles(user_query)`). No extra inference from `result["response"]` for the initial list of titles except when parsed response yields no movies, in which case a single fallback title may come from `get_search_phrases(result["response"])`.

---

## 4. Proposed tests (pytest) to lock invariants

**Convention:** Use existing `tests/unit/` layout. Fixtures/mocks keep tests deterministic (no live TMDB/network unless a single optional integration test).

### 4.1 `tests/unit/test_media_enrichment_dedup.py` (new)

- **test_hero_not_in_did_you_mean_when_ambiguous**  
  - Mock `tmdb_resolver.resolve_movie` to return `TMDBResolveResult(status="ambiguous", candidates=[c1, c2])` with distinct `id`/title/year.  
  - Call `enrich(user_query, ...)` (with token mock) and assert `result.media_strip` (hero) has a `tmdb_id` (or title+year) that does not appear in any `result.media_candidates` entry (after candidates expose `tmdb_id`; see below).  
  - Fixture: mock resolver, minimal token/config.

- **test_media_candidates_exclude_hero_by_tmdb_id**  
  - Same ambiguous mock; assert that for every card in `media_candidates`, `card.get("tmdb_id") != media_strip.get("tmdb_id")`.  
  - Ensures dedup is by id once `_build_candidate_from_tmdb` (or attachment builder) sets `tmdb_id` on candidate cards.

- **test_all_attachments_unique_by_tmdb_id**  
  - Build a result that has both `media_strip` and `media_candidates` (e.g. from a single `enrich()` call with ambiguous mock).  
  - Build attachment items (e.g. `_movie_card_item(strip)` and `_movie_card_item(c) for c in candidates`).  
  - Assert all items are unique by `(item.get("tmdbId") or (item.get("title"), item.get("year")))`.

### 4.2 `tests/unit/test_playground_attachments_invariants.py` (new)

- **test_playground_single_movie_hero_not_in_did_you_mean**  
  - Mock `enrich()` to return `MediaEnrichmentResult(media_strip=hero_card, media_candidates=[hero_card, other_card])` (simulating current bug).  
  - Call `apply_playground_attachment_behavior(user_query, result)`.  
  - Assert the primary_movie section’s single poster item does not appear in the did_you_mean section (same tmdbId or same title+year).  
  - Documents current bug or, after fix, locks behavior.

- **test_playground_title_seed_from_query_only**  
  - Call `apply_playground_attachment_behavior("Inception (2010)", result)` with `result` that has `result["response"] = "Some other text"`.  
  - Assert (via mocks or debug metadata) that the title used for enrichment came from parsing `"Inception (2010)"` as response or from `get_search_phrases("Inception (2010)")`, not from `result["response"]`.  
  - Mock `parse_response` / `extract_movie_titles` / `get_search_phrases` to verify which string was used as the seed.

- **test_playground_fallback_to_response_only_when_parsed_empty**  
  - Call `apply_playground_attachment_behavior("", result)` with `result["response"] = "The Matrix (1999)"`.  
  - Assert that when `parse_response("")` yields no movies, the fallback title comes from `get_search_phrases(result["response"])` (single query_title), and that enrichment is called with that fallback.  
  - Mocks: `parse_response` returns no movies; spy on `get_search_phrases` and `enrich`.

### 4.3 `tests/unit/test_attach_media_non_playground.py` (new)

- **test_non_playground_uses_recommended_movies_when_present**  
  - Set `result["recommended_movies"] = ["Inception", "Avatar"]`.  
  - Call `attach_media_to_result(user_query, result)` with any `user_query`.  
  - Assert batch enrichment was called with `["Inception", "Avatar"]` (or equivalent), not with titles derived from `user_query` (e.g. spy on `extract_movie_titles` and ensure it was not used to set batch_titles when recommended_movies is set).

- **test_non_playground_no_user_query_seed_when_response_titles_available**  
  - Simulate that result has some “response-derived” titles (e.g. set a custom attribute or use a minimal agent path that sets `recommended_movies` from metadata).  
  - Call `attach_media_to_result(user_query, result)`.  
  - Assert that the titles passed to `enrich_batch` (or used for single-movie) do not come from `extract_movie_titles(user_query)` when `recommended_movies` is present.  
  - Ensures invariant: in non-playground, user_query is not used as title seed when response data exists.

### 4.4 Optional: `tests/unit/test_tmdb_resolver_ambiguous.py` (or extend existing resolver tests)

- **test_resolve_ambiguous_returns_multiple_candidates**  
  - Mock TMDB API response with 2+ results; call `resolve_movie(title, ...)`.  
  - Assert `status == "ambiguous"` and `len(candidates) >= 2`.  
  - Ensures resolver contract used by enrich() for “Did you mean?”.

- **test_resolve_resolved_returns_single_candidate**  
  - Mock TMDB API response with one clear top result (high score, gap).  
  - Assert `status == "resolved"`, `movie_id` set, and `candidates` has one element.  
  - Ensures no did_you_mean in resolved path.

---

## 5. Fixtures / mocks summary

| Test file | Fixtures / mocks |
|-----------|------------------|
| `test_media_enrichment_dedup.py` | Patch `tmdb_resolver.resolve_movie` to return `TMDBResolveResult` (ambiguous with 2+ candidates, or resolved). Patch `config.get_tmdb_access_token` / `is_tmdb_enabled` to return a non-empty token so enrich runs. Optional: in-memory or mock `MediaCache`. |
| `test_playground_attachments_invariants.py` | Patch `enrich`, `enrich_batch`, `parse_response`, `classify_attachment_intent`, `get_search_phrases`, `extract_movie_titles` as needed. Use a minimal `result` dict (e.g. `{}`, or with `response`, `query`). |
| `test_attach_media_non_playground.py` | Patch `enrich_batch`, `extract_movie_titles`, and optionally `build_attachments_from_media`. Use `result = {}` or `result = {"recommended_movies": [...]}`. |
| `test_tmdb_resolver_ambiguous.py` | Patch `urllib.request.urlopen` (or the request layer used by `resolve_movie`) to return JSON `{ "results": [ {...}, {...} ] }` with controlled ids/titles/years. |

---

## 6. Acceptance checklist

- [x] Exact function(s) and fields causing duplication identified: `media_enrichment.enrich()` (L225–246), `_build_strip_from_tmdb` (first candidate), `payloads` (all candidates), `media_candidates = payloads` without excluding hero; `_build_candidate_from_tmdb` does not set `tmdb_id` on candidate cards.
- [x] Proposed tests cover ambiguous TMDB matches (hero vs did_you_mean dedup), resolved matches (uniqueness, no did_you_mean when resolved), and query-only playground runs (title seed from user_query only; fallback to result["response"] only when parsed empty).
- [x] Invariants defined: hero not in did_you_mean; all attachments unique by tmdb_id (or title+year); non-playground does not use user_query as title seed when response data exists; playground uses user_query as only title seed (with single fallback from result["response"] when parsed yields no movies).

**Implementation (done):** Code has been updated to enforce these invariants: `media_enrichment.enrich()` and `build_attachments_from_media()` exclude the hero from candidates; `_build_candidate_from_tmdb()` sets `tmdb_id`; `attach_media_to_result()` uses only result-derived titles in non-playground; playground filters candidates with `_same_movie_as_strip`. Tests in `test_media_enrichment_dedup.py`, `test_playground_attachments_invariants.py`, and updated `test_media_enrichment.py` lock the behavior.
