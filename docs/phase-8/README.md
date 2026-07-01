# Phase 8 — Sentiment & Escalation

**Goal:** the agent knows when to stop and hand off.
**Exit criterion:** the §10.1 mandatory-escalation triggers fire (incl. **frustration**); the Manager
is reached with full context; escalation ends in a **transfer or a callback**.

**11 files, no deletions.** Vendor boundary clean; worker compiles; **3/3** sentiment tests pass.

## What's in it
- `sentiment/sentiment_scorer.py` — a deterministic **lexical** scorer (fr/ar/en) behind a
  `SentimentScorer` interface. No per-turn LLM call → zero added latency. The LLM-backed scorer is
  the documented swap behind the same `.score()` (built in `providers/` to keep the vendor boundary).
- `sentiment/sentiment_hook.py` — `attach_sentiment(session)`: on each **finalized caller turn**
  (`user_input_transcribed`) it updates `consecutive_negative_turns` / `should_offer_escalation`.
  It only *measures*; the policy engine's `ESC_FRUSTRATION` rule and the personas *act*.
- `server.py` — wires `attach_sentiment(session)` next to metrics.
- `telephony/sip_transfer.py` — `transfer_to_human`: resolves an advisor **dynamically** (never a
  hardcoded trunk); if none is free **or** SIP isn't available (console/dev), it falls back to a
  **callback**. The real cold transfer (`transfer_sip_participant`, needs SIP REFER) is coded
  defensively for the telephony path.
- `clients/routing_client.py` — `resolve_available_advisor(skill_tag)`; returns `None` in the pilot
  (no live advisor system yet), so escalations land on the callback path.
- `tasks/callback_schedule_task.py` — `CallbackScheduleTask`: offers a callback, records the
  preferred time. The **written** SMS/Email confirmation is sent by the notification-service in Phase 9.
- `agents/manager_agent.py` — the Manager now owns `transfer_to_human`; reached on the shared
  session, so it has the prior conversation as context.
- `session/session_state.py` — adds `current_persona_skill_tag`, `callback_requested`, `callback_when`.

## How frustration connects end-to-end
1. The hook scores each caller turn; two negative turns → `consecutive_negative_turns >= 2`.
2. `tools/guarded_action.py` already maps `consecutive_negative_turns >= 3` into the policy context
   as `frustration=True` (Phase 6).
3. The policy engine returns **`ESC_FRUSTRATION`** (mandatory chain, evaluated first) → the tool
   returns an `escalate` outcome → the persona calls `escalate_to_manager` → Manager → transfer/callback.

> Note: the hook's escalation recommendation triggers at **2** negative turns; the *policy* frustration
> flag triggers at **3** (a deliberately stricter bar for blocking an action vs. merely *offering* a human).
> Both are single constants you can align if you prefer.

## Apply & run
Unzip at repo root. No new services, no new env. Run the stack as in Phase 7 (context 8101,
knowledge 8102, decision 8103, policy 8104, execution 8105, MCP 8201, worker).

## Proving the exit criterion
- **Sentiment → escalation:** say two angry turns (*"this is unacceptable"*, *"ridiculous, worst
  service ever"*) — the worker logs `sentiment: negative_turns=2 -> escalation recommended`. Then
  attempt a sensitive action → policy `ESC_FRUSTRATION` → handed to the Manager.
- **Other §10.1 triggers** (already deterministic in the engine): VIP (`+21629744108`) → `ESC_VIP`;
  repeated identity failure → `ESC_IDENTITY_FAILURE`; fraud → `ESC_FRAUD` (unit-tested).
- **Manager → callback:** the Manager calls `transfer_to_human`; with no live advisor it runs
  `CallbackScheduleTask`, captures a preferred time (`callback_requested=True`), and confirms.
- **Offline test:** `cd apps/agent-worker && PYTHONPATH=src python -m pytest -q tests/sentiment` → 3 passed.

## Honest scope notes
- **Lexical scorer by default** — robust and deterministic; the cookbook's cheap-LLM scorer is the
  documented production swap behind the same interface.
- **SIP transfer is telephony-only** — needs a SIP trunk with REFER; the console demo exercises the
  callback fallback. The transfer call is guarded so it never crashes a non-telephony run.
- **Written callback confirmation (SMS/Email)** is **Phase 9** (notification-service); Phase 8 records
  the request and confirms verbally.

**Traceability:** CDC §4.2 → sentiment scorer/hook; §4.9/§6.4/§10.1 → frustration → `ESC_FRUSTRATION`;
§5.12 → `transfer_to_human` + `CallbackScheduleTask` + Manager. **Next:** Phase 9 — Ticketing &
Notifications (the `ticketing-glpi` MCP server incl. `resolve_ticket` from your review note 2, and the
notification-service for the written confirmations).
