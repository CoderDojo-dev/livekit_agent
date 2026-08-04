# Version 80 — Identity gate floor fix ("agent announces then goes silent") + admin dashboard cookbooks batch 1 (C5–C14)

> **Base branch:** `version_79` (`eda5f58`)
> **Commits:** 11 (1 fix commit inside batch1 C5 + 10 cookbook commits)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump — confirmed `pip show` in container)
> **Dependency change:** None

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged, confirmed in container) |
| livekit-server     | `v1.8.4` (unchanged)    |
| Agent-worker image | **Rebuilt + recreated** (2 builds: fix, then fix + cosmetic layer); container `Up (healthy)`, worker `telecom-agent` registered |
| Docker Compose     | Unchanged               |

---

## 1. Production fix — "The agent says 'let me check' then goes silent" (guards.py)

### Diagnosis (root cause C4)

`tools/guards.py::ensure_identity_verified` awaited an `AgentTask` from inside a
`@function_tool` **without holding the floor**. In livekit-agents 1.6.5 an `AgentTask` takes
control of the session (`update_agent` → previous activity suspended →
`AgentActivity.scheduling_paused = True`). Speech the parent turn tries to schedule is
**dropped, not queued** — live log:
`WARNING:livekit.agents:skipping user input, speech scheduling is paused` followed by
`Tools executed: change_plan` with no speech. The caller had to say "ok" to hand the floor
back before the agent could read the answer.

Exact mechanism verified against the 1.6.5 source: generation resumption depends on
`fnc_call_out is not None` (gate A) **and** `reply_required` (gate B), not on
`len(tool_output.output) > 0`. Only two intentional-silence cases exist (S1: `StopResponse`
via `say_and_stop`/successful transfer; S2: `None` return outside handoff) — neither is the bug.

### Fix applied (single required change)

`apps/agent-worker/src/tools/guards.py` — the `IdentityVerificationTask` now runs inside
`async with context.foreground():` which waits for the session to be idle then **holds the
floor** for the sub-task duration:

```python
async with context.foreground():
    verified = await asyncio.wait_for(
        IdentityVerificationTask(...),
        timeout=GATE_TIMEOUT_S,
    )
```

Design decisions strictly per guide: `asyncio.wait_for` **inside** the `async with`
(`GATE_TIMEOUT_S` measures the task, not the queue; hierarchy 5.0 < 45.0 < 60.0 untouched);
`except Exception` left as-is (`ActivityClosedError`/`RuntimeError` must fail closed,
`asyncio.CancelledError` propagates); no defensive `getattr`, no feature flag
(`RunContext.foreground()` confirmed present on the 1.6.5 pin).

### Optional cosmetic layer (applied after the fix)

`apps/agent-worker/src/agents/instruction_kit.py` — `TOOL_TIMING_POLICY` appended to all
personas via `build_persona_instructions`: never announce a check ("let me check that"),
run the tool first, then speak once with the actual answer. Deliberately cites **no tool
name** so `instruction_violations()` can never flag it.

### Impact & rollback

- 7 tools fixed at once behind the gate: `get_plan_details`, `change_plan`, `top_up`,
  `toggle_roaming`, `unblock_sim_pin`, `get_invoice_summary`, `get_balance_summary`.
- `_TransferContext` (manager_agent) unaffected — `transfer_to_human` never calls the gate.
- Policy/execution/audit outputs bit-identical (same boolean returned → same verdicts).
- Rollback: `git checkout version_79 -- apps/agent-worker/src/tools/guards.py` (no migration,
  no env var, no data cleanup).

---

## 2. Batch 1 — Admin dashboard cookbooks C5–C14 (10 commits, reversible one-by-one)

Backend: only `apps/business-api/src/business_api/repositories.py` modified — **purely
additive**; `main.py` zero diff (the 7 local ruff findings pre-exist). Every route is
role-gated (conseiller/superviseur/administrateur, verified live via `curl`).

| Commit | Cookbook | Routes |
|---|---|---|
| `68afd4f` | **C5** Tickets | `/api/v1/tickets` (list) + `/tickets` view, ticket detail |
| `5406cb5` | **C6** Knowledge / RAG | `/knowledge` (inventory, health, upload, purge, probe) — talks to knowledge-service `:8102` server-side only |
| `ed13eed` | **C7** Guardrails & policies | `/policies` read-only registry with enforcement provenance (D13 env-share note) |
| `9efc9e0` | **C13** Escalations handoff | removes `/conversations`, dossier view, +`created_at`/`customer_id` keys |
| `5a06195` | **C8** Decisions ledger | verdict→action chain, `/decisions`, `decision_ledger` + `GET /api/v1/decisions` |
| `e842842` | **C9** KPIs & analytics | live `/overview` + trend `/analytics`, `GET /api/v1/analytics/trend`, service inventory w/o fake health |
| `50e88a7` | **C10** Audit, integrity & retention | live `/settings`, `audit_entries` + `GET /api/v1/audit/entries`, guarded two-phase purge |
| `ada60a1` | **C11** Customers & 360 | `/customers`, 360 modal, `GET /api/v1/customers`, search/pagination/status |
| `5579a44` | **C12** Agents & persona graph | `/agents`, `GET /api/v1/agents/activity`, static catalog, drift-visible roster |
| `a590e7d` | **C14** Reference catalogs | `/reference`, `GET /api/v1/reference/catalogs/{catalog}`, retires `/rules` → `/reference` |

Frontend (`Frontend/admin_dashboard`): new routes (tickets, knowledge, policies, decisions,
analytics, settings, customers, agents, reference), new nexus components
(`advisor-form`, `callback-outcome`, `modal`, `schedule-editor`, `states`, `transcript`…),
new server-side API clients (`auth`, `advisors`, `availability`, `callbacks`…),
`callback-view.ts`/`escalation-view.ts` mapping `callback_scheduled`.

### Per-cookbook gate (verified)

- `bunx tsc --noEmit` → **CLEAN**
- `bun run build` → exit 0 (at authoring time)
- `git diff --stat -- package.json` → empty (zero new dependency)
- `git diff --stat -- apps/ packages/` → exactly `repositories.py` (additive)
- Colour scan (`rgb(`, hex) on new files → 0 hits (achromatic bible respected)
- Date-trap scan (`getDay(`/`getHours(`/`new Date(`/`toLocaleString(`) → 0 hits
- Overlays/fixed → portal `document.body` verified
- Role gates verified live (`curl`): conseiller→403 / superviseur→200 on tickets &
  escalations; superviseur→403 / administrateur→200 on business-rules

---

## Validation

- agent-worker suite: **85/85 PASS** (regression after the `foreground()` fix)
- Full chain `test_committed.ps1 -Ref version_80`: **136/136 PASS**
  (business-api 24, agent-worker 85, notification 10, policy 17)
- Focus: `test_identity_timeout_hierarchy.py`, `test_identity_invalid_budget.py`,
  `tests/identity/`, `test_handoff_loop_guard.py`, `test_persona_contract.py` → 31/31 PASS
- `scripts/persona_contract_checks.py`: 43 OK / 5 FAIL — identical to clean `version_79`
  export (pre-existing, NOT introduced by the cosmetic layer)
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47` (5 new
  `callback_schedules` rows dated 2026-08-03 = integration activity, not test writes)
- No new unit test for `foreground()` — deliberate (would mock LiveKit's scheduling state
  machine; the honest check is the live recipe)

---

## Known environment note (not a v80 regression)

`bun run build` currently fails on this machine with
`ERR_REQUIRE_ESM` / "Vite requires Node.js 20.19+ or 22.12+": the global Node is
**v22.11.0** while the installed Vite 8.1.5 requires `>=22.12.0`. `package.json` and
`vite.config.ts` have **zero diff** between `version_79` and `version_80` — the failure is
environmental (Node version), not introduced by this branch. `bunx tsc --noEmit` is CLEAN.

---

## Out of scope (left open, unchanged)

- Live call recipe scenarios A–D (real phone call to LiveKit cloud): operator-run ⏳ —
  monitor `docker compose logs agent-worker | Select-String "speech scheduling is paused"`
- Debt logged by the patch (D1–D5): identity gate = nested AgentTask (safe via
  `foreground()`, ideal state = dedicated muted turn); `conversation_ending` undeclared on
  `SessionUserData`; `human_transfer_in_progress` vs `human_transfer_announced` naming;
  `_clarification_pending` reset only via `on_user_turn_completed`; agent-worker tests not in
  CI + `STRICT_PERSONA_CONTRACT` never set in CI
- Honest gap: `routing_tools.py`, `outcomes.py`, `ticket_tools.py` not audited for S2 return
  shape (needs a raw reproduction)
