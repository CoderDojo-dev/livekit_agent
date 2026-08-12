# Version 86 — P1-2 code inconsistencies fix + P1-3 CI pipeline (agent-worker tests now run)

> **Base branch:** `version_85` (`d9a6fbc` = P0-3 + P1-2 + P1-3 committed locally)
> **Commits:** 2 (features lot committed on v85 locally, + this spec-doc commit)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** None
> **Migration:** None (head stays `0016_portal_identity`)
> **Rebuild:** required — agent-worker AND business-api (P1-2 server.py + repositories changes)

---

## Containers & SDK

| Item               | Change                                                                 |
|--------------------|------------------------------------------------------------------------|
| New containers     | None                                                                   |
| livekit-agents SDK | `1.6.5` (unchanged — `livekit-plugins-gladia==1.6.3` was a *declared* dev dep install) |
| livekit-server     | `v1.8.4` (unchanged)                                                   |
| Docker Compose     | Unchanged                                                              |
| agent-worker image | **Rebuild required** (server.py disposition + retention + ruff fixes)  |
| business-api image | **Rebuild required** (repositories.py `speaker` predicate)             |

---

## What's New in This Branch

`version_86` carries forward the two already-committed lots on `version_85` plus this spec-doc
commit. They ship together because P1-3's inventory is measured against the P1-2 source tree.

### P1-2 — Fix Identified Code Inconsistencies

P0-1/P0-2/P0-3 closed the security and data-capture holes; P1-2 closes the gaps where a mechanism
exists, is wired, is DB-constrained, and is **simply never invoked**.

- **`final_disposition` derivation (the centrepiece)**: `conversation.call_sessions.final_disposition`
  had a column, a CHECK constraint (`resolved/escalated/dropped/abandoned`), a writer parameter,
  and a persistence branch — but **no caller ever passed a value** (all 129 sessions were NULL,
  five dashboards reported zero). Fixed by `_derive_disposition(user_data)` reading already-maintained
  session state (`human_transfer_outcome`, `escalation_reason`, `conversation_ending`,
  `caller_turn_index`) and passing it at the single `finish_session` call site
  (`server.py`). The 129 historical NULL rows are **not backfilled** (data-mutation decision, A7.4).
- **`conversation_ending` field**: the declared `conversation_ending: bool = False` added to
  `SessionUserData` (it existed in `session_flow_tools.py` reads but never on the dataclass).
- **Seed auth**: `Makefile` `seed` recipe chains `seed_pilot && seed_reference && seed_auth_credentials`
  + `seed_admin`.
- **Portal sessions retention**: `jobs/retention.py` purges `auth.portal_sessions` with a 7-day
  horizon, its own audit entry + commit, independently guarded (existing block untouched).
- **Port fix**: root `.env.example` `BUSINESS_API_URL` was `http://localhost:8107` (token-service,
  wrong); corrected to `:8108` with explanatory comment. Compose override was already correct.
- **Retire `apps/supervisor-dashboard`**: removed (genuinely broken per A7.3 — a retirement
  decision, not an inconsistency).
- **`backfill_p1_2_dispositions.sql`**: created (dry-run, sanity-checked, never auto-runs).

### P1-3 — CI: make the pipeline actually run

- **`scripts/run_tests.py`**: inventory extended — `apps/agent-worker` (6 shared package srcs on
  PYTHONPATH; 104 tests, 6 async — **never run by automation before**), `apps/token-service` (1 test),
  `services/decision-service` (`[]` paths — `scorer.py` uses only stdlib). `run_tests.py` sets
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` so most targets stay hermetic; for agent-worker only, autoload is
  re-enabled so `pytest-asyncio` loads (the 6 `@pytest.mark.asyncio` tests were failing under the
  autoload-disabled default).
- **`.github/workflows/ci.yml`**: `test` job now calls `python scripts/run_tests.py` instead of an
  inline loop; installs hoisted up front (services + MCP + apps + agent-worker, identity-verified vs
  the Makefile lists); `cache: pip` added. Triggers `branches: [ main, 'version_*' ]` (build/scan jobs
  keep their `if: github.ref == 'refs/heads/main'` so this costs no registry pushes on `version_*`).
- **`docker-build` matrix**: trimmed 9 → 6 (only `services/*`); `token-service`/`business-api`/
  `agent-worker` move to `docker-build-apps` (correct `apps/` path, identical tags) — eliminates
  impossible legs + duplicate `:latest` pushes (`security-scan` left at all 9: it consumes tags).
- **Ruff safe-autofix**: `147 → 0` (67 auto; 80 reviewed). `voice_flow.py` B010 rewrote
  `setattr(session_state, ...)` into attribute access on the live voice path — **reverted**
  (guard deliberate; file ratcheted with `B010` + explanatory comment).
- **Ruff ratchet** (`[tool.ruff.lint.per-file-ignores]`): 14 entries, exact-path, rules-only-violated
  (e.g. `server.py` = `["E402"]`); new files get none.
- **Mypy ratchet** (`[[tool.mypy.overrides]]` ignore_errors = true for exactly 14 modules): `M0 = 52 →
  Success: no issues found in 236 source files`. Every other file still strict; new modules get no
  entry.
- **Discovery (report, not added to CI)**: a root `tests/` directory (`conftest.py`,
  `test_geo_resolver.py`, `test_network_status_honesty.py`, `test_nms_adapter_honesty.py`, `load/`)
  exists in **neither** inventory — left to a design conversation (needs
  `packages/persistence/src` + `services/nms-sim/src` + `packages/integration-adapters/src` on the
  path).

---

## Validation

- `ruff check .` → **All checks passed!** (147 → 0; 67 auto + 36 reviewed, 14 grandfathered)
- `mypy packages/ services/ apps/` → **Success: no issues found in 236 source files** (52 → 0; ratchet)
- `python scripts/run_tests.py` → **17 targets, all `[ok]`, All suites passed.** (was 15)
- `pytest apps/business-api/tests -q` → **66 passed** (60 + P1-2 3-guard + P0-3 2 tests + P1-1 metric-test... counted under v85)
- `pytest apps/agent-worker/tests/conversation -q` → **22 passed** (P0-3 disposition tests included)
- Full chain `test_committed.ps1 -Ref version_86`: **197/197 PASS**
  (business-api 66, agent-worker 104, notification 10, policy 17)
- `verify_p0_1.sh` → **20/20** ; `verify_p0_2.sh` → **9/9**
- D13 live check: `POLICY_*` identical in `policy-service` and `business-api` containers
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47`, `conversation.turns=490`
  (probe `DELETE`d, never `TRUNCATE`d — turns unchanged after P0-3 probe cleanup)
- `P1-3 live gate #9`: `git diff --stat HEAD -- ci.yml pyproject.toml run_tests.py` against the
  v85 doc-tree = empty (anchors valid; P1-2 did not touch them)

---

## Out of scope / honest gaps (unchanged)

- Root `tests/` directory not wired into CI — reported as a P2 design decision (no improvised
  PYTHONPATH tuple).
- No live call on the rebuilt agent-worker since the recreate — the in-container probe from v85
  remains the end-to-end proof.
- All items previously listed as out of scope in v79–v85.