# Frontend Patterns

> JavaScript and HTML conventions for the CineMind web frontend (`web/`).

<details>
<summary><strong>Quick AI Context</strong> — Jump to what you need</summary>

| I need guidance on... | Jump to |
|----------------------|---------|
| No-framework architecture rules | [Architecture Rules](#architecture-rules) |
| How modules communicate | [Callback Wiring Pattern](#callback-wiring-pattern) |
| State management rules | [State Management](#state-management) |
| DOM element patterns | [DOM Patterns](#dom-patterns) |
| API call conventions | [API Client Pattern](#api-client-pattern) |
| How to build UI elements | [Rendering Patterns](#rendering-patterns) |
| Response normalization | [Data Normalization](#data-normalization) |
| Error handling in the UI | [Error Handling](#error-handling) |
| Naming rules | [Naming Conventions](#naming-conventions) |
| What NOT to do | [Anti-Patterns to Avoid](#anti-patterns-to-avoid) |

</details>

---

## Architecture Rules

### No Build Step

The frontend is vanilla JS served as-is. No bundler, transpiler, or framework.

- ES Modules (`import`/`export`) for modularity
- No npm dependencies
- No TypeScript (use JSDoc for type hints if needed)
- No JSX — DOM manipulation via `document.createElement` or `innerHTML`

### Module Boundaries

```
js/
├── app.js              ← Entry point (wiring only)
├── config.js           ← Configuration (non-module, global)
└── modules/
    ├── state.js        ← State + constants
    ├── dom.js          ← DOM refs
    ├── api.js          ← HTTP client
    ├── layout.js       ← Sidebar, header, panels
    ├── messages.js     ← Chat messages
    ├── posters.js      ← Movie cards, carousels
    ├── normalize.js    ← Data transforms
    └── where-to-watch.js  ← Streaming drawer
```

**Each module has one responsibility.** If a new feature needs UI, API, and state changes, modify the relevant existing modules — don't create a new "feature" module that does all three.

---

## Callback Wiring Pattern

Modules cannot import each other directly (circular dependency risk). Instead, they expose setter functions:

```javascript
// In messages.js
let _callbacks = {};
export function setMessageCallbacks(cb) { _callbacks = cb; }

// Later, when needing to call layout:
_callbacks.showRetrieving();
```

```javascript
// In app.js (wiring)
setMessageCallbacks({
    showRetrieving,        // from layout.js
    hideRetrieving,        // from layout.js
    createHeroCard,        // from posters.js
    createUnifiedMovieStrip, // from posters.js
});
```

### Rules

- `app.js` is the only file that imports from multiple feature modules
- Feature modules import only from `state.js`, `dom.js`, `api.js`, `normalize.js`
- Cross-feature communication goes through callbacks registered in `app.js`
- Never add direct imports between `layout.js`, `messages.js`, `posters.js`, or `where-to-watch.js`

---

## State Management

### Single Source of Truth

`appState` in `state.js` holds all application state:

```javascript
export const appState = {
    conversations: [],
    activeConversationIndex: 0,
    activeSubIndex: -1,
    useRealAgent: false,
    projects: [],
};
```

### Rules

- All state mutations go through `appState` — never store state in DOM attributes or closures
- After mutating state, call the appropriate render function to update UI
- Helper functions (`getActiveConversation()`, `getActiveThread()`) encapsulate navigation logic

### State → UI Flow

```
User action → Mutate appState → Call render function → DOM updates
```

Never:
```
User action → Mutate DOM directly → Hope state stays in sync
```

---

## DOM Patterns

### Pre-rendered Shell

All DOM elements are defined in `index.html`. JavaScript toggles visibility, never creates structural elements.

```html
<!-- In index.html -->
<div class="retrieving hidden" id="retrievingRow">...</div>
```

```javascript
// In layout.js
export function showRetrieving() {
    dom.retrievingRow.classList.remove('hidden');
}
```

### Cached References

`dom.js` caches all element lookups at import time:

```javascript
export const messageList = document.getElementById('messageList');
export const sendBtn = document.getElementById('sendBtn');
```

### Rules

- Never call `document.getElementById()` outside `dom.js`
- Use `dom.elementName` everywhere else
- For dynamically created elements (messages, cards), use `document.createElement()`
- Toggle visibility with `.hidden` class, not `style.display`

---

## API Client Pattern

### Callback Style for Fire-and-Forget

```javascript
export function fetchWhereToWatch(movie, callback) {
    fetch(url).then(res => {
        if (!res.ok) return callback(new Error(res.statusText));
        return res.json().then(data => callback(null, data));
    }).catch(err => callback(err));
}
```

### Async/Await for Request-Response

```javascript
export async function sendQuery(text, useRealAgent) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), SEND_TIMEOUT_MS);
    try {
        const response = await fetch(API_BASE + '/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_query: text }),
            signal: controller.signal,
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return await response.json();
    } finally {
        clearTimeout(timeoutId);
    }
}
```

### Rules

- Always set a timeout via `AbortController`
- Always handle non-200 responses
- Parse errors gracefully (don't assume response is valid JSON)
- API module (`api.js`) is the only file that calls `fetch()`

---

## Rendering Patterns

### Message Rendering

Messages are rendered by building DOM fragments and appending to `#messageList`:

```javascript
const bubble = document.createElement('div');
bubble.className = 'message-bubble';
if (role === 'assistant') {
    renderAssistantContent(text, bubble); // creates <p>, <ul>, <ol>, <li> with textContent
} else {
    bubble.appendChild(document.createTextNode(text));
}
dom.messageList.appendChild(bubble);
```

### Card/Poster Rendering

Movie cards are built as self-contained DOM trees with event listeners attached:

```javascript
export function createHeroCard(movie) {
    const card = document.createElement('div');
    card.className = 'hero-card';
    // Build poster, overlay, actions
    card.querySelector('.wtw-btn').addEventListener('click', () => {
        _callbacks.openWhereToWatch(movie);
    });
    return card;
}
```

### Rules

- Return DOM elements from creation functions, don't append them
- Callers decide where to insert
- Event listeners are attached during creation, not with global delegation
- Use `textContent` for user data (XSS safe), `innerHTML` only for trusted/escaped content

---

## Data Normalization

### Backend → Frontend Contract

`normalize.js` handles all response normalization:

```javascript
export function normalizeMeta(raw) {
    // Handle legacy media_strip format
    // Handle missing attachments
    // Escape HTML in user content
    return normalized;
}
```

### Rules

- All backend responses pass through `normalizeMeta()` before rendering
- Never assume response fields exist — check and default
- HTML-escape user-generated content with `escapeHtml()`
- Keep normalization in `normalize.js`, not spread across modules

---

## Error Handling

### Global Error Overlay

`index.html` includes a global error handler that displays load failures:

```javascript
window.addEventListener('error', function(e) {
    // Show error overlay
});
```

### Per-Operation Errors

```javascript
try {
    const result = await sendQuery(text, useRealAgent);
    appendMessage('assistant', result.response, result);
} catch (err) {
    appendMessage('assistant', 'Something went wrong: ' + err.message);
}
```

### Rules

- Never swallow errors silently
- Show user-facing errors in the chat as assistant messages
- Log to console for debugging
- Timeout errors get a specific message

---

## Naming Conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| Module files | `kebab-case.js` | `where-to-watch.js` |
| Exported functions | `camelCase` | `createHeroCard()` |
| Callbacks object | `_callbacks` | Private, set via setter |
| DOM IDs | `camelCase` | `messageList`, `sendBtn` |
| CSS classes | `kebab-case` | `.hero-card`, `.where-to-watch-drawer` |
| Constants | `UPPER_SNAKE_CASE` | `API_BASE`, `SEND_TIMEOUT_MS` |
| State properties | `camelCase` | `activeConversationIndex` |

---

## Visual consistency (look and feel)

- **Design tokens** for the light shell live in [`web/css/base.css`](../web/css/base.css). Prefer `var(--token)` over new hex values in regional CSS. See [`docs/features/web/WEB_DESIGN_TOKENS.md`](../features/web/WEB_DESIGN_TOKENS.md).
- **Manual pass** when changing layout or styling: main chat, sub-hub, Projects page, movie details modal, where-to-watch drawer — borders, background grays, button styles, and header density should feel like one product.

## Anti-Patterns to Avoid

| Anti-Pattern | Instead Do |
|-------------|-----------|
| Hard-coded `#rrggbb` in `web/css/*.css` for chrome that already has a token | Add or reuse a variable in `base.css`, then `var(--…)` in the component sheet |
| Direct cross-module imports | Use callback wiring via `app.js` |
| `document.getElementById()` in feature modules | Use `dom.js` cached refs |
| State in DOM attributes | Use `appState` |
| Raw `fetch()` in feature modules | Use `api.js` functions |
| `innerHTML` with user data | Use `textContent` or `escapeHtml()` |
| Adding npm dependencies | Write vanilla JS |
| Framework-style components | Keep it simple — functions that return DOM elements |
