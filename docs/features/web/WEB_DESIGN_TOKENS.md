# Web design tokens and shared UI chrome

> **Purpose:** Keep the light shell (chat, sidebar, Projects, drawers, panels) visually consistent. New UI should use tokens from [`web/css/base.css`](../../../web/css/base.css) instead of ad hoc hex values.

**Related:** [WEB_FRONTEND.md](WEB_FRONTEND.md) · [FRONTEND_PATTERNS.md](../../practices/FRONTEND_PATTERNS.md)

---

## Where tokens live

| Location | Role |
|----------|------|
| [`web/css/base.css`](../../../web/css/base.css) | `:root` variables for color, type scale, spacing, radii, shadows, motion; optional utility classes (`.app-btn--*`, `.app-list-row--interactive`) |
| [`web/css/chat.css`](../../../web/css/chat.css) | Poster/media math (`:root` blocks for `--poster-*`, `--media-*`) |
| [`web/css/movie-details.css`](../../../web/css/movie-details.css) | **Cinematic dark modal** — intentionally separate palette; do not force light-shell tokens here |

---

## Cross-surface parity

These surfaces should **feel like one product** (same neutrals, borders, primary buttons, header density):

| Surface | Notes |
|---------|--------|
| Main chat (`index.html`) | `--surface-page`, `--surface-sidebar`, `--border-hairline` |
| Sub-context Movie Hub | `--sub-*` surfaces; text/borders align with app tokens where possible |
| Projects (`projects.html`) | Same header min-height (`--chrome-header-min-height`), primary CTA matches composer (`--accent-primary`) |
| Where-to-watch drawer | Matches sidebar background (`--surface-sidebar`) |
| Side / right panels | Glazed sidebar color (`--surface-panel-glaze`, `--border-glass`) |

**Manual pass after meaningful UI changes:** main chat → open sub-hub → Projects page → “More info” modal → where-to-watch drawer; confirm no jarring gray/border/radius shifts.

---

## Token groups (summary)

- **Text:** `--text-primary`, `--text-body-tone`, `--text-secondary`, `--text-muted`, `--text-subtle`, `--text-heading`, `--text-inverse`, `--text-error`
- **Surfaces:** `--surface-page`, `--surface-sidebar`, `--surface-muted`, `--surface-bubble`, `--surface-hover`, `--surface-row-hover`, `--surface-active`, `--surface-placeholder`
- **Borders:** `--border-default`, `--border-hairline`, `--border-strong`, `--border-emphasis`, `--border-subtle-alpha`, `--border-glass`
- **Accents:** `--accent-primary`, `--accent-user`, `--accent-indigo-*` (hub quiet actions), `--accent-warm-*` (badges)
- **Dark media chrome (carousels on light app):** `--surface-dark-chrome`, `--surface-dark-chrome-soft`, `--text-on-dark-muted`
- **Radii:** `--radius-xs` … `--radius-2xl`, `--radius-pill`
- **Shadows:** `--shadow-card`, `--shadow-popover`, `--shadow-modal`, `--shadow-toggle-*`
- **Typography scale:** `--text-body`, `--text-sm`, `--text-xs`, `--text-2xs`, `--text-title`, etc.
- **Spacing:** `--space-1` … `--space-6`
- **Motion:** `--duration-fast`, `--duration-normal`, `--ease-standard` (respects `prefers-reduced-motion` in `base.css`)

---

## Component appearance patterns

| Pattern | Approach |
|---------|----------|
| **Primary button** | `background` / `border`: `--accent-primary`; hover: `--accent-primary-hover` or `--accent-hush-hover` for icon sends |
| **Outline / secondary control** | Border `--border-strong`; hover `--surface-row-hover` |
| **Quiet / hub chip** | Default: `--surface-muted` + `--text-secondary`; hover: `--accent-indigo-*` |
| **List row** | Hover: `--surface-row-hover`; active: `--surface-active`; optional class `.app-list-row--interactive` |
| **Composer strip** | `--surface-sidebar` inner field, `--border-hairline`; focus ring `--accent-primary` |

Optional HTML hooks: `.app-btn`, `.app-btn--primary`, `.app-btn--secondary`, `.app-btn--quiet` (defined in `base.css`).

### Tooltip / pseudo-element pitfall

- For hover pills and `::after` labels on icon controls, do not rely on inherited typography from `body`; explicitly set line-height and center alignment so main and sub-context surfaces render the same.
- Current pattern: `--media-strip-tooltip-line-height` token + `inline-flex` centering in poster overlay tooltip styles (`web/css/media.css`).
