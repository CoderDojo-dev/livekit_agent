# Telecom AI Voice Agent — one place to install, run, verify (diagnostic #1, #7, #9).
SHELL := /bin/bash
PACKAGES := domain-core persistence audit-trail pii-shield observability-kit service-auth cache object-storage notification-client integration-adapters
SERVICES := services/context-service services/knowledge-service services/decision-service services/policy-service services/execution-service services/notification-service apps/token-service apps/business-api
MCP := mcp-servers/ai-knowledge-rag mcp-servers/ticketing-glpi mcp-servers/messaging-gateway
INFRA := infra/docker-compose/docker-compose.yml
APPS := infra/docker-compose/docker-compose.apps.yml
export DATABASE_URL ?= postgresql+psycopg://telecom:telecom@localhost:15432/telecom

.DEFAULT_GOAL := help
.PHONY: help install infra infra-livekit migrate seed dev up down health test frontends

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:  ## Install packages (correct order) + services + MCP + honcho (editable)
	pip install honcho
	pip install $(addprefix -e ./packages/,$(PACKAGES))
	pip install $(addprefix -e ./,$(SERVICES)) $(addprefix -e ./,$(MCP)) -e ./apps/agent-worker
	@echo "→ frontends: run 'make frontends'"

frontends:  ## npm install both web apps
	cd apps/supervisor-dashboard && npm install
	cd apps/client-widget && npm install

infra:  ## Start infrastructure containers (postgres/redis/qdrant/minio/otel)
	docker compose -f $(INFRA) up -d

infra-livekit:  ## Also start the self-hosted LiveKit server (SKIP if using LiveKit Cloud)
	docker compose -f $(INFRA) --profile self-hosted-livekit up -d

migrate:  ## Apply DB migrations (alembic upgrade head)
	cd packages/persistence && alembic upgrade head

seed:  ## Seed pilot callers + reference catalogs
	cd packages/persistence && python -m seed.seed_pilot && python -m seed.seed_reference

dev: install infra migrate seed  ## ONE COMMAND: install + infra + migrate + seed, then run everything (honcho)
	@echo "Starting all app processes via honcho (Ctrl-C to stop all)…"
	honcho start

up:  ## Full container path: infra + every app service via compose (builds images)
	docker compose -f $(INFRA) -f $(APPS) up -d --build

down:  ## Stop everything (infra + apps + optional livekit)
	docker compose -f $(INFRA) -f $(APPS) --profile self-hosted-livekit down

health:  ## Probe every service /health
	python scripts/health_check.py

test:  ## Run the offline test suite across packages/services
	python scripts/run_tests.py