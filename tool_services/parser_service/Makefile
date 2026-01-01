.PHONY: help dev up down logs ps build health migrate

help:
	@echo "parser_service - commands:"
	@echo "  make dev      Start dev stack (docker compose up -d)"
	@echo "  make logs     Tail logs"
	@echo "  make down     Stop stack"
	@echo "  make health   Curl readiness"
	@echo "  make migrate  Run alembic migrations"

dev up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

build:
	docker compose build --no-cache

health:
	@curl -fsS http://localhost:8031/health/ready && echo ""

migrate:
	docker compose run --rm migrations alembic upgrade head

