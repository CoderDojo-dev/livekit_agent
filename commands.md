# Telecom AI Agent — Commands & Quick Reference

## Quick Start

```bash
# One command: install deps + start infra + migrate + seed + run everything
make dev

# First time only — install web frontends
make frontends
```

## Make Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available targets |
| `make install` | Install Python packages (correct order) + services + MCP + honcho |
| `make frontends` | npm install both web apps (supervisor-dashboard, client-widget) |
| `make frontends-clean` | Reinstall frontend deps (fixes Rollup optional deps) |
| `make infra` | Start infrastructure containers (postgres, redis, qdrant, minio, otel) |
| `make infra-livekit` | Start infra + self-hosted LiveKit server (skip if using LiveKit Cloud) |
| `make create-db` | Create the telecom database in Postgres |
| `make migrate` | Apply DB migrations (alembic upgrade head) |
| `make seed` | Seed pilot callers + reference catalogs |
| `make dev` | Install + infra + migrate + seed + run everything via honcho |
| `make up` | Start all containers (infra + apps) |
| `make down` | Stop everything (infra + apps + optional livekit) |
| `make rebuild` | Stop + rebuild + redeploy all containers (use after code changes) |
| `make health` | Probe every service /health endpoint |
| `make live-logs` | Follow token-service + agent-worker logs during a call |
| `make test` | Run the offline test suite across packages/services |

## Docker Compose

```bash
# Infrastructure only (postgres, redis, qdrant, minio, otel-collector)
docker compose -f infra/docker-compose/docker-compose.yml up -d

# Infrastructure + all app services (context, knowledge, decision, policy,
# execution, notification, token-service, business-api, agent-worker)
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --build

# Also start self-hosted LiveKit
docker compose -f infra/docker-compose/docker-compose.yml --profile self-hosted-livekit up -d

# Stop everything
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml --profile self-hosted-livekit down --remove-orphans
```

## Docker Logs

```bash
# Follow specific service logs
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml logs -f --tail=100 <service-name>

# Common services: token-service, agent-worker, context-service,
#   decision-service, execution-service, policy-service,
#   knowledge-service, notification-service, business-api

# Follow agent-worker + token-service during a browser call
make live-logs

# All services
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml logs -f
```

## Supervisor Dashboard (Frontend)

```bash
# Start the Vite dev server (http://localhost:5173)
cd apps/supervisor-dashboard && npm run dev

# Production build
cd apps/supervisor-dashboard && npm run build

# TypeScript type checking
cd apps/supervisor-dashboard && npm run typecheck
```

## Client Widget (Frontend)

```bash
cd apps/client-widget && npm install
```

```bash
cd apps/client-widget && npm run dev
```


## Individual Services (via honcho)

Services are defined in the Procfile and managed by honcho:

```bash
# Start all services in one terminal
honcho start

# Start a specific service alone (port overrides via env)
cd services/context-service && uvicorn context_service.main:app --port 8101 --reload
cd services/decision-service && uvicorn decision_service.main:app --port 8103 --reload
cd services/policy-service && uvicorn policy_service.main:app --port 8104 --reload
cd services/execution-service && uvicorn execution_service.main:app --port 8105 --reload
cd services/notification-service && uvicorn notification_service.main:app --port 8108 --reload

# Token service
cd apps/token-service && uvicorn token_service.main:app --port 8107 --reload

# Business API
cd apps/business-api && uvicorn business_api.main:app --port 8100 --reload

# Agent-worker
cd apps/agent-worker && uvicorn server:app --port 8106 --reload
```

## Python Setup

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate
# Linux/Mac:  source .venv/bin/activate
# Windows:    .venv\Scripts\activate

# Install package in editable mode
pip install -e ./packages/domain-core
pip install -e ./packages/persistence
pip install -e ./packages/audit-trail
pip install -e ./packages/pii-shield
pip install -e ./packages/observability-kit
pip install -e ./packages/service-auth
pip install -e ./packages/cache
pip install -e ./packages/object-storage
pip install -e ./packages/notification-client
pip install -e ./packages/integration-adapters

# Install services + MCP + agent-worker
pip install -e ./services/context-service
pip install -e ./services/knowledge-service
pip install -e ./services/decision-service
pip install -e ./services/policy-service
pip install -e ./services/execution-service
pip install -e ./services/notification-service
pip install -e ./apps/token-service
pip install -e ./apps/business-api
pip install -e ./mcp-servers/ai-knowledge-rag
pip install -e ./mcp-servers/ticketing-glpi
pip install -e ./mcp-servers/messaging-gateway
pip install -e ./apps/agent-worker
```

## Database

```bash
# Create database (if not exists)
make create-db

# Run migrations
make migrate

# Seed data
make seed

# Direct psql access
docker compose -f infra/docker-compose/docker-compose.yml exec postgres psql -U telecom -d telecom
```

## System Architecture & Ports

| Service | Port | Description |
|---------|------|-------------|
| `business-api` | 8100 | Backend for supervisor dashboard |
| `context-service` | 8101 | Customer context & CRM data |
| `knowledge-service` | 8102 | RAG knowledge base |
| `decision-service` | 8103 | Agent decision engine |
| `policy-service` | 8104 | Business policy evaluation |
| `execution-service` | 8105 | Action execution & projections |
| `agent-worker` | 8106 | LiveKit voice agent |
| `token-service` | 8107 | JWT token generation for LiveKit |
| `notification-service` | 8108 | Notifications |
| `supervisor-dashboard` | 5173 (Vite) | Web dashboard |
| `postgres` | 5432 | Primary database |
| `redis` | 6379 | Cache & session store |
| `qdrant` | 6333 | Vector store |
| `minio` | 9000/9001 | Object storage |
| `otel-collector` | 4317/4318 | OpenTelemetry traces |

## Quick Troubleshooting

```bash
# Reset everything (destroys containers, keeps data)
make down
make up
make health

# Full rebuild after code changes
make rebuild

# Reinstall frontends for current OS
make frontends-clean

# Check container status
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml ps

# View logs for a specific service
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml logs -f --tail=50 agent-worker
```


# agent_worker logs
```bash
docker logs docker-compose-agent-worker-1 | grep tts_characters_count
docker compose logs agent-worker | grep caller_transcript
```
