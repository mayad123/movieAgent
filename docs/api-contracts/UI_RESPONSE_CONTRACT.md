# CineMind UI Response Contract

Stable payload contract for the chat UI. **Playground and full agent use the same shape.** The UI must render reliably for any backend mode and never break on missing or malformed data.

---

## 1. API response shape (top-level)

The `/query` response is stored as **message meta** for assistant messages. The UI reads from `meta`:

| Field              | Type     | Required | Description |
|--------------------|----------|----------|-------------|
| `response`         | string   | **Yes**  | Assistant reply text (or `answer` for legacy). |
| `attachments`       | object   | No       | **Preferred.** Ordered `sections[]` (primary_movie, movie_list, did_you_mean, scenes). See [ATTACHMENTS_SCHEMA.md](../docs/ATTACHMENTS_SCHEMA.md). |
| `media_strip`      | object   | No       | Hero media (legacy). See §2. Kept for backward compatibility. |
| `media_candidates` | array    | No       | "Did you mean…?" / similar list (legacy). See §3. Kept for backward compatibility. |

**Normalization:** The UI MUST treat `content = String(meta.response ?? meta.answer ?? '').trim()` and use that for the message body. When `meta.attachments.sections` is present and non-empty, the UI SHOULD render attachments by section type; otherwise fall back to `media_strip` + `media_candidates`. Missing `meta` → render content only, no media.

---

## 2. Hero media (`media_strip`)

Renders a **single hero**: title + image or placeholder.

| Field               | Type     | Required to show strip | Description |
|---------------------|----------|-------------------------|-------------|
| `movie_title`       | string   | **Yes**                 | Display title. Non-empty after trim. |
| `primary_image_url` | string   | No                      | Hero image URL. Empty/missing → placeholder. |
| `page_url`          | string   | No                      | Link to Wikipedia (optional). |
| `year`              | number   | No                      | 4-digit year (optional). |
| `thumbnail_urls`    | string[] | No                      | Up to 3 extra thumbnails (optional). |

**Placeholder behavior:** If `movie_title` is present but `primary_image_url` is missing or empty, the UI shows a single card: title + “No image available yet.” No image request; no layout break.

**When to show:** Only when `meta.media_strip` exists and `meta.media_strip.movie_title` is non-empty after trim. Otherwise do not render the hero block (no empty slot).

---

## 3. Candidate gallery (`media_candidates`)

Renders a horizontal “Did you mean…?” strip when the query is ambiguous.

| Field               | Type     | Required | Description |
|---------------------|----------|----------|-------------|
| `movie_title`       | string   | **Yes**  | Card label. |
| `page_url`          | string   | **Yes**  | Link (use `#` if missing to avoid broken link). |
| `year`              | number   | No       | Show as “Title (Year)”. |
| `primary_image_url` | string   | No       | Card thumbnail; missing → placeholder. |

**`media_gallery_label` (optional):** Label above the gallery. Default "Did you mean…?" when absent. Use "Similar movies" for batch-enriched recommendations.

**When to show:** When `meta.media_candidates` is an array with at least one item. Each item MUST have `movie_title` (trimmed); skip items with empty title. Invalid or non-array → do not render gallery; do not throw.

---

## 4. JSON schema (reference)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CineMind UI Response Payload",
  "type": "object",
  "required": ["response"],
  "properties": {
    "response": { "type": "string", "description": "Assistant reply text" },
    "media_strip": {
      "type": "object",
      "properties": {
        "movie_title": { "type": "string" },
        "primary_image_url": { "type": "string" },
        "page_url": { "type": "string" },
        "year": { "type": "integer" },
        "thumbnail_urls": { "type": "array", "items": { "type": "string" } }
      },
      "required": []
    },
    "media_candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "movie_title": { "type": "string" },
          "page_url": { "type": "string" },
          "year": { "type": "integer" },
          "primary_image_url": { "type": "string" }
        },
        "required": ["movie_title", "page_url"]
      }
    }
  }
}
```

---

## 5. Error and edge behavior

- **Network/API error:** Show message content as `"Error: <message>"`. Do not render media_strip or media_candidates. Do not throw; always append a message.
- **Malformed meta:** If `meta` is not an object, treat as `null`. If `media_strip` or `media_candidates` have wrong types, ignore them (no strip / no gallery).
- **Empty content:** Allow empty string; bubble still renders (e.g. media only).
- **Image load error:** Replace that image slot with the same placeholder card (title + “No image available yet.”). Do not break the message or the list.

---

## 6. Render order (assistant bubble)

1. **Hero** (if `media_strip.movie_title` present)
2. **Candidate gallery** (if `media_candidates` is non-empty array)
3. **Message content** (always; may be empty)
4. **Raw response** toggle (if meta present)

Same contract for **playground** (`/query` with FakeLLM) and **full agent** (live or cached). Backend always attaches `media_strip` / `media_candidates` via the shared enrichment layer when available.
