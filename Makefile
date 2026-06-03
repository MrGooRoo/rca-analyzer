.PHONY: install dev test lint typecheck run docker-up docker-down

install:
	pip install -e '.[dev]'

dev:
	uvicorn src.api.app:app --reload --port 8000

test:
	pytest -v

test-contracts:
	pytest tests/contracts/ -v

test-unit:
	pytest tests/unit/ -v

test-api:
	pytest tests/api/ -v

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

docker-up:
	docker compose up --build

docker-down:
	docker compose down

logs:
	docker compose logs -f api
