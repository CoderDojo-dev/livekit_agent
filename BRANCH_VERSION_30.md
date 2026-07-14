# version_30 — The Third Working Version with Persistence Fixes

## Description
make a description of what we add ad the fixes we apply : (the containers and livekit sdk version change etc..)

## Changes & Patches & Updates

### 1. Language-Locked Specialist Agents
All three specialist agents now receive a `language` parameter and enforce locked instructions:

**BillingAgent** — `billing_agent.py`:
- Accepts `language: str` in constructor, resolved via `_LANG_NAMES` dict
- Instructions prefixed with `"You MUST speak ONLY in {lang_name}. Never switch to another language."`
- `on_enter` resolves language from session `userdata.language` (with fallback to constructor param), then issues language-locked `generate_reply`

**TechnicalAgent** — `technical_agent.py`:
- Same language-locking pattern: constructor param, locked instructions, language-resolved `on_enter`
- Knowledge search answer language matches the locked language

**AccountServicesAgent** — `account_services_agent.py`:
- Same language-locking pattern: constructor param, locked instructions, language-resolved `on_enter`

### 2. Routing Tools — Language Propagation
- `routing_tools.py`: new `_resolve_language(context)` helper extracts 2-letter language code from `session.userdata.language`
- `route_to_billing`, `route_to_technical`, `route_to_account_services` now pass `language=_resolve_language(context)` to their respective agents
- Ensures consistent language across triage-to-specialist handoffs — no language drift

## Files Affected (4 files, +88/-24)

| File | Status | Change |
|------|--------|--------|
| `apps/agent-worker/src/agents/billing_agent.py` | Modified | Language-locked instructions + on_enter |
| `apps/agent-worker/src/agents/technical_agent.py` | Modified | Language-locked instructions + on_enter |
| `apps/agent-worker/src/agents/account_services_agent.py` | Modified | Language-locked instructions + on_enter |
| `apps/agent-worker/src/tools/routing_tools.py` | Modified | _resolve_language + language param on handoff |
