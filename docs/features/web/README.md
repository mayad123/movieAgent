# Web feature documentation (`docs/features/web/`)

These docs describe the **vanilla JS** UI under `web/` (no bundler). Start with **[WEB_FRONTEND.md](WEB_FRONTEND.md)** for the full file map, callback wiring, API usage, and CSS architecture.

| Document | Scope |
|----------|--------|
| [WEB_FRONTEND.md](WEB_FRONTEND.md) | Entry point: `index.html`, `js/modules/*`, API client, message vs sub-hub rendering, backend contract |
| [WEB_DESIGN_TOKENS.md](WEB_DESIGN_TOKENS.md) | Visual consistency: CSS variables in `base.css`, cross-surface parity, button/list patterns |
| [WEB_HOME_PAGE.md](WEB_HOME_PAGE.md) | Main chat view (`conversationView === 'main'`) |
| `web/projects.html` + `web/js/projects-app.js` | Dedicated Projects page for persistent multi-project movie context collections |
| [WEB_SUB_CONTEXT_PAGE.md](WEB_SUB_CONTEXT_PAGE.md) | Sub-conversation Movie Hub: hub marker, multi-turn `hubConversationHistory`, filter history UI, reset/replay, TMDB similar fallback |
| [WEB_MORE_INFO_PAGE.md](WEB_MORE_INFO_PAGE.md) | Movie Details modal |

**Related:** [API Server](../api/API_SERVER.md) · [Movie Hub errors / guardrails](../../errors/MOVIE_HUB_AND_SUBCONTEXT.md) · [Frontend patterns](../../practices/FRONTEND_PATTERNS.md)
