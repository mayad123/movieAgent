# CineMind UI — Data contracts

Normalized contracts for the production UI so it runs correctly before additional APIs are added. The UI MUST tolerate missing or legacy fields (backward compatibility).

**For contributors:** The **stable UI response payload** (hero media, candidate gallery, placeholders, error handling) and a reference JSON schema are defined in **[UI_RESPONSE_CONTRACT.md](./UI_RESPONSE_CONTRACT.md)**. Playground and full agent use the same contract; the UI normalizes and renders from that shape and never breaks on missing or malformed data.

---

## 1. Message contract

Messages are the unit of a single user or assistant turn.

| Field    | Type   | Required | Constraints | Notes |
|----------|--------|----------|-------------|--------|
| `role`   | string | **Yes**  | One of `"user"` \| `"assistant"` | Determines layout and styling. |
| `content` | string | **Yes**  | Non-null string (may be `""`) | Displayed as the main message body. |
| `meta`   | object \| null | No | If present, see below. | Only used for **assistant** messages. Ignored for user. |

**Assistant `meta` (optional):**

- **`media_strip`** — Optional. When present and valid, the UI renders a Media Strip at the top of the assistant bubble. See [Media Strip contract](#2-media-strip-contract).
- **`media_candidates`** — Optional. When present, the UI renders a "Did you mean…?" candidate strip (small gallery). See [Media Candidates contract](#3-media-candidates-contract).
- **Raw response** — The entire `meta` object may be shown for debugging via the “Raw response” toggle. No specific shape required; the UI stringifies `meta` as JSON. Additional fields in `meta` are allowed and preserved.

**Constraints:**

- `content` is always string; the UI uses `String(msg.content)` when reading.
- `meta` may be `null`, `undefined`, or an object. The UI must not assume `meta` exists or has any specific keys except when explicitly rendering Media Strip or raw JSON.

---

## 2. Media Strip contract

The Media Strip is **optional** and **non-blocking**. It is rendered only for **assistant** messages, and only when `meta.media_strip` is present and has at least `movie_title`. See playground rules: top of assistant bubble, above response text; no strip if absent.

| Field               | Type     | Required to render strip | Constraints | Notes |
|---------------------|----------|---------------------------|-------------|--------|
| `movie_title`       | string   | **Yes**                   | Non-empty after trim. | Used as label and for placeholder / accessibility. |
| `primary_image_url` | string   | No                        | Valid URL string if present. | One primary image; empty string treated as absent. |
| `page_url`          | string   | No                        | Valid URL if present. | Link to Wikipedia page. |
| `year`              | number   | No                        | 4-digit year. | Extracted from title when available. |
| `thumbnail_urls`    | string[] | No                        | Array of URL strings; UI uses at most first 3. | Extra elements ignored. Non-strings filtered out. |

**Render rules (align with current playground):**

1. **Strip is shown** only when `meta.media_strip` exists and `movie_title` is present and non-empty (after trim). Otherwise no Media Strip is rendered (no empty slot).
2. **With images:** If `primary_image_url` and/or `thumbnail_urls` are present, the UI shows one primary image and up to three thumbnails. Fixed-height slots; skeleton until load; on error, fallback to placeholder for that slot.
3. **Without images:** If only `movie_title` is set (no URLs, or URLs empty), the UI shows a single placeholder card: movie title + “No image available yet.”
4. Images are optional content; layout does not reflow drastically when images load or fail.

**Constraints:**

- `movie_title` is normalized with `String(...).trim()`; empty after trim is treated as missing.
- `primary_image_url` and elements of `thumbnail_urls` are trimmed; empty strings are treated as absent.
- The UI must not depend on live image retrieval (e.g. external APIs) to render; URLs are used as-is for `<img src>`.

---

## 3. Media Candidates contract ("Did you mean…?" gallery)

When the query is ambiguous (e.g. remakes, sequels, same-name films), the API may return `meta.media_candidates` — a small gallery for disambiguation. The UI shows this above or alongside the main response when present.

| Field               | Type     | Required | Constraints | Notes |
|---------------------|----------|----------|-------------|--------|
| `movie_title`       | string   | **Yes**  | Non-empty after trim. | Display label. |
| `page_url`          | string   | **Yes**  | Valid URL. | Link to Wikipedia page. |
| `year`              | number   | No       | 4-digit year. | Extracted from title when available. |
| `primary_image_url` | string   | No       | Valid URL if present. | Thumbnail for the candidate card. |

**Render rules:**

1. **Show candidate strip** when `meta.media_candidates` exists, is an array, and has at least one item.
2. **Layout:** Horizontal strip of clickable cards; each card shows title (+ year if present), optional thumbnail, links to `page_url`.
3. **Fallback:** If `primary_image_url` is missing, show placeholder per card.
4. **Single vs gallery:** If only `media_strip` is present, render the single hero (no candidate strip). If both are present, render the hero plus the candidate strip for "Did you mean…?".

---

## 4. Conversation contract

A conversation is the top-level container for a chat session (sidebar item + message list).

| Field      | Type     | Required | Constraints | Notes |
|------------|----------|----------|-------------|--------|
| `id`       | string   | **Yes**  | Non-empty; unique per conversation. | Stable identifier for routing and storage. |
| `title`    | string   | No       | — | Display in header and sidebar. If missing, UI may derive from first user message. |
| `createdAt`| number   | No       | Unix ms (e.g. `Date.now()`). | For ordering or display. |
| `updatedAt`| number   | No       | Unix ms. | For ordering or display. |
| `messages` | Message[]| **Yes**  | Array of [Message](#1-message-contract) objects. | May be empty. |

**Constraints:**

- `messages` must be an array. If missing or not an array, the UI should treat as empty array.
- Order of `messages` is significant; the UI renders in array order.

---

## 4. Backward compatibility rules

So that **older cached conversations** and **responses from older backends** still render:

1. **Missing `meta`:** Treat as `null`. No Media Strip, no raw payload. Message still renders with `content` only.
2. **`meta` without `media_strip`:** No Media Strip. Other `meta` fields (e.g. for raw response) still used if present.
3. **`media_strip` without `movie_title`:** Do not render the Media Strip. Ignore the strip object.
4. **`movie_title` empty or whitespace:** After trim, treat as missing; do not render the strip.
5. **Wrong types:** Use defensive normalization: `content = String(msg.content ?? '')`, `role` only used if `"user"` or `"assistant"` (otherwise treat as assistant or skip invalid entries per product rule). For `media_strip`, use `String(movie_title).trim()`, and treat `thumbnail_urls` as array only if `Array.isArray(...)` else `[]`. For `media_candidates`, treat as array only if `Array.isArray(...)` else `[]` (ignore otherwise).
6. **Conversation without `id`:** If loading from cache, generate or use a fallback id so the conversation can still be shown; avoid overwriting other conversations.
7. **Conversation without `messages`:** Treat as `messages: []`. Show empty state.
8. **Raw response:** Always show whatever is in `meta` (even if empty or legacy shape) when the user opens “Raw response”. No requirement that `meta` match a fixed schema for debugging.

The UI MUST NOT throw or break the thread when it encounters unknown fields or missing optional fields; it MUST degrade to a safe default (e.g. no strip, empty content, or derived title).

---

## 5. Reference: current playground Media Strip rules

Aligned with `web/index.html` and `web/js/app.js`:

- **Where:** Top of the assistant message bubble, above the response text.
- **When:** Only when the API (or cached payload) includes `meta.media_strip` with at least `movie_title`.
- **If no `media_strip`:** The bubble shows only text; no empty Media Strip slot.
- **With images:** 1 primary image + up to 3 thumbnails; fixed-height slots; skeleton until load; placeholder on error.
- **Without images:** Single placeholder card with movie title and “No image available yet.”
- **No API required:** The strip is optional; the message renders correctly with no `media_strip` or with only `movie_title`.

---

## 6. Summary table

| Contract       | Required fields           | Optional fields | Backward compatibility |
|----------------|---------------------------|-----------------|-------------------------|
| **Message**    | `role`, `content`         | `meta`          | Missing `meta` → no strip, no raw payload. |
| **Media Strip**| `movie_title` (to show strip) | `primary_image_url`, `page_url`, `year`, `thumbnail_urls` | Empty/missing URLs → placeholder card. |
| **Media Candidates** | `movie_title`, `page_url` | `year`, `primary_image_url` | Optional; show "Did you mean…?" strip when present. |
| **Conversation** | `id`, `messages`        | `title`, `createdAt`, `updatedAt` | Missing `messages` → []. Derive title from first user message if needed. |
