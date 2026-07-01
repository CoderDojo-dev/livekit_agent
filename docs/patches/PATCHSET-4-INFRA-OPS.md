# Patch-Set 4 (final) — Infra, storage & ops (tester report)

Closes the remaining infrastructure items. The storage/cache/RAG code is **gated + no-op by default**
(so dev/CI is unchanged); the ops artifacts are standard, validated deployment files.

## Report items closed (9)
| # | Item | What changed |
|---|---|---|
| 6 🟠 | No Qdrant retriever | `knowledge_service.retriever`: `QdrantRetriever` + `get_retriever()` — uses Qdrant + OpenAI embeddings when `QDRANT_URL` is set, **falls back to the lexical retriever** otherwise. `main.py` uses the factory |
| 7 🟠 | No Redis cache | new `packages/cache`: `get_cache()` → `RedisCache` when `REDIS_URL` set, else `NullCache` (reads miss, writes no-op). Wired into `context-service` resolve (Customer-360 read cache) |
| 8 🟠 | No object storage | new `packages/object-storage`: `get_store()` → `MinioStore` when `MINIO_ENDPOINT` set, else `NullStore`. The retention job now purges recording blobs (gated) before clearing the pointer |
| 30 🟡 | No Dockerfiles | **11 Dockerfiles** (every service/app/MCP + the worker) — monorepo pattern (build from repo root; shared packages layer-cached), non-root user, healthcheck; plus `.dockerignore` |
| 18 🟠 | No API gateway | `deploy/gateway/nginx.conf` + compose: only `/token/` and `/api/` are public; the 6 internal services stay private behind `INTERNAL_API_KEY` |
| 19 🟠 | No CI/CD | `.github/workflows/ci.yml`: ruff + the offline test suite across packages/services, a Postgres job that runs `alembic upgrade head` + seeds, and an audit-chain verify hook |
| 20 🟡 | No Helm charts | `deploy/helm/telecom-agent`: Chart + values (one entry per deployable) + a templated Deployment/Service per service and the worker; secrets via `telecom-secrets` |
| 22 🟡 | No backup/restore | `deploy/backup/{backup.sh,restore.sh}` (pg_dump/pg_restore, 14-day retention) + `verify_audit_chain.py` |
| 23 🟡 | No secrets management | `deploy/secrets/README.md`: k8s Secret / SOPS / External-Secrets + Vault; compose reads `${...}`; rotation guidance |

## Why it's safe
Every new dependency is **optional and gated**: `REDIS_URL` / `MINIO_ENDPOINT` / `QDRANT_URL` unset →
the code returns the Null/lexical implementation and behaves exactly as before. The libraries
(`redis`, `minio`, `qdrant-client`) are declared but import-guarded, so a missing lib degrades
gracefully instead of crashing.

## Turn it on (staging, in `.env`)
```bash
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333   OPENAI_API_KEY=...   # embeddings for RAG
MINIO_ENDPOINT=minio:9000  MINIO_ROOT_USER=...  MINIO_ROOT_PASSWORD=...
```
```bash
# build + deploy
docker build -f apps/business-api/Dockerfile -t registry.local/business-api:0.1.0 .   # (repeat per service)
helm upgrade --install telecom deploy/helm/telecom-agent
docker compose -f infra/docker-compose/docker-compose.yml -f deploy/gateway/docker-compose.gateway.yml up -d gateway
```

## Verification (offline)
cache **2** · object-storage **2** · knowledge **3** (lexical fallback) — and the **full platform
sweep is 70 tests green**. YAML (CI, Helm Chart/values, gateway) parses; `bash -n` clean on the backup
scripts; `verify_audit_chain.py` no-ops safely without `DATABASE_URL`; 11 Dockerfiles well-formed.
Live paths (Qdrant/Redis/MinIO/nginx/Helm) are exercised on the real stack.
