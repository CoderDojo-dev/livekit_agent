# Per-agent time and token usage ΓÇö implementation and operations cookbook

## Definitions and units
- **Sessions/calls:** distinct persisted `conversation.call_sessions` having at least one turn attributed to the persona in the selected 7/14/30-day window.
- **Time spent:** sum of persisted whole-call `duration_seconds` for those sessions. A handoff means the same call can appear for multiple personas; this is attributed session time, not exclusive execution time.
- **Average duration:** arithmetic mean of those persisted durations. Open sessions have no duration and do not contribute time.
- **Input/output/total tokens:** provider-reported LiveKit LLM metric counters. Total is input + output. Missing counters are never estimated. Cost is intentionally absent because no durable, authoritative price/cost event exists.

## Ingestion and Decision ΓåÆ Policy ΓåÆ Execution boundary
LiveKit `metrics_collected` remains observability-only. For `llm_metrics`, the worker accepts integer prompt/input and completion/output counters actually emitted by the provider, attributes them to `session.current_agent`, and enqueues them through the existing non-blocking `ConversationWriter`. This neither makes a decision nor bypasses Policy/Execution. Prompt, response, customer, tool argument, and transcript content are not stored in usage events.

## Schema and migration
Migration `0018_agent_usage_events` creates `conversation.agent_usage_events`: UUID id/session FK, agent, optional provider/model, non-negative input/output counters, and occurred_at. Indexes cover `(agent, occurred_at)`, session lookup, turn agent/session, and session start windows. Deploy migration before the worker. Downgrade drops only these additions.

## Aggregation and API
Supervisor-protected `GET /api/v1/agents/activity?days=N` clamps N to 1..365. It returns totals and per-agent duration, average, sessions, last seen, tokens, token-session coverage, and daily duration points. `coverage` is `available`, `partial`, or `unavailable`; `token_history=forward_only_no_backfill` is explicit. The dashboard server adapter independently requires `superviseur`, forwards role, validates the window, and includes the window in its query key.

## UI and accessibility
The Agents surface provides selectable windows, truthful KPI cards, responsive table/detail disclosure, keyboard-operable rows, loading/error/empty states, and literal `Unavailable` token labels. Partial coverage is data, not a zero. Compact durations use minutes while detail values retain seconds.

## Privacy and security
Only operational counters, model/provider identifiers, persona class, session FK, and timestamp are stored. No prompts or responses. Existing business-api authentication and supervisor RBAC apply; administrators inherit supervisor access. Database retention and access controls must match conversation telemetry policy.

## Configuration, performance, and operations
No pricing configuration exists and no cost is shown. No feature flag is required. Confirm migration head, deploy business-api, then worker, then dashboard. Monitor dropped conversation writes and query latency. Analyze indexes after high-volume rollout; use EXPLAIN on the time-window and agent predicates before changing indexes.

## Testing and rollout
Run persistence migration-integrity tests, worker writer/metrics tests, business-api agent aggregation tests, then dashboard test/typecheck/lint/build. Existing calls provide real duration/session history. **Token history starts only after migration + worker deployment; there is no historical backfill.** Never derive tokens from text length or billing estimates.

## Rollback
Roll back dashboard/API/worker first. If data retention is not required, downgrade 0018. Downgrading destroys captured token events; export only under approved privacy controls. Existing call/turn records are unaffected.

## Troubleshooting
- Tokens unavailable: provider omitted usage, pre-rollout call, or writer dropped the event. Inspect worker metric type/counter fields and write warnings.
- Partial: fewer token-bearing sessions than attributed sessions; expected across rollout or mixed providers.
- Zero duration: open/abandoned session or persisted zero-second call.
- Persona absent: no attributed persisted turns in the window.
- 403: account lacks supervisor rank.

## Jury demo
Select 7d then 30d, explain persisted attribution and non-exclusive handoffs, open a persona detail, and point out real session duration. Show `Unavailable`/`partial` honestly for pre-rollout token history, then place a post-rollout provider-backed call and refresh to demonstrate forward-only input/output/total capture. Do not claim cost or backfilled tokens.
