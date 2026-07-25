# Version 50 — Per-persona TTS Voices, Deterministic Handoff Messages & Consent UX

## What's new
- **`build_persona_tts(language, persona)`**: dedicated TTS FallbackAdapter per agent with Cartesia voice overridable via `CARTESIA_VOICE_<PERSONA>` env vars
- **Deterministic handoff messages**: `route_to_billing/technical/account_services` and `escalate_to_manager` speak a fixed transition phrase in the caller's language instead of returning a bare Agent (eliminates hallucinated/silent transitions)
- **Consent UX**: proper self-introduction as "customer-support virtual assistant"; caller explicitly told they are FREE TO DECLINE; no duplicate speech after consent answer
- **Context-aware greetings**: all agents acknowledge the specific request from prior turn instead of generic "how can I help"; Manager introduces as senior advisor
- **Language switch fix**: `_update_tts_language` no longer resets voice (Cartesia Sonic is multilingual)
