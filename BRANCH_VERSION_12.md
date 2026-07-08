# version_12 — Docker Compose Inter-Service Networking Fix

## Purpose
Resolve inter-service connectivity failures under full-Docker deployment. When all services run in containers, `localhost` resolves to the container itself, not the host — so each service was unable to reach its dependencies (Redis, Qdrant, MinIO, domain services, MCP servers) despite `.env` having the correct values for host-based dev.

## Major Changes

### 1. Per-Service URL Overrides
Each service now receives Compose-service-name URLs via `environment:` blocks, overriding the `localhost`-based values from `.env`:

| Service | Override Added |
|---------|---------------|
| `context-service` | `REDIS_URL: redis://redis:6379/0` |
| `knowledge-service` | `QDRANT_URL: http://qdrant:6333` |
| `business-api` | `MINIO_ENDPOINT: minio:9000` |
| `ai-knowledge-rag` | `KNOWLEDGE_SERVICE_URL: http://knowledge-service:8102` |
| `ticketing-glpi` | `NOTIFICATION_SERVICE_URL: http://notification-service:8106` |
| `messaging-gateway` | `NOTIFICATION_SERVICE_URL: http://notification-service:8106` |
| `agent-worker` | All 6 domain service URLs + 2 MCP URLs overridden |

### 2. Structured `depends_on` Conditions
All services changed from flat list syntax to structured with health conditions:

- **Infra services** (postgres, redis, qdrant): `condition: service_healthy`
- **App services**: `condition: service_started`
- Agent-worker now depends on ALL upstream services (`context-service`, `decision-service`, `policy-service`, `execution-service`, `notification-service`, `ai-knowledge-rag`, `ticketing-glpi`) plus `postgres`

## Files / Modules Affected (1 file)

| File | Change |
|------|--------|
| `infra/docker-compose/docker-compose.apps.yml` | +55/-13: URL overrides + structured depends_on + improved comments |

## Design Rationale
- `.env` is shared with host-based dev (`make dev` / `honcho`) where `localhost` is correct
- Overrides live in the compose file, not `.env`, so host dev is unaffected
- Same pattern already established for `DATABASE_URL` in the same compose file

## Differences from version_11

| Aspect | version_11 | version_12 |
|--------|-----------|-----------|
| Inter-service URLs | localhost (broken under Docker) | Compose service names (works) |
| depends_on syntax | Flat list `[postgres, ...]` | Structured with health conditions |
| agent-worker deps | 4 direct deps | 7 deps + postgres |
