# version_23 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches & updates added to this new branch.

## Changes & Patches & Updates

### 1. FrontendEventPublisher — PII-Safe Realtime Tool Events
- **New file**: `apps/agent-worker/src/frontend_events.py` — publishes bounded tool-event metadata over LiveKit text streams
- Topic: `telecom.tool-events` — carries only `version`, `kind`, `id`, `name`, `label`, `status`, `created_at`
- PII-safe: tool arguments and outputs are intentionally excluded (can contain customer, auth, billing, or account data)
- 15 display labels mapped (knowledge_search, billing reads, routing, escalation, identity verification, consent, etc.)
- Integrated into `server.py` entrypoint: `FrontendEventPublisher(ctx.room)` created per-room, publishes on every `FunctionToolsExecutedEvent`, drained on shutdown via `aclose()`

### 2. LiveConversation Component — Real-Time Conversation Rail
- **New file**: `apps/client-widget/src/components/app/live-conversation.tsx` — real-time conversation rail showing latest 3 turns
- Uses `useTranscriptions` for caller/agent speech rendering, `useTextStream` for tool events
- Three conversation roles: `caller` ("You"), `agent` ("Assistant"), `tool` ("Service action")
- Tool events rendered with Wrench icon + Check (done) / X (error) status badge
- `AnimatePresence` with staggered opacity/scale for smooth enter/exit transitions
- Responsive layout: desktop = fixed right rail beside Aura visualizer; mobile/tablet = below voice experience
- Integrated into `App.tsx` below the voice experience section

### 3. Aura Visualizer — Performance Optimizations
- RAF-throttled React state updates (capped at 30fps via `requestAnimationFrame` + interval check) to reduce render pressure
- FFT size reduced 512→256; smoothing increased 0.55→0.7 for less jittery volume tracking
- Animation easing changed to cubic-bezier `[0.16, 1, 0.3, 1]` (pentatonic ease-out) for smoother visual transitions
- Removed unnecessary re-renders: early return guards in volume-responsive scale animation
- Cleanup: animation controls cancelled on unmount, frame refs properly cleaned

### 4. Shader — Reduced GPU Load
- WebGL shader iterations 36 → 28 (22% fewer iterations)
- `devicePixelRatio` 1 → 0.75 (fewer effective pixels to shade on HiDPI displays)
- CSS `contain: layout paint style` + `transform: translateZ(0)` + `backface-visibility: hidden` applied to aura/canvas elements for GPU compositing isolation

### 5. Session Factory — TTS-Aligned Transcripts
- `session_factory.py`: added `use_tts_aligned_transcript=True` so transcription segments are synchronized with TTS audio boundaries for more accurate live transcription display

### 6. StrictMode Removed
- `main.tsx`: removed React `StrictMode` wrapper (eliminates double-render in development, which caused duplicate transcription streams in the UI)

### 7. Live Conversation CSS
- `index.css`: added ~190 lines of CSS for the live conversation rail, including:
  - `.live-conversation` — fixed right-rail positioning (desktop), inline flow (mobile)
  - `.live-turn` — role-styled cards (caller=cyan, agent=default, tool=amber) with depth-based opacity/saturation
  - `.live-turn__caret` — blinking text cursor for partial/interim transcripts
  - `.live-turn__tool-icon` / `.live-turn__tool-status` — circular badges for tool events
  - Responsive breakpoints at 1100px (rail collapses below Aura) and 640px (mobile adjustments)
  - `@media (prefers-reduced-motion: reduce)` disables animations

## Files Affected (10 files, +968/-53)

| File | Status | Change |
|------|--------|--------|
| `apps/agent-worker/src/frontend_events.py` | **New** | 126 lines: PII-safe tool event publisher |
| `apps/agent-worker/src/server.py` | Modified | FrontendEventPublisher integration + shutdown |
| `apps/agent-worker/src/providers/session_factory.py` | Modified | use_tts_aligned_transcript=True |
| `apps/client-widget/src/components/app/live-conversation.tsx` | **New** | 401 lines: real-time conversation rail |
| `apps/client-widget/src/App.tsx` | Modified | LiveConversation component added |
| `apps/client-widget/src/hooks/agents-ui/use-agent-audio-visualizer-aura.ts` | Modified | RAF-throttled updates, FFT 512→256, easing |
| `apps/client-widget/src/components/agents-ui/agent-audio-visualizer-aura.tsx` | Modified | Shader iterations 36→28 |
| `apps/client-widget/src/components/agents-ui/react-shader-toy.tsx` | Modified | devicePixelRatio 1→0.75 |
| `apps/client-widget/src/index.css` | Modified | Live conversation CSS + performance isolation |
| `apps/client-widget/src/main.tsx` | Modified | Removed StrictMode |
