"""
Клиент эмбеддингов OpenRouter (POST /api/v1/embeddings, OpenAI-совместимый).

Особенности:
- Асинхронный embed() — репозиторий умеет await'ить awaitable-результат.
- Запрашиваем dimensions=384 (Matryoshka-модели OpenAI это поддерживают);
  если модель/провайдер не принимает параметр — повторяем запрос без него
  и приводим вектор к 384 (усечение/дополнение нулями) с L2-нормализацией.
- Retry с экспоненциальным backoff на 429/5xx/сетевые ошибки.
- Все ошибки оборачиваются в EmbeddingServiceError — репозиторий по ней
  откатывается на локальный LocalHashEmbeddingService.

Переменные окружения:
    EMBEDDINGS_PROVIDER=openrouter      — включить этот провайдер (фабрика)
    OPENROUTER_EMBEDDING_MODEL          — по умолчанию openai/text-embedding-3-small
    OPENROUTER_API_KEY                  — общий ключ OpenRouter (обязателен)
    OPENROUTER_EMBEDDING_TIMEOUT        — секунды, по умолчанию 30
    OPENROUTER_EMBEDDING_MAX_RETRIES    — по умолчанию 3
"""

from __future__ import annotations

import asyncio
import logging
import math
import os

import httpx

from src.services.embedding_service import (
    EMBEDDING_DIMENSION,
    EmbeddingServiceError,
)

logger = logging.getLogger(__name__)

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"

DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"

# Максимум символов текста на один запрос: страховка от слишком больших
# DOCX-описаний (у embedding-моделей контекст ~8K токенов).
_MAX_INPUT_CHARS = 16_000

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class OpenRouterEmbeddingService:
    """
    Embedding-провайдер через OpenRouter.

    Контракт совпадает с LocalHashEmbeddingService (Protocol EmbeddingService),
    но embed() — корутина. Вектор всегда длины EMBEDDING_DIMENSION и нормализован.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model_name = model or os.getenv("OPENROUTER_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.dimension = EMBEDDING_DIMENSION
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.timeout = timeout or float(os.getenv("OPENROUTER_EMBEDDING_TIMEOUT", "30"))
        self.max_retries = max_retries or int(os.getenv("OPENROUTER_EMBEDDING_MAX_RETRIES", "3"))
        self.base_url = base_url or OPENROUTER_EMBEDDINGS_URL

        # Поддерживает ли модель параметр dimensions — выясняем по первому 4xx.
        self._supports_dimensions: bool = True

    async def embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise EmbeddingServiceError("OPENROUTER_API_KEY не задан — embeddings недоступны")

        prepared = (text or "").strip()[:_MAX_INPUT_CHARS]
        if not prepared:
            return [0.0] * self.dimension

        raw_vector = await self._request_embedding(prepared)
        return self._fit_dimension(raw_vector)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    async def _request_embedding(self, text: str) -> list[float]:
        payload: dict = {"model": self.model_name, "input": text}
        if self._supports_dimensions:
            payload["dimensions"] = self.dimension

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await client.post(
                        self.base_url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com/MrGooRoo/rca-analyzer",
                            "X-Title": "RCA Analyzer",
                        },
                    )
                except httpx.HTTPError as exc:
                    last_error = exc
                    logger.warning(
                        "[Embeddings] сетевая ошибка (попытка %d/%d): %s",
                        attempt, self.max_retries, exc,
                    )
                    await self._backoff(attempt)
                    continue

                if response.status_code == 200:
                    return self._parse_response(response)

                # Модель не принимает dimensions → повторить без параметра.
                if (
                    response.status_code in (400, 404, 422)
                    and "dimensions" in payload
                ):
                    logger.info(
                        "[Embeddings] модель %s отклонила dimensions=%d (HTTP %d), "
                        "повторяю без параметра",
                        self.model_name, self.dimension, response.status_code,
                    )
                    self._supports_dimensions = False
                    payload.pop("dimensions", None)
                    continue

                if response.status_code in _RETRYABLE_STATUS:
                    last_error = EmbeddingServiceError(
                        f"OpenRouter embeddings HTTP {response.status_code}: {response.text[:300]}"
                    )
                    logger.warning(
                        "[Embeddings] HTTP %d (попытка %d/%d)",
                        response.status_code, attempt, self.max_retries,
                    )
                    await self._backoff(attempt)
                    continue

                raise EmbeddingServiceError(
                    f"OpenRouter embeddings HTTP {response.status_code}: {response.text[:300]}"
                )

        raise EmbeddingServiceError(
            f"OpenRouter embeddings: исчерпаны попытки ({self.max_retries}); "
            f"последняя ошибка: {last_error}"
        )

    @staticmethod
    def _parse_response(response: httpx.Response) -> list[float]:
        try:
            data = response.json()
            vector = data["data"][0]["embedding"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise EmbeddingServiceError(
                f"OpenRouter embeddings: неожиданный формат ответа: {exc}"
            ) from exc
        if not isinstance(vector, list) or not vector:
            raise EmbeddingServiceError("OpenRouter embeddings: пустой вектор в ответе")
        return [float(v) for v in vector]

    @staticmethod
    async def _backoff(attempt: int) -> None:
        await asyncio.sleep(min(2 ** (attempt - 1), 8))

    # ------------------------------------------------------------------
    # Приведение размерности
    # ------------------------------------------------------------------

    def _fit_dimension(self, vector: list[float]) -> list[float]:
        """
        Привести вектор к EMBEDDING_DIMENSION и L2-нормализовать.

        Для Matryoshka-моделей (text-embedding-3-*) усечение первых N компонент —
        штатный способ уменьшения размерности. Для прочих моделей это
        аппроксимация, но косинусная близость сохраняется достаточно хорошо.
        """
        if len(vector) > self.dimension:
            vector = vector[: self.dimension]
        elif len(vector) < self.dimension:
            vector = vector + [0.0] * (self.dimension - len(vector))

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]
