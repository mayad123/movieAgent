# Attachment Intent Classifier

Deterministic classifier that selects **attachment intent** from the **parsed response** first; the user question and resolver ambiguity are used only as secondary hints.

## Inputs

| Input | Type | Description |
|-------|------|-------------|
| `parsed_response` | `ResponseParseResult` | From `response_movie_extractor.parse_response(response_text)`. |
| `user_query_title` | `str \| None` | Optional title candidate from the user query (e.g. from title extraction). |
| `resolver_ambiguous` | `bool \| None` | Optional; `True` if the resolver reported ambiguity (e.g. multiple candidates). |

## Outputs

| Field | Type | Description |
|-------|------|-------------|
| `intent` | `str` | One of: `primary_movie`, `movie_list`, `scenes`, `did_you_mean`, `none`. |
| `titles` | `list[str]` | Ordered titles to use for enrichment (one or many). |
| `rationale` | `str` | Debug string for logs only; not user-facing. |

## Precedence Rules (first match wins)

1. **Ambiguity**  
   If `resolver_ambiguous is True` → **did_you_mean**.  
   `titles` = movies from response, or `[user_query_title]` if no movies.

2. **2+ movies and list-like**  
   If parsed response has **2 or more distinct movies** and **list-like structure** → **movie_list**.  
   List-like = `has_bullets` \| `has_numbered_list` \| `has_bold_titles` \| `has_title_year_pattern`.  
   `titles` = ordered movie titles from response.

3. **1 movie and scene-like signals**  
   If parsed response has **exactly 1 distinct movie** and **scene trigger** → **scenes**.  
   Scene trigger (user need not say “scenes”): any of  
   - **Scene phrases:** key moments, memorable sequences, opening scene, climax, set pieces, montage, shots, etc.  
   - **Deep-dive phrases:** overview, summary, key points, breakdown, etc.  
   - **Structure:** multiple bullet/numbered items that look like scene descriptions (not Title (Year)).  
   - **Single-movie language:** “the film” / “the movie” mentioned ≥ 2 times.  
   `titles` = `[that movie]`.

4. **1 movie**  
   If parsed response has **exactly 1 distinct movie** → **primary_movie**.  
   `titles` = `[that movie]`.

5. **None**  
   Else → **none**.  
   If `user_query_title` is provided, classifier may still return **primary_movie** with `titles = [user_query_title]` so enrichment can run; otherwise `titles = []`.

## Scenes intent signals (no user “scenes” required)

Scenes intent can trigger when the **response** is effectively about key moments or scenes, even if the user never said “scenes”. All of the following are computed deterministically from the parsed response:

- **Scene-like phrases** (single vocabulary list in `response_movie_extractor`): e.g. `key moments`, `memorable sequences`, `opening scene`, `climax`, `set pieces`, `montage`, `standout moments`, `best moments`, `notable scenes`, `iconic scene`, `shots`, `sequence`, `moment in the film`, `cinematography`, etc.
- **Deep-dive phrases**: `overview`, `summary`, `key points`, `breakdown`, `in detail`, etc.
- **Structural:** `scene_like_enumeration` = True when there are ≥ 2 bullet/numbered lines that look like scene descriptions (no `Title (Year)`, length in range). So enumerated “key moments” or “memorable sequences” trigger without the user asking for scenes.
- **Single-movie language:** `the_film_movie_references` = count of “the film” + “the movie” in the response. If ≥ 2, treated as single-movie deep-dive and can trigger scenes when there is exactly one movie.

Threshold policy in the classifier: **scenes** is triggered when (1 movie and any of: scene phrases, deep-dive phrases, `scene_like_enumeration`, or `the_film_movie_references >= 2`). Multi-movie cases are unchanged (2+ movies and list-like → movie_list).

## Determinism

Given the same `parsed_response`, `user_query_title`, and `resolver_ambiguous`, the classifier always returns the same `intent`, `titles`, and `rationale`. No randomness or external state.

## Usage

```python
from cinemind.response_movie_extractor import parse_response
from cinemind.attachment_intent_classifier import classify_attachment_intent

parsed = parse_response(agent_response_text)
result = classify_attachment_intent(
    parsed,
    user_query_title=extracted_query_title,  # optional
    resolver_ambiguous=resolver_ambiguous,   # optional
)
# result.intent, result.titles, result.rationale
```

Logging: the module logs the selected intent and extracted titles at debug level.
