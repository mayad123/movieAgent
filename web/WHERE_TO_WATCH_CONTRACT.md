# Where to Watch — UX & Backend Event Contract

No backend changes yet. This document defines the UI/state contract and the event contract for the future backend call.

---

## 1. UX & State

### 1.1 Affordance

- **Where to Watch** is a button (icon button) on each movie poster card.
- It appears on **poster hover** (same overlay as Add to Collection / Add to Conversation).
- **Single UI action:** clicking it runs `onWhereToWatch(movie)` and opens the drawer. No direct external calls from the browser (e.g. no Watchmode from the client).

### 1.2 Panel (drawer)

- **Position:** Left slide-out panel (drawer) that **pushes** main content to the right when open.
- **Close:** Explicit close affordance (button) and **ESC** key closes the panel.
- **Existing poster interactions** (Add to Collection, Add to Conversation, card link) are unchanged; only the Where to Watch control opens the drawer.

### 1.3 Panel states

| State     | Description |
|----------|-------------|
| **loading** | Skeleton UI while waiting for the backend response. |
| **success** | Results list grouped by **access type** (subscription / free / rental / purchase / TVE if available). Each row: provider name, access type, price (if present), “Open” link (web and/or device deeplink if returned). |
| **empty**   | Message: “No results for your region.” |
| **error**   | Message for rate limit / missing key / network (or other server error). |

State is driven entirely by the result of the single backend call triggered by `onWhereToWatch(movie)`.

### 1.4 State management (UI)

- **Drawer open:** boolean.
- **Current movie:** `{ title, year?, pageUrl?, pageId? }` for which results are shown; `null` when closed.
- **Status:** `'idle' | 'loading' | 'success' | 'empty' | 'error'`.
- **Results:** normalized response (grouped by access type) when status is `'success'`; otherwise `null`.
- **Error message:** string when status is `'error'`; otherwise `null`.

One source of truth: the backend response (or error) sets status and results/error; the UI only renders from that.

---

## 2. Backend event contract

The UI calls **one** endpoint when the user clicks Where to Watch. The backend is responsible for talking to any provider (e.g. Watchmode); the browser never does.

### 2.1 Request (input)

**Method:** `GET` or `POST` (TBD).  
**Path:** TBD (e.g. `/api/where-to-watch` or `/where-to-watch`).

**Query (GET) or body (POST) — JSON shape:**

```json
{
  "title": "The Matrix",
  "year": 1999,
  "pageUrl": "https://en.wikipedia.org/wiki/The_Matrix",
  "pageId": "12345"
}
```

| Field     | Type   | Required | Description |
|----------|--------|----------|-------------|
| `title`  | string | Yes      | Movie title (display / matching). |
| `year`   | number | No       | Release year. |
| `pageUrl`| string | No       | Canonical page URL (e.g. Wikipedia) if available. |
| `pageId` | string | No       | External ID (e.g. Wikipedia page ID) if available. |

All fields are optional on the client for resilience; the backend may require at least `title` and return an error otherwise.

### 2.2 Response (output)

**Success (200):**

```json
{
  "movie": {
    "title": "The Matrix",
    "year": 1999
  },
  "region": "US",
  "groups": [
    {
      "accessType": "subscription",
      "label": "Subscription",
      "offers": [
        {
          "providerName": "Netflix",
          "price": null,
          "webUrl": "https://www.netflix.com/title/20557937",
          "deeplink": null
        }
      ]
    },
    {
      "accessType": "rental",
      "label": "Rent",
      "offers": [
        {
          "providerName": "Apple TV",
          "price": { "amount": 3.99, "currency": "USD" },
          "webUrl": "https://tv.apple.com/...",
          "deeplink": "https://..."
        }
      ]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `movie` | object | Echo or normalized `{ title, year? }`. |
| `region` | string | Region used for results (e.g. `"US"`). |
| `groups` | array | List of access-type groups. |
| `groups[].accessType` | string | One of: `subscription`, `free`, `rental`, `purchase`, `tve`. |
| `groups[].label` | string | Display label (e.g. "Subscription", "Rent"). |
| `groups[].offers` | array | Offers in this group. |
| `offers[].providerName` | string | Provider display name. |
| `offers[].price` | object \| null | `{ amount: number, currency: string }` or null. |
| `offers[].webUrl` | string \| null | Web link to watch. |
| `offers[].deeplink` | string \| null | Device/app deeplink if available. |

**Normalized response (current API):** `GET /api/watch/where-to-watch?tmdbId=&mediaType=movie|tv&country=US` returns **`title`** `{ id, name, year?, mediaType }`, **`region`**, **`offers`** (flat array: provider `{ id, name }`, accessType, price?, webUrl?, iosUrl?, androidUrl?, quality?, lastUpdated). Sorted by accessType then provider name; de-duped. UI accepts both **offers** and legacy **groups** shape.

**Empty results (200):** Same shape with `groups: []` or no offers. UI shows “No results for your region.”

**Error (4xx / 5xx):** JSON body recommended for consistency:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Try again later."
}
```

or

```json
{
  "error": "missing_key",
  "message": "Where to Watch is not configured."
}
```

UI maps HTTP status and optional `error` / `message` to the **error** state and message. The UI normalizes known messages (e.g. **title not found**): a single canonical line is shown — *"Title not found. Try a different spelling or add the year."* — and repeated sentences are de-duplicated.

### 2.3 Access type values

- `subscription` — Included in subscription.
- `free` — Free to watch (ad-supported or free tier).
- `rental` — Rent (time-limited).
- `purchase` — Buy (own).
- `tve` — TV Everywhere (cable/sign-in).

Order of groups in the UI can follow backend order or a fixed order (e.g. subscription → free → rental → purchase → tve).

---

## 3. Wiring the backend (UI side)

The app drives the drawer with **one** action: `onWhereToWatch(movie)`. It opens the drawer, shows the loading state, then calls an optional **`fetchWhereToWatch(movie, callback)`** function:

- **`fetchWhereToWatch(movie, callback)`** — not called from the browser by default. When you implement the backend, define this function (same scope as the app) so that:
  - It calls your backend endpoint with the request shape above.
  - On success (200 + body with `groups`): `callback(null, responseBody)`.
  - On error (network, 4xx/5xx): `callback(new Error('message'))` or `callback({ message: '...' })`.

If `fetchWhereToWatch` is not defined, the UI shows loading then the **empty** state (no results) so you can test the drawer without a backend.

## 4. Server configuration (Watchmode key)

- The backend uses **`WATCHMODE_API_KEY`** (server-side only; never exposed to the client). See **docs/ENV_AND_SECRETS.md**.
- If the key is missing and a Where-to-Watch route is called, the server returns a structured **500** with `error: "missing_key"` and a clear message.

## 5. Constraints

- **No Watchmode (or other provider) calls from the browser.** All lookups go through the app backend.
- **Existing poster interactions** (links, Add to Collection, Add to Conversation) are unchanged; only the Where to Watch control uses this contract and opens the drawer.
