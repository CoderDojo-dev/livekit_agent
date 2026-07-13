# version_26 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches & updates added to this new branch.

## Changes & Patches & Updates

### 1. End_Conversation Tool — Agent-Initiated Graceful Close
- **New file**: `apps/agent-worker/src/tools/session_flow_tools.py`
- `end_conversation` function tool: speaks a bounded, in-language farewell (FR/AR/EN) to completion via `say_and_wait(allow_interruptions=False)`, then deletes the LiveKit room via `api.DeleteRoomRequest`
- Room deletion disconnects the caller, triggering the identical frontend cleanup as the manual End Call button — no parallel teardown path
- `StopResponse` prevents any trailing LLM/TTS turn after the farewell
- `conversation_ending` idempotency flag prevents duplicate execution (raises `StopResponse` on re-entry)
- Farewell messages in `_FAREWELLS` dict (Merci/شكراً/Thank you) per supported language

### 2. Shared Closing Protocol — Every Persona
- `base_agent.py`: `CLOSING_PROTOCOL` appended to every persona's instructions — confirm nothing else is needed, then call `end_conversation`
- `BaseTelecomAgent.__init__` auto-injects `end_conversation` into every persona's tool list
- Ensures consistent graceful-end capability across all specialists (triage, billing, technical, etc.)

### 3. Unified Motion Language — Single Source of Truth
- **New file**: `apps/client-widget/src/lib/motion.ts` — `EASE_SMOOTH`, `EASE_EXIT`, `DURATION` (micro/base/macro), and ready-made `TRANSITION_*` objects
- `index.css`: CSS custom properties `--ease-smooth`, `--ease-exit`, `--dur-micro/base/macro` replacing all hardcoded durations/easings
- `agent-control-bar.tsx`: imports `DURATION.base`/`EASE_SMOOTH`
- `live-conversation.tsx`: imports `TRANSITION_BASE`/`TRANSITION_MICRO`

### 4. UI — AnimatePresence + Stable inCall Latch
- `App.tsx`: `AnimatePresence` with `mode="wait"` cross-fades between Start button and `AgentControlBar` (no jarring snap)
- `inCall` latch uses `connectionState !== "disconnected"` instead of `isConnected` for stable toolbar across connect/ICE/agent-join cycles
- `key={callId}` forces `LiveConversation` remount per call — clears stale transcript on reconnection
- `useEffect` clears error state when `connectionState` becomes "disconnected" for clean restart

## Files Affected (7 files, +252/-53)

| File | Status | Change |
|------|--------|--------|
| `apps/agent-worker/src/tools/session_flow_tools.py` | **New** | 85 lines: end_conversation tool |
| `apps/agent-worker/src/agents/base_agent.py` | Modified | CLOSING_PROTOCOL + auto-inject end_conversation |
| `apps/client-widget/src/lib/motion.ts` | **New** | 29 lines: motion constants |
| `apps/client-widget/src/index.css` | Modified | CSS motion variables |
| `apps/client-widget/src/App.tsx` | Modified | AnimatePresence, inCall latch, callId key |
| `apps/client-widget/src/components/agents-ui/agent-control-bar.tsx` | Modified | Import motion constants |
| `apps/client-widget/src/components/app/live-conversation.tsx` | Modified | Import motion constants |
