.PHONY: install dev test lint typecheck run docker-up docker-down migrate

install:
	pip install -e '.[dev]'

dev:
	uvicorn src.api.app:app --reload --port 8000

test:
	pytest -v

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

migrate:
	docker compose exec api alembic upgrade head

migrate-new:
	docker compose exec api alembic revision --autogenerate -m "$(name)"

createsuperuser:
	docker compose exec -it api python scripts/createsuperuser.py

setrole:
	docker compose exec -it api python scripts/set_role.py

admin-users:
	docker compose exec api python scripts/set_role.py --list
