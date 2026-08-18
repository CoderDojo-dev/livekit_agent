# Version 95 — Cookbooks 12-14 (data truth fixes, services/billing boundary, runtime proof), agent detail view + audit route, services rebuild, alembic 0019

> **Base branch:** `version_94` (`43a7a75`, pushed state)
> **Commits:** 3 — cookbook 9.7/10 services rebuild + activity notifications `60d9a18`, agent detail view + audit route + services/billing API improvements `91f2b1a`, cookbooks 12-14 applied + regression tests + migration 0019 `375105e`
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** **0019_agent_activity_indexes** (down_revision `0018_agent_usage_events`) — restores `uuid_generate_v4()` default on `conversation.agent_usage_events.id` + concurrent indexes `ix_call_sessions_start_time`, `ix_turns_active_agent_session_id`
> **Rebuild:** business-api (me_reads, repositories), agent-worker (metrics_hook), customer_portal + admin_dashboard web bundles
> **New CI/verification:** `verify-portal.sh` extended (12-check guard gains coverage of the new portal routes)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | business-api (`main.py` billing/me endpoints, `me_reads.py`, `repositories.py` +229), agent-worker (`observability/metrics_hook.py` usage events) |
| Frontend builds       | admin_dashboard (agents + audit routes), customer_portal (services/billing/activity/profile) |
| alembic head          | `0019_agent_activity_indexes` (was `0018_agent_usage_events`)  |
| DB impact             | `agent_usage_events.id` gets `uuid_generate_v4()` default (fixes NOT NULL violations that kept the table empty); new concurrent indexes on `call_sessions.start_time` and `turns(active_agent, session_id)` partial |

---

## What's New in This Branch

### Commit 1 — Cookbook 9.7 + cookbook 10: services rebuild, activity notifications (`60d9a18`)

- `customer_portal/src/routes/_portal/services.tsx` — services page rebuilt: grouped balances, top-ups, tiles.
- `activity.tsx` — notifications home with calls/messages grouping; honest empty states; metric tile marked pending.
- `copy.ts` (+65), `portal/data.tsx`, `profile.tsx`, `preferences.tsx`, `security.tsx` — copy and structure aligned with the rebuild.

### Commit 2 — Agent detail view, audit route, services/billing API improvements (`91f2b1a`)

- **admin_dashboard** — `routes/agents.tsx` + `lib/nexus/agent-view.ts` + `components/nexus/agent-detail.tsx` (agent detail view, +134); `routes/audit.tsx` rebuilt as the audit route; `lib/api/agents.server.ts` (+80); `nav.test.ts` aligned.
- **customer_portal** — `services.tsx` further rebuilt (grouped balances/top-ups), `billing.tsx` simplified, `profile.tsx` (+55), `billing.server.ts`, `me.server.ts`, `copy.ts` adjustments.
- **backend** — `repositories.py` +229 (usage aggregation), `me_reads.py`, `main.py` billing/me API improvements; `metrics_hook.py` usage-event emission.
- **tests** — `conftest.py` (+26), `test_agent_activity_speaker.py` (+416, usage aggregation contract), `test_auth_http.py` (+47).
- `verify-portal.sh` extended (+21) — 12-check guard covers the new portal routes.

### Commit 3 — Cookbooks 12-14 applied: data truth, services/billing boundary, runtime proof (`375105e`)

- **Alembic migration `0019_agent_activity_indexes`** — fixes the `uuid_generate_v4()` default missing from `conversation.agent_usage_events.id` (migration 0018 created the table without it, so every usage insert failed with NOT NULL violation and the table stayed empty); adds `postgresql_concurrently` indexes for bounded AI-persona activity aggregation.
- **New frontend tests** — `agent-activity-sparkline.tsx` + test, `retention-panel.test.tsx`, `agents.server.test.ts`, `agent-view.test.ts`, `agents.test.tsx`, `audit-page.tsx` + test (components/audit/), `customer_portal pagination.test.ts`.
- **New backend tests** — `test_me_reads_isolation.py`, `test_me_reads_paging.py` (business-api), `test_metrics_hook_usage.py` (agent-worker).
- **Cookbook specs** — `features_to_apply/client_portal_cookbooks/cookbooks-v95/`: `00-REVIEW-OF-version_94.md`, `12-data-truth-fixes.md`, `13-services-and-billing-boundary.md`, `14-runtime-proof-and-regression-tests.md`.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_95` → **GREEN, exit 0** — 187 + 119 + 10 + 17 = **333 passed**, 0 failed.
- Version_94 on remotes untouched (`43a7a75`).