# ---- базовый образ ----
FROM python:3.11-slim AS base
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Копируем манифест зависимостей — кэш слоя не сбрасывается при изменении кода
COPY pyproject.toml ./
# Заглушка для hatchling (требует src/__init__.py на этапе metadata)
RUN mkdir -p src && touch src/__init__.py

# Устанавливаем все зависимости прямо из pyproject.toml —
# больше не нужно дублировать список в Dockerfile
RUN pip install --upgrade pip && pip install -e .

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
RUN pip install -e ".[dev]"
COPY . .
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
