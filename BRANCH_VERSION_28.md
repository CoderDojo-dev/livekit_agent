# version_28 — The Third Working Version with Persistence Fixes

## Description
The third working version with persistence fixes: mention changes & patches & updates added to this new branch.

## Changes & Patches & Updates

### 1. OpenTelemetry Helpers — Distributed Trace Propagation
- **`inject_trace_context()`**: injects W3C `traceparent`/`tracestate` headers into outbound HTTP requests (safe no-op when OTel is absent)
- **`extract_trace_context()`**: extracts remote trace context from incoming HTTP headers (FastAPI `Request.headers` or plain dict)
- **`trace_span()`**: context manager starting a span with optional remote context extraction from headers; safe no-op without OTel
- **`trace_requests()`**: FastAPI/Starlette HTTP middleware wrapping every request (except health probes `/health`, `/livez`, etc.) in a span with `http.method` + `http.target` attributes
- **`get_tracer()`**: returns an OTel tracer by service name

### 2. Agent-Worker Clients — Trace Context Injection
All 5 HTTP clients now pass `inject_trace_context()` headers on every outbound call:
- `context_client.py`: `/context/{msisdn}`, `/verify-identity`, `/billing/{id}/invoices`, `/balance/{id}`
- `decision_client.py`: `/recommend`
- `execution_client.py`: `/execute`
- `notification_client.py`: `/notify`
- `policy_client.py`: `/evaluate-action`, `/evaluate-response`

### 3. Service Entrypoints — HTTP Tracing Middleware
- `context-service/main.py`: `configure_tracer("context-service")` + `trace_requests(app, "context-service")`
- `execution-service/main.py`: `configure_tracer("execution-service")` + `trace_requests(app, "execution-service")`
- `policy-service/main.py`: `configure_tracer("policy-service")` + `trace_requests(app, "policy-service")`

### 4. Audit Trail — Span Wrapping
- `ledger.py`: both `AuditLedger.append()` (in-memory) and `PgAuditLedger.append()` (PG) wrapped in `trace_span("audit.append", ...)` with `audit.event_type` + `audit.session_id` attributes

### 5. Public API — New Exports
- `observability_kit.__init__`: exports `get_tracer`, `inject_trace_context`, `extract_trace_context`, `trace_requests`, `trace_span`

### 6. Tests
- `test_trace_helpers_never_raise`: verifies `inject_trace_context`, `extract_trace_context`, `get_tracer`, `trace_span` are safe no-ops without OTel
- `test_trace_requests_noop`: verifies middleware registration on a dummy FastAPI-style app never raises

## Files Affected (12 files, +164/-39)

| File | Status | Change |
|------|--------|--------|
| `packages/observability-kit/src/observability_kit/telemetry.py` | Modified | 5 new trace helpers (inject, extract, span, requests, tracer) |
| `packages/observability-kit/src/observability_kit/__init__.py` | Modified | Export all new symbols |
| `packages/observability-kit/tests/test_telemetry.py` | Modified | 2 new test cases for trace helpers |
| `packages/audit-trail/src/audit_trail/ledger.py` | Modified | append() wrapped in trace_span |
| `apps/agent-worker/src/clients/context_client.py` | Modified | inject_trace_context on all requests |
| `apps/agent-worker/src/clients/decision_client.py` | Modified | inject_trace_context on recommend |
| `apps/agent-worker/src/clients/execution_client.py` | Modified | inject_trace_context on execute |
| `apps/agent-worker/src/clients/notification_client.py` | Modified | inject_trace_context on notify |
| `apps/agent-worker/src/clients/policy_client.py` | Modified | inject_trace_context on evaluate |
| `services/context-service/src/context_service/main.py` | Modified | configure_tracer + trace_requests |
| `services/execution-service/src/execution_service/main.py` | Modified | configure_tracer + trace_requests |
| `services/policy-service/src/policy_service/main.py` | Modified | configure_tracer + trace_requests |
