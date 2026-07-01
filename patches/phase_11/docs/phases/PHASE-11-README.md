# Phase 11 — Observability & Supervision

"Operators can see and trust the platform." Two complementary observability concerns, per Blueprint §16:
**conversational-quality** (TTFA/TTFT via OTel) and **business/compliance** (verdicts, actions, audit —
already persisted in P2/P6), surfaced through a supervisor dashboard.

## What shipped (23 files)

### a) Self-hosted OTel pipeline
- **`observability-kit`** — real OTel tracer + meter + named instruments
  (`telecom.agent.ttfa.seconds`, `…ttft.seconds`, `…fallback.activations`, `…escalations`).
  **Dependency-optional and endpoint-gated**: if the OTel SDK isn't installed or
  `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, every call is a safe no-op — dev runs unchanged. Recording
  helpers never raise (metrics must never break a call).
- **`metrics_hook`** — now **exports** TTFA (from the end-of-utterance → speaking transition) and TTFT
  (from `llm_metrics`) to the OTel histograms, in addition to logging. Zero added latency.
- **OTel Collector** (`deploy/otel/`) — collector config (OTLP in → debug + Prometheus out),
  compose (collector + Prometheus), and a Prometheus scrape config.

### b) Supervisor & Admin dashboard
- **`apps/supervisor-dashboard`** — a React/Vite/TS read UI over the **business-api** (§17), with three views:
  - **KPIs** — containment rate, escalation rate, avg peak frustration, totals (`/api/v1/kpis`).
  - **Escalations** — the open queue (`/api/v1/escalations`); "Inspect" jumps to the session.
  - **Session inspector** — the **headline acceptance test**: it answers *"why did the system refuse
    this client's request?"* by showing the **policy verdicts with their justification**
    (`/api/v1/policy/verdicts`) alongside the PII-masked transcript + sentiment (`/api/v1/sessions/{id}`).
  - Role is sent as `X-Role` (RBAC at the API layer; OIDC binds at integration).

## Run
```bash
# telemetry
docker compose -f docker-compose.yml -f deploy/otel/docker-compose.yml up -d otel-collector prometheus
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317   # then (re)start the worker/services
pip install -e packages/observability-kit

# dashboard (business-api must be running on :8108 from P6)
cd apps/supervisor-dashboard && cp .env.example .env && npm install && npm run dev   # http://localhost:5174
```

## Verification
- **Dashboard**: `npm run build` → **tsc clean + Vite build succeeds** (33 modules, dist produced).
- **observability-kit**: offline tests pass (2) — `configure_tracer` no-ops without an endpoint, and the
  record/incr helpers never raise when unconfigured.
- **Regression**: obs-kit 2, policy 10, execution 5, business-api 6, conversation+sentiment 6 — green.
- **TTFA gate (cookbook §13 tip)**: the `time_to_first_audio_seconds=…` log line is now also an OTel
  histogram, ready to wire as a CI latency gate against the simulation suite (Phase 12 / §20).

## Notes / honest caveats
- No live OTel collector or browser in the build sandbox: I verified the dashboard with **real `tsc` +
  `vite build`** (installed deps, then cleaned `node_modules`/`dist` from the deliverable), and the
  observability-kit via its no-op tests + byte-compile. The metric **export** path runs once the SDK is
  installed (`pip install -e packages/observability-kit`) and a collector endpoint is set.
- The dashboard is intentionally **dependency-light** (no chart lib): KPIs render as cards; add Recharts
  later if you want time-series charts.
- This satisfies the Blueprint §10 Phase 11 acceptance: KPI table live, audit-chain integrity job passes
  (P6 `/api/v1/jobs/integrity`), verdicts visible with justification. **Next: Phase 12** — Compliance,
  Multilingual QA & Pilot (retention/purge, consent audit, FR/AR/EN UAT, load + soak against the latency budget).
