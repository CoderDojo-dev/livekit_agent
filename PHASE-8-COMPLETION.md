# Phase 8 — completion (personas act on sentiment + clarification trigger)

Closes the two loose ends flagged at Phase 8 delivery.

## What changed
- **`agents/base_agent.py` (new)** — `BaseTelecomAgent` overrides the `on_user_turn_completed`
  lifecycle hook: it scores each caller turn (updating the frustration signal) and, when
  frustration is flagged, injects a transient system note so the persona PROACTIVELY acknowledges
  it and offers a human (cookbook §12 — "personas act on the signal"). The note lasts one turn.
- **All personas now inherit `BaseTelecomAgent`** (triage, billing, technical, manager).
- **`tools/clarification_tools.py` (new)** — `request_clarification`: Triage asks ambiguous
  questions through it, so `clarification_attempts` is counted; the 2nd unresolved attempt returns
  `escalate`, making the §10.1 "two failed clarifications → ESCALATE" trigger deterministic (it
  also feeds the policy `ESC_CLARIFICATION` rule).
- **Sentiment scoring moved** from the session-level hook into the per-turn agent hook; the old
  `sentiment/sentiment_hook.py` is **deleted** and `server.py` no longer wires `attach_sentiment`.

## Apply
Unzip at repo root, then delete the superseded file:
`rm -f apps/agent-worker/src/sentiment/sentiment_hook.py`

## Verify
- Frustration: after two negative turns, the persona itself now apologizes and offers a human
  (log: `frustration high -> injected proactive de-escalation note`) — no sensitive action required.
- Clarification: two ambiguous turns → `request_clarification` returns `escalate` → Manager.
- Offline: `cd apps/agent-worker && PYTHONPATH=src python -m pytest -q tests/sentiment` → 3 passed.
