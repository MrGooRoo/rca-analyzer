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

# ---- продакшн + HF-эмбеддинги ----
FROM base AS prod-embeddings
# torch CPU-only (значительно меньше образ, чем с CUDA)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -e ".[embeddings]"
COPY src/       ./src/
COPY configs/   ./configs/
COPY alembic/   ./alembic/
COPY alembic.ini ./

# HF_HOME — кэш моделей монтируется как volume (переживает пересборку)
ENV HF_HOME=/app/.cache/huggingface

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- dev (с dev-зависимостями) ----
FROM base AS dev
RUN pip install -e ".[dev]"
COPY . .
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- dev + HF-эмбеддинги ----
FROM dev AS dev-embeddings
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -e ".[embeddings]"
ENV HF_HOME=/app/.cache/huggingface
