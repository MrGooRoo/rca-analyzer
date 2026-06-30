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

# Не запускаем uvicorn от root: при компрометации контейнера атакующий
# получает только права непривилегированного пользователя.
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

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

RUN useradd --create-home --shell /bin/bash --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# HF_HOME — кэш моделей монтируется как volume (переживает пересборку)
ENV HF_HOME=/app/.cache/huggingface

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- dev (с dev-зависимостями) ----
FROM base AS dev
RUN pip install -e ".[dev]"
COPY . .

RUN useradd --create-home --shell /bin/bash --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- dev + HF-эмбеддинги ----
FROM dev AS dev-embeddings
USER root
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -e ".[embeddings]"
RUN chown -R appuser:appuser /app
USER appuser
ENV HF_HOME=/app/.cache/huggingface
