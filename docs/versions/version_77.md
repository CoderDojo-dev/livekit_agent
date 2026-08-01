# Version 77 — Policy Fail-Closed Observability: Measure and Classify Escalation Causes

> **Base branch:** `version_76`
> **Files changed:** 1 modified (`apps/agent-worker/src/clients/policy_client.py`, +46/−2)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| Docker Compose     | Unchanged (21 services, `livekit-server` v1.8.4 self-hosted profile untouched) |
| agent-worker image | Rebuilt locally to embed the new code (`docker.io/library/docker-compose-agent-worker`); no image tag change |

---

## Purpose

The policy-service verdict ledger is append-only and hash-chained, so every policy decision is
already recorded. What was **not** measurable was the other direction: escalations **suffered**
when the policy-service could not be reached. Every fail-closed path (`evaluate_action` →
`ESCALATE`, `evaluate_response` → `REFUSED`) logs with the identical message `policy
evaluate-action failed; failing closed…`, so a timeout, a 500 and a refused connection were
indistinguishable in the logs. This version makes escalations measurable and classifiable by
cause, exactly as the §7 instrument prescribes.

---

## Changes Applied

### `apps/agent-worker/src/clients/policy_client.py` — instrumentation only

- `evaluate_action` and `evaluate_response` now measure the real call duration
  (`time.perf_counter()`) and classify every fail-closed failure into one of three causes:
  `cause=timeout` (httpx.TimeoutException) / `cause=http_status` (httpx.HTTPStatusError) /
  `cause=transport` (anything else — refused connection, DNS, …).
- The budget is memorised (`self._timeout`) so it can be quoted in the logs.
- A `logger.warning("policy_slow …")` is emitted only when the call exceeds half the budget —
  a slow checkpoint is a future fail-closed escalation, warned before it becomes one.
- Stable markers `policy_fail_closed` / `policy_slow` replace the accidentally identical
  messages of the old code, so logs can be counted per cause.
- **The returned dictionaries are byte-identical to before** (verified live):
  `{"verdict": "escalate", "rule_id": "POLICY_UNAVAILABLE", …}` and
  `{"verdict": "refused", "rule_id": "POLICY_UNAVAILABLE", …}` — the verdict contract is
  unchanged; nothing the patch explicitly forbade was touched.

---

## Proof — Live Scenarios (harness run inside the container via the real `PolicyClient`)

| Scenario | Observed output |
|---|---|
| Healthy `TOP_UP` | `{"verdict": "authorized", "rule_id": "TOP_OK", …, "verdict_id": …}` — fast, **no** `policy_slow` |
| Healthy `evaluate_response` | `{"verdict": "authorized", "rule_id": "OUT_OK", …, "verdict_id": …}` |
| Refused connection (`policy-service:9`) | `policy_fail_closed evaluate-action cause=transport elapsed=0.003s budget=2.0s; ESCALATE:` → verdict `escalate`/`POLICY_UNAVAILABLE` unchanged |
| Timeout (budget 0.001s) | `policy_fail_closed evaluate-action cause=timeout …; ESCALATE:` → verdict unchanged |
| HTTP error (404) | `policy_fail_closed evaluate-action cause=http_status …; ESCALATE:` → verdict unchanged |
| Slowness > half budget (1.2s of 2.0s) | `policy_slow evaluate-action took 1.204s of a 2.0s budget` — response still handled |
| `evaluate_response` failure | `policy_fail_closed evaluate-response cause=transport …; REFUSED:` → verdict `refused`/`POLICY_UNAVAILABLE` unchanged |

**Anomaly measured, in the spirit of the patch itself:** the first call (payload `pay_bill`,
before the correct vocabulary) exceeded the budget (client timeout at 2.081s) **while the
engine had already processed and persisted the decision** — exactly the class
« the service works, it is too slow for the budget » that `cause=timeout` now makes
identifiable. Significant detail: `pay_bill` is not in `SUPPORTED_ACTIONS`, so the engine
returned `ESCALATE/POLICY_UNKNOWN_ACTION` — the « edge case » described in the document (not a
policy problem; widening `SUPPORTED_ACTIONS` would be a mistake). No recipe row was touched;
the row is kept in the database as a v77 recipe trace (append-only registry).

---

## Validation

| Step | Result |
|---|---|
| agent-worker suite on working tree | **74 passed** (11.22s) |
| Full chain `test_committed.ps1 -Ref HEAD` on committed `384001d` | **125/125 PASS** (24 + 74 + 10 + 17) |
| No agent-worker test references `PolicyClient` (change without test impact) | observed |
| `python -m py_compile` | OK |
| Code in image (rebuilt, container recreated) | `grep -c 'policy_fail_closed\|policy_slow'` → **4** (both markers in both methods) |
| `server.py` log level | `logging.basicConfig(level=logging.INFO)` → markers reach stdout in production |

---

## Out of Scope (left open, unchanged)

- Widening `SUPPORTED_ACTIONS` (would be a mistake per the document — `pay_bill` is a
  vocabulary problem, not a policy problem).
- The real-traffic §7 control on a call day (requires real traffic, not available at patch
  time).
- All items previously listed as out of scope in v76 (identity verification timings, Twilio
  SIP, pre-existing ruff findings, etc.).
