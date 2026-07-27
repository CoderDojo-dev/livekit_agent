# Version 58 — Ticketing MCP Parsing Fix, TTS NOT_GIVEN Sentinel Fix, Sub-flow TTS Wiring

> **Base branch:** `version_57`
> **Files changed:** 5 (+59 / -21)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

### Ticketing MCP Result Parsing Fix (`ticket_tools.py`)

**Bug:** The old `_mcp_call()` only read `result.structuredContent` from the MCP `CallToolResult`. FastMCP (our server framework) populates `content` (JSON text blocks), not `structuredContent`. This meant every ticketing tool call (`lookup_tickets`, `create_ticket`, `update_support_ticket`) returned `None`, and the wrappers reported "unavailable" even though GLPI had actually created the ticket.

**Fix:** Added `_extract_result()` helper that:
1. Tries `structuredContent` first (MCP 2025-06+ protocol)
2. Falls back to parsing the JSON text from `content` blocks — what FastMCP actually returns
3. Unwraps the `{"result": ...}` key consistently in both paths, so dict returns (e.g. `{"ticket_id": ...}`) pass through untouched while list returns (e.g. `lookup_tickets`) come back as lists whether wrapped or not

This is a minimal, backward-compatible change — if a future MCP client populates `structuredContent`, it is still used with priority.

### TTS Node Crash Fix (`voice_flow.py`)

**Bug:** `persona_tts()` and `active_persona_tts()` returned `None` when no persona TTS was explicitly set. LiveKit's TTS resolution logic is:

```
agent.tts if is_given(agent.tts) else session.tts
```

`is_given(None)` returns `True`, so `tts=None` is interpreted as "this agent has NO TTS configured" — not "use the session default". This caused a runtime crash: `"tts_node called but no TTS node is available"` — a hard agent failure on any call that triggered a sub-flow (consent, identity verification, payment confirmation, SIM replacement, callback scheduling).

**Fix:** Both functions now return `NOT_GIVEN` (the sentinel constant from `livekit.agents.types`) instead of `None`. `NOT_GIVEN` is the proper "unspecified" value that means "fall back to the session TTS". The guard condition now uses `isinstance(tts, NotGiven)` rather than `isinstance(tts, NotGivenOr)` — `NotGivenOr` is a `Union` type alias, not a class, so `isinstance` on it raises `TypeError`.

### Sub-flow TTS Wiring

With `active_persona_tts()` now correct, three more call sites were wired:

| File | Sub-flow | TTS source |
|------|----------|------------|
| `billing_agent.py` | `PaymentConfirmTask` in `make_payment()` | `active_persona_tts(context)` |
| `technical_agent.py` | `SimReplacementTaskGroup` in `replace_sim()` | `active_persona_tts(context)` |
| `triage_agent.py` | `ConsentTask` (recording consent) | `persona_tts(self.tts)` — uses the agent's own TTS identity instead of querying a `None` context |

The triage change is a subtle improvement: `active_persona_tts(None)` relied on the triage agent being set as `session.current_agent` at call time, which is the common case but not guaranteed. `persona_tts(self.tts)` directly uses the triage agent's own TTS, which is always available.
