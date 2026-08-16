# Cookbook — Three Verified Fixes: Roaming Projection, Business-API Port Default, Post-Success Duplicate Window

> **Base:** current workspace HEAD (v89 era, alembic head `0017_notification_failure_reason`)
> **Scope:** 3 bugs, verified against source on 2026-08-15. Every claim below carries a file:line
> reference read during verification. No fix touches anything outside its evidence chain.
> **Migration:** none. **Dependency change:** none. **New config:** none (one new module constant).
> **Containers to rebuild after apply:** `execution-service`, `agent-worker`.

---

## 0. Verification verdicts (why these are real, not false positives)

### Bug 1 — Roaming disable is a silent no-op: **CONFIRMED, in BOTH connector modes**

The full chain was traced:

1. `apps/agent-worker/src/tools/account_tools.py:71-75` — `toggle_roaming(context, enable: bool)`
   sends `execute_guarded_action(context, "ACTIVATE_ROAMING", {"enable": enable})`. One action
   type carries **both** directions; the direction lives only in `payload["enable"]`.
2. `services/policy-service/src/policy_service/rules/account.py:47-53` — `check_roaming` REFUSES
   when `enable` is absent (`ROAM_NO_DIRECTION`) and AUTHORIZES both `true` and `false`
   (`ROAM_OK`). Policy's contract is correct: **an AUTHORIZED verdict always carries `enable`.**
3. `services/execution-service/src/execution_service/executor.py:82-85` — live dispatch propagates
   the direction correctly: `set_roaming(customer_id, bool(payload.get("enable", True)), key)`.
4. `services/provisioning-sim/src/provisioning_sim/provisioning.py:201-224` — the sim honors it:
   `subscription.roaming_enabled = bool(enable)` (and refuses a redundant toggle).
5. **The defect:** `services/execution-service/src/execution_service/projections.py:347-348`:

   ```python
   elif req.action_type == "ACTIVATE_ROAMING":
       subscription.roaming_enabled = True
   ```

   `project_domain_effect` runs after **every** successful dispatch
   (`services/execution-service/src/execution_service/service.py:83-87`, SAVEPOINT-wrapped, no
   mode check). So:
   - **mock mode:** the projection is the only write → disable never happens.
   - **live mode:** the sim writes `roaming_enabled = False`, then the projection **overwrites it
     back to `True`** in the same transaction, on the same shared `telecom` database.

   Net effect both ways: caller hears "roaming is off", `action_ledger` records `succeeded`, the
   audit chain records `execution_result` — and `crm.subscriptions.roaming_enabled` stays `True`.
   Customer-360 and the admin console then keep showing roaming ON.

### Bug 2 — Agent-worker default points business-api traffic at the token-service: **CONFIRMED, env-masked**

1. `apps/agent-worker/src/config/settings.py:109` —
   `business_api_url: str = Field("http://localhost:8107", alias="BUSINESS_API_URL")`.
2. `apps/business-api/src/business_api/main.py:820` — `uvicorn.run(app, host="0.0.0.0", port=8108)`.
3. `apps/token-service/src/token_service/main.py:129` — `uvicorn.run(app, host="0.0.0.0", port=8107)`.
4. `.env.example:249-250` already documents the truth — the wrong value is even left in, commented:

   ```
   # BUSINESS_API_URL=http://localhost:8107
   BUSINESS_API_URL=http://localhost:8108  # business-api listens on 8108; 8107 is token-service.
   ```

   So the drift was found and patched **in the env template only**; the code default was never
   fixed. Anyone running `honcho start` without copying `.env` (or with a partial one) has the
   worker POSTing advisor-claim and callback-reserve to the token-service, which returns 404s.
5. Affected callers (verified): `apps/agent-worker/src/clients/routing_client.py:109` (advisor
   claim/release for SIP transfer) and `apps/agent-worker/src/clients/callback_client.py:87`
   (callback slots/reserve). Both degrade gracefully by design, so the failure is silent in logs
   at call time — exactly why it survived.
6. **Coupled constraint (must be handled in the same patch):**
   `settings.py:110` defaults `nms_service_url` to `http://localhost:8108` as well, and the
   `_distinct_service_urls` validator (`settings.py:119-141`) **raises at startup** on any
   collision. Fixing only line 109 would make a fresh no-env checkout crash on boot
   (`business_api_url` and `nms_service_url` both → 8108). The nms default must move in the same
   edit. Host-reachable nms-sim port is **8110**
   (`infra/docker-compose/docker-compose.apps.yml:158` maps host `8110` → container `8108`).

### Bug 3 — Double-execution window after success: **CONFIRMED, designed-but-unsafe**

1. `apps/agent-worker/src/session/session_state.py:69-86` — the key is memoized per
   (session, action_type, payload fingerprint) and **kept while unconfirmed**, so transport
   retries can never double-charge. On success, `release_idempotency_key` **deletes** the key.
   The docstring states this is deliberate: a later identical request should be a genuinely new
   action (e.g. a caller intentionally topping up the same denomination twice in one call).
2. `apps/agent-worker/src/tools/guarded_action.py:90-94` — the release fires the moment the
   outcome is `executed`.
3. `services/execution-service/src/execution_service/service.py:34-37, 69-71, 105-107` — the
   server dedupes **by key only**: a seen key returns `ExecuteResponse(replay=True)` with no
   re-dispatch; a new key is a new `action_ledger` row and a new dispatch.
4. The gap: an LLM duplicate tool call with identical arguments **after** the first success —
   a documented function-calling behavior under interruptions and retries — gets a fresh key and
   executes again. Only `make_payment` is serialized by a human confirmation task;
   `toggle_roaming` (`account_tools.py:71-75`), `top_up`, and `change_plan` go straight to
   `execute_guarded_action`, so a duplicate top-up double-charges with no human gate.
5. Not a false positive, but the fix must **preserve the documented intent** (deliberate repeats
   are legitimate). The fix below therefore closes only the *machine-duplicate* window instead of
   banning repeats outright.

---

## Fix 1 — Honor `payload["enable"]` in the roaming projection

**File:** `services/execution-service/src/execution_service/projections.py`
**Lines:** 347-348. **One line changes.**

```python
# BEFORE
    elif req.action_type == "ACTIVATE_ROAMING":
        subscription.roaming_enabled = True

# AFTER
    elif req.action_type == "ACTIVATE_ROAMING":
        # Mirror executor.py's live dispatch exactly: the direction comes from the payload,
        # and policy (ROAM_NO_DIRECTION) guarantees it is present on an AUTHORIZED verdict.
        subscription.roaming_enabled = bool(req.payload.get("enable", True))
```

**Why `bool(req.payload.get("enable", True))` and not anything else:**
- Identical semantics to the live adapter call (`executor.py:84`), so mock and live modes now
  project the same truth the adapter applied. Consistency with the existing code, not a new rule.
- The `True` default is dead code on the guarded path — `check_roaming` REFUSES a missing
  direction before execution ever runs (`rules/account.py:51-52`) — but keeping it identical to
  the executor's default means the two files cannot drift in opposite directions again.
- `ProvisioningRequest.parameters = req.payload` (line 329) already stores the direction, so the
  durable record was always correct; only the `Subscription` read-model lied. No migration: rows
  written before this fix carry the right `parameters` if an operator ever wants to reconcile.

**What this does NOT change:** the action name stays `ACTIVATE_ROAMING` (both directions). Renaming
or splitting it would touch the policy allowlist (`engine.py:28`), the rules module, the executor
map, the reference prefix map (`executor.py:22,28`), the agent tool, and the persona contract test
(`apps/agent-worker/tests/test_persona_contract.py:60` lists `toggle_roaming`) — a large diff for
zero behavioral gain. Out of scope.

---

## Fix 2 — Point the defaults at the services that actually listen there

**File:** `apps/agent-worker/src/config/settings.py`
**Lines:** 109-110. **Two defaults change; the second is mandatory, not optional** (validator at
`settings.py:136-141` raises on collision).

```python
# BEFORE
    business_api_url: str = Field("http://localhost:8107", alias="BUSINESS_API_URL")
    nms_service_url: str = Field("http://localhost:8108", alias="NMS_SERVICE_URL")

# AFTER
    # business-api binds 8108 (apps/business-api main.py); 8107 is the token-service.
    business_api_url: str = Field("http://localhost:8108", alias="BUSINESS_API_URL")
    # nms-sim publishes host port 8110 (docker-compose.apps.yml maps 8110 -> 8108).
    nms_service_url: str = Field("http://localhost:8110", alias="NMS_SERVICE_URL")
```

**File:** `.env.example` — line 242, align the template with host dev (compose overrides it anyway
via `docker-compose.apps.yml:216`, so this cannot break containerized runs):

```bash
# BEFORE
NMS_SERVICE_URL=http://nms-sim:8108

# AFTER
# Host dev: nms-sim is published on localhost:8110. Under full docker-compose the worker's
# environment overrides this with http://nms-sim:8108 (docker-compose.apps.yml), so the
# compose-internal hostname never needs to live in this file.
NMS_SERVICE_URL=http://localhost:8110
```

Optionally delete the stale commented line 249 (`# BUSINESS_API_URL=http://localhost:8107`) —
line 250 already carries the correct value and comment. Cosmetic; safe either way.

**Why no other file changes:** the docker-compose path was already correct
(`docker-compose.apps.yml:215` sets `BUSINESS_API_URL: "http://business-api:8108"` for the
containerized worker); only the bare-host defaults and the shared template were wrong. If sims are
not running on host dev, the NMS client degrades to its honest "unavailable" state — the same
behavior as today, minus the wrong-port confusion.

---

## Fix 3 — Close the post-success duplicate window without banning deliberate repeats

**File:** `apps/agent-worker/src/session/session_state.py`
**Lines:** 59, 69-86. The execution-service needs **zero** changes: it already replays a seen key
with `replay=True` and no re-dispatch (`service.py:34-37, 105-107`). We keep the key alive briefly
after success so a duplicate replays the recorded success instead of executing again.

Step 1 — module constant and imports (top of file; `time` is the only addition):

```python
import time
```

```python
# A repeat of an identical action inside this window after a success is treated as a machine
# duplicate (LLM double tool-call under interruption/retry) and replays the first result.
# After the window, an identical request is a deliberate new action and gets a new key.
_DUPLICATE_WINDOW_S = 60.0
```

Step 2 — new field next to `_idempotency_keys` (line 59):

```python
    _idempotency_keys: dict[str, str] = field(default_factory=dict)
    _completed_at: dict[str, float] = field(default_factory=dict)  # fingerprint -> monotonic ts
```

Step 3 — replace `new_idempotency_key` and `release_idempotency_key` (lines 69-86):

```python
    def new_idempotency_key(self, action_type: str, payload: dict | None = None) -> str:
        """Return the idempotency key for ONE logical operation.

        The key is memoised per (session, action_type, business payload) and kept while the
        operation is unconfirmed, so any retry (timeout, transport error) reuses it and can never
        double-charge. After ``mark_operation_completed`` the key is RETAINED for
        ``_DUPLICATE_WINDOW_S``: an identical request inside the window is a duplicate of an action
        that already succeeded, so the same key is returned and execution replays the recorded
        success instead of running again. Once the window expires, an identical request is a
        deliberate new action and receives a fresh key.
        """
        fingerprint = self._operation_fingerprint(action_type, payload)
        completed_at = self._completed_at.get(fingerprint)
        if completed_at is not None:
            key = self._idempotency_keys.get(fingerprint)
            if key is not None and time.monotonic() - completed_at < _DUPLICATE_WINDOW_S:
                return key  # duplicate of a just-succeeded action -> server replays it
            # Window expired: forget the old operation entirely, then mint below.
            self._completed_at.pop(fingerprint, None)
            self._idempotency_keys.pop(fingerprint, None)
        if fingerprint not in self._idempotency_keys:
            seed = f"{self.session_id}:{fingerprint}:{uuid.uuid4()}"
            self._idempotency_keys[fingerprint] = hashlib.sha256(seed.encode()).hexdigest()
        return self._idempotency_keys[fingerprint]

    def mark_operation_completed(self, action_type: str, payload: dict | None = None) -> None:
        """Record that the operation executed, starting the duplicate-replay window.

        The key is deliberately NOT dropped: dropping it is what let an immediate duplicate mint
        a fresh key and execute twice.
        """
        self._completed_at[self._operation_fingerprint(action_type, payload)] = time.monotonic()
```

**Rename note:** `release_idempotency_key` is renamed because a method that now *retains* the key
cannot keep a name that says "release" — that would recreate the same class of lie this codebase's
docstrings exist to prevent. Verified safe: the only call site is
`apps/agent-worker/src/tools/guarded_action.py:94`, and no test references either method
(grep over `apps/agent-worker/tests` and `services/execution-service/tests` returns zero hits).

Step 4 — one call-site + comment update in `apps/agent-worker/src/tools/guarded_action.py`,
lines 90-94:

```python
# BEFORE
    # A confirmed execution closes this logical operation: release its key so a further request
    # with the same parameters is dispatched as a NEW action instead of replaying this one.
    # A failure keeps the key, which is exactly what makes a retry safe.
    if isinstance(result, dict) and "executed" in {result.get("outcome"), result.get("status")}:
        user_data.release_idempotency_key(action_type, operation_payload)
    return result

# AFTER
    # A confirmed execution starts the duplicate window: an identical call within
    # _DUPLICATE_WINDOW_S replays this result via the retained key (no double charge);
    # after the window it is a genuinely NEW action. A failure keeps the key with no
    # timestamp, which is exactly what makes a retry safe.
    if isinstance(result, dict) and "executed" in {result.get("outcome"), result.get("status")}:
        user_data.mark_operation_completed(action_type, operation_payload)
    return result
```

**Why a 60-second window and not "never release":** LLM double-invocations fire within seconds of
the first result; a human deliberately repeating an operation ("top up 20 TND again") speaks a new
turn, confirms again, and lands far outside the window. Never releasing would make that legitimate
repeat silently replay the first receipt — the exact behavior the original docstring argues
against. The window closes the machine case while honoring the documented human case.

**Failure path unchanged:** on a failed/timeout dispatch the key is memoized with **no**
completion timestamp, so retries reuse it exactly as today.

---

## Validation (run in this order)

1. **Static gates**

   ```bash
   ruff check apps/agent-worker services/execution-service
   python scripts/run_tests.py   # full offline inventory (agent-worker + execution-service suites included)
   ```

   Expected: ruff clean (both files are outside the grandfather lists — keep them that way),
   full suite green. Version-89 baseline was 197/197; this patch adds no failures.

2. **Fix 1 functional proof (mock or live, both work — projections run in both):**

   ```sql
   -- pick a seeded postpaid subscription with roaming on
   SELECT id, msisdn, roaming_enabled FROM crm.subscriptions WHERE roaming_enabled = true;
   ```
   Place a call (or drive `execute_guarded_action` directly) with `toggle_roaming(enable=false)`,
   then:
   ```sql
   SELECT roaming_enabled FROM crm.subscriptions WHERE id = '<same id>';   -- expect: false
   SELECT parameters, status FROM provisioning.provisioning_requests
     ORDER BY created_at DESC LIMIT 1;                                      -- expect: {"enable": false}, completed
   SELECT action_type, status, parameters FROM execution.action_ledger
     ORDER BY created_at DESC LIMIT 1;                                      -- expect: ACTIVATE_ROAMING, succeeded
   ```
   Before the fix the first query returned `true`; after the fix it returns `false`. Repeat with
   `enable=true` to confirm the enable direction still works (projection now mirrors the payload,
   so both directions follow the payload).

3. **Fix 2 boot proof (no env):**

   ```bash
   env -u BUSINESS_API_URL -u NMS_SERVICE_URL python -c \
     "import sys; sys.path.insert(0, 'apps/agent-worker/src'); from config import get_settings; \
      s = get_settings(); print(s.business_api_url, s.nms_service_url)"
   ```
   Expected: `http://localhost:8108 http://localhost:8110` and **no**
   `Service URL collision` error. (Pre-fix with only line 109 changed, this would have raised —
   that is why line 110 ships in the same patch.)

4. **Fix 3 unit-level proof** (new test, suggested location
   `apps/agent-worker/tests/test_idempotency_window.py` — small, offline, no LiveKit):

   ```python
   """Duplicate window: a just-executed action replays; after the window it is a new action."""
   import time
   from session.session_state import SessionUserData, _DUPLICATE_WINDOW_S

   def _ud():
       return SessionUserData(session_id="s1")

   def test_retry_before_success_reuses_key():
       ud = _ud()
       assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) == \
              ud.new_idempotency_key("TOP_UP", {"amount": 20})

   def test_duplicate_inside_window_replays_same_key():
       ud = _ud()
       key = ud.new_idempotency_key("TOP_UP", {"amount": 20})
       ud.mark_operation_completed("TOP_UP", {"amount": 20})
       assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) == key

   def test_new_action_after_window_gets_fresh_key(monkeypatch):
       ud = _ud()
       key = ud.new_idempotency_key("TOP_UP", {"amount": 20})
       ud.mark_operation_completed("TOP_UP", {"amount": 20})
       # fast-forward past the window without sleeping
       fp = ud._operation_fingerprint("TOP_UP", {"amount": 20})
       ud._completed_at[fp] = time.monotonic() - (_DUPLICATE_WINDOW_S + 1)
       assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) != key

   def test_failure_keeps_key_without_window():
       ud = _ud()
       key = ud.new_idempotency_key("TOP_UP", {"amount": 20})
       # no mark_operation_completed: a retry must reuse the key indefinitely
       assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) == key

   def test_distinct_payload_is_a_distinct_operation():
       ud = _ud()
       assert ud.new_idempotency_key("TOP_UP", {"amount": 20}) != \
              ud.new_idempotency_key("TOP_UP", {"amount": 50})
   ```

   Wire check: `python scripts/run_tests.py` already includes the `apps/agent-worker` target, so
   the new file is picked up with zero CI changes (single inventory, P1-3 contract).

5. **End-to-end duplicate check (optional but recommended):** call `toggle_roaming(true)` twice in
   one session with identical payload inside 60 s. Expected in `execution.action_ledger`: **one**
   new row; the second tool result carries `replay=True` semantics (same reference). In the admin
   console actions view, no second `succeeded` row appears.

---

## Regression risk assessment

| Change | Blast radius | Risk |
|---|---|---|
| Fix 1 (one line, projections) | `ACTIVATE_ROAMING` projection only | Near zero. Enable direction unchanged (was already always `True`). Disable direction goes from "never worked" to "works" — no caller depends on it being broken; Customer-360/admin simply start telling the truth. |
| Fix 2 (two defaults + env template) | Host-dev boot config only; compose already overrides | Near zero. The only behavioral change is for environments that were silently broken. Validator collision explicitly handled in the same edit. |
| Fix 3 (session state + one call site) | All guarded actions' post-success duplicate handling | Low. Within-window identical repeats now replay instead of re-executing — that is the fix working. Deliberate repeats after 60 s unchanged. Failed-retry path byte-identical. No tests referenced the renamed method (verified by grep). |

## Explicit non-goals (do not "improve" while applying)

- No rename/split of `ACTIVATE_ROAMING` (see Fix 1).
- No change to the execution-service replay contract — it is already correct.
- No change to `make_payment`'s confirmation task — it is already serialized by human confirmation.
- No change to token-service/business-api ports themselves — the ports are right; the worker's
  defaults were wrong.
- No TTL/window made configurable via env: one module constant, matching how
  `_FRUSTRATION_STREAK` and `GATE_TIMEOUT_S` already live in code. Add a setting only if
  operations actually need to tune it.
