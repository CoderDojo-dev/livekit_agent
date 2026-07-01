COMPOSE = docker compose -f infra/docker-compose/docker-compose.yml

.PHONY: up down logs ps fmt

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

fmt:
	ruff check --fix . || true