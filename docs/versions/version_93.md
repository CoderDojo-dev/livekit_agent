# Version 93 — Client portal cookbooks 1-7 applied, service-health panel, agent usage metrics, alembic 0018

> **Base branch:** `version_92` (`d43726d`)
> **Commits:** 12 (cookbooks 1-7 `120a627`→`64e35da`, dashboard polish + persistence/metrics `192c969`, service-health + audit + nav tests `1e03802`, migration + test alignment `7cba8f0`)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none (no pyproject/package.json changes)
> **Migration:** `0018_agent_usage_events` (new `conversation.agent_usage_events` table + index) — **applied to dev DB**
> **Rebuild:** required — agent-worker (metrics_hook persistence) + business-api (service_health endpoint); admin_dashboard web bundle on deploy
> **New CI job:** none (existing `frontend-test` covers the new nav/service-health unit tests)
> **Security:** history scrubbed of GCP + Deepgram keys on all remotes (see notes)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| Backend service code  | agent-worker (`conversation/writer.py`, `observability/metrics_hook.py`, `server.py`), business-api (`main.py`, `repositories.py`, `service_health.py`) |
| Infra change          | `docker-compose.apps.yml`: business-api env `SERVICE_HEALTH_TIMEOUT_MS` + `SERVICE_HEALTH_TARGETS` (8 health targets, ticketing optional) |
| Image rebuild         | **agent-worker**, **business-api**; admin_dashboard web bundle on deploy |
| alembic head          | `0018_agent_usage_events` (**migration added and applied**)     |
| New table             | `conversation.agent_usage_events` (provider LLM token metrics, FK cascade on session) |

---

## What's New in This Branch

### Cookbooks 1-7 — Client portal (applied)

- **01 audit & cleanup** (`120a627`) — portal codebase audit, dead code removal.
- **02 API & auth foundation** (`18fef4a`) — `/me` auth foundation, api auth hardening.
- **03 client self-service reads** (`9fb6cfc`, `0d7ebaf`) — customer data pages wired to `/me` reads; prettier formatting (`5300e95`).
- **04 UX & data layout revamp** (`fc3919f`) — portal layout and data presentation.
- **05 orb & realtime assistant** (`f92b847`) — orb/realtime assistant integration.
- **06 tool event timeline** (`8bdf1d2`) — tool event timeline view.
- **07 final polish & CI** (`64e35da`) — final polish and CI wiring.

### Admin dashboard & metrics

- **`192c969`** — agents/overview/settings polish; agent-worker conversation persistence (`conversation/writer.py`) and provider metrics (`metrics_hook.py` writing `AgentUsageEvent`); business-api repository cleanup (`repositories.py` rewritten `agent_activity()` — per-agent session duration + token usage, no per-turn caller count).
- **`1e03802`** — NEW `business_api/service_health.py` + `/api/v1/service-health` endpoint, admin dashboard `service-health-panel` (UI + tests), `routes/audit.tsx`, `lib/nexus/nav.test.ts`, cookbook application docs under `docs/enhancement_starter/` and `features_to_apply/client_portal_cookbooks/`.

### Migration 0018 + test alignment (`7cba8f0`)

- **NEW `alembic/versions/0018_agent_usage_events.py`** — creates `conversation.agent_usage_events` (UUID pk, `session_id` FK CASCADE, `agent`, `provider`, `model`, `input_tokens`/`output_tokens` >= 0, `occurred_at`, index on `session_id`). Missing before this commit — tests hit `UndefinedTable`.
- **`test_agent_activity_speaker.py`** — aligned with the v93 session-based contract (`sessions == 1` instead of removed `turns` count).
- **`test_retention_portal_sessions.py`** — self-heal `_purge_eligible()`: `run_retention()` commits, so earlier runs' eligible rows inflated counts; tests now purge residuals first.

---

## Validation

- `scripts/test_committed.ps1 -Ref version_93` → **GREEN, exit 0** — 79 + 109 + 10 + 17 = **215 passed**, 0 failed.

---

## Security note (v93)

All remotes (`origin`/chouaib-saad, GitLab, CoderDojo-dev) were force-pushed with a
`git filter-repo` history rewrite removing the real GCP API key and Deepgram key from
every branch; verified by fresh clones (0 secret blobs). The working repo is fully
re-aligned on the rewritten history. Recommended: rotate the GCP key and the Deepgram
key in their consoles.
