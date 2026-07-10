# version_19 — First Working Voice Agent: Interruption-Safe Tool Speech & Deterministic Handoffs

## Purpose
This is the first version where the voice agent can complete a full call flow without silent failures. The core bug was that tool-only LLM turns (clarification, handoff, escalation) produced empty text streams that were passed into TTS, resulting in no audio output. Every tool that needs to speak now does so explicitly through bounded, interruption-safe primitives.

## Root Cause Fixed
- **Before**: Tools returned dicts like `{"outcome": "ask", "question": "..."}` or tuples like `(ManagerAgent(), "message")` — the LLM then generated a follow-up reply, but since the tool already "answered," it often produced an empty text stream that stalled TTS
- **After**: Tools speak directly via `say_and_wait()` / `say_and_stop()` and use `StopResponse` to terminate the tool-only turn, preventing any empty LLM→TTS cycle

## Changes

### 1. New Module: `voice_flow.py`
Interruption-safe speech primitives shared by all tools:

| Function | Purpose |
|----------|---------|
| `say_and_wait()` | Speak a message, await completion/interruption, bounded by `DEFAULT_SPEECH_TIMEOUT_S=20s` |
| `say_and_stop()` | Speak then raise `StopResponse` to terminate the tool turn |
| `handoff_with_message()` | Speak a transition message (interruptions disabled), return next Agent |
| `current_chat_ctx()` | Extract current agent's `chat_ctx` so handoffs preserve conversation history |
| `_interrupt_speech()` | Best-effort speech cleanup compatible with multiple SpeechHandle API versions |

### 2. Clarification Tools (rewrite)
- **First attempt**: speaks the question via `say_and_stop()` + `StopResponse` — no empty LLM turn
- **Second attempt**: calls `escalate_to_manager()` directly — deterministic, not a dict
- **Empty question guard**: falls back to "Pouvez-vous préciser votre demande ?"

### 3. Escalation Tools (rewrite)
- `handoff_with_message()` for guaranteed speech before manager takeover
- `ManagerAgent(chat_ctx=current_chat_ctx(context))` — preserves full conversation history
- `record_escalation()` wrapped in try/except — persistence never blocks handoff
- Returns `Agent` (not `tuple`) — compatible with LiveKit 1.6.x handoff API

### 4. Routing Tools (rewrite)
- `route_to_billing` / `route_to_technical` now return `Agent` via `handoff_with_message()`
- Specialist agents receive `chat_ctx` from TriageAgent — conversation continuity preserved
- French transition messages

### 5. SIP Transfer
- Uses `say_and_wait()` with French message, `allow_interruptions=False` during human transfer
- Import `voice_flow` added

### 6. Tests (new)
- `tests/interruption/test_voice_flow.py` — pytest suite covering:
  - `say_and_wait` completes, times-out, rejects empty text
  - First clarification speaks + StopResponse
  - Second clarification hands off to manager
  - All escalation trigger paths (frustration, clarify_fail, identity_fail, hard_failure)
  - Specialist handoffs preserve chat_ctx
  - No tool file calls `session.interrupt()` directly
  - All interactive AgentTask subclasses remain bounded + idempotent

## Files / Modules Affected (6 files)

| File | Status | Change |
|------|--------|--------|
| `apps/agent-worker/src/tools/voice_flow.py` | **New** | 120 lines: say_and_wait, say_and_stop, handoff_with_message, current_chat_ctx |
| `apps/agent-worker/src/tools/clarification_tools.py` | Modified | +4/-31: deterministic escalation, StopResponse, empty question guard |
| `apps/agent-worker/src/tools/escalation_tools.py` | Modified | +35/-20: handoff_with_message, chat_ctx preservation, writer try/except |
| `apps/agent-worker/src/tools/routing_tools.py` | Modified | +13/-9: handoff_with_message, Agent return type, chat_ctx preservation |
| `apps/agent-worker/src/telephony/sip_transfer.py` | Modified | +5/-1: say_and_wait, French message, allow_interruptions=False |
| `apps/agent-worker/tests/interruption/test_voice_flow.py` | **New** | 260 lines: pytest suite |

## Key Design Decisions
- **Bounded speech**: `say_and_wait` has a 20s timeout that interrupts and cleans up
- **No tuple returns**: Returning `(Agent, str)` from a tool was the root cause of empty TTS streams
- **chat_ctx threading**: Handoffs preserve conversation history so the next agent sees the full context
- **Fail-closed**: Writer/notification failures are logged but never block a handoff
