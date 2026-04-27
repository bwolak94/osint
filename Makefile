.PHONY: dev prod test test-backend test-frontend lint migrate seed reset-dev gen-types shell logs clean

dev:
	docker compose --profile dev up --build

prod:
	docker compose -f docker-compose.yml up --build -d

test: test-backend test-frontend

test-backend:
	docker compose exec api pytest --tb=short -q

test-frontend:
	docker compose exec frontend npm run test

lint:
	docker compose exec api ruff check src/
	docker compose exec frontend npm run lint

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python -m src.scripts.seed_admin

gen-types:
	docker compose exec frontend npm run gen:api-types

reset-dev:
	@echo "This will stop all containers and wipe all volumes (DB, Redis, Neo4j, MinIO)."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v --remove-orphans
	docker compose --profile dev up --build -d
	sleep 5
	docker compose exec api python -m src.scripts.seed_admin

shell:
	docker compose exec api /bin/bash

logs:
	docker compose logs -f --tail=100

clean:
	@echo "This will remove all containers, volumes, and orphans."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v --remove-orphans
