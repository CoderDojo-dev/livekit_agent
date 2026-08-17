# COOKBOOK 5 — ORB + REALTIME ASSISTANT

**The one dependency decision in the whole plan.** `Frontend/customer_portal/package.json` has **no** LiveKit package (verified). `apps/client-widget/package.json` has `livekit-client ^2.20.1` and `@livekit/components-react ^2.9.23` (verified). There is no way to run a real voice session in the portal without those two packages, so this cookbook adds exactly those two, at exactly those versions, and nothing else.

**The orb is not touched.** `orb.tsx`, `orb-renderer.ts`, `orb-plinth.tsx`, and `orb-config.ts` are read-only in this cookbook. Only the *inputs* (`state`, `level`) change from fake to real.

---

## 5.0 What exists, verified

### The orb contract (`components/orb/orb.tsx`, `lib/orb-config.ts`)

```ts
// orb-config.ts
export type OrbState =
  | "disconnected" | "connecting" | "preConnect" | "initializing"
  | "idle" | "listening" | "thinking" | "speaking" | "failed";

export const ORB_SIZE = { rest: 320, call: 240, mobile: 160 } as const;
export const ORB_ACTIVE_STATES: readonly OrbState[] /* the non-resting subset */;
```

```tsx
// orb.tsx — props, verified
<Orb state={orbState} level={level /* 0..1 */} size={number} className?={string} />
```

Internals (do not change): `createOrbRenderer(canvas, { reducedMotion })`, then `renderer.setState(state)` and `renderer.setLevel(level)` on prop change; `reducedMotion` is read **once** at mount from `matchMedia`; a WebGL failure falls back to a static element; the canvas is `aria-hidden`.

### The LiveKit agent state machine (`apps/client-widget/src/App.tsx`, verified)

`useAgent().state` returns exactly: `disconnected`, `connecting`, `pre-connect-buffering`, `initializing`, `idle`, `listening`, `thinking`, `speaking`, `failed`.

**Nine LiveKit states, nine orb states, one hyphen of difference.** `preConnect` ↔ `pre-connect-buffering`. Nothing has to be invented.

### The session flow (verified in `App.tsx`)

```ts
const tokenSource = TokenSource.custom(async (options) => { /* POST /token */ });
const session = useSession(tokenSource, {
  roomName: ROOM_PREFIX,
  participantName: "Caller",
  agentConnectTimeoutMilliseconds: 30_000,
});
<AgentSessionProvider session={session} volume={1} muted={false}>

// inside:
const session = useSessionContext();
await session.start({
  tracks: {
    microphone: { enabled: true, publishOptions: { preConnectBuffer: true } },
    camera: { enabled: false },
    screenShare: { enabled: false },
  },
});
await session.end();
session.isConnected;
session.connectionState;   // "disconnected" is the only reliable end-of-call latch
```

### The token service (verified, `apps/token-service/src/token_service/main.py`)

`POST /token {room, identity, name}` → `{token, url, room, agent_name}`; 15-minute TTL; grants `room_join` only (`room_create=False`, `can_update_own_metadata=False`); dispatches `LIVEKIT_AGENT_NAME`; sets participant attribute `telecom.caller_msisdn` **from the `PILOT_MSISDN` env var**; `POST /client-events` for browser telemetry; CORS default `http://localhost:5173`.

Two consequences the portal must handle:

1. **`/token` is unauthenticated and takes a client-supplied `room` and `identity`.** The portal must never expose it to the browser. Mint through a **server function** so the room name and identity are derived from the verified session cookie, and the token-service origin stays server-side (exactly the discipline `.env.example` already demands for `BUSINESS_API_URL`).
2. **The caller MSISDN is global.** With `PILOT_MSISDN`, every portal caller looks like the pilot subscriber to the agent. That is fine for a demo and wrong for a real portal → decision gate §5.2.

---

## 5.1 Dependencies (approval gate 1)

```diff
   "dependencies": {
+    "@livekit/components-react": "^2.9.23",
+    "livekit-client": "^2.20.1",
```

Exactly the client-widget versions, so one LiveKit generation is in play across the repo. No other manifest change. Note for CI (Cookbook 7): this is the commit that makes the portal build weigh more; lazy-load the assistant route (§5.6) so the other nine tabs do not pay for it.

---

## 5.2 Caller identity (approval gate 2)

**Option A — additive optional field on the token service (recommended).**

```diff
 class TokenRequest(BaseModel):
     room: str
     identity: str
     name: str | None = None
+    caller_msisdn: str | None = None
@@
-    token.with_attributes({CALLER_MSISDN_ATTRIBUTE: PILOT_MSISDN})
+    caller_msisdn = req.caller_msisdn or PILOT_MSISDN
+    token.with_attributes({CALLER_MSISDN_ATTRIBUTE: caller_msisdn})
```

Purely additive: the field defaults to `None`, so `apps/client-widget` and every existing caller behave **identically**. The portal supplies the MSISDN it read from `/api/v1/me/profile/detail` for the authenticated customer — server-side, never from the browser.

**Option B — change nothing.** The portal works, the orb works, the transcript works, but the agent greets every portal customer as the pilot subscriber. Acceptable only for a demo.

Do not consider a third option that lets the browser choose the MSISDN.

---

## 5.3 Server-side token minting

**Modify** `src/lib/api/config.ts` — one addition, following the existing no-`VITE_` rule:

```ts
/**
 * Token service origin. Server-only, exactly like BUSINESS_API_URL: the browser
 * must never learn it, because POST /token is unauthenticated and accepts a
 * caller-chosen room and identity.
 */
export const TOKEN_SERVICE_URL = (
  process.env["TOKEN_SERVICE_URL"] ?? "http://localhost:8107"
).replace(/\/$/, "");
```

**Modify** `.env.example`:

```
# ---------------------------------------------------------------------------
# token-service origin (server-to-server; the browser never calls it directly)
# ---------------------------------------------------------------------------
# POST /token is unauthenticated and accepts a caller-supplied room/identity, so
# the portal mints tokens server-side from the verified session cookie only.
TOKEN_SERVICE_URL=http://localhost:8107
# Inside docker compose:
# TOKEN_SERVICE_URL=http://token-service:8107
```

**Add** `src/lib/api/voice.server.ts`:

```ts
import { createServerFn } from "@tanstack/react-start";
import { TOKEN_SERVICE_URL, BUSINESS_API_TIMEOUT_MS } from "./config";
import { ApiError } from "./errors";
import { authedMiddleware } from "./middleware";
import { getSession } from "./session.server";
import { fetchProfileDetail } from "./me.server";

export type VoiceGrant = {
  token: string;
  url: string;
  room: string;
  agentName: string | null;
  /** Display name for the customer's own turns in the transcript. */
  participantName: string;
};

/**
 * Mint a LiveKit join token for the signed-in customer.
 *
 * Why this is a server function and not a browser fetch:
 *   - token-service POST /token has no authentication and trusts the room and
 *     identity it is given, so only the server may choose them;
 *   - the identity is derived from the session cookie (customer_id), which the
 *     browser cannot forge (HMAC-signed, httpOnly);
 *   - the token-service origin never reaches the client bundle, matching the
 *     BUSINESS_API_URL discipline documented in .env.example.
 *
 * The returned token is short-lived by design (15 minutes, set by the token
 * service) and is only ever used to join one room.
 */
export const createVoiceGrant = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<VoiceGrant> => {
    const session = await getSession();
    if (!session?.customerId) {
      throw new ApiError(401, "No customer session.", "/token");
    }

    // The agent needs a subscriber to resolve. Read it from the client-scoped
    // profile route, never from the browser.
    const profile = await fetchProfileDetail();

    // Stable prefix + random suffix: one room per call, never reused, and never
    // guessable by another customer.
    const suffix = crypto.randomUUID().slice(0, 8);
    const room = `portal-${session.customerId}-${suffix}`;
    const identity = `customer-${session.customerId}`;
    const participantName = profile.full_name ?? profile.first_name ?? "You";

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), BUSINESS_API_TIMEOUT_MS);

    try {
      const response = await fetch(`${TOKEN_SERVICE_URL}/token`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          room,
          identity,
          name: participantName,
          // Only meaningful once the token service accepts it (Cookbook 5 §5.2,
          // Option A). Older builds ignore the field and fall back to
          // PILOT_MSISDN, so sending it is always safe.
          caller_msisdn: profile.msisdn ?? null,
        }),
      });

      if (!response.ok) {
        throw new ApiError(response.status, await response.text(), "/token");
      }

      const payload = (await response.json()) as {
        token: string;
        url: string;
        room: string;
        agent_name?: string | null;
      };

      if (!payload.token || !payload.url) {
        throw new ApiError(502, "Token service returned an incomplete grant.", "/token");
      }

      return {
        token: payload.token,
        url: payload.url,
        room: payload.room,
        agentName: payload.agent_name ?? null,
        participantName,
      };
    } finally {
      clearTimeout(timer);
    }
  });

/** Fire-and-forget browser telemetry, proxied so the origin stays server-side. */
export const reportVoiceEvent = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .validator((input: { event: string; details?: Record<string, unknown> }) => input)
  .handler(async ({ data }) => {
    try {
      await fetch(`${TOKEN_SERVICE_URL}/client-events`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ event: data.event, details: data.details ?? {} }),
      });
    } catch {
      // Observability must never block or fail the call path — same rule the
      // client-widget and frontend_events.py both follow.
    }
    return { ok: true } as const;
  });
```

> `BUSINESS_API_TIMEOUT_MS` is already exported by `config.ts` (verified, default 15000). If it is not exported, use a local `15_000`.

---

## 5.4 The state bridge — `src/lib/orb-state.ts`

One pure function, unit-testable, and the *only* place a LiveKit state becomes an orb state.

```ts
import type { AgentState } from "@livekit/components-react";
import type { OrbState } from "@/lib/orb-config";

/**
 * LiveKit AgentState -> OrbState.
 *
 * The two machines are the same size (9 states); only "pre-connect-buffering"
 * is spelled differently from the orb's "preConnect". The map is exhaustive on
 * purpose: a future LiveKit state falls back to "idle" while connected and
 * "disconnected" otherwise, so the orb can never freeze on a stale frame.
 */
export function toOrbState(
  agentState: AgentState | undefined,
  connected: boolean,
): OrbState {
  switch (agentState) {
    case "disconnected":
      return "disconnected";
    case "connecting":
      return "connecting";
    case "pre-connect-buffering":
      return "preConnect";
    case "initializing":
      return "initializing";
    case "idle":
      return "idle";
    case "listening":
      return "listening";
    case "thinking":
      return "thinking";
    case "speaking":
      return "speaking";
    case "failed":
      return "failed";
    default:
      return connected ? "idle" : "disconnected";
  }
}
```

### Level (the `0..1` the orb consumes)

`assistant.tsx` currently fakes it with `0.25 + Math.random() * 0.65` every 140 ms. The real value comes from `useTrackVolume`, which `apps/client-widget/src/hooks/agents-ui/use-agent-audio-visualizer-aura.ts` already uses with `{ fftSize: 256, smoothingTimeConstant: 0.7 }` (verified).

**Add** `src/hooks/use-orb-level.ts`:

```ts
import { useEffect, useRef, useState } from "react";
import { useTrackVolume, type TrackReference } from "@livekit/components-react";

const FRAME_MS = 1000 / 30; // same 30fps commit budget as the client-widget hook

/**
 * Smoothed 0..1 level for Orb.setLevel().
 *
 * Same analyser settings as the client-widget aura hook so both surfaces react
 * identically to the same audio. Committed at 30fps instead of every analyser
 * frame, because the orb renderer reads the value on its own animation loop and
 * a 60fps React commit is wasted work.
 */
export function useOrbLevel(track: TrackReference | undefined): number {
  const volume = useTrackVolume(track as TrackReference, {
    fftSize: 256,
    smoothingTimeConstant: 0.7,
  });

  const [level, setLevel] = useState(0);
  const latest = useRef(0);
  latest.current = Number.isFinite(volume) ? Math.min(Math.max(volume, 0), 1) : 0;

  useEffect(() => {
    const id = window.setInterval(() => {
      setLevel((previous) => {
        const target = latest.current;
        // Asymmetric smoothing: rise fast so speech feels immediate, fall slow
        // so the orb does not flicker between syllables.
        const next = target > previous ? previous + (target - previous) * 0.6 : previous * 0.82;
        return Math.abs(next - previous) < 0.004 ? previous : next;
      });
    }, FRAME_MS);
    return () => window.clearInterval(id);
  }, []);

  return level;
}
```

Which track to pass: the **agent’s** audio while `speaking`, the **microphone** while `listening`/`preConnect`. `useAgent()` exposes the agent’s tracks (the client-widget passes `agent.microphoneTrack` to its aura visualiser). Open `apps/client-widget/src/components/agents-ui/agent-audio-visualizer-aura.tsx` at implementation time and use the same field name; do not guess a different one.

---

## 5.5 Session provider

**Add** `src/components/assistant/voice-session.tsx`:

```tsx
import { createContext, useContext, useMemo, type ReactNode } from "react";
import { TokenSource } from "livekit-client";
import { useSession, AgentSessionProvider } from "@livekit/components-react";
import { createVoiceGrant, reportVoiceEvent } from "@/lib/api/voice.server";

/**
 * Wraps the LiveKit session for the portal.
 *
 * Same shape as apps/client-widget/src/App.tsx, with one difference that matters:
 * the token comes from our own server function, so the room name and the
 * participant identity are derived from the signed session cookie instead of
 * being generated in the browser.
 */
const NameContext = createContext<string>("You");
export const useParticipantName = () => useContext(NameContext);

export function VoiceSessionProvider({
  participantName,
  children,
}: {
  participantName: string;
  children: ReactNode;
}) {
  const tokenSource = useMemo(
    () =>
      TokenSource.custom(async () => {
        const grant = await createVoiceGrant();
        void reportVoiceEvent({ data: { event: "token_received", details: { room: grant.room } } });
        return { serverUrl: grant.url, participantToken: grant.token };
      }),
    [],
  );

  const session = useSession(tokenSource, {
    // The real room and identity are decided server-side; these are only the
    // hints TokenSource passes back to us, and we ignore them there.
    roomName: "portal",
    participantName,
    agentConnectTimeoutMilliseconds: 30_000,
  });

  return (
    <NameContext.Provider value={participantName}>
      <AgentSessionProvider session={session} volume={1} muted={false}>
        {children}
      </AgentSessionProvider>
    </NameContext.Provider>
  );
}
```

---

## 5.6 The rebuilt `/assistant`

**Replace** `src/routes/_portal/assistant.tsx`. Deleted with it: the `SCRIPT` constant, the `setTimeout` ladder (900/1700/2500/3200 and `2600 + text.length * 12`), the random `level` interval, the hardcoded `"4m 18s"` and `"2"`, the handler-less composer, and the `interactions` fixture import.

Structure (design identity preserved exactly — orb centred, plinth beneath, assurance chips, one primary action):

```tsx
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useAgent, useSessionContext, StartAudioButton } from "@livekit/components-react";
import { AnimatePresence, motion } from "motion/react";
import { Mic, MicOff, PhoneCall, PhoneOff, LockKeyhole } from "lucide-react";
import { Orb } from "@/components/orb/orb";
import { OrbPlinth } from "@/components/orb/orb-plinth";
import { ORB_SIZE, type OrbState } from "@/lib/orb-config";
import { toOrbState } from "@/lib/orb-state";
import { useOrbLevel } from "@/hooks/use-orb-level";
import { VoiceSessionProvider, useParticipantName } from "@/components/assistant/voice-session";
import { LiveStream } from "@/components/assistant/live-stream";
import { Button, Card, IconButton, StatusChip } from "@/components/portal/primitives";
import { T_BASE, T_MICRO } from "@/components/portal/data";
import { duration } from "@/lib/format";
import { copy } from "@/lib/copy";
import { reportVoiceEvent } from "@/lib/api/voice.server";

export const Route = createFileRoute("/_portal/assistant")({
  head: () => ({ /* unchanged */ }),
  component: AssistantScreen,
  // The LiveKit bundle is only paid for on this route.
  ssr: false,
});

function AssistantScreen() {
  // full_name from the existing profile-detail query; "You" until it resolves.
  const participantName = useCustomerName();
  return (
    <VoiceSessionProvider participantName={participantName}>
      <AssistantStage />
    </VoiceSessionProvider>
  );
}

function AssistantStage() {
  const session = useSessionContext();
  const agent = useAgent();
  const name = useParticipantName();

  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callId, setCallId] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  const connected = session.isConnected;
  // connectionState is the only reliable latch: isConnected oscillates while
  // ICE settles and while the agent joins. Verified pattern from App.tsx.
  const inCall = session.connectionState !== "disconnected";

  const orbState: OrbState = toOrbState(agent.state, connected);
  const level = useOrbLevel(agent.microphoneTrack);
  const stateCopy = copy.assistant.state[orbState] ?? copy.assistant.state.disconnected;

  const start = useCallback(async () => {
    if (starting || connected) return;
    setError(null);
    setStarting(true);
    setCallId((n) => n + 1);
    void reportVoiceEvent({ data: { event: "start_session_clicked", details: { surface: "portal" } } });
    try {
      await session.start({
        tracks: {
          microphone: { enabled: true, publishOptions: { preConnectBuffer: true } },
          camera: { enabled: false },
          screenShare: { enabled: false },
        },
      });
      setStartedAt(Date.now());
      void reportVoiceEvent({ data: { event: "session_started", details: { surface: "portal" } } });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy.assistant.errors.generic);
      void reportVoiceEvent({ data: { event: "session_start_failed", details: {} } });
    } finally {
      setStarting(false);
    }
  }, [starting, connected, session]);

  const end = useCallback(async () => {
    setError(null);
    await session.end();
    void reportVoiceEvent({ data: { event: "session_ended", details: {} } });
  }, [session]);

  // Any disconnect — End, the agent's end_conversation tool deleting the room,
  // or a dropped network — clears the transient error. The visible restore is
  // already reactive through connectionState. Verified pattern from App.tsx.
  useEffect(() => {
    if (session.connectionState === "disconnected") setError(null);
  }, [session.connectionState]);

  return (
    <div className="flex min-h-[calc(100vh-8rem)] flex-col items-center justify-center gap-sp-9">
      {/* ORB — untouched component, real inputs. */}
      <div className="relative flex flex-col items-center">
        <Orb
          state={orbState}
          level={level}
          size={inCall ? ORB_SIZE.call : ORB_SIZE.rest}
          className="transition-[width,height] duration-500"
        />
        <OrbPlinth />
      </div>

      {/* STATE COPY — cross-faded, aria-live so it is announced once. */}
      <div className="min-h-[72px] text-center" aria-live="polite">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={orbState}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={T_BASE}
          >
            <div className="t-title-2 text-ink-1">{stateCopy.label}</div>
            <p className="t-body mt-sp-3 text-ink-4">{stateCopy.detail}</p>
          </motion.div>
        </AnimatePresence>
      </div>

      {error ? (
        <div role="alert" className="t-caption max-w-md rounded-r-3 border border-stroke-strong bg-surface-2 px-sp-6 py-sp-5 text-ink-2">
          {error}
        </div>
      ) : null}

      {/* CONTROLS — Start swaps for the call bar at --z-callbar. */}
      <div className="flex min-h-14 items-center gap-sp-5">
        <AnimatePresence mode="wait" initial={false}>
          {!inCall ? (
            <motion.div key="start" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} transition={T_BASE}>
              <Button variant="primary" size="lg" onClick={start} disabled={starting}>
                <PhoneCall size={17} strokeWidth={1.5} />
                {starting ? copy.assistant.connecting : copy.assistant.start}
              </Button>
            </motion.div>
          ) : (
            <motion.div key="bar" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} transition={T_BASE}>
              <CallBar onEnd={end} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Browsers block autoplay until a gesture: this is how the customer
          hears the assistant. Same component the client-widget uses. */}
      <StartAudioButton label={copy.assistant.enableAudio} />

      <div className="flex items-center gap-sp-5">
        <StatusChip tone="outline">
          <LockKeyhole size={12} strokeWidth={1.5} /> {copy.assistant.assurance.encrypted}
        </StatusChip>
        <StatusChip tone="dotted">{copy.assistant.assurance.audioOnly}</StatusChip>
      </div>

      {/* LIVE STREAM — keyed on callId so each call starts with a clean stack. */}
      <LiveStream key={callId} participantName={name} />

      {/* SUMMARY — real duration, never a hardcoded string. */}
      {!inCall && startedAt ? (
        <Card className="w-full max-w-lg">
          <div className="t-micro-2 text-ink-5">{copy.assistant.summary.heading}</div>
          <div className="mt-sp-5 grid grid-cols-2 gap-sp-6">
            <MetricPair label={copy.assistant.summary.duration} value={duration((Date.now() - startedAt) / 1000)} />
            <MetricPair label={copy.assistant.summary.turns} value={copy.assistant.summary.turnsPending} />
          </div>
          <p className="t-caption mt-sp-6 text-ink-4">{copy.assistant.summary.savedNote}</p>
        </Card>
      ) : null}
    </div>
  );
}
```

### Two honesty rules on this screen

* **Turn count and “what changed” are not known client-side.** The durable record is written by the worker’s `ConversationWriter` into `conversation.turns` **after** the call. Do not count DOM bubbles and present it as the transcript length. Either show `copy.assistant.summary.turnsPending` (“Saved to your activity in a moment”) with a link to `/activity`, or refetch `qk.conversations(cid, 1, 0)` a few seconds after the call and show the server’s `turns`. Never invent “2”.
* **`copy.assistant.summary.nothingChanged`** (“Nothing in your account was changed.”) may only be shown if you can prove it. You cannot, client-side. Delete that key or replace it with `savedNote`: “A written record of this conversation appears in your activity shortly.”

### `CallBar`

The only component allowed to use `--z-callbar: 40` — the token that has existed with no consumer since day one (D‑10):

```tsx
function CallBar({ onEnd }: { onEnd: () => void }) {
  const { microphoneToggle } = useInputControls();  // copy the client-widget hook, §5.7
  const muted = !microphoneToggle.enabled;
  return (
    <div className="z-callbar flex items-center gap-sp-4 rounded-r-5 border border-stroke-default bg-surface-2 p-sp-3 shadow-elev-3">
      <IconButton
        label={muted ? copy.assistant.controls.unmute : copy.assistant.controls.mute}
        onClick={() => void microphoneToggle.toggle()}
      >
        {muted ? <MicOff size={16} strokeWidth={1.5} /> : <Mic size={16} strokeWidth={1.5} />}
      </IconButton>
      <Button variant="danger" size="sm" onClick={onEnd}>
        <PhoneOff size={15} strokeWidth={1.5} />
        {copy.assistant.end}
      </Button>
    </div>
  );
}
```

Add the utility once in `styles.css` so the token is used rather than a literal:

```css
@utility z-callbar {
  z-index: var(--z-callbar);
}
```

---

## 5.7 Microphone controls

**Copy** `apps/client-widget/src/hooks/agents-ui/use-agent-control-bar.ts` into `Frontend/customer_portal/src/hooks/use-input-controls.ts` **verbatim**, then delete the camera and screen-share branches (the portal is audio-only: `camera: { enabled: false }`, `screenShare: { enabled: false }`). Keep `usePersistentUserChoices` so the customer’s microphone selection survives a reload — that is the behaviour the client-widget already ships.

Do not re-derive this hook from memory; copy the verified file and trim it.

---

## 5.8 The live transcript — `src/components/assistant/live-stream.tsx`

The behaviour you asked for (new messages fade in, older ones fade out, tool calls in real time, agent/persona and customer names visible) is **already solved** in `apps/client-widget/src/components/app/live-conversation.tsx` (verified). Port that logic, keep the portal’s tokens.

What to keep from the verified implementation, unchanged in substance:

* `useTranscriptions({ room: session.room })` and de-duplication by `lk.segment_id` (falling back to `lk.transcribed_track_id`, then `streamInfo.id`), with `lk.transcription_final === "true"` replacing the interim text.
* Interim updates only when the new text is **longer** (or final), so a partial never shrinks mid-word.
* `useTextStream("telecom.tool-events", { room })` for tool events, kept separate from transcripts.
* `timestampMs()` — LiveKit timestamps may be seconds or milliseconds (`value < 10_000_000_000 ? value * 1000 : value`).
* `MAX_VISIBLE_ITEMS = 3` and `.slice(-MAX_VISIBLE_ITEMS)` — this **is** the “old messages disappear” behaviour.
* `AnimatePresence mode="popLayout"` + `layout="position"`, depth-based opacity `1 / 0.52 / 0.22` and scale `1 / 0.985 / 0.97`.
* `dir="auto"` on every text node — the only reason Arabic renders correctly today.
* The ephemeral-by-design comment: the durable transcript lives in PostgreSQL via `ConversationWriter`; this UI is a window, not a store.

What changes for the portal:

| client-widget | portal |
|---|---|
| `live-conversation` CSS classes (external stylesheet) | portal tokens: `bg-surface-2`, `border-stroke-subtle`, `rounded-r-4`, `t-body`, `t-micro-2`, `shadow-elev-1` |
| role label `"You"` / `"Assistant"` | `participantName` (the customer’s real `full_name`) and the persona name from the turn’s `active_agent` when present, else `copy.assistant.stream.assistant` |
| `Wrench` + status tick for tools | Cookbook 6’s `ToolEventRow` with customer wording |
| `live-turn__caret` class | the **existing unused `caret` keyframe** in `styles.css` (D‑11) |

Skeleton of the ported component:

```tsx
const MAX_VISIBLE_ITEMS = 3;
const TOOL_EVENT_TOPIC = "telecom.tool-events";

type StreamItem = {
  id: string;
  role: "caller" | "agent" | "tool";
  text: string;
  timestamp: number;
  partial?: boolean;
  status?: "done" | "error";
  persona?: string | null;
};

export function LiveStream({ participantName }: { participantName: string }) {
  const session = useSessionContext();
  const agent = useAgent();
  const transcriptions = useTranscriptions({ room: session.room });
  const { textStreams: toolStreams } = useTextStream(TOOL_EVENT_TOPIC, { room: session.room });

  const items = useMemo(() => { /* exact algorithm from live-conversation.tsx */ }, [
    session.room, transcriptions, toolStreams,
  ]);

  if (!session.isConnected && items.length === 0) {
    return (
      <p className="t-caption text-ink-5" aria-hidden="true">
        {copy.assistant.stream.willAppear}
      </p>
    );
  }

  return (
    <section
      aria-label={copy.assistant.stream.heading}
      aria-live="polite"
      aria-atomic="false"
      className="w-full max-w-2xl"
    >
      <div className="mb-sp-4 flex items-center justify-between">
        <span className="t-micro-2 text-ink-5">{copy.assistant.stream.heading}</span>
        <span className="t-micro-2 text-ink-5">
          {copy.assistant.state[toOrbState(agent.state, session.isConnected)].label}
        </span>
      </div>

      <div className="flex flex-col gap-sp-4">
        <AnimatePresence initial={false} mode="popLayout">
          {items.map((item, index) => {
            const depth = items.length - 1 - index;
            const opacity = depth === 0 ? 1 : depth === 1 ? 0.52 : 0.22;
            const scale = depth === 0 ? 1 : depth === 1 ? 0.985 : 0.97;
            return (
              <motion.article
                key={item.id}
                layout="position"
                data-depth={depth}
                initial={{ opacity: 0, y: 10, scale: 0.985 }}
                animate={{ opacity, y: 0, scale }}
                exit={{ opacity: 0, y: -8, scale: 0.96 }}
                transition={T_BASE}
                className="rounded-r-4 border border-stroke-subtle bg-surface-2 px-sp-6 py-sp-5"
              >
                {item.role === "tool" ? (
                  <ToolEventRow label={item.text} status={item.status ?? "done"} />
                ) : (
                  <>
                    <div className="t-micro-2 text-ink-5">
                      {item.role === "caller"
                        ? participantName
                        : (item.persona ?? copy.assistant.stream.assistant)}
                    </div>
                    <p dir="auto" className="t-body mt-sp-2 text-ink-1">
                      {item.text}
                      {item.partial && depth === 0 ? (
                        <span className="assistant-caret" aria-hidden="true" />
                      ) : null}
                    </p>
                  </>
                )}
              </motion.article>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}
```

And the caret finally uses its keyframe (append to `styles.css`, no new token):

```css
/* Uses the `caret` keyframe that has existed unused since the design system
   was written. */
.assistant-caret {
  display: inline-block;
  width: 1px;
  height: 1em;
  margin-inline-start: 2px;
  vertical-align: text-bottom;
  background: var(--ink-2);
  animation: caret 1s steps(1) infinite;
}
```

> Verify the keyframe name before shipping: `git grep -n "@keyframes" -- Frontend/customer_portal/src/styles.css`. If it is named differently, use that name; do not add a second keyframe.

---

## 5.9 Copy for this screen

`copy.assistant.state` already covers all nine orb states with label + detail (verified) — **do not rewrite it**. Add only:

```ts
  assistant: {
    // …existing title / start / end / assurance / state / stream / controls…
    connecting: "Connecting…",
    enableAudio: "Enable assistant audio",
    errors: {
      generic: "We could not open the line. Try again in a moment.",
      microphone: "We need access to your microphone to start a conversation.",
      timeout: "The assistant did not join in time. Try again.",
    },
    stream: {
      // …existing keys…
      willAppear: "Your conversation will appear here as you speak.",
      waiting: "Listening for the first words…",
    },
    summary: {
      // …existing keys…
      turnsPending: "Saving…",
      savedNote: "A written record of this conversation appears in your activity shortly.",
    },
  },
```

Delete `copy.assistant.stream.composer`, `sentAsText`, `copyTranscript`, `downloadTranscript`, `copy.assistant.controls.volume`, `controls.captions`, `controls.keyboard`, and `copy.assistant.summary.nothingChanged` / `actions` / `changed` / `helpful` / `download` / `viewInActivity` unless the corresponding affordance is actually implemented in this cookbook. Deleting the string is the point: the UI cannot silently regain a fake feature.

---

## 5.10 Acceptance

| # | Check | Expected |
|---|---|---|
| 1 | Load `/assistant` with LiveKit unreachable | orb `disconnected`, Start visible, no console error, other tabs unaffected |
| 2 | Press Start | `connecting` → `preConnect` → `initializing` → `idle`; the orb passes through all four without a stall |
| 3 | Speak | `listening`; the orb’s level tracks your voice; no `Math.random` anywhere: `git grep -n "Math.random" -- Frontend/customer_portal/src` returns nothing |
| 4 | Wait for the agent to reply | `thinking` → `speaking`; audio plays after `StartAudioButton` is pressed once |
| 5 | Say something that triggers a tool | a tool row appears within a second, wording from Cookbook 6, never `function_tools_executed` |
| 6 | Keep talking | only the last three items stay; older ones fade out and are removed |
| 7 | Mute | mic track disabled, icon flips, the agent stops hearing you, the orb stops reacting |
| 8 | End | `connectionState === "disconnected"`, Start returns, summary shows a **real** duration |
| 9 | Let the agent end the call itself (`end_conversation` deletes the room) | identical restore to manual End |
| 10 | Kill the network mid-call | `failed`, error strip, End still works |
| 11 | Deny microphone permission | the microphone error copy, no crash, Start still available |
| 12 | Open two tabs and start both | two different rooms (`portal-{cid}-{suffix}`); neither hears the other |
| 13 | Inspect the client bundle | no `TOKEN_SERVICE_URL`, no LiveKit API key, no token: `grep -r "8107" dist/client` → nothing |
| 14 | Reload during a call | the session ends cleanly; no zombie room |
| 15 | Arabic reply | text renders right-to-left thanks to `dir="auto"` |
| 16 | Reduced motion on | orb honours the OS setting (single read at mount); the transcript stack still updates, without spring motion |

### Rollback

Revert the commit: the two dependencies leave `package.json`, `/assistant` returns to the template. The token service change (Option A) is a defaulted optional field — reverting it cannot break the client-widget, which never sends it.
