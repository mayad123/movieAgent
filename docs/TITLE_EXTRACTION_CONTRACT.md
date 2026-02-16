# Title Extraction & Intent Gating Contract

Deterministic (no LLM) extraction of movie titles from user queries for media enrichment. Used by both playground and full agent.

---

## 1. Purpose

- Extract candidate movie title(s) from free-form queries
- Support common phrasings: direct title, "show me images for X", "movies like X"
- Provide routing hints (single vs. similar vs. compare) for enrichment
- Output a stable payload the UI can render as 1 card or a small set

---

## 2. Supported Patterns

| Phrasing | Example | Extracted | Intent |
|----------|---------|-----------|--------|
| Direct | "How to Train Your Dragon" | Full query | single_title |
| Images | "show me images for Inception" | "Inception" | single_title |
| Images | "images for X", "images of X" | X | single_title |
| Similar | "movies like X", "films like X" | X | seed_for_similar |
| Similar | "recommend movies like X", "similar to X" | X | seed_for_similar |
| Info | "who directed The Matrix?" | "The Matrix" | single_title |
| Info | "tell me about X", "what is X" | X | single_title |
| Compare | "compare X and Y" | [X, Y] | compare |

Prefixes are ordered by length (longest first) so "show me images for" wins over "images for".

---

## 3. API

### `extract_movie_titles(user_query: str) -> TitleExtractionResult`

```python
@dataclass
class TitleExtractionResult:
    titles: tuple[str, ...]   # Candidate titles in priority order
    reason: str               # Heuristic: "direct", "prefix:movies_like", etc.
    intent: str               # "single_title" | "seed_for_similar" | "compare"
```

### `get_search_phrases(user_query: str) -> list[str]`

Returns the same titles as `extract_movie_titles(...).titles` for media_enrichment compatibility.

---

## 4. Routing Rules

- **single_title**: Enrich the first title that resolves (hero card)
- **seed_for_similar**: Same as single_title — resolve the seed, show its card; LLM provides similar recommendations in text
- **compare**: Extract X and Y; enrich each; first → media_strip, rest → media_candidates (future multi-card support)

---

## 5. Output Consistency

The enrichment layer (`media_enrichment.py`) produces:

- **media_strip**: Single hero (movie_title, primary_image_url?, page_url?, year?)
- **media_candidates**: Gallery for disambiguation or compare (each: movie_title, page_url, year?, primary_image_url?)

UI contract: `web/UI_RESPONSE_CONTRACT.md`. Renders 1 hero card or hero + candidate strip.

---

## 6. Adding New Patterns

1. Add prefix to `_TITLE_PREFIXES` in `title_extraction.py` (ordered by length)
2. Set intent in the prefix match block
3. Add tests in `tests/unit/test_title_extraction.py`
