# CSS Style Guide

> CSS architecture and naming conventions for the CineMind web frontend (`web/css/`).

---

## Architecture

### File Organization

```
css/
├── app.css              ← Import aggregator (no rules)
├── base.css             ← Reset, body, CSS custom properties
├── sidebar.css          ← Left sidebar component
├── header.css           ← Header bar component
├── chat.css             ← Chat column, messages, composer
├── media.css            ← Poster cards, carousels, attachments
├── right-panel.css      ← Collections panel
└── where-to-watch.css   ← Streaming drawer
```

**One file per UI region.** `app.css` only contains `@import` statements:

```css
@import "base.css";
@import "sidebar.css";
@import "right-panel.css";
@import "header.css";
@import "chat.css";
@import "media.css";
@import "where-to-watch.css";
```

### Adding a New CSS File

1. Create `css/<component>.css`
2. Add `@import "<component>.css";` to `app.css`
3. Keep imports in logical order (base → layout → features)

---

## Naming Convention

### BEM-Like with Kebab-Case

Classes follow a flat BEM-like convention without strict `__` / `--` separators:

```css
/* Block */
.hero-card { }

/* Block + element */
.hero-card-overlay { }
.hero-card-title { }
.hero-card-actions { }

/* Block + modifier */
.hero-card.active { }

/* State */
.hidden { }
.collapsed { }
```

### Naming Rules

| Pattern | Convention | Example |
|---------|-----------|---------|
| Component block | `.component-name` | `.where-to-watch-drawer` |
| Child element | `.component-name-element` | `.where-to-watch-drawer-header` |
| State/modifier | `.component-name.state` or `.component-name-modifier` | `.right-panel.collapsed` |
| Utility | `.utility-name` | `.hidden` |

### Prefixing by Region

Each CSS file "owns" a namespace:

| File | Prefix | Examples |
|------|--------|---------|
| `sidebar.css` | `.sidebar-*` | `.sidebar-header`, `.sidebar-agent-toggle` |
| `header.css` | `.header-*` | `.header-title`, `.header-sub-view` |
| `chat.css` | `.message-*`, `.composer-*` | `.message-avatar`, `.composer-input` |
| `media.css` | `.hero-card-*`, `.candidate-card-*`, `.carousel-*` | `.hero-card-overlay` |
| `right-panel.css` | `.right-panel-*` | `.right-panel-header`, `.right-panel-dropdown` |
| `where-to-watch.css` | `.where-to-watch-*` | `.where-to-watch-drawer-content` |

---

## CSS Custom Properties (Design Tokens)

### Defined in `base.css`

```css
:root {
    --sub-surface-bg: #e8e8ec;
    --sub-surface-elevated: #e8e8ec;
    --sub-surface-soft: #d8d8de;
    --sub-text-primary: #0d0d0d;
    --sub-text-secondary: #4b5563;
    --sub-border: rgba(0, 0, 0, 0.1);
    --sub-poster-width: clamp(3rem, 9vw, 5.5rem);
    --sub-badge-ring: rgba(0, 0, 0, 0.12);
    --sub-header-min-height: clamp(2.75rem, 8vh, 3.5rem);
    --sub-content-padding: clamp(0.75rem, 2vw, 1rem);
}
```

### When to Use Tokens

| Use Case | Token | Example |
|----------|-------|---------|
| Background colors | `--sub-surface-*` | `background: var(--sub-surface-bg)` |
| Text colors | `--sub-text-*` | `color: var(--sub-text-secondary)` |
| Borders | `--sub-border` | `border: 1px solid var(--sub-border)` |
| Spacing | `--sub-content-padding` | `padding: var(--sub-content-padding)` |
| Poster sizing | `--sub-poster-width` | `width: var(--sub-poster-width)` |

### Rules

- **Always** use tokens for colors, spacing, and sizing that should be consistent
- Add new tokens to `base.css` `:root` when a value is used in 3+ places
- Name tokens as `--sub-<category>-<variant>`
- Use `clamp()` for responsive values

---

## Responsive Design

### Approach: Fluid + Clamp

No media queries for layout. Use `clamp()` for fluid sizing:

```css
/* Fluid padding: min 0.75rem, preferred 2vw, max 1rem */
padding: clamp(0.75rem, 2vw, 1rem);

/* Fluid poster width: min 3rem, preferred 9vw, max 5.5rem */
width: clamp(3rem, 9vw, 5.5rem);
```

### Panel Behavior

Sidebar and right panel collapse via CSS class toggling:

```css
.sidebar { width: 260px; transition: width 0.2s; }
.sidebar.collapsed { width: 0; }

.right-panel { width: 320px; }
.right-panel.collapsed { width: 0; }
```

---

## Layout Patterns

### App Shell (Grid)

```css
.app {
    display: grid;
    grid-template-columns: auto 1fr auto;
    height: 100vh;
}
```

### Chat Column (Flex)

```css
.main {
    display: flex;
    flex-direction: column;
    height: 100%;
}
.chat-column { flex: 1; overflow-y: auto; }
.composer-wrap { flex-shrink: 0; }
```

### Card Layouts (Flex)

```css
.carousel-wheel {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
}
```

---

## Visibility

Use the `.hidden` utility class — never set `display` directly in JS:

```css
.hidden { display: none !important; }
```

```javascript
// GOOD
element.classList.add('hidden');
element.classList.remove('hidden');

// BAD
element.style.display = 'none';
element.style.display = 'block';
```

---

## Transitions & Animations

### Sidebar/Panel Transitions

```css
.sidebar {
    transition: width 0.2s ease;
}
```

### Loading States

```css
.retrieving-dots .dot {
    animation: blink 1.4s infinite;
}
```

### Rules

- Keep transitions under 300ms for responsiveness
- Use `ease` or `ease-in-out` — never `linear` for UI elements
- Skeleton loaders for async content (Where-to-Watch uses `.where-to-watch-skeleton`)
- No transitions on initial page load (avoids flash)

---

## Example: Adding a New Component

Say you're adding a "Movie Quiz" panel.

### 1. Create the CSS file

```css
/* css/quiz.css */

.quiz-panel { }
.quiz-panel-header { }
.quiz-panel-question { }
.quiz-panel-options { }
.quiz-panel-option { }
.quiz-panel-option.selected {
    background: var(--sub-surface-soft);
    border-color: var(--sub-border);
}
.quiz-panel-result { }
```

### 2. Add the import

```css
/* In app.css */
@import "quiz.css";
```

### 3. Add the HTML shell

```html
<!-- In index.html -->
<aside class="quiz-panel hidden" id="quizPanel">
    <div class="quiz-panel-header">...</div>
    <div class="quiz-panel-question" id="quizQuestion"></div>
    <div class="quiz-panel-options" id="quizOptions"></div>
</aside>
```

### 4. Add DOM refs

```javascript
// In dom.js
export const quizPanel = document.getElementById('quizPanel');
export const quizQuestion = document.getElementById('quizQuestion');
export const quizOptions = document.getElementById('quizOptions');
```

---

## Anti-Patterns to Avoid

| Anti-Pattern | Instead Do |
|-------------|-----------|
| Inline styles in JS | Use CSS classes and toggle them |
| Magic numbers (`padding: 13px`) | Use CSS custom properties or consistent scales |
| `!important` (except `.hidden`) | Increase specificity or restructure selectors |
| ID selectors for styling | Use class selectors (IDs are for JS only) |
| Deeply nested selectors | Keep to 2-3 levels max |
| `px` for responsive values | Use `clamp()`, `rem`, `vw`, or custom properties |
| Colors as hex literals everywhere | Define in `:root` as custom properties |
