# Cookbook 11 - Verification and runtime proof

**Target branch:** version_94
**Product code added:** none. This cookbook adds no features. It exists because nothing in version_93 has ever been executed.
**Apply last**, after CB8, CB9 and CB10 are merged.

---

## 11.1 Why this cookbook exists

The version_93 results document is admirably candid, and reading it closely produces one conclusion:

- `scripts/verify-portal.sh` never ran - the implementer's `bash` was a broken WSL launcher ("Catastrophic failure"), so the 12 checks were replicated by hand in PowerShell.
- Docker was unreachable, so **no service was ever started**. No LiveKit session was made. No tool event was ever received by the portal. No 401, 403 or 429 was ever observed. No orb state beyond `disconnected` was ever rendered against a real agent.
- `pytest apps/business-api/tests` was not run.
- Every `/me/*` route on version_93 is type-clean and mypy-clean and **has never returned a row**.

That is not a criticism of the work - the code reads correctly and the two bugs the implementer caught by compiling (the `.id` attribute names, the missing `ticketing.tickets.updated_at`) are exactly the class of bug that only surfaces that way. But "compiles and type-checks" and "works" are different claims, and right now only the first is supported.

This cookbook is the ordered runbook that converts the second claim from assumption to evidence. Every step states its expected output, so a mismatch is a finding rather than a judgement call.

---

## 11.2 Environment, once

Run everything from a real shell. If Docker Desktop is still unreachable, fix that first - none of section 11.5 onward is possible without it, and no amount of static review substitutes.

```bash
docker compose up -d postgres
# expected: postgres healthy within ~10s
docker compose ps
# expected: postgres  running (healthy)
```

```bash
python scripts/run_tests.py --alembic-upgrade
# expected: alembic head 0017_notification_failure_reason, no pending migration
```

Required environment, both sides of the new gate:

```bash
# apps/token-service and Frontend/customer_portal must carry the SAME value
INTERNAL_API_KEY=<same on both>
PILOT_MSISDN=<the pilot subscriber>
```

If `INTERNAL_API_KEY` differs between the two, the assistant will silently serve the pilot customer to every signed-in user. That is the single most likely misconfiguration this batch introduces, and step 11.6.3 is designed to catch it.

---

## 11.3 Static gates - what CI will now do for you

```bash
cd Frontend/customer_portal
npm ci
npm run typecheck   # expected: 0 errors
npm run lint        # expected: 0 errors
npm test            # expected: 4 suites pass (orb-state, tool-events, format, copy)
npm run verify      # expected: 12/12 checks pass - FIRST REAL RUN
npm run build       # expected: build succeeds
```

**Expect `npm run verify` to fail on its first honest execution.** It has never run. When it fails, read the check name, fix the code, and never weaken the script - a guard edited to pass is worse than no guard.

Then the backend:

```bash
ruff check apps/business-api packages/persistence
mypy apps/business-api
pytest apps/business-api/tests -q
```

### The one open question from the version_93 review

The results document reports 16 ruff and 2 mypy errors in "pre-existing dirty-tree files": `metrics_hook.py`, `repositories.py`, `service_health.py`, `test_service_health.py`, `persistence/models/__init__.py`.

I verified from the branch listing that `service_health.py`, `metrics_hook.py` and `test_service_health.py` are **not committed** on version_93 - they exist only in the implementer's working tree, so they cannot fail CI. But `repositories.py` and `models/__init__.py` **are** committed, and I cannot run ruff to check them.

**The first push of version_94 settles this.** Read the `lint` job in the CI run:

- green - the reported errors were local-only, close the question
- red on `repositories.py` or `models/__init__.py` - a real pre-existing debt is now blocking; fix only the lines the job names, in a separate commit, and touch nothing else in those files

Do not fix these speculatively before seeing the job output. `repositories.py` is 50,884 B of business logic that this batch has no reason to touch.

---

## 11.4 Full stack up

```bash
docker compose up -d
# expected: postgres, livekit, token-service :8107, business-api :8108, agent-worker
curl -s localhost:8108/health   # expected: {"status":"ok"}
curl -s localhost:8107/health   # expected: ok
```

```bash
cd Frontend/customer_portal && npm run dev   # expected: :8080
```

If agent-worker is not registered with LiveKit under `LIVEKIT_AGENT_NAME=telecom-agent`, every call will connect and then sit in `connecting` forever. Check the worker log for its registration line before blaming the portal.

---

## 11.5 Auth paths - every one of these is currently unproven

| # | Action | Expected |
|---|---|---|
| 1 | Sign in with a seeded client account | 200, redirect to the portal, session cookie `nexus_portal_session` set `HttpOnly` |
| 2 | Wrong password | 401, the mapped copy string, **no** raw detail, no stack trace |
| 3 | Wrong password 6 times | 429 with the lockout message, not a generic error (`MAX_FAILED_ATTEMPTS=5`, `LOCKOUT_MINUTES=15`) |
| 4 | Sign up with a 9-character password | 400 with the length message (`MIN_PASSWORD_LENGTH=10`) |
| 5 | Open a protected route while signed out | redirect to `/login`, no flash of portal content |
| 6 | Hard refresh while signed in | session restores; no logged-out flash |
| 7 | Sign in, then delete the cookie, then click a list | the expired-session path, not a raw 401 toast |
| 8 | `revoke-all`, then use the old tab | forced back to login on the next request |
| 9 | Staff token against `/api/v1/me/profile` | **403** - this is the `_client_customer_id()` narrowing path and it has never executed |
| 10 | `curl` any `/me/*` route with a body carrying another `customer_id` | ignored; rows belong to the token's customer |
| 11 | Two different client tokens on the same route | fully disjoint row sets |
| 12 | `grep -R "nexus_portal_session\|PORTAL_SESSION" .output/public` | zero hits - the secret never ships to the browser |

Check 9 is the important one. The whole client-scoping design rests on `require_client` plus `_client_customer_id()`, and a 200 there would be a data-leak class bug.

---

## 11.6 The live assistant call - the largest untested surface

### 11.6.1 One complete call

1. Open `/assistant`. Orb is `disconnected`; the Start control is enabled.
2. Press Start. Orb goes `connecting` -> `preConnect` -> `initializing` -> `idle`. **No state may be skipped visually and none may stick for more than a few seconds.**
3. Speak. Orb goes `listening` while you speak, `thinking` on silence, `speaking` when the agent replies.
4. The agent's speech is audible on the first try, or the audio-enable control is visible and works after one click (browser autoplay policy).
5. Your words appear in the transcript as they are recognised; interim text is visually distinct from final.
6. New messages fade and slide in; older ones fade out at the configured opacities (1 / 0.52 / 0.22) with at most `MAX_VISIBLE_ITEMS = 3` prominent.
7. Your name and the agent persona name are shown - not identities, not `customer-<uuid>`.
8. Press End. Orb returns to `disconnected`. The summary shows a real duration and a real turn count within ~6s (CB8 8.5).
9. Open `/activity`. The call is listed **without a manual reload**, even though no write tool ran (this is the CB8 8.5 fix; on version_93 it fails).

### 11.6.2 Tool events

Ask something that triggers a read tool ("what is my balance?"), then something that triggers a write tool ("schedule a callback").

| Check | Expected |
|---|---|
| Event arrives | a timeline row appears on the `telecom.tool-events` topic within ~1s of the agent's action |
| Wording | customer-facing, e.g. "Checking your account securely..." |
| **No raw codes** | never `function_tools_executed`, `check_network_status`, `knowledge_search` or any of the 15 tool names |
| Unknown tool | a new tool name the frontend does not know shows a safe generic line, not the raw name and not a crash |
| Status | pending -> done transitions visibly; a failure shows a neutral failed state |
| Write tools refresh | after "schedule a callback", the callback appears under Requests without a reload |
| Overlap | with 5+ events, the timeline does not overlap the orb or the callbar at 1440, 1024 and 390 px |

### 11.6.3 The new token gate (CB8 8.1)

```bash
# untrusted: MSISDN must be ignored
curl -s -X POST localhost:8107/token -H 'content-type: application/json' \
  -d '{"room":"probe","identity":"probe","caller_msisdn":"+21690000000"}'
# expected: 200, and the service log shows
#   ignored caller_msisdn from untrusted caller identity=probe room=probe

# trusted: MSISDN must be honoured
curl -s -X POST localhost:8107/token -H 'content-type: application/json' \
  -H "x-internal-api-key: $INTERNAL_API_KEY" \
  -d '{"room":"probe","identity":"probe","caller_msisdn":"+21690000000"}'
# expected: 200, no warning line
```

Then the end-to-end proof that matters more than either curl: **sign in as a non-pilot customer and start a call.** The agent must greet *that* customer and answer with *their* balance. If it answers with the pilot subscriber's data, `INTERNAL_API_KEY` does not match between the portal and token-service. This is the check that catches the misconfiguration.

And confirm the widget still works:

```bash
# apps/client-widget sends neither key nor MSISDN
# expected: connects exactly as on version_93, agent resolves PILOT_MSISDN
```

### 11.6.4 Failure paths

| Scenario | Expected |
|---|---|
| Stop token-service, press Start | a clear "could not start" message; orb returns to `disconnected`; no infinite spinner |
| Stop agent-worker, press Start | connects then times out with an explanatory state, not a permanent `connecting` |
| Deny microphone permission | a specific message about the microphone; Start is not left in a pending state |
| Kill the network mid-call | orb reaches a failed state; End remains usable |
| Reload during a call | no zombie session; the room is not rejoined silently |
| Two tabs, both Start | each gets its own room (`portal-<customerId>-<suffix>`); neither breaks the other |

---

## 11.7 Data pages against real rows

Use the seeded census as the oracle: 129 sessions, 490 turns, 21 tickets, 48 notifications, 2 invoices, 2 billing accounts.

| # | Check | Expected |
|---|---|---|
| 1 | Activity page 1 and page 2 | different conversations; `total` matches `count(*)` for that customer |
| 2 | Open a conversation | turns in chronological order within each turn index (CB8 8.4); speaker labels correct |
| 3 | 490 turns cap | a long conversation renders without freezing (`_TURN_MAX = 400`) |
| 4 | Requests filter | each of the five statuses filters correctly; the count tiles agree with the list |
| 5 | Filter then page | changing the filter resets to page 1 (CB9 9.6) |
| 6 | Billing | outstanding equals the SQL aggregate and is identical on every page |
| 7 | Notifications | 48 rows page correctly at 20 per page |
| 8 | Callbacks | page 2 reachable |
| 9 | Services prepaid | main credit in TND visible; data in GB/MB; neither formatted as the other |
| 10 | Services postpaid | page is not sparse - plan, subscriptions and invoice context are present |
| 11 | Recharges | completed and failed top-ups both listed, newest first |
| 12 | Forbidden fields | `grep -REn "frustration\|sentiment\|token_digest\|failure_reason\|audio_record_url\|recording_consent\|customer_vip\|last_synced_at\|outcome_note\|transaction_reference" Frontend/customer_portal/src` - **zero hits** |
| 13 | Same, over the wire | capture every `/me/*` response and grep the JSON for the same list - zero hits |

Check 13 matters more than 12: the frontend not naming a field does not prove the API does not send it.

---

## 11.8 Design and responsive sweep

At 1440, 1024 and 390 px, on all ten tabs:

1. No horizontal scroll at 390 px.
2. No section header hidden under the sticky topbar or the callbar at any scroll position.
3. Skeletons occupy the height of the rows they replace - throttle the network and watch for a jump.
4. Tab through every page: every interactive element has a visible focus ring; nothing is unreachable.
5. Open a detail panel: Tab cycles inside it, the page behind does not scroll, Escape returns focus to the opening row (CB8 8.6.3).
6. Switch browser tabs and back on Activity: the list does not grey out (CB8 8.6.2).
7. Trigger a route change: a 2px progress line is visible (CB8 8.6.4).
8. With motion disabled, no transform animations run (CB10 10.5).
9. Empty a list (filter to a status with no rows): the empty state names a next step and is visually distinct from the error state.
10. `git diff version_93..version_94 -- src/styles.css src/components/orb` is **empty** - tokens and orb untouched.

---

## 11.9 CI is the final authority

Push `version_94` and read every job. `push` triggers on `main` and `version_*`, so this runs automatically.

| Job | Must show |
|---|---|
| `lint` | ruff + mypy green, or exactly the pre-existing findings from 11.3 and nothing new |
| `frontend-test` | unchanged from version_93 |
| `customer-portal-test` | npm ci, typecheck, lint, **Guard (verify-portal.sh)**, test, build - all green |
| `test` | pytest green |
| `db-migrations` | head `0017_notification_failure_reason`, no pending migration |
| `docker-build` | 6 services build |
| `docker-build-apps` | token-service, business-api, agent-worker build |

The `Guard (verify-portal.sh)` step appearing green is the deliverable of CB8 8.2 and the first machine-verified execution of those 12 checks in the project's history.

---

## 11.10 Sign-off record

Record in the version_94 results document, per section: **pass / fail / not run**. "Not run" is an acceptable answer and far more useful than an optimistic pass - the version_93 document's honesty about the broken bash is exactly what made this review possible.

```
11.3 static gates        [ ] pass  [ ] fail  [ ] not run
11.5 auth paths (12)     [ ] pass  [ ] fail  [ ] not run
11.6.1 live call         [ ] pass  [ ] fail  [ ] not run
11.6.2 tool events       [ ] pass  [ ] fail  [ ] not run
11.6.3 token gate        [ ] pass  [ ] fail  [ ] not run
11.6.4 failure paths     [ ] pass  [ ] fail  [ ] not run
11.7 data pages (13)     [ ] pass  [ ] fail  [ ] not run
11.8 design sweep (10)   [ ] pass  [ ] fail  [ ] not run
11.9 CI jobs (7)         [ ] pass  [ ] fail  [ ] not run
```

When 11.6 and 11.7 are fully green, the portal is genuinely complete rather than structurally complete. Until then, that is the honest status - and it is a matter of running the code, not writing more of it.

### One credential to rotate before any of this reaches a shared environment

`test-client-403@example.tn` / `client-secret-test-55` appears in the repository. It was fine for local work and must not survive into a deployed environment.
