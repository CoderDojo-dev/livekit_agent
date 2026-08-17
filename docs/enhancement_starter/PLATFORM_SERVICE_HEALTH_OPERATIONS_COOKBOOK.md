# Platform Service-Health Monitoring ΓÇö Implementation and Operations Cookbook

## Product and architecture decision

Runtime health is an **administrator-only, server-side snapshot**, separate from the existing `/api/v1/system/overview` inventory and metrics. `business-api` is the control-plane aggregator because it already owns dashboard RBAC and the admin dashboard already accesses it through a server-only BFF. The browser never calls internal services. An empty or invalid registry is `unknown`, never healthy.

This is reachability/readiness evidence, not an SLA, dependency trace, synthetic transaction, or proof that a business workflow succeeds. Existing `/health` liveness endpoints remain compatible.

## Architecture

`browser -> TanStack server function -> business-api /api/v1/system/health -> configured /health targets`

The BFF reads the sealed HTTP-only session, requires `administrateur`, and forwards its bearer token. Business-api repeats the administrator check. Targets are probed concurrently with independent bounded timeouts. Only names, domains, classifications, reason codes and latency leave the aggregator; URLs, headers and response bodies do not.

The Compose registry covers meaningful request-path services: context, knowledge, decision, policy, execution, notification, token and optional ticketing. Business-api is intentionally not self-probed. PostgreSQL, Redis, Qdrant and MinIO retain native orchestrator probes; adding credential-bearing deep probes here would widen privileges and duplicate readiness checks. Workers have no HTTP readiness contract and are therefore not falsely represented.

## Endpoint and schema

`GET /api/v1/system/health` requires role `administrateur`; 401 means no valid identity and 403 means insufficient rank. Successful aggregation returns HTTP 200 even when dependencies fail, because the payload is the report.

```json
{
  "schema_version": 1,
  "overall": "degraded",
  "checked_at": "2026-01-01T12:00:00+00:00",
  "timeout_ms": 1500,
  "services": [{
    "name": "knowledge-service",
    "domain": "retrieval",
    "configured": true,
    "required": true,
    "status": "degraded",
    "reason": "service_reported_degraded",
    "latency_ms": 42
  }]
}
```

No URL or raw body is in the contract. Schema additions should be backward compatible; breaking changes require `schema_version: 2`.

## Probe semantics

- **configured** is independent of runtime status. Invalid registry entries are `configured=false`, `unknown`, `invalid_configuration`.
- **reachable**: 2xx JSON object whose `status` is `ok`, `healthy`, `ready`, or `reachable`.
- **degraded**: service explicitly reports `degraded`, `warning`, or `partial`; an HTTP 4xx indicates the process answered but its health contract is unusable.
- **unavailable**: timeout, connection failure, HTTP 5xx, non-2xx outside the 4xx classification, or explicit unhealthy status.
- **unknown**: valid response with malformed JSON, wrong shape, or unrecognized/missing status.
- Overall considers required services: unavailable wins; degraded/unknown produces degraded; all required reachable produces reachable. Optional failures remain visible but do not reduce overall. No configured services means unknown.

A maximum of 64 KiB is read. `SERVICE_HEALTH_TIMEOUT_MS` defaults to 1500 and is clamped to 100ΓÇô5000 ms. Probes run concurrently, so wall time is bounded near one timeout rather than target count times timeout.

## Configuration

`SERVICE_HEALTH_TARGETS` is a JSON array on business-api:

```json
[{"name":"context-service","domain":"conversation context","url":"http://context-service:8101/health","required":true}]
```

Use service-discovery names in containers/Kubernetes and localhost only for host development. Never embed credentials, query secrets, tokens, or externally supplied URLs. The registry is operator-controlled configuration and therefore an SSRF-sensitive allow-list. In production place it in a ConfigMap/value, not a browser variable; secrets remain in Secrets. Configure only services with a stable JSON `/health` contract.

## Security and observability

Authorization is defense-in-depth at BFF and API. CORS does not substitute for RBAC. The endpoint is read-only and does not log response bodies. Internal addresses remain server-side. Keep ingress exposure limited to business-api/dashboard; internal targets remain ClusterIP/private network.

Observe request count, duration and API errors using existing HTTP telemetry. Service reason and latency are deliberately returned for diagnosis; avoid target URLs as metric labels. Alerting should debounce repeated reportsΓÇöone snapshot is not an incident.

## Dashboard behavior

Overview retains the non-health service catalog and adds a distinct health panel. Non-admins see a restricted state and the query is disabled. Administrators receive:

- skeleton during first load; retryable error when no snapshot exists;
- explicit no-probes state for empty configuration;
- configured/invalid and required/optional labels;
- status and measured latency, with manual refresh;
- 30-second freshness window, 60-second foreground polling, and a stale warning after 120 seconds;
- previous data retained by React Query if a background refresh fails, plus an inline error.

The server adapter key is `["system", "health"]`. Neither target URLs nor credentials enter client code.

## Tests and verification

Backend unit tests cover empty/invalid registries, redaction, concurrent probing, status precedence, optional targets and timeout bounding. Frontend tests cover RBAC query suppression, truthful rendering, empty configuration and retryable failure.

Run from repository root:

```bash
pytest apps/business-api/tests/test_service_health.py -q
cd Frontend/admin_dashboard
npm test -- --run src/components/nexus/service-health-panel.test.tsx
npm run typecheck
npm run lint
npm run build
```

Validate Compose syntax with both files and deploy locally:

```bash
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml config --quiet
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --build
```

Runtime proof requires a real administrator token (shown as `$TOKEN`, never paste it into logs):

```bash
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8108/api/v1/system/health
```

Confirm: 200; expected service count; no `url`, authorization or secret fields; plausible latency; stopping one required container changes it to unavailable; restoring it returns reachable; an admin dashboard refresh shows the same classification. Also verify a supervisor receives 403.

**Evidence boundary:** passing source tests/typecheck/lint/build proves local source correctness only. A local Compose curl proves that local runtime. Neither proves deployed Kubernetes/production behavior. Deployed proof requires querying the deployed authenticated endpoint, checking the deployed configuration/revision, and recording orchestrator readiness and dashboard evidence for that revision.

## Deployment

1. Deploy business-api code and target configuration first. Empty registry safely reports unknown.
2. Confirm private DNS/network policy permits business-api egress only to registered health ports.
3. Deploy dashboard after endpoint availability; RBAC prevents premature access.
4. Smoke-test admin 200, supervisor 403, redaction, required failure and recovery.
5. Add production registry values to the Helm release/ConfigMap; the legacy Helm chart currently needs this explicit value wiring. Do not claim deployed support until that release configuration is applied and verified.

## Rollback

Remove/empty `SERVICE_HEALTH_TARGETS` to disable probes safely (UI becomes unknown/empty). Roll back the dashboard to remove the panel. Roll back business-api last; the route is additive and does not alter existing health or overview contracts. No database migration or data rollback exists. Restore prior Compose/Helm configuration and verify `/health` liveness.

## Failure modes and troubleshooting

- **No probes configured:** registry absent/`[]`; set valid JSON on business-api and restart.
- **health-registry unknown:** malformed JSON or non-array; validate quoting/YAML folding.
- **invalid configuration:** missing name/domain/url or non-HTTP(S) URL.
- **connection_failed:** DNS, port, network policy, process down, or wrong container name. Test from the business-api network namespace, not the browser.
- **timeout:** increase only after measuring; max 5000 ms. Fix slow health handlers rather than masking them.
- **invalid_response/unrecognized_status:** target does not honor the JSON health contract; correct endpoint or implementation.
- **HTTP 401/403 from target:** do not put credentials in the registry. Prefer a non-sensitive internal readiness endpoint.
- **Dashboard 401/403:** renew session/check administrator role; both BFF and API enforce it.
- **Stale snapshot/inline refresh error:** business-api or BFF is unreachable; old data is intentionally labeled stale, not replaced with fake health.
- **Optional outage but overall reachable:** expected; inspect individual rows. Mark required only when loss should change platform roll-up.
- **Infrastructure missing:** consult native Docker/Kubernetes readiness and observability; it is intentionally not inferred from application liveness.
