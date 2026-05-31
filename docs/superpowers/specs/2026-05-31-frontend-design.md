# AIDungeon Frontend Design

**Date:** 2026-05-31  
**Status:** Approved

## Overview

Add a React + Vite web frontend to the existing AIDungeon CLI game. The Python game logic stays unchanged; a FastAPI server wraps it as an API and serves the built React app as static files. Accessible from phone via local network.

## Directory Structure

```
D:\projects\AIDungeon\
├── backend/
│   ├── server.py       ← new: FastAPI app
│   ├── config.py
│   ├── llm.py
│   ├── storage.py
│   ├── game.py         ← small change: add take_turn_stream generator
│   └── main.py         ← CLI unchanged
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── MainMenu.jsx
│   │   │   └── GameView.jsx
│   │   └── components/
│   │       ├── StoryFeed.jsx
│   │       ├── InputBar.jsx
│   │       └── Sidebar.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── adventures/         ← runtime data, stays at root
├── requirements.txt
└── README.md
```

## Backend: FastAPI (`backend/server.py`)

### Endpoints

```
GET  /api/adventures                   list adventures
POST /api/adventures                   create {name, premise}
DEL  /api/adventures/{slug}            delete adventure

POST /api/adventures/{slug}/load       load into state
POST /api/adventures/{slug}/turn       SSE stream: take a turn {action}
POST /api/adventures/{slug}/save       librarian_batch + save_trunk
POST /api/adventures/{slug}/retry      restore snapshot + retake last turn (SSE)

GET  /api/adventures/{slug}/cards      list all cards
GET  /api/adventures/{slug}/state      full state dump

GET  /api/config                       current model + params
POST /api/config/model                 change model {model_id}
POST /api/config/params                tune story params

GET  /                                 serves frontend/dist/index.html
GET  /assets/*                         serves frontend/dist/assets/*
```

### SSE Event Shape (turn + retry endpoints)

```json
{"type": "status", "text": "Thinking..."}
{"type": "token",  "text": "You "}
{"type": "done"}
```

### Change to `game.py`

Add `take_turn_stream(player_action)` — a generator that yields SSE event dicts, interleaving status events (`thinking`, `writing`) with story tokens. Existing `take_turn` stays unchanged for CLI use.

## Frontend: React + Vite

### Stack
- React 18, Vite, plain CSS (no UI library)
- No TypeScript (keep it simple)
- Native `EventSource` API for SSE

### Pages

**MainMenu** — adventure list with create/delete, model display, change model + params buttons.

**GameView** — full-height dark layout:
- Header: back arrow + adventure name + Cards button
- Story area: centered content column (~680px max), dark background (`#111`), light text, scrolls to bottom on new tokens
- Input bar: fixed at bottom, mode switcher (`Do` / `Say` / `Story`), submit on Enter or button

### Visual Style (AI Dungeon-inspired)
- Background: `#111111`
- Content column background: transparent (dark page)
- Story text: `#e8e8e8`, readable serif or clean sans-serif, ~1.7 line-height
- Input bar: slightly lighter dark (`#1e1e1e`), border top
- Accent: muted purple or amber (single color for buttons/active states)
- Mobile-first: full viewport height, no horizontal scroll

### Cards Sidebar
- Slides in from right as a drawer (mobile) or fixed panel (desktop ≥ 900px)
- Lists cards grouped by category with triggers visible

### Mode Switcher
Maps to existing action prefixes:
- `Do` → `You {input}` (bare text)
- `Say` → `You say, "{input}"`
- `Story` → `{input}` (narrator mode, `>` prefix in CLI)

## Data Flow: Taking a Turn

1. User types in InputBar, hits Enter
2. POST `/api/adventures/{slug}/turn` with `{action: "..."}`
3. Server calls `take_turn_stream`, yields SSE events
4. Frontend uses `fetch` with `ReadableStream` (not `EventSource` — native EventSource is GET-only; fetch streaming handles POST + SSE correctly)
5. On `{"type": "done"}`, close EventSource, re-enable input
6. State auto-saved server-side every turn (existing `save_trunk` behavior)

## Running

**Dev:**
```bash
# terminal 1
cd backend && uvicorn server:app --reload --port 8000

# terminal 2
cd frontend && npm run dev   # Vite on :5173, proxies /api to :8000
```

**Production (phone access):**
```bash
cd frontend && npm run build
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000
# visit http://<local-ip>:8000 on phone
```

## Out of Scope
- Authentication
- Multi-user / multiplayer
- Persistence beyond what the CLI already does
- PWA / install-to-home-screen
