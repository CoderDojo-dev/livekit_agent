 # Telecom AI Voice Agent — one place to install, run, verify (diagnostic #1, #7, #9).
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

.DEFAULT_GOAL := help
.PHONY: help install infra infra-livekit create-db migrate seed dev up down rebuild health live-logs test frontends frontends-clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:  ## Install packages (correct order) + services + MCP + honcho (editable)
	$(PIP) install honcho
	$(PIP) install $(addprefix -e ./packages/,$(PACKAGES))
	$(PIP) install $(addprefix -e ./,$(SERVICES)) $(addprefix -e ./,$(MCP)) -e ./apps/agent-worker
	@echo "→ frontends: run 'make frontends'"

frontends:  ## npm install both web apps
	cd apps/supervisor-dashboard && npm install
	cd apps/client-widget && npm install

frontends-clean:  ## Reinstall frontend deps for the current OS (fixes Rollup optional deps)
	cd apps/supervisor-dashboard && rm -rf node_modules && npm install
	cd apps/client-widget && rm -rf node_modules && npm install

infra:  ## Start infrastructure containers (postgres/redis/qdrant/minio/otel)
	docker compose -f $(INFRA) up -d

infra-livekit:  ## Also start the self-hosted LiveKit server (SKIP if using LiveKit Cloud)
	docker compose -f $(INFRA) --profile self-hosted-livekit up -d

create-db:  ## Create the telecom database in Postgres if it does not exist yet
	docker compose -f $(INFRA) exec -T postgres psql -U "$${POSTGRES_USER:-telecom}" -d postgres -c "CREATE DATABASE \"$${POSTGRES_DB:-telecom}\" OWNER \"$${POSTGRES_USER:-telecom}\";" 2>/dev/null || true

migrate: create-db  ## Apply DB migrations (alembic upgrade head)
	cd packages/persistence && $(PYTHON) -m alembic upgrade head

seed:  ## Seed pilot callers + reference catalogs
	cd packages/persistence && $(PYTHON) -m seed.seed_pilot && $(PYTHON) -m seed.seed_reference

dev: install infra migrate seed  ## ONE COMMAND: install + infra + migrate + seed, then run everything (honcho)
	@echo "Starting all app processes via honcho (Ctrl-C to stop all)…"
	$(HONCHO) start

up:  ## Full container path: infra + every app service via compose (builds images)
	docker compose -f $(INFRA) -f $(APPS) up -d --build

down:  ## Stop everything (infra + apps + optional livekit)
	docker compose -f $(INFRA) -f $(APPS) --profile self-hosted-livekit down

rebuild: down  ## Stop + rebuild + redeploy all containers (use after code changes)
	docker compose -f $(INFRA) -f $(APPS) up -d --build
	@echo "→ All images rebuilt & containers running. Run 'make health' to verify."

health:  ## Probe every service /health
	$(PYTHON) scripts/health_check.py

live-logs:  ## Follow token-service + agent-worker logs during a browser call
	docker compose -f $(INFRA) -f $(APPS) logs -f --tail=120 token-service agent-worker

test:  ## Run the offline test suite across packages/services
	$(PYTHON) scripts/run_tests.py
