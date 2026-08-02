# Version 79 — Handoff loop guard, RAG timeouts & warm-up, identity timeout hierarchy, log dedup

> **Base branch:** `version_78`
> **Files changed:** 12 modified, 5 new (4 tests + version doc)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| livekit-server     | `v1.8.4` self-hosted profile unchanged |
| Docker Compose     | Unchanged (21 services) |
| Agent-worker image | **Rebuilt required** — production code changed (voice_flow, guards, identity task, server, log_masking, knowledge_toolset); rebuild + live verification pending (see Out of Scope) |

---

## What's New in This Branch

### Lot 1 — Handoff loop guard (voice_flow.py, session_state.py, base_agent.py, escalation_tools.py, instruction_kit.py)

A caller can no longer bounce between agents forever:

- `handoff_with_message` refuses a handoff once **`MAX_HANDOFFS_PER_CALL = 4`** are recorded on
  the session, **or** when a handoff already happened on the **same caller turn** (one routing
  per concern); on refusal it speaks a polite message **in the call's language** (fr/ar/en) and
  ends the call via `say_and_stop` instead of returning the next agent.
- `SessionUserData` gains `caller_turn_index`, `handoff_count`, `last_handoff_turn`;
  `base_agent.on_user_turn_completed` increments `caller_turn_index`.
- Manager escalation stays a legitimate transfer: `escalate_to_manager` passes
  `loop_guard=False` + `language=`.

### Lot 2 — RAG timeouts (knowledge_toolset.py, .env/.env.example)

- The MCP client session timeout is now `KNOWLEDGE_MCP_TIMEOUT_S` (default **9.0 s**) while the
  server budget is `KNOWLEDGE_SEARCH_TIMEOUT_S` (**7.0 s**).
- **Invariant:** `7.0 < 9.0` — the server always answers before the MCP client abandons. The
  installed `MCPServerHTTP` default (5.0 s client) used to equal the server budget (5.0 s),
  making the client time out exactly when the server did.

### Lot 3 — RAG warm-up (knowledge-service/main.py)

- One **real** retrieval (`get_retriever().search("forfait", top_k=1)`) runs at boot (end of the
  lifespan); failures are logged without crashing the boot. The first caller question no longer
  pays the Qdrant connection + filters + RRF fusion path cost.

### Lot 4 — Identity verification timeout hierarchy (identity_verification_task.py, guards.py)

- `TASK_DEADLINE_S` **30.0 → 45.0**; `GATE_TIMEOUT_S` **40.0 → 60.0**.
- **Cascade:** `VERIFY_CALL_TIMEOUT_S (5.0) < TASK_DEADLINE_S (45.0) < GATE_TIMEOUT_S (60.0)` —
  each layer fails in order, the task timeout is no longer swallowed by the external deadline.

### Lot 5 / 5.2 — Observability + log deduplication (guards.py, identity_verification_task.py, server.py, log_masking.py)

- Readable `identity gate fail-closed (%s: %s)` log with `type(exc).__name__` + `exc or "no detail"`.
- `MAX_INVALID_INPUTS = 4` budget → `_fail_closed("max_invalid_inputs")` when the caller keeps
  providing unusable digits.
- **Log dedup root cause (proved in the worker container):** `livekit.agents.cli.log.setup_logging`
  adds a `StreamHandler` + JsonFormatter on the root logger while `server.py` had already run
  `basicConfig` → every line was rendered twice (JSON via the LiveKit handler + raw via
  basicConfig). `server.py` now guards `if not root_logger.handlers` before `basicConfig` and
  clears handlers before `agents.cli.run_app(server)`.
- The PII mask filter is registered on the **root logger** as well, not only on existing handlers.

### New tests (4)

- `test_handoff_loop_guard.py` — first handoff allowed, same-turn handoff refused, new caller
  turn unlocks the next, budget capped at 4, manager escalation never refused.
- `test_identity_timeout_hierarchy.py` — 5.0 < 45.0 < 60.0 cascade.
- `test_identity_invalid_budget.py` — 4 invalid inputs → fail-closed.
- `test_knowledge_toolset_timeout.py` — MCP timeout resolution.

---

## Fixes Applied During Validation (the patch's own tests had never been executed)

1. **`voice_flow.py` read `context.session.session_state`, which does not exist** anywhere in the
   codebase (never assigned). The real LiveKit contract is `session.userdata` (`SessionUserData`,
   used by every other tool/task). Without this fix the loop guard could never record or refuse a
   handoff in production — `_record_handoff(None)` is a no-op. **Corrected to `userdata`.**
2. **`_handoff_refusal_reason` now also enforces the same-caller-turn rule** (a handoff on the
   turn where one already happened is refused) — the test-documented behaviour was missing from
   the code.
3. **`test_escalation_consent._fake_handoff`** updated to accept the new `language=`/`loop_guard=`
   kwargs (existing test broke on the new signature).
4. **Handoff test message aligned** to the actual `_HANDOFF_REFUSAL` text documented in the patch.

---

## Investigation lots — measured, deliberately NOT applied (per the guide)

| Lot | Question | Measurement | Decision |
|---|---|---|---|
| 6.1 | FR vs EN alignment | FR wins 3/5 pairs (0.1760–0.3829 CE scores vs EN 0.0093–0.9586) | **Lot 7 not applied** — threshold is 4/5, measurement not conclusive |
| 6.2 | Language filter / arabic volume | Corpus is 296/296 French, **0 arabic docs** | **Lot 8 not applicable** |
| 6.3 | Out-of-domain false positives | `reparation machine a laver` → RETURN with `ce_score=0.0912 ≥ 0.08`; full calibration: worst noise `ce_max_kept=0.4518` > best TP `0.0023` — **no CE threshold separates TP from noise** | **Thresholds NOT modified** (0.08 kept); raising it would break 4/10 legitimate queries |
| 6.4 | Abstention counter | Exactly **1** `no passage cleared the relevance gates` in logs | **No statistical basis** — thresholds intact |

---

## Validation

- `py_compile`: all 10 modified Python files compile.
- agent-worker suite: **85/85 PASS** (74 pre-existing + 4 new + fixed escalation consent).
- Full chain `test_committed.ps1` on the committed tree: **125/125 PASS** (see below).
- Ledger append-only untouched by tests.

---

## Out of Scope (left open, unchanged)

- **Container rebuild + live verification pending** (agent-worker image recreated with the new
  code; `/health` worker + knowledge-service; `initSession` 200; one log line per event; no
  `Waited 5.0 seconds`; `handoff refused by loop guard` only in the expected case; identity gate
  fail-closed with non-empty reason; `time_to_first_audio`). The user does the VS Code rebuild;
  live checks after.
- The real-traffic §7 control (escalations counter on a real call day).
- All items previously listed as out of scope in v78 (no compose service for the frontend,
  Twilio SIP, pre-existing ruff findings, etc.).
