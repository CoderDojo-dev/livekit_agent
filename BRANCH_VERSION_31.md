# version_31 — The Third Working Version with Persistence Fixes

## Description
make a description of what we add ad the fixes we apply : (the containers and livekit sdk version change etc..)

## Changes & Patches & Updates

### 1. SessionResilienceMonitor — LiveKit Room Recovery
- New `SessionResilienceMonitor` class in `providers/_resilience.py` attaching to LiveKit room events:
  - **reconnecting**: logs warning, sets `user_data.is_reconnecting=True`, records `webrtc_reconnecting` metric
  - **reconnected**: logs info, clears `is_reconnecting`, speaks apology via `session.say()`
  - **disconnected**: detects `TOKEN_EXPIRED` reason (logs error, sets `user_data.token_expired`, records `webrtc_token_expired`); other disconnections log warning + `webrtc_disconnected`
  - **connection_quality_changed**: detects POOR/LOST quality, sets `user_data.webrtc_degraded`, records `webrtc_degraded`
- `monitor_room_resilience()` factory integrated in `server.py` entrypoint

### 2. Language-Locked Agents — Completion + De-escalation
- `base_agent.py`: extracts `language` from kwargs, stores `self._language`/`self._lang_name`; de-escalation note now references agent's language (was hardcoded to French)
- `manager_agent.py`: accepts `language` parameter, instructions locked to language, `on_enter` resolves from userdata

### 3. Cross-Routing Between Specialists
- `account_services_agent.py`: added `route_to_billing` and `route_to_technical` tools
- `billing_agent.py`: added `route_to_account_services` and `route_to_technical` tools
- `technical_agent.py`: added `route_to_account_services` and `route_to_billing` tools
- Allows specialists to re-route when a caller's need falls outside their domain

### 4. Import Cycle Fix — Lazy Imports
- `routing_tools.py`: `TYPE_CHECKING` guard + deferred local imports inside tool functions to break circular imports between agents and routing_tools
- `escalation_tools.py`: `_resolve_language` helper; passes `language=` to `ManagerAgent`

### 5. Tests — Resilience Monitor Coverage
- `test_chaos_wiring.py`: new `test_room_resilience_monitor_handlers` verifies all 4 event callbacks with a `FakeRoom`

## Files Affected (10 files, +189/-15)

| File | Status | Change |
|------|--------|--------|
| `apps/agent-worker/src/providers/_resilience.py` | Modified | SessionResilienceMonitor + monitor_room_resilience |
| `apps/agent-worker/src/server.py` | Modified | monitor_room_resilience integration |
| `apps/agent-worker/src/agents/base_agent.py` | Modified | Language storage + language-locked de-escalation |
| `apps/agent-worker/src/agents/manager_agent.py` | Modified | Language param + locked instructions |
| `apps/agent-worker/src/agents/account_services_agent.py` | Modified | Cross-routing tools added |
| `apps/agent-worker/src/agents/billing_agent.py` | Modified | Cross-routing tools added |
| `apps/agent-worker/src/agents/technical_agent.py` | Modified | Cross-routing tools added |
| `apps/agent-worker/src/tools/routing_tools.py` | Modified | TYPE_CHECKING guard + lazy imports |
| `apps/agent-worker/src/tools/escalation_tools.py` | Modified | _resolve_language + language param |
| `apps/agent-worker/tests/resilience/test_chaos_wiring.py` | Modified | Room resilience monitor test |
