# Running the platform

Two ways: **honcho** (one terminal, native processes — best for development) or **docker compose**
(containers — closest to prod). Both replace the old "20 terminals" flow (diagnostic #1).

## Prerequisites
Docker + Docker Compose, Python 3.12, Node ≥ 20. Copy the env template: `cp .env.example .env` and fill
in the `⚠` values (LiveKit + provider keys). **`.env.example` at the repo root is the single source of
truth** — ignore any older `deploy/secrets/.env.example`.

## Option A — honcho (recommended for dev)
```bash
make dev
```
That's it. `make dev` = `install` (packages in the correct order + services + MCP + honcho) → `infra`
(containers) → `migrate` → `seed` → **`honcho start`** (every service, MCP, the worker, and both
frontends in one terminal). Stop with Ctrl-C.

First time only, also install the web apps: `make frontends`.

## Option B — everything in containers
```bash
make up        # infra + all app services (builds images from the per-service Dockerfiles)
make health    # probe every /health
make down
```

## Install order (was undocumented — diagnostic #7)
`make install` encodes it: the ten shared packages first (`domain-core → persistence → audit-trail →
…`), then the services, MCP servers, and the worker. You never need to remember it; but if you install
by hand, shared packages come before any service.

## LiveKit: Cloud vs self-hosted (diagnostic #9)
The self-hosted `livekit-server` container is now **opt-in** behind a compose profile. If your `.env`
points to LiveKit Cloud (`wss://…livekit.cloud`), do nothing — it won't start. To run LiveKit locally:
```bash
make infra-livekit
```

## Handy targets
`make help` lists them. Common: `make health`, `make test`, `make migrate`, `make down`.

## Console scripts (diagnostic #2, #8)
After `make install`, each service has a short command (from `[project.scripts]`): `context-service`,
`policy-service`, `business-api`, `ticketing-glpi`, … — no more full `uvicorn …:app --port` incantation.