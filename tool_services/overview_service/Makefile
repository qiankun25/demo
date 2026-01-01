.PHONY: help dev up down logs ps build health

help:
	@echo "overview_service - commands:"
	@echo "  make dev      Start dev stack"
	@echo "  make logs     Tail logs"
	@echo "  make down     Stop stack"
	@echo "  make health   Curl readiness"

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
	@curl -fsS http://localhost:8040/health/ready && echo ""

