# Home Page (Main Chat View)

> **See also:** [Web Frontend overview](WEB_FRONTEND.md), [Sub-context Movie Hub](WEB_SUB_CONTEXT_PAGE.md) (when opening a poster sub-thread).

## Design
- Vanilla JS single-page UI (no router); views are toggled via DOM visibility and CSS classes.
- DOM elements are pre-rendered in `web/index.html`; JS toggles `hidden` and classes based on `appState`.
- State-first: the UI reflects `appState.conversationView === 'main'` and the active conversation/thread.

## UI Goals
- Keep the primary conversation experience fast and scannable.
- Render assistant responses as plain text + simple lists (no arbitrary HTML).
- Present movie context (posters/media) and follow-up affordances inside the existing chat flow.

## Features
### Layout regions
- Sidebar conversation list (and scope selection) on the left.
- Main chat column in the center: header + message list + composer.
- Right panel for collections/projects.
- Where-to-Watch drawer launched from poster cards.

### Request / response flow (what the UI expects)
- Main action posts user text to the backend via `POST /query`.
- UI normalizes backend results into a stable rendering model using `web/js/modules/normalize.js`.
- Messages are appended to `#messageList` and rendered by `web/js/modules/messages.js`.

### Rendering expectations (assistant text contract)
- Assistant messages are rendered as structured text using paragraphs and simple lists.
- HTML injection is avoided by using `textContent` / `createTextNode` paths.
- Newlines drive paragraph/list structure; list formatting is based on lines that start with `- ` or `1. `.

## Expectations (how the “home view” should behave)
- `appState.conversationView === 'main'`
  - `#movieHubView` should be hidden.
  - `#messageList` should be visible (full chat transcript).
- **Sub-context** (`conversationView === 'sub'`) is documented in [WEB_SUB_CONTEXT_PAGE.md](WEB_SUB_CONTEXT_PAGE.md): the **Movie Hub** is shown at the top of the chat column and `#messageList` is **hidden** so filters don’t duplicate as a second chat thread; the composer still sends messages and state remains in `sub.messages`.
- Switching conversations/sub-conversations should call the view update path in `web/js/modules/layout.js`:
  - `updateHeaderForView()` toggles `main.main` (adds `sub-conversation-view` when in sub view).
  - In main view, `updateHeaderForView()` hides `movieHubView` and shows `messageList`.

