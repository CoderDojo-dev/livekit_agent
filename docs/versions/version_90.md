# Version 90 — Admin dashboard: supervision verdicts + action ledger wiring (48/48) and telemetry timeline chart

> **Base branch:** `version_89` (`b5b0ac6`)
> **Commits:** 1 (two frontend-only bundles + 2 cookbook/status specs)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** none (head stays `0017_notification_failure_reason`)
> **Rebuild:** none required (frontend-only — admin_dashboard bundle rebuild on deploy)
> **Backend:** zero bytes touched

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged)                                           |
| livekit-server        | `v1.8.4` (unchanged)                                          |
| Backend service code  | **Zero bytes touched** (both bundles are `Frontend/admin_dashboard/src/**` only) |
| Image rebuild         | Not required; admin_dashboard web bundle rebuilt on deploy    |
| alembic head          | `0017_notification_failure_reason` (unchanged)                |
| Frontend              | admin_dashboard: 6 new files + 5 edits; customer_portal untouched |

---

## What's New in This Branch

Two frontend-only bundles. The admin dashboard goes from **46/48 wired → 48/48**
(every backend surface has a client) and gains a real per-session telemetry chart
that was already being paid for over the wire but discarded by TypeScript.

### Bundle 1 — Supervision surfaces wiring (verdicts + action ledger)

Two backend routes had no client at all — `GET /api/v1/policy/verdicts` and
`GET /api/v1/actions` — while `query-keys.ts` already declared (unused)
`supervision.verdicts(sessionId)` and `supervision.actions(status)` for them.

- **`lib/api/supervision.server.ts` (NEW)** — server functions + narrow 5-key
  wire types, read from the real repositories before writing (rule 1.4):
  `SessionVerdict` (`id/action/verdict/rule_id/justification`, `created_at` ASC)
  and `LedgerAction` (`id/action_type/status/idempotency_key/reference` nullable,
  `created_at` DESC). `session_id` as **query** param; status enum
  `["failed","retrying","pending","succeeded"]` default `"failed"` (mirrors the
  backend default; no "all" branch); both under
  `authedMiddleware` + `requireRole("superviseur")`.
- **`lib/nexus/supervision-view.ts` (NEW)** — pure helpers: `sessionVerdictLabel`
  (title-case normalisation — no cast to the decisions `Verdict` enum),
  `isEscalateVerdict`, `isBlockingVerdict` (REFUSED/ESCALATE), `actionScopeLabel`
  (count-only roll-up, honest about the missing `attempt_count`/`error_message`),
  `verdictSequence` (step number conveys the ASC order since the projection has
  no timestamps).
- **`components/nexus/session-verdicts.tsx` (NEW)** — `SessionVerdicts({ sessionId })`
  per-call chronological policy verdicts using the already-declared
  `queryKeys.supervision.verdicts(sessionId)`, `enabled: Boolean(sessionId)`.
  Blocking verdicts get row emphasis; ESCALATE gets the strong Token; full
  `CardSkeleton`/`ErrorState`/`EmptyState` coverage.
- **`components/nexus/action-ledger.tsx` (NEW)** — whole-ledger scan filtered by
  status, newest first, per-status cache key
  (`queryKeys.supervision.actions(status)`). Four-way `Segmented`
  (Failed/Retrying/Pending/Succeeded), default `failed`; chips reuse
  `actionStatusKey()` (no new `status.ts` key); `reference` Token rendered only
  when non-null; docstring documents this is NOT the decisions-table Actions
  column (which is scoped to the last 100 verdicts).
- **`routes/calls.tsx`** — mount `<SessionVerdicts sessionId={selected} />` after
  the Transcript card.
- **`routes/decisions.tsx`** — mount `<ActionLedgerPanel />` between the
  verdict-distribution card and `TableShell`.

**Live probes** (administrateur token, running business-api): verdicts route
exercised with real rows — `pay_bill/ESCALATE/POLICY_UNKNOWN_ACTION`,
`outbound_response/AUTHORIZED/OUT_OK`, `TOP_UP/AUTHORIZED/TOP_OK` — returning the
exact 5-key projection; `422` missing param / `401` no token confirmed. Action
ledger is currently empty (no rows in `execution.action_ledger` for any status)
so `{"actions":[]}` is what the `EmptyState` renders — honest, expected.

### Bundle 2 — Telemetry timeline chart

`GET /api/v1/telemetry/timeline` always returned **two halves**; only
`verdict_distribution` was typed, so the 50-point `timeline` was decoded at
runtime and discarded by TypeScript. The backend is untouched — this bundle
reads the half that was already paid for.

- **`lib/api/decisions.server.ts`** — the `businessApi<T>` generic is widened to
  `TelemetrySnapshot` (`timeline: TelemetryPoint[]` + `verdict_distribution`),
  with new exported types `TelemetryPoint`/`TelemetrySnapshot`. `getVerdictDistribution`
  name deliberately kept (comment records the misnomer); a second server function
  would have meant a second HTTP round-trip of identical bytes. Backwards-compatible:
  `overview.tsx`'s `.verdict_distribution` keeps working untouched.
- **`lib/nexus/telemetry-view.ts` (NEW)** — pure helpers, zero JSX/IO/`new Date()`:
  `TELEMETRY_METRICS` (Duration/Frustration), `isPlottable` (≥ 2 points — the
  x-step divides by `length - 1`), `metricValues`, `metricMax` (**floor of 1**:
  an all-zero series draws a flat baseline instead of NaN geometry), `formatMetric`,
  `metricUnit`, `averageOf`, `axisTicks` (≤ 6 evenly spaced anchors for 50 points),
  `timelineSpan`, `dispositionTone`/`dispositionTally`. Timestamps are bare
  `%H:%M:%S` strings — echoed verbatim, never parsed.
- **`components/nexus/blocks.tsx`** — new `SeriesChart` primitive (additive,
  placed above `Legend`, no new imports). Same house idiom as `LineChart`
  (`viewBox 0 0 100 100` + `preserveAspectRatio="none"`), **lines not circles**
  (circles would stretch into ellipses), `vectorEffect="non-scaling-stroke"`,
  caller-supplied scale, sparse ticks, **hover lifted to the caller** (blocks.tsx
  stays a pure stateless module — it has no `useState` import and still won't),
  DOM-space hit-slice layer. No floating tooltip: the numeric readout lives in a
  fixed row inside the card.
- **`components/nexus/telemetry-timeline.tsx` (NEW)** — `TelemetryTimeline`:
  `useQuery(analyticsKeys.verdicts(), getVerdictDistribution)` so Overview and
  Analytics share **one cache entry and one fetch**
  (`queryKeys.supervision.telemetryTimeline` intentionally unused — D2 recorded
  in the cookbook). `Segmented` switches the plotted series — **one metric at a
  time, no dual y-axis**. Pending → `CardSkeleton lines={6}`; error →
  `ErrorState`; < 2 points → `EmptyState`. Idle readout: Sessions / Average /
  Peak / Window; hovered readout: Time / Duration / Frustration / Outcome with a
  per-session outcome band (one 6px segment per session via `dispositionTone`,
  dimmed to 40% except the hovered index) + a density-sorted `dispositionTally`
  legend.
- **`routes/analytics.tsx`** — 1 import line + mount immediately after the Volume
  Trend card. `overview.tsx` stays **byte-identical** (a 220px chart does not
  belong in a density-first landing grid).

---

## Validation

- `tsc --noEmit` (admin_dashboard): **0 errors**
- `npm run build`: **success** (vite client + SSR + nitro; new chunks present)
- `npm run lint`: **0 errors, 9 warnings — all pre-existing** (shadcn `ui/*`,
  `advisors.tsx`, `callbacks.tsx`); none in touched files
- `prettier --write` on the new files only
- Full chain `test_committed.ps1 -Ref version_90`: **197/197 PASS**
  (business-api 66, agent-worker 104, notification 10, policy 17)
- Backend regression: `pytest apps/business-api/tests` → **66 passed**

### Invariants (all held)

- `overview.tsx` byte-identical (`git diff` empty)
- `status.ts` (the 27-key truth table) untouched
- No `.py`, `.github/*`, `Makefile`, `Dockerfile*`, `pyproject.toml`,
  `package.json` changes
- No new colours: only existing tokens `--n-7/8/11/12`, `--stroke-subtle`,
  `bg-n-*`, `bg-surface-*`, `text-ink-*`
- No `new Date(...)` in any new code; timestamps echoed verbatim
- Existing `LineChart`/`BarChart`/`Legend`/`HeroStat`/`StatCard` signatures
  unchanged; `SeriesChart` purely additive

---

## Out of scope / debt logged (NOT fixed)

- **`LineChart` NaN edge** — divides by `Math.max(...values) * 1.08`; an all-zero
  `daily` series produces NaN coordinates. `SeriesChart` already guards via
  `metricMax()`'s floor of 1; backporting the floor to `LineChart` is a separate
  patch (recorded in both the results file and the status report).
- **`inputValidator()` deprecation warning** during build — pre-existing and
  codebase-wide; the new server file matches the established pattern exactly.
- P2-3 Bundles J/L, R12 (GLPI), R14 (persona), R15 (lint ratchet) — unchanged
  from version_89.
- `ADMIN_DASHBOARD_STATUS.md` (new spec in `features_to_apply/`) is the full
  402-line wiring-truth audit of all 20 routes + 22 API modules; Section B lists
  remaining gaps and blind spots.