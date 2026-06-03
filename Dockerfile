# ---- базовый образ ----
FROM python:3.11-slim AS base
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Устанавливаем зависимости напрямую — без editable install
RUN pip install --upgrade pip && pip install \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.29" \
    "httpx>=0.27" \
    "pydantic>=2.7" \
    "jinja2>=3.1" \
    "tenacity>=8.3" \
    "sqlalchemy[asyncio]>=2.0" \
    "asyncpg>=0.29" \
    "alembic>=1.13"

# ---- продакшн ----
FROM base AS prod
COPY src/       ./src/
COPY configs/   ./configs/
COPY alembic/   ./alembic/
COPY alembic.ini ./

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- dev (с dev-зависимостями) ----
FROM base AS dev
RUN pip install \
    "pytest>=8.2" \
    "pytest-asyncio>=0.23" \
    "respx>=0.21" \
    "ruff>=0.4" \
    "mypy>=1.10" \
    "aiosqlite>=0.20"
COPY . .
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
