# Phase 10 — Frontend (browser caller reaches the agent)

**Goal:** a caller can talk to the agent from a web page.
**Exit criterion:** open the page → **Start call** → speak → the worker auto-joins the room and
the agent answers, end to end.

**13 files, no deletions.** token-service token test passes; the React/TS widget typechecks clean.

## What's in it

### token-service (`apps/token-service/`, port 8107)
FastAPI endpoint that mints a short-lived LiveKit JWT.
- `POST /token {room, identity, name}` → `{token, url, room}` — a 1-hour `room_join` grant, built
  with `api.AccessToken().with_grants(VideoGrants(room_join=True, room=...))`. Reads
  `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` from the environment; returns the browser-facing
  `LIVEKIT_URL` (ws:// dev, wss:// later).
- CORS is open (`*`) for dev — lock it to the widget origin in staging+.

**Dispatch:** our worker registers with **no `agent_name`**, so LiveKit **automatically** dispatches
it to every new room — a plain `room_join` token is all the browser needs. If you later give the
worker a name, switch to explicit dispatch (commented `RoomConfiguration` / `RoomAgentDispatch`
block in `main.py`).

### client-widget (`apps/client-widget/`, React 19 + Vite + TS)
- `src/App.tsx` — **Start call** fetches a token, `Room.connect(url, token)`, enables the mic, and
  attaches the agent's audio track on `RoomEvent.TrackSubscribed`; **End call** disconnects. Status
  pill (idle / connecting / connected / error).
- `src/styles.css` — a small dark themed widget.
- `.env.example` — `VITE_TOKEN_URL` (token-service base URL).

## Apply & run
Unzip at repo root, then:
```bash
# token-service (needs LIVEKIT_API_KEY / LIVEKIT_API_SECRET / LIVEKIT_URL in env or .env)
cd apps/token-service && pip install -e . && uvicorn token_service.main:app --port 8107

# client-widget
cd apps/client-widget && cp .env.example .env && npm install && npm run dev   # http://localhost:5173
```
Make sure the LiveKit server (7880), the worker, and the rest of the stack are running. Then open
the page, click **Start call**, allow the microphone, and talk.

**Docker DNS:** set `VITE_TOKEN_URL=http://token-service:8107` (and the worker/token-service share
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`).

## Proving the exit criterion
1. Worker running (no `agent_name`) + LiveKit + token-service + client-widget up.
2. Open `http://localhost:5173` → **Start call** → grant mic.
3. The agent greets you (consent → greeting from Phase 8/7) and you can route a request end to end.
4. `curl -XPOST http://localhost:8107/token -H 'content-type: application/json' -d '{}'` returns a
   token + url if you want to verify the endpoint directly.

## Honest notes
- **Mic needs a secure context:** browsers allow `getUserMedia` on `http://localhost`; from another
  host you need HTTPS (and `wss://` for `LIVEKIT_URL`).
- **CORS `*`** is dev-only.
- **Transcription rendering** (showing live captions in the widget) is easy to add later via
  LiveKit text streams; the widget is audio-first for now.
- The token test runs offline; the full browser↔worker round-trip needs the live LiveKit stack.

**Next:** Phase 11 — Observability & Supervision (self-hosted OTel, supervisor-dashboard, KPIs,
audit-chain integrity job), then Phase 12 (compliance/QA/pilot) and the deferred Persistence phase.
