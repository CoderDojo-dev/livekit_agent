# Version 57 — Unified Instruction Architecture, TTS-aware Sub-flows, Widget Lazy Loading

> **Base branch:** `version_56`
> **Files changed:** 17 (+493 / -340)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)

---

## Containers & SDK

| Item                | Change                  |
|---------------------|-------------------------|
| New containers      | None                    |
| livekit-agents SDK  | `1.6.5` (unchanged)     |
| livekit-client (JS) | `2.20.1` → `2.21.0`     |
| Vite                | `6.0.7` → `6.4.3`       |
| React               | `19.0.0` → `19.2.8`     |
| TypeScript          | `5.7.2` → `5.9.3`       |

---

## What's New

### Agent Instruction Architecture Overhaul

**`base_agent.py`** — The most significant change in this version:

- **`NO_DEAD_END_MANDATE`** — A new routing mandate appended to every persona agent. Forces agents to use `route_to_billing`, `route_to_account_services`, `route_to_technical`, or `request_clarification` instead of telling callers to "call a different number". If nothing fits, `escalate_to_manager`. This eliminates a class of user-experience dead ends where the LLM would give generic advice without transferring.

- **`merge_instructions()`** — A new factory function that assembles each persona's complete instruction block: persona-specific core → `NO_DEAD_END_MANDATE` → `CLOSING_PROTOCOL` → `LANGUAGE_SWITCH_POLICY`, with deduplication. The `tts_provided` flag controls whether the language-lock reminder is appended.

- **`KNOWLEDGE_ABSTENTION_RULE`** — Completely rewritten. The old rule simply said "answer only from passages and cite source". The new rule adds comprehensive spoken-response guidance: never read passages verbatim, never use numbered/bulleted lists or headings, answer in one or two natural sentences like a real call-center advisor, offer more detail only if the caller asks for it. This addresses the problem of the agent sounding robotic when citing knowledge sources.

- **Init cleanup**: Removed the inline `instructions + CLOSING_PROTOCOL + LANGUAGE_SWITCH_POLICY` concatenation from `BaseTelecomAgent.__init__`. Each persona now explicitly calls `merge_instructions()` with its own core instructions, making the composition explicit and testable.

**All 4 persona agents** (`account_services`, `billing`, `technical`, `triage`) switched from `instructions=(...)` to `instructions=merge_instructions(...)`.

### TTS-aware Bounded Sub-flows

Previously, when a sub-task like `IdentityVerificationTask` or `ConsentTask` ran, it used the session's default TTS voice, not the voice of the currently active persona agent. This meant a billing agent asking for CIN verification might suddenly switch voice.

**`voice_flow.py`** added two helpers:
- **`persona_tts()`** — Safely normalizes `NotGivenOr` TTS values so callers can pass them to `AgentTask.__init__` without type errors.
- **`active_persona_tts()`** — Inspects `session.current_agent` and borrows its TTS identity. Returns `None` when no agent is active (safe fallback to session voice).

**All 5 task classes** now accept a `tts` parameter and wire it via `persona_tts()`:
- `CallbackScheduleTask`
- `ConsentTask`
- `IdentityVerificationTask`
- `PaymentConfirmTask`
- `SimReplacementTaskGroup`

**Call sites updated:**
- `guards.py` — passes `tts=active_persona_tts(context)` when launching `IdentityVerificationTask`
- `sip_transfer.py` — passes `tts=active_persona_tts(context)` when launching `CallbackScheduleTask`
- `triage_agent.py` — passes `tts=active_persona_tts(None)` when launching `ConsentTask`

### Test Updates

**`test_voice_flow.py`**:
- `test_specialist_handoffs_preserve_context` — Simplified: removed the `agent_attribute` parameter (no longer needed since routing functions are now direct references). Uses an async `fake_route` mock instead of `FakeAgent` monkey-patching.
- `test_manager_escalation_paths` — `FakeManager` now accepts `language` parameter. Asserts that `say_and_wait` is called with a language-appropriate advisor message (`conseiller`/`مستشار`/`advisor`), proving the spoken handoff message works.
- `test_no_tool_calls_session_interrupt_directly` — Added explicit `encoding="utf-8"` to file reads to avoid platform-dependent default encoding issues.

### Client Widget Improvements

**`App.tsx`**:
- `AgentAudioVisualizerAura` is now **lazy-loaded** with `React.lazy()` and wrapped in `<Suspense>` with a CSS-only fallback (using `AgentAudioVisualizerAuraVariants` for consistent sizing). This reduces the initial bundle size since the visualization component is only loaded when the voice experience is actually active.

**`vite.config.ts`**:
- Added `watch.usePolling: true` with `interval: 100` — enables file-watch polling for environments (like Docker/WSL) where native FS events don't propagate.
- Enabled `hmr.overlay: true` for clearer hot-reload error feedback.
- Set `clearScreen: false` to preserve terminal output.

### Dependency Updates (package-lock.json)

Transitive dependency bumps resulting from `npm install`:

| Package | From | To |
|---------|------|----|
| esbuild | 0.24.2 | 0.25.12 |
| livekit-client | 2.20.1 | 2.21.0 |
| @livekit/protocol | 1.46.6 | 1.50.4 |
| Vite | 6.0.7 | 6.4.3 |
| React | 19.0.0 | 19.2.8 |
| React-DOM | 19.0.0 | 19.2.8 |
| scheduler | 0.25.0 | 0.27.0 |
| TailwindCSS | 4.3.2 | 4.3.3 |
| TypeScript | 5.7.2 | 5.9.3 |
| postcss | 8.5.15 | 8.5.23 |
| nanoid | 3.3.15 | 3.3.16 |
| hono | 4.12.29 | 4.12.32 |
| lucide-react | 1.24.0 | 1.27.0 |

