 # Telecom AI Voice Agent — one place to install, run, verify (diagnostic #1, #7, #9).
# NOTE: Requires `make` + bash (WSL/Git Bash on Windows).
#       Windows PowerShell users: run `.\start.ps1 up` / `.\start.ps1 rebuild` instead.
SHELL := /bin/bash
PACKAGES := domain-core persistence audit-trail pii-shield observability-kit service-auth cache object-storage notification-client integration-adapters
SERVICES := services/context-service services/knowledge-service services/decision-service services/policy-service services/execution-service services/notification-service apps/token-service apps/business-api
MCP := mcp-servers/ai-knowledge-rag mcp-servers/ticketing-glpi mcp-servers/messaging-gateway
INFRA := infra/docker-compose/docker-compose.yml
APPS := infra/docker-compose/docker-compose.apps.yml
export DATABASE_URL ?= postgresql+psycopg://telecom:telecom@localhost:5432/telecom
PYTHON := "$(shell if [ -x .venv/bin/python ]; then echo $(CURDIR)/.venv/bin/python; elif [ -x .venv/Scripts/python.exe ]; then echo $(CURDIR)/.venv/Scripts/python.exe; elif command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi)"
PIP := $(PYTHON) -m pip
UVICORN := $(PYTHON) -m uvicorn
HONCHO := $(shell if [ -x .venv/bin/honcho ]; then echo $(CURDIR)/.venv/bin/honcho; elif [ -x .venv/Scripts/honcho.exe ]; then echo $(CURDIR)/.venv/Scripts/honcho.exe; else echo honcho; fi)
DOCKER := $(shell if command -v docker >/dev/null 2>&1; then echo docker; elif [ -x "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" ]; then echo "'/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe'"; elif [ -x "/mnt/c/Program Files/Docker/Docker/resources/bin/docker" ]; then echo "'/mnt/c/Program Files/Docker/Docker/resources/bin/docker'"; elif [ -x "/usr/bin/docker" ]; then echo docker; else echo docker; fi)

.DEFAULT_GOAL := help
.PHONY: help install infra infra-livekit create-db migrate seed dev up down rebuild health live-logs test frontends frontends-clean frontend frontend-portal frontend-admin frontend-stop

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:  ## Install packages (correct order) + services + MCP + honcho (editable)
	$(PIP) install honcho
	$(PIP) uninstall -y knowledge-glpi-mcp 2>/dev/null || true
	$(PIP) install $(addprefix -e ./packages/,$(PACKAGES))
	$(PIP) install $(addprefix -e ./,$(SERVICES)) $(addprefix -e ./,$(MCP)) -e ./apps/agent-worker
	@echo "→ frontends: run 'make frontends'"

frontends:  ## npm install the shipped web apps (admin dashboard + customer portal)
	cd Frontend/admin_dashboard && npm install
	cd Frontend/customer_portal && npm install
	cd apps/client-widget && npm install

frontends-clean:  ## Reinstall frontend deps for the current OS (fixes Rollup optional deps)
	cd Frontend/admin_dashboard && rm -rf node_modules && npm install
	cd Frontend/customer_portal && rm -rf node_modules && npm install
	cd apps/client-widget && rm -rf node_modules && npm install

# Frontend dev servers: the shipped node_modules hold WINDOWS native bindings
# (rolldown/esbuild), so npm must be the Windows one. When make runs inside WSL
# (the only make on this machine), call it through cmd.exe; otherwise use npm directly.
ifeq ($(wildcard /mnt/c/*),)
FRONTEND_ADMIN_CMD := cd Frontend/admin_dashboard && npm run dev -- --port 8081 --strictPort
FRONTEND_PORTAL_CMD := cd Frontend/customer_portal && npm run dev -- --port 8080 --strictPort
else
WIN_CURDIR := $(shell wslpath -w "$(CURDIR)")
FRONTEND_ADMIN_CMD := cmd.exe /c "cd /d $(WIN_CURDIR)\Frontend\admin_dashboard && npm run dev -- --port 8081 --strictPort"
FRONTEND_PORTAL_CMD := cmd.exe /c "cd /d $(WIN_CURDIR)\Frontend\customer_portal && npm run dev -- --port 8080 --strictPort"
endif

frontend: frontend-stop  ## Run BOTH frontends: admin dashboard (http://localhost:8081) + customer portal (http://localhost:8080). Ctrl-C stops both. Frees ports 8080/8081 first.
	@echo "→ admin dashboard   http://localhost:8081  (Frontend/admin_dashboard)"
	@echo "→ customer portal   http://localhost:8080  (Frontend/customer_portal)"
	@trap 'kill 0' INT TERM EXIT; \
	($(FRONTEND_ADMIN_CMD)) & \
	($(FRONTEND_PORTAL_CMD)) & \
	wait

frontend-portal:  ## Run the customer portal (client) frontend on http://localhost:8080
	@$(FRONTEND_PORTAL_CMD)

frontend-admin:  ## Run the admin dashboard frontend on http://localhost:8081
	@$(FRONTEND_ADMIN_CMD)

frontend-stop:  ## Stop both frontend dev servers (kills whatever listens on :8080/:8081)
	@powershell.exe -NoProfile -Command 'Get-NetTCPConnection -State Listen -LocalPort 8080,8081 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $$_.OwningProcess -Force -ErrorAction SilentlyContinue }; exit 0'
	@echo "→ frontend dev servers stopped (ports 8080/8081)"

infra:  ## Start infrastructure containers (postgres/redis/qdrant/minio/otel)
	$(DOCKER) compose -f $(INFRA) up -d

infra-livekit:  ## Also start the self-hosted LiveKit server (SKIP if using LiveKit Cloud)
	$(DOCKER) compose -f $(INFRA) --profile self-hosted-livekit up -d

create-db:  ## Create the telecom database in Postgres if it does not exist yet
	$(DOCKER) compose -f $(INFRA) exec -T postgres psql -U "$${POSTGRES_USER:-telecom}" -d postgres -c "CREATE DATABASE \"$${POSTGRES_DB:-telecom}\" OWNER \"$${POSTGRES_USER:-telecom}\";" 2>/dev/null || true

migrate: create-db  ## Apply DB migrations (alembic upgrade head)
	cd packages/persistence && $(PYTHON) -m alembic upgrade head

seed:  ## Seed pilot callers + reference catalogs + the logins P0-1 made mandatory
	cd packages/persistence && $(PYTHON) -m seed.seed_pilot && $(PYTHON) -m seed.seed_reference && $(PYTHON) -m seed.seed_auth_credentials
	$(PYTHON) -m business_api.seed_admin

dev: install infra migrate seed  ## ONE COMMAND: install + infra + migrate + seed, then run everything (honcho)
	@echo "Starting all app processes via honcho (Ctrl-C to stop all)…"
	$(HONCHO) start

up:  ## Start all containers (infra + apps) — use 'rebuild' after code changes
	$(DOCKER) compose -f $(INFRA) -f $(APPS) up -d --remove-orphans

down:  ## Stop everything (infra + apps + optional livekit)
	$(DOCKER) compose -f $(INFRA) -f $(APPS) --profile self-hosted-livekit down --remove-orphans

rebuild: down  ## Stop + rebuild + redeploy all containers (use after code changes)
	$(DOCKER) compose -f $(INFRA) -f $(APPS) up -d --build --remove-orphans
	$(DOCKER) builder prune -f
	@echo "→ All images rebuilt & containers running. Run 'make health' to verify."

health:  ## Probe every service /health
	$(PYTHON) scripts/health_check.py

live-logs:  ## Follow token-service + agent-worker logs during a browser call
	$(DOCKER) compose -f $(INFRA) -f $(APPS) logs -f --tail=120 token-service agent-worker

test:  ## Run the offline test suite across packages/services
	$(PYTHON) scripts/run_tests.py
