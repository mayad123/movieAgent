# Web Frontend

> **Directory:** `web/`
> **Purpose:** Vanilla JS single-page application — the CineMind chat UI. No build step, no framework. Plain HTML, ES modules, and CSS custom properties.

---

## File Map

### Entry

| File | Role | Lines |
|------|------|-------|
| `index.html` | Shell: layout skeleton, all DOM elements, script tags | ~154 |
| `js/app.js` | Module entry point: imports, callback wiring, boot | ~82 |
| `js/config.js` | API base URL configuration | ~7 |

### JavaScript Modules (`js/modules/`)

| Module | Role | Lines |
|--------|------|-------|
| `state.js` | Application state, constants, conversation helpers | ~165 |
| `dom.js` | Cached DOM element references | ~39 |
| `api.js` | HTTP client for backend calls | ~86 |
| `layout.js` | Sidebar, header, right panel, toasts, modal | ~481 |
| `messages.js` | Message rendering, append, send | ~220 |
| `posters.js` | Movie cards, carousels, collections, projects | ~857 |
| `normalize.js` | Response normalization, HTML escaping | ~94 |
| `where-to-watch.js` | Streaming availability drawer | ~227 |

### CSS (`css/`)

| File | Role | Lines |
|------|------|-------|
| `app.css` | Import aggregator (no rules, just `@import`) | ~9 |
| `base.css` | Reset, body, CSS custom properties | ~29 |
| `sidebar.css` | Left sidebar, conversation list, agent toggle | ~219 |
| `header.css` | Header bar, breadcrumb, sub-conversation view | ~218 |
| `chat.css` | Chat column, messages, composer, modal | ~330 |
| `media.css` | Hero cards, carousels, posters, scenes, attachments | ~670 |
| `right-panel.css` | Collections panel, project assets, stack | ~402 |
| `where-to-watch.css` | Streaming availability drawer | ~144 |

---

## Architecture

```mermaid
flowchart TD
    subgraph HTML["index.html"]
        SHELL["DOM Shell<br/>All elements pre-defined"]
    end

    subgraph JS["JavaScript (ES Modules)"]
        APP["app.js<br/>(entry + wiring)"]
        STATE["state.js<br/>(appState)"]
        DOM["dom.js<br/>(element refs)"]
        API_MOD["api.js<br/>(HTTP client)"]
        LAYOUT["layout.js<br/>(sidebar, header, panel)"]
        MSG["messages.js<br/>(chat messages)"]
        POSTERS["posters.js<br/>(cards, carousels)"]
        NORM["normalize.js<br/>(data transforms)"]
        WTW["where-to-watch.js<br/>(drawer)"]
    end

    subgraph CSS["CSS (Component Files)"]
        BASE_CSS["base.css"]
        SIDEBAR_CSS["sidebar.css"]
        HEADER_CSS["header.css"]
        CHAT_CSS["chat.css"]
        MEDIA_CSS["media.css"]
        PANEL_CSS["right-panel.css"]
        WTW_CSS["where-to-watch.css"]
    end

    APP --> STATE
    APP --> DOM
    APP --> LAYOUT
    APP --> MSG
    APP --> POSTERS
    APP --> WTW

    MSG --> API_MOD
    MSG --> NORM
    WTW --> API_MOD
    POSTERS --> DOM
    LAYOUT --> DOM
    LAYOUT --> STATE
    MSG --> STATE
```

---

## Callback Wiring System

Modules avoid circular imports through a callback registration pattern:

```mermaid
flowchart LR
    APP["app.js"]

    APP -->|"setLayoutCallbacks()"| LAYOUT["layout.js"]
    APP -->|"setPosterCallbacks()"| POSTERS["posters.js"]
    APP -->|"setMessageCallbacks()"| MSG["messages.js"]

    LAYOUT -.->|"calls back"| MSG
    LAYOUT -.->|"calls back"| POSTERS
    MSG -.->|"calls back"| LAYOUT
    MSG -.->|"calls back"| POSTERS
    POSTERS -.->|"calls back"| LAYOUT
    POSTERS -.->|"calls back"| WTW["where-to-watch.js"]
```

Each module exposes a `setXxxCallbacks(obj)` function. `app.js` calls all three at boot to inject cross-module references. This means:
- No module directly imports another feature module
- `app.js` is the only place where all modules meet
- Circular dependencies are impossible

---

## Application State (`state.js`)

### State Shape

```mermaid
classDiagram
    class appState {
        +conversations: Conversation[]
        +activeConversationIndex: number
        +activeSubIndex: number
        +useRealAgent: boolean
        +projects: Project[]
    }

    class Conversation {
        +id: string
        +title: string
        +messages: Message[]
        +subConversations: SubConversation[]
        +collections: CollectionItem[]
        +createdAt: string
    }

    class Message {
        +role: "user" | "assistant"
        +content: string
        +meta: Object
    }

    class SubConversation {
        +id: string
        +title: string
        +messages: Message[]
        +movieContext: Object
    }

    appState --> Conversation
    Conversation --> Message
    Conversation --> SubConversation
```

### Key Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `API_BASE` | From `window.CINEMIND_CONFIG.apiBase` | Backend URL |
| `SEND_TIMEOUT_MS` | `60000` | Request abort timeout |

### Key Helpers

| Function | Purpose |
|----------|---------|
| `getActiveConversation()` | Current conversation object |
| `getActiveThread()` | Current message thread (main or sub) |
| `getAssetKey(movie)` | Unique key for deduplicating movie assets |
| `migrateConversationsToNested()` | Upgrades legacy flat conversations |

---

## API Client (`api.js`)

Two backend calls:

### `sendQuery(text, useRealAgent)`

```mermaid
sequenceDiagram
    participant UI as messages.js
    participant API as api.js
    participant Backend as FastAPI

    UI->>API: sendQuery("who directed inception", false)
    API->>Backend: POST /query {user_query, requestedAgentMode}
    Backend-->>API: MovieResponse JSON
    API-->>UI: parsed result
```

### `fetchWhereToWatch(movie, callback)`

```mermaid
sequenceDiagram
    participant WTW as where-to-watch.js
    participant API as api.js
    participant Backend as FastAPI

    WTW->>API: fetchWhereToWatch({title, tmdbId})
    API->>Backend: GET /api/watch/where-to-watch?tmdbId=...
    Backend-->>API: availability data
    API-->>WTW: callback(null, data)
```

---

## UI Layout

```mermaid
flowchart LR
    subgraph App["#app"]
        SIDEBAR["aside.sidebar<br/>(conversation list)"]
        MAIN["main.main"]
        RIGHT["aside.right-panel<br/>(collections)"]
        WTW_DRAWER["aside.where-to-watch-drawer"]
    end

    subgraph Main Content
        HEADER["header.header"]
        CHAT["div.chat-column"]
        COMPOSER["div.composer-wrap"]
    end

    MAIN --> HEADER
    MAIN --> CHAT
    MAIN --> COMPOSER
```

### Panel States

| Panel | States | Toggle |
|-------|--------|--------|
| Sidebar | Expanded / Collapsed | `#sidebarToggle` button |
| Right Panel | Expanded / Collapsed | `#rightPanelToggle` button |
| Where-to-Watch | Open / Closed | Triggered from poster cards |

---

## Message Rendering Flow

```mermaid
flowchart TD
    SEND["User sends message"]
    SEND --> APPEND_USER["appendMessage('user', text)"]
    APPEND_USER --> SHOW_LOADING["showRetrieving()"]
    SHOW_LOADING --> API_CALL["sendQuery(text, useRealAgent)"]
    API_CALL --> NORMALIZE["normalizeMeta(result)"]
    NORMALIZE --> APPEND_ASSIST["appendMessage('assistant', response, meta)"]

    APPEND_ASSIST --> CHECK{"meta.attachments?"}
    CHECK -->|Yes| ATTACHMENTS["createAttachmentsFromSections()"]
    CHECK -->|No| MEDIA{"meta.media_strip?"}
    MEDIA -->|Yes| STRIP["createUnifiedMovieStrip()"]
    MEDIA -->|No| DONE["Render text only"]

    ATTACHMENTS --> DONE
    STRIP --> DONE
```

---

## Media & Poster System (`posters.js`)

The richest UI module — renders movie cards, carousels, and manages collections.

### Card Types

```mermaid
flowchart LR
    subgraph Cards
        HERO["Hero Card<br/>(large poster + overlay info)"]
        CANDIDATE["Candidate Card<br/>(compact poster)"]
    end

    HERO --> ACTIONS["Where to Watch<br/>Add to Collection<br/>Sub-conversation"]
    CANDIDATE --> ACTIONS
```

### Attachment Rendering

```mermaid
flowchart TD
    SECTIONS["attachments.sections[]"] --> LOOP{"For each section"}
    LOOP -->|"type: primary_movie"| HERO["createHeroCard()"]
    LOOP -->|"type: movie_list"| GALLERY["Poster gallery carousel"]
    LOOP -->|"type: scenes"| SCENES["Scene backdrop carousel"]
    LOOP -->|"type: did_you_mean"| DYM["Disambiguation cards"]
```

### Collections & Projects

| Feature | Storage | Scope |
|---------|---------|-------|
| Collections | In `appState.conversations[].collections` | Per-conversation |
| Projects | In `appState.projects` | Cross-conversation |

---

## Where-to-Watch Drawer (`where-to-watch.js`)

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Loading: openWhereToWatchDrawer()
    Loading --> Results: API success
    Loading --> Empty: No results
    Loading --> Error: API error
    Results --> Closed: Close button
    Empty --> Closed: Close button
    Error --> Closed: Close button
```

---

## CSS Architecture

### Import Chain

```mermaid
flowchart TD
    APP_CSS["app.css<br/>(imports only)"]
    APP_CSS --> BASE["base.css<br/>Reset + custom properties"]
    APP_CSS --> SIDEBAR["sidebar.css"]
    APP_CSS --> PANEL["right-panel.css"]
    APP_CSS --> HEADER["header.css"]
    APP_CSS --> CHAT["chat.css"]
    APP_CSS --> MEDIA["media.css"]
    APP_CSS --> WTW["where-to-watch.css"]
```

### CSS Custom Properties (Design Tokens)

Defined in `base.css`:

| Token | Value | Purpose |
|-------|-------|---------|
| `--sub-surface-bg` | `#e8e8ec` | Sub-conversation background |
| `--sub-surface-elevated` | `#e8e8ec` | Elevated surfaces |
| `--sub-surface-soft` | `#d8d8de` | Soft surfaces |
| `--sub-text-primary` | `#0d0d0d` | Primary text |
| `--sub-text-secondary` | `#4b5563` | Secondary text |
| `--sub-border` | `rgba(0,0,0,0.1)` | Border color |
| `--sub-poster-width` | `clamp(3rem,9vw,5.5rem)` | Poster size |

### Component ↔ CSS Mapping

| Component | CSS File | Key Classes |
|-----------|----------|-------------|
| Sidebar | `sidebar.css` | `.sidebar`, `.conversation-list`, `.sidebar-agent-toggle` |
| Header | `header.css` | `.header`, `.header-title`, `.header-sub-view`, `.mode-badge` |
| Chat | `chat.css` | `.chat-column`, `.message-*`, `.composer-*`, `.retrieving` |
| Posters/Media | `media.css` | `.hero-card`, `.candidate-card`, `.carousel-wheel`, `.attachments-*` |
| Right Panel | `right-panel.css` | `.right-panel`, `.collection-*`, `.project-assets-*` |
| Where-to-Watch | `where-to-watch.css` | `.where-to-watch-drawer`, `.where-to-watch-*` |

---

## Backend ↔ Frontend Contract

### Response Shape Consumed

```mermaid
classDiagram
    class MovieResponse {
        +response: string
        +sources: List
        +request_type: string
        +search_metadata: Object
        +media_strip: MediaStrip
        +attachments: Attachments
    }

    class MediaStrip {
        +movie_title: string
        +primary_image_url: string
        +thumbnail_urls: List
    }

    class Attachments {
        +sections: Section[]
    }

    class Section {
        +type: string
        +title: string
        +year: number
        +poster_url: string
        +movies: List
        +scenes: List
    }

    MovieResponse --> MediaStrip
    MovieResponse --> Attachments
    Attachments --> Section
```

### Normalization (`normalize.js`)

`normalizeMeta()` handles backward compatibility:
- Legacy `media_strip` (object) → standardized format
- Missing `attachments` → infer from `media_strip` / `media_candidates`
- HTML escaping for user-generated content

---

## Dependencies

### Backend Endpoints Used

| Endpoint | Module | Purpose |
|----------|--------|---------|
| `POST /query` | `api.js` | Send movie query |
| `GET /api/watch/where-to-watch` | `api.js` | Streaming availability |
| `GET /health` | (config check) | Mode detection |

### External Dependencies

**None.** Zero npm packages, zero CDN imports. Vanilla JS only.

### Browser Requirements

| Feature | Minimum |
|---------|---------|
| ES Modules | Chrome 61+, Firefox 60+, Safari 11+ |
| CSS Custom Properties | Chrome 49+, Firefox 31+, Safari 9.1+ |
| `clamp()` | Chrome 79+, Firefox 75+, Safari 13.1+ |
| `fetch` | Chrome 42+, Firefox 39+, Safari 10.1+ |

---

## Design Patterns & Practices

1. **No Build Step** — plain HTML/CSS/JS served as-is; no bundler, transpiler, or framework
2. **Callback Registry** — cross-module communication via `setXxxCallbacks()` avoids circular imports
3. **DOM Pre-rendered** — all elements exist in `index.html`; JS only toggles visibility and populates content
4. **State-First** — `appState` is the single source of truth; UI renders from state
5. **Progressive Enhancement** — error overlay in `index.html` catches load failures before modules execute
6. **CSS Component Files** — one CSS file per UI region; `app.css` is the import aggregator
7. **Design Tokens** — CSS custom properties in `base.css` for theming consistency

---

## Change Impact Guide

| If you change... | Also check... |
|-----------------|---------------|
| `MovieResponse` shape (backend) | `normalize.js`, `messages.js`, `posters.js` |
| Attachment section types | `posters.js` `createAttachmentsFromSections()` |
| Where-to-Watch API | `api.js` `fetchWhereToWatch()`, `where-to-watch.js` |
| CSS custom properties | All CSS files that reference `--sub-*` tokens |
| DOM element IDs | `dom.js` (all cached refs), `index.html` |
| State shape | `state.js`, `layout.js`, `messages.js` |
| API base URL | `config.js`, deployment configs |
| Callback signatures | `app.js` wiring, all `setXxxCallbacks()` consumers |
