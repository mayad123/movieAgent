# Environment and secrets

Server loads from `.env` (repo root or cwd) via `src/config`. **Never** put API keys in `web/` or expose them to the client.

## Setup

```bash
cp .env.example .env
# Edit .env with your values
```

## Watchmode (Where to Watch)

- **`WATCHMODE_API_KEY`** — Optional. Used only on the server for the Where-to-Watch feature (e.g. `/api/where-to-watch`). Get an API key from [Watchmode signup](https://watchmode.com).
- **Server-side only:** The key is read in `src/config` and never sent to the browser or bundled into `web/`.
- **Runtime validation:** At startup, the server logs whether `WATCHMODE_API_KEY` is set. If a Where-to-Watch route is called and the key is missing, the server returns a **structured 500**:
  ```json
  { "error": "missing_key", "message": "Where to Watch is not configured. Set WATCHMODE_API_KEY in the server environment (e.g. .env or secrets manager). Get an API key from https://watchmode.com." }
  ```
- In production, set the key via your secrets manager or platform env (e.g. Cloud Run `--set-env-vars`, GitHub Actions secrets). Do not commit `.env`.

## Other common vars

| Variable | Required | Notes |
|----------|----------|--------|
| `OPENAI_API_KEY` | For Real Agent | Required for real LLM mode. |
| `TAVILY_API_KEY` | No | Enhanced search. |
| `TMDB_READ_ACCESS_TOKEN` | No | TMDB posters/scenes when `ENABLE_TMDB_SCENES=true`. |
| `ENABLE_TMDB_SCENES` | No | `true`/`false`. |
| `WATCHMODE_API_KEY` | No | Where to Watch (server-only). |
| `DATABASE_URL` | No | Default `cinemind.db`. |
| `PORT` | No | API server port (default 8000). |

See `.env.example` for a full commented list.
