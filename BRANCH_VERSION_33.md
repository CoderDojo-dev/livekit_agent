# Version 33 — Language-Switch Policy + LiveKit Agents 1.6.3 Compatibility

## Summary

This version introduces an explicit language-switch policy that allows callers to
request a mid-call language change, fixes the reconnection apology to respect
the caller's current language, and rewrites `switch_spoken_language` to work
correctly with **LiveKit Agents SDK 1.6.3** (FallbackAdapter read-only STT/TTS).

## Changes

### 1. Language-Switch Policy (`apps/agent-worker/src/agents/base_agent.py`)
- **Removed** the hardcoded `_DEESCALATION_NOTE` (caller frustration prompt).
- **Added** `LANGUAGE_SWITCH_POLICY`: appended to every persona's instructions,
  this policy tells the LLM it **must never drift** from its assigned language
  on its own, but **must** call `switch_spoken_language` if the caller
  *explicitly* asks to continue in French, Arabic, or English.
- This resolves the contradiction between the per-persona "never switch
  language" lock and the auto-injected `switch_spoken_language` tool.

### 2. Multilingual Reconnection Apology (`apps/agent-worker/src/providers/_resilience.py`)
- `SessionResilienceMonitor` now selects the reconnection apology from a
  multilingual dictionary (`fr`, `ar`, `en`) based on `user_data.language`,
  instead of the previous hardcoded English message.

### 3. LiveKit Agents 1.6.3 Fix (`apps/agent-worker/src/tools/session_flow_tools.py`)
- **Problem**: In `livekit-agents >= 1.6.3`, `session.stt` and `session.tts`
  are **read-only FallbackAdapters**. Assigning to them (e.g.,
  `session.stt = build_stt(...)`) raised an `AttributeError`, making the
  `switch_spoken_language` tool fail silently after the first use.
- **Fix**:
  - **Added** `_wrapped_providers(adapter, attr)` — reaches the concrete
    Deepgram/Cartesia instances behind the FallbackAdapter.
  - **Added** `_update_stt_language(session, preset)` — calls
    `stt.update_options(language=...)` on each concrete STT provider (the
    supported LiveKit API for mid-call reconfiguration).
  - **Added** `_update_tts_language(session, preset)` — calls
    `tts.update_options(language=..., voice=...)` on each concrete TTS provider.
- **ChatCtx mutation removed**: The old code patched
  `chat_ctx.messages[0].content`, which was a **guaranteed no-op**:
  `ChatMessage.content` is a `list[dict]` in livekit-agents, not a `str`, so the
  `isinstance(content, str)` guard never matched.
- **Replaced** with `agent.update_instructions()` — the supported async API
  that actually re-points the system instructions with the new language name.

### Files Changed
| File | Insertions | Deletions |
|------|-----------|-----------|
| `apps/agent-worker/src/agents/base_agent.py` | 14 | 6 |
| `apps/agent-worker/src/providers/_resilience.py` | 9 | 2 |
| `apps/agent-worker/src/tools/session_flow_tools.py` | 51 | 29 |
| **Total** | **74** | **37** |

## Containers & Dependencies
- No container or dependency version changes in this version.
- The `switch_spoken_language` rewrite is a **backward-compatible code fix** for
  `livekit-agents >= 1.6.3` — no SDK version bump was required.

## Testing Notes
- `switch_spoken_language` tool: verify mid-call switch from FR → AR, AR → EN,
  EN → FR works across multiple consecutive calls.
- Reconnection: force a disconnect/reconnect cycle and confirm the apology is
  spoken in the caller's current language.
- Regression: ensure `end_conversation` remains unaffected.
