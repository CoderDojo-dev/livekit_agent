# Version 96 — Cookbook 16: topbar profile cache-key fix, customer portal error-handling polish, Makefile frontend dev-server targets

> **Base branch:** `version_95` (`1df2c64`, pushed state)
> **Commits:** 4 — topbar key + me_reads docstring sync `b9dd349`, error handling polish + Makefile `8a70823`, Makefile frontend targets + toApiError tests + cookbook specs `93cff7a`, test self-heal + cache stability `bfae9df` (verify hash at push time)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0019_agent_activity_indexes`)
> **Rebuild:** customer_portal web bundle (topbar + errors.ts)
> **New Makefile targets:** `make frontend`, `make frontend-portal`, `make frontend-admin`, `make frontend-stop`

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | none (business-api test-only changes)                         |
| Frontend builds       | customer_portal (portal-topbar, errors.ts, new errors tests)  |
| alembic head          | `0019_agent_activity_indexes` (unchanged)                     |
| New Makefile targets  | `frontend` (both dev servers on :8080/:8081), `frontend-portal`, `frontend-admin`, `frontend-stop` — auto-detects WSL (`cmd.exe` bridge) vs native npm, because shipped `node_modules` hold Windows native rolldown/esbuild bindings |

---

## What's New in This Branch

### Commit 1 — Cookbook 16: scoped topbar profile key (`b9dd349`)

- `portal-topbar.tsx` — the `/me/profile/detail` query now uses the signed-in customer key (`qk.profileDetail` + `staleTime: 30_000`), shared/deduped with the profile page. The old unscoped key survived the logout sweep (`removeQueries({ queryKey: ["me", customerId] })` did not match), so after a same-tab account switch the topbar rendered the **previous account's name** until a focus-triggered refetch replaced it. Fixed.
- `test_me_reads_paging.py` — docstring synced to cookbook wording.

### Commit 2 — Customer portal error handling polish + Makefile (`8a70823`)

- `customer_portal/src/lib/api/errors.ts` (+137/−13) — `toApiError` and serialized-error predicates hardened across portal API reads.
- `Makefile` — dev-server support bootstrap (PHONY line).

### Commit 3 — Makefile frontend targets + toApiError regression tests + specs (`93cff7a`)

- **Makefile** (+31) — new `frontend` / `frontend-portal` / `frontend-admin` / `frontend-stop` targets; when make runs inside WSL, npm is invoked through `cmd.exe` (Windows npm) because the shipped `node_modules` hold Windows-native rolldown/esbuild bindings; `frontend-stop` kills whatever listens on :8080/:8081.
- `errors.test.ts` — regression tests for `toApiError` passthrough/reconstruction and the serialized-error predicates.
- Cookbook specs committed: `features_to_apply/client_portal_cookbooks/cookbooks-v96/00-REVIEW-OF-version_95.md`, `16-topbar-key-and-missing-tests.md`.

### Commit 4 — Test self-heal + cache stability (fixes required by migration 0019)

- `test_agent_activity_speaker.py` — the dev database now holds **live calls and usage events** (migration 0019 unlocked real inserts), so the 8 tests asserting global totals over an empty table failed. Added `_purge_conversation()` self-heal (FK-ordered purge of `agent_usage_events`, `turns`, `sentiment_samples`, `escalation_cases`, `callback_schedules`, `call_sessions`) inside the rolled-back transaction — same pattern as the v93 `_purge_eligible` fix.
- `test_service_health.py` — `test_cache_expires_and_advances` was flaky: with TTL=0 two back-to-back probes could produce microsecond-identical `checked_at` timestamps; added a 2ms advance before the second probe.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_96` → **GREEN, exit 0** — 187 + 119 + 10 + 17 = **333 passed**, 0 failed.
- Version_95 on remotes untouched (`1df2c64`).