# version_29 — The Third Working Version with Persistence Fixes

## Description
make a description of what we add ad the fixes we apply : (the containers and livekit sdk version change etc..)

## Changes & Patches & Updates

### 1. Supervisor Dashboard — Carbon Design System Rewrite
Complete rewrite from bare React to IBM Carbon Design System (Gray 100 / g100 theme):
- **Shell**: `HeaderContainer` with `Header`, `SideNav` (rail), `Content`, `SkipToContent`
- **Navigation**: 9 tabs — Telemetry Overview, Performance KPIs, Escalation Queue, Session Inspector, Customer 360, Action Ledger, Policy Rules, Audit & Integrity, System Matrix
- **New dependencies**: `@carbon/react`, `@carbon/charts-react`, `@carbon/icons-react`, `@carbon/styles`, `@carbon/charts`
- **New files** (9):
  - `shared.tsx` — `PageHeader`, `ErrorBanner`, `VerdictTag`, `StatusTag`, `pct()` helper
  - `refresh.tsx` — `RefreshProvider` + `useRefresh` + `usePoll` (stale-while-revalidate polling with configurable 5s–1min interval)
  - `TelemetryOverview.tsx` — Carbon `LineChart` for timeline + verdict distribution
  - `KpiPanel.tsx` — Carbon `Grid`/`Column`/`Tile` with 6 KPI cards, skeleton loading
  - `EscalationQueue.tsx` — Carbon `DataTable` with search, pagination, `ContentSwitcher` (open/resolved), `Tag` styling
  - `SessionInspector.tsx` — Session lookup with `TextInput`, sentiment `LineChart`, verdicts `DataTable`, transcript turn list
  - `ActionLedgerPanel.tsx`, `AuditInspector.tsx`, `BusinessRuleRegistry.tsx`, `Customer360View.tsx`, `SystemMatrix.tsx`
- `vite.config.ts` — `optimizeDeps.include` for `flatpickr` + `@carbon/react`; `commonjsOptions` for node_modules
- `index.scss` — 225 lines of Carbon-themed SCSS (shell, page transitions, KPI tiles, transcript, inline forms, live pulse, tables, responsive)
- `main.tsx` — imports Carbon charts CSS + `index.scss` (replaced `styles.css`)
- `types.ts` — 9 new interfaces: `Action`, `BusinessRule`, `AuditVerifyResponse`, `IntegrityReport`, `SystemOverview`, `TelemetryTimeline`, `CustomerSubscription`, `CustomerInvoice`, `CustomerTicket`, `Customer360Data`, `ServiceProbe`

### 2. Business API — New Endpoints
- `GET /api/v1/system/overview` — DB row counts (calls, turns, verdicts, actions, audit entries, customers, escalations) + static service registry matrix (11 services with name, port, domain, status)
- `GET /api/v1/telemetry/timeline` — Last 50 sessions with timestamp/duration/frustration/disposition + verdict distribution (authorized/refused/escalated) from last 100 verdicts

### 3. API Client — New Methods
- `api.ts`: `actions()`, `businessRules()`, `auditVerify()`, `integrityJob()`, `customer360()`, `systemOverview()`, `telemetryTimeline()`

## Files Affected (22 files, +4184/-427)

| File | Status | Change |
|------|--------|--------|
| `apps/supervisor-dashboard/src/components/TelemetryOverview.tsx` | **New** | Timeline chart + verdict distribution |
| `apps/supervisor-dashboard/src/components/KpiPanel.tsx` | **New** | Full rewrite: Carbon tiles + skeleton |
| `apps/supervisor-dashboard/src/components/EscalationQueue.tsx` | **New** | Full rewrite: Carbon DataTable |
| `apps/supervisor-dashboard/src/components/SessionInspector.tsx` | **New** | Full rewrite: Carbon + chart |
| `apps/supervisor-dashboard/src/components/ActionLedgerPanel.tsx` | **New** | Action ledger panel |
| `apps/supervisor-dashboard/src/components/AuditInspector.tsx` | **New** | Audit chain inspector |
| `apps/supervisor-dashboard/src/components/BusinessRuleRegistry.tsx` | **New** | Business rules viewer |
| `apps/supervisor-dashboard/src/components/Customer360View.tsx` | **New** | Customer 360 viewer |
| `apps/supervisor-dashboard/src/components/SystemMatrix.tsx` | **New** | Service registry matrix |
| `apps/supervisor-dashboard/src/components/shared.tsx` | **New** | Shared UI components |
| `apps/supervisor-dashboard/src/refresh.tsx` | **New** | Polling context + hook |
| `apps/supervisor-dashboard/src/index.scss` | **New** | Carbon-themed SCSS (225 lines) |
| `apps/supervisor-dashboard/src/App.tsx` | **New** | Full rewrite: Carbon shell with 9 tabs |
| `apps/supervisor-dashboard/src/main.tsx` | Modified | Carbon imports + StrictMode |
| `apps/supervisor-dashboard/src/api.ts` | Modified | 7 new API methods |
| `apps/supervisor-dashboard/src/types.ts` | Modified | 9 new TypeScript interfaces |
| `apps/supervisor-dashboard/src/styles.css` | **Deleted** | Replaced by index.scss |
| `apps/supervisor-dashboard/vite.config.ts` | Modified | optimizeDeps + commonjsOptions |
| `apps/business-api/src/business_api/main.py` | Modified | 2 new endpoints |
| `apps/business-api/src/business_api/repositories.py` | Modified | system_overview + telemetry_timeline |
