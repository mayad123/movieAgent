---
name: cinemind-ux-web
description: >-
  Applies CineMind web UX and visual consistency for vanilla JS/CSS/HTML. Use when
  redesigning UI, improving accessibility, updating layout or themes, adding screens,
  or when the user mentions design system, spacing, typography, color tokens, movie
  hub layout, chat UI, or web/ styling.
---

# CineMind UX and web design

## Canonical references (read before substantial UI change)

- **Architecture and module boundaries:** [`docs/practices/FRONTEND_PATTERNS.md`](../../../docs/practices/FRONTEND_PATTERNS.md) — no build step, `app.js` wiring only, `state.js` / `dom.js` / `api.js`, callback setters, anti-patterns.
- **Hard constraints:** [`.cursor/rules/web-frontend.mdc`](../../rules/web-frontend.mdc) — no new npm deps or framework; network via `web/js/modules/api.js`; prefer `textContent` for user strings.
- **Visual source of truth:** [`web/css/app.css`](../../../web/css/app.css) and sibling sheets under [`web/css/`](../../../web/css/) — extend shared variables and classes before adding one-off inline styles or duplicated values in JS.

## Workflow

1. **Scope** — Identify which modules need changes (`layout.js`, `messages.js`, `posters.js`, etc.) per FRONTEND_PATTERNS; avoid new monolithic “god” modules.
2. **Tokens first** — Extend [`web/css/base.css`](../../../web/css/base.css) (`:root` variables) for color, spacing, type scale, radii, shadows, and motion. Do **not** introduce new one-off hex/radius values in component sheets unless unavoidable (e.g. cinematic modal). Reference: [`docs/features/web/WEB_DESIGN_TOKENS.md`](../../../docs/features/web/WEB_DESIGN_TOKENS.md).
3. **State and DOM** — New UI state lives in `state.js` patterns; DOM entry points in `dom.js`; do not scatter `document.querySelector` in feature modules for shared chrome.
4. **Safety** — Trusted vs user-derived content: follow the rule file for `innerHTML` vs `textContent`.
5. **Cross-surface inheritance checks** — For overlays, pseudo-elements, and icon controls (`::before`/`::after`), explicitly verify inherited typography (`line-height`, `font-size`) in both main and sub-context surfaces. Reference: [`docs/AIbuilding/DEFECT_TO_TOOLING.md`](../../../docs/AIbuilding/DEFECT_TO_TOOLING.md) and [`docs/features/web/WEB_DESIGN_TOKENS.md`](../../../docs/features/web/WEB_DESIGN_TOKENS.md).
6. **Verification (online-first)** — Exercise the UI in a **browser against a running backend** (no JS unit runner in repo). Hooks still run [`tests/smoke/`](../../../tests/smoke/) after `web/` edits; treat that as a quick check, not a substitute for manual online passes.
7. **Visual consistency checklist** — After meaningful UI/CSS changes, spot-check in the browser: **main chat** → **sub-context Movie Hub** → **`projects.html`** → **Movie Details** modal → **Where to watch** drawer. Confirm headers, borders, primary buttons, list/hub chips, and tooltip text centering match documented token patterns.

## Personal vs project

Team-wide layout and constraints live here and in **rules**. Optional **personal** skills under `~/.cursor/skills/` may capture individual brand or copy voice without bloating this file.
