# Response Attachments Schema (P0)

Generalized "attachments" payload for assistant responses. Replaces hardcoded "Similar movies" with a section-based model that can represent primary movie, movie lists, disambiguation candidates, and scenes.

## 1. Top-level shape

Responses may include an **`attachments`** object with an ordered list of sections:

```json
{
  "response": "...",
  "attachments": {
    "sections": [
      { "type": "primary_movie", "title": "This movie", "items": [...] },
      { "type": "movie_list", "title": "Similar movies", "items": [...] }
    ]
  }
}
```

- **`attachments`** — Optional. When present, the UI renders each section in order.
- **`attachments.sections`** — Array of section objects. Order is significant.

**Backward compatibility:** The backend continues to emit `media_strip` and `media_candidates`. The UI SHOULD prefer `attachments.sections` when present and fall back to `media_strip` / `media_candidates` when absent.

---

## 2. Section object

| Field   | Type   | Required | Description |
|--------|--------|----------|-------------|
| `type` | string | **Yes**  | Section kind: `primary_movie` \| `movie_list` \| `did_you_mean` \| `scenes` |
| `title` | string | **Yes**  | UI label (e.g. "This movie", "Did you mean?", "Similar movies", "Scenes") |
| `items` | array | **Yes**  | Ordered list of cards/items. Shape depends on `type`. |

### Section types

| type             | Use case                    | Default title (if backend omits) |
|------------------|-----------------------------|----------------------------------|
| `primary_movie`  | Single hero (main subject)  | "This movie"                     |
| `movie_list`     | List of movies (e.g. similar)| "Similar movies"                 |
| `did_you_mean`   | Disambiguation candidates   | "Did you mean?"                  |
| `scenes`         | Scene stills / clips        | "Scenes"                         |

---

## 3. Item shapes per section type

### Movie card (for `primary_movie`, `movie_list`, `did_you_mean`)

Each item is an object with:

| Field       | Type   | Required | Description |
|------------|--------|----------|-------------|
| `title`    | string | **Yes**  | Display title (e.g. movie title). |
| `year`     | number | No       | 4-digit release year. |
| `imageUrl` | string | No       | Poster or thumbnail URL. |
| `sourceUrl`| string | No       | Link (e.g. Wikipedia page). |
| `id`       | string | No       | Stable id for dedupe/keys (e.g. page URL or slug). |

Example:

```json
{
  "title": "Dune (1984 film)",
  "year": 1984,
  "imageUrl": "https://upload.wikimedia.org/.../Dune_1984_Poster.jpg",
  "sourceUrl": "https://en.wikipedia.org/wiki/Dune_(1984_film)",
  "id": "https://en.wikipedia.org/wiki/Dune_(1984_film)"
}
```

### Scene item (for `scenes`)

| Field        | Type   | Required | Description |
|-------------|--------|----------|-------------|
| `imageUrl`  | string | **Yes**  | Scene/still image URL. |
| `caption`   | string | No       | Short description. |
| `sourceUrl` | string | No       | Link to source or clip. |
| `source`    | string | No       | Attribution provider key (e.g. `"TMDB"`). |
| `sourceLabel` | string | No     | Attribution label for UI (e.g. `"The Movie Database"`). |

Example:

```json
{
  "imageUrl": "https://image.tmdb.org/t/p/w780/abc.jpg",
  "caption": "Backdrop (42 votes)",
  "sourceUrl": "https://www.themoviedb.org/movie/27205",
  "source": "TMDB",
  "sourceLabel": "The Movie Database"
}
```

---

## 4. Mapping from legacy fields

When building `attachments.sections` from existing response fields:

- **`media_strip`** → one section `type: "primary_movie"`, `title: "This movie"`, one item:  
  `title` ← `movie_title`, `year` ← `year`, `imageUrl` ← `primary_image_url`, `sourceUrl` ← `page_url`, `id` ← `page_url` or omitted.
- **`media_candidates`** → one section:
  - If `media_gallery_label` is "Did you mean?" or absent (and single primary): `type: "did_you_mean"`, `title: "Did you mean?"`.
  - Else (e.g. "Similar movies", "Movies"): `type: "movie_list"`, `title` ← `media_gallery_label` or "Similar movies".
  - Items: same movie-card shape from each candidate.
- **`scenes`** — Future: section `type: "scenes"`, items with `imageUrl`, `caption?`, `sourceUrl?`.

---

## 5. Reference JSON schema (sections only)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Attachments",
  "type": "object",
  "properties": {
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "title", "items"],
        "properties": {
          "type": { "enum": ["primary_movie", "movie_list", "did_you_mean", "scenes"] },
          "title": { "type": "string" },
          "items": {
            "type": "array",
            "items": {
              "type": "object",
              "description": "Movie card: title, year?, imageUrl?, sourceUrl?, id?. Scene: imageUrl, caption?, sourceUrl?"
            }
          }
        }
      }
    }
  },
  "required": ["sections"]
}
```
