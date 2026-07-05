.PHONY: install check lint typecheck test migrate up down

install:
	pip install -e ".[dev]"

lint:
	ruff check app tests
	ruff format --check app tests

typecheck:
	mypy app

test:
	pytest

check: lint typecheck test

migrate:
	alembic upgrade head

up:
	docker compose up -d

down:
	docker compose down
