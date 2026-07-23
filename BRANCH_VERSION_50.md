# version_50 — Per-Persona TTS Voices + Deterministic Handoff Messages + Consent UX

## Summary
This version gives **each agent its own voice** (Cartesia Sonic per-persona), ensures **every handoff speaks a deterministic transition phrase** (no hallucinated or silent transfers), and improves the **consent flow** to eliminate duplicate speech and add proper self-introduction. The multi-TTS provider system from v49 is retained and enriched with persona voice overrides.

## Per-Persona TTS Voices

**Problem:** Previously all agents shared the same TTS instance. At handoff, the voice remained unchanged (same Cartesia voice for triage, billing, technical, manager — caller heard no distinction between personas). Workarounds using `update_options` were brittle and unsupported.

**Solution:** Each agent now receives its own TTS `FallbackAdapter` via `build_persona_tts(language, persona)` at construction time. When LiveKit hands off between agents, it automatically uses the new agent's `tts=` instance — the voice changes **naturally** without any `update_options` call.

- **`CARTESIA_VOICE_TRIAGE`**, **`CARTESIA_VOICE_TECHNICAL`**, **`CARTESIA_VOICE_BILLING`**, **`CARTESIA_VOICE_ACCOUNT`**, **`CARTESIA_VOICE_MANAGER`** — env vars to set per-persona Cartesia voice UUIDs
- Voices are Sonic (multilingual: same UUID speaks fr/ar/en)
- If a persona's env var is empty, it falls back to the base preset voice (never crashes)
- Only Cartesia primary is overridden; fallback providers (ElevenLabs, Inworld, Smallest.ai) keep their default voice

## Deterministic Handoff Messages

**Problem:** When an agent returns `BillingAgent(chat_ctx=..., language=...)`, LiveKit schedules the reply before the handoff — the LLM generates a transition phrase. This can be hallucinated, too long, or inconsistent.

**Solution:** A new `handoff_with_message(context, next_agent, message)` function (in `voice_flow.py`) tells the current agent to speak a **deterministic, pre-authored phrase** in the caller's language before handing off to the next agent — no LLM involved:

- `route_to_billing`: _"Très bien, je vous mets en relation avec notre service de facturation."_ (fr/ar/en)
- `route_to_technical`: _"Très bien, je vous mets en relation avec notre service technique."_
- `route_to_account_services`: _"Très bien, je vous mets en relation avec notre service de gestion de compte."_
- `escalate_to_manager`: _"Je vous transfère à un conseiller qui va poursuivre avec vous."_

## Consent UX Improvements

### ConsentTask Rewrite
- **Self-introduction**: Agent now introduces itself as _"the customer-support virtual assistant"_ (not just "greet briefly")
- **Clear opt-in**: Explicitly says _"You are FREE TO DECLINE"_ — consent is requested, not stated as already happening
- **No duplicate speech**: ConsentTask no longer produces spoken output after the caller answers. The collecting agent (triage) acknowledges the decision on the **next turn** via a `consent_just_collected` flag:
  - Consent granted → _"Thank you for agreeing, how can I help?"_
  - Consent denied → _"I'll continue without recording, how can I help?"_
  - Already collected (same session) → _"How can I help today?"_

### Triage Agent Greeting
- Context-aware: acknowledges the specific request from the conversation so far instead of generic "how can I help"
- No repetition of information already given

## Persona Greeting Improvements
All agent greeting prompts rewritten to be **context-aware**:
- **technical_agent**: _"ACKNOWLEDGE the specific technical problem the caller already described... If NO specific problem was mentioned yet, simply ask how you can help."_
- **billing_agent**: _"ACKNOWLEDGE the specific billing matter the caller already mentioned..."_
- **account_services_agent**: _"ACKNOWLEDGE the specific request the caller already mentioned earlier (plan, phone line, recharge, or roaming)..."_
- **manager_agent**: _"Briefly introduce yourself as a senior advisor, ACKNOWLEDGE the reason the call was escalated..."_

This eliminates the frustrating "how can I help you?" loop after a handoff.

## Language Switch Fix
`_update_tts_language` no longer resets the `voice` parameter — Cartesia Sonic voices are multilingual, so updating only the language preserves the persona voice across language switches.

## No Container / SDK Changes
No Dockerfile, docker-compose, or library version changes in this version.

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `apps/agent-worker/src/providers/tts.py` | MODIFIED | build_persona_tts() with Cartesia voice override per persona |
| `apps/agent-worker/src/agents/triage_agent.py` | MODIFIED | Per-persona TTS; context-aware consent acknowledgment |
| `apps/agent-worker/src/agents/technical_agent.py` | MODIFIED | Per-persona TTS; context-aware greeting |
| `apps/agent-worker/src/agents/billing_agent.py` | MODIFIED | Per-persona TTS; context-aware greeting |
| `apps/agent-worker/src/agents/account_services_agent.py` | MODIFIED | Per-persona TTS; context-aware greeting |
| `apps/agent-worker/src/agents/manager_agent.py` | MODIFIED | Per-persona TTS; senior advisor greeting |
| `apps/agent-worker/src/tools/routing_tools.py` | MODIFIED | Deterministic handoff messages (fr/ar/en) |
| `apps/agent-worker/src/tools/escalation_tools.py` | MODIFIED | Deterministic escalation message |
| `apps/agent-worker/src/tools/session_flow_tools.py` | MODIFIED | Language switch preserves persona voice |
| `apps/agent-worker/src/tasks/consent_task.py` | MODIFIED | Self-introduction; no duplicate speech; clear opt-in |
| `.env.example` | MODIFIED | CARTESIA_VOICE_* per-persona env vars |
