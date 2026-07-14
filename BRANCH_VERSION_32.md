# version_32 — The Third Working Version with Persistence Fixes

## Description
make a description of what we add ad the fixes we apply : (the containers and livekit sdk version change etc..)

## Changes & Patches & Updates

### 1. Mid-Call Language Switching — `switch_spoken_language` Tool
- **New tool** in `session_flow_tools.py`: hot-swaps STT/TTS providers mid-call
- Rebuilds STT/TTS from `LANGUAGE_PRESETS` for the requested language (FR/AR/EN)
- Updates `user_data.language` to the new language code
- Updates current agent's `_language`/`_lang_name` attributes
- Patches the first system message in `chat_ctx` — replaces old language name with new one (e.g. "French" → "Arabic") so agent instructions reflect the new language
- Returns structured outcome: `executed` (success), `refused` (unsupported language), or `already_active` (idempotent)
- Tool-driven acknowledgment: returned `message` tells the LLM to acknowledge in the new language

### 2. Auto-Injection — Every Persona
- `BaseTelecomAgent.__init__`: `switch_spoken_language` auto-injected into every persona's tool list (alongside `end_conversation`)
- Ensures the language-switch capability is universal across all agents (triage, billing, technical, account-services, manager)

## Files Affected (2 files, +72/-1)

| File | Status | Change |
|------|--------|--------|
| `apps/agent-worker/src/tools/session_flow_tools.py` | Modified | New switch_spoken_language tool (69 lines) |
| `apps/agent-worker/src/agents/base_agent.py` | Modified | Auto-inject switch_spoken_language into all personas |
