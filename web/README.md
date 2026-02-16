# CineMind Web App (canonical UI)

**This is the canonical playground UI.** The server serves this `web/` app at `http://localhost:8000/`.

## Structure

```
web/
├── index.html          # Entry page
├── css/
│   └── app.css         # All styles (layout, messages, media strip, composer)
├── js/
│   ├── config.js       # Config (API base URL); override for production
│   └── app.js          # App logic (chat, sidebar, API, media strip)
├── DATA_CONTRACTS.md   # Message, Media Strip, Conversation contracts; backward-compat rules
└── README.md
```

## Configuration

- **API base URL**: Set before loading the app, or edit `js/config.js`.
  - Default: `http://localhost:8000`
  - Override: `window.CINEMIND_API_BASE = 'https://api.example.com';` (must run before `app.js`), or set `window.CINEMIND_CONFIG = { apiBase: '...' };` in `config.js` for your build.

## Serving

### Option 1: CineMind playground server (dev)

From the project root:

```bash
python -m tests.playground_server
```

Then open: **http://localhost:8000/** or **http://localhost:8000/app/**.

The server serves the API (`/query`, `/health`) and this `web/` folder at the root (`http://localhost:8000/`).

### Option 2: Any static server

Serve the contents of `web/` as static files. The app will call the API at the URL set in `config.js` (same-origin or CORS must allow it).

Examples:

```bash
# From project root
cd web && python3 -m http.server 9000
# Open http://localhost:9000 (API must be at localhost:8000 or set CINEMIND_API_BASE)

# Or use npx serve
npx serve web -p 3000
```

### Option 3: Production deploy

Deploy the `web/` directory to your CDN or web server. Point `config.js` (or a build-time replacement) at your production API URL.

## Behaviors (aligned with playground UI)

- **Sidebar**: Conversation list (current thread’s user prompts), collapse/expand, “+ New chat”.
- **Header**: Conversation title, Offline badge, “New” action.
- **Chat column**: Empty state, message list (user / assistant), “Retrieving…” row, Media Strip when API returns `media_strip.movie_title`, Raw response toggle.
- **Composer**: Fixed at bottom, multiline input, send on Enter.

No build step is required; plain HTML, CSS, and JS.

## Data contracts

See **`DATA_CONTRACTS.md`** for:

- **Message**: `role`, `content`, `meta` (optional; assistant may have `media_strip` and raw payload).
- **Media Strip**: `movie_title` (required to show strip), `primary_image_url`, `thumbnail_urls` (optional).
- **Conversation**: `id`, `messages`, and optional `title`, `createdAt`, `updatedAt`.
- **Backward compatibility**: how the UI handles missing or legacy fields so older cached conversations still render.
