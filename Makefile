.PHONY: up down run lint fmt test test-all test-int sync migrate downgrade revision psql

# Зависимости окружения: postgres + redis
up:
	docker compose up -d db redis

down:
	docker compose down

sync:
	uv sync --all-groups

run:
	uv run uvicorn adlex.main:create_app --factory --reload

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src

fmt:
	uv run ruff format .
	uv run ruff check . --fix

# Быстрые тесты: без контейнеров и без платных прогонов LLM
test:
	uv run pytest -q -m "not integration and not evals"

test-all:
	uv run pytest -q

# Тесты, которым нужна поднятая база (make up сначала)
test-int:
	uv run pytest -q -m integration

# Схема базы меняется только миграциями — никаких ручных ALTER TABLE
migrate:
	uv run alembic upgrade head

downgrade:
	uv run alembic downgrade -1

# make revision m="add landing tables"
revision:
	uv run alembic revision --autogenerate -m "$(m)"

psql:
	docker compose exec db psql -U adlex -d adlex
