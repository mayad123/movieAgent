# Batch Enrichment Contract

Multi-movie enrichment for "similar movies" and other multi-card responses.

---

## 1. API

### `enrich_batch(titles, *, max_concurrent=2, max_titles=8) -> list[dict]`

Enriches multiple movie titles to UI-ready cards with bounded concurrency.

- **Input:** `titles: list[str]` — movie title strings (deduped, order preserved)
- **Output:** List of card dicts (same shape as `media_candidates` items): `movie_title`, `page_url`, optional `year`, `primary_image_url`
- **Throttling:** `max_concurrent=2` limits parallel Wikipedia requests
- **Graceful degradation:** One failure does not fail the batch; failed titles become placeholder cards `{movie_title, page_url: "#"}`

---

## 2. attach_media_to_result (batch mode)

When `result["recommended_movies"]` has 2+ titles, `attach_media_to_result` uses batch enrichment:

- `media_strip` = first card (hero)
- `media_candidates` = remaining cards
- `media_gallery_label` = "Similar movies" (or custom via `gallery_label` param)

When `recommended_movies` is absent or has ≤1 title, single-title enrichment from `user_query` is used.

---

## 3. Agent integration

For recommendation responses, FakeLLM populates `LLMResponse.metadata["similar_movies"]`. The agent copies this to `result["recommended_movies"]` before calling `attach_media_to_result`. For live OpenAI, structured output or post-processing could populate `recommended_movies` similarly.

---

## 4. UI

The UI renders `media_candidates` with an optional label (`media_gallery_label`). Default "Did you mean…?" for disambiguation; "Similar movies" for batch. Same card layout for both.
