"""
Тесты OpenRouterEmbeddingService: HTTP-мокинг через respx,
приведение размерности, retry, фолбэк в репозитории.
"""

from __future__ import annotations

import math

import httpx
import pytest
import respx

from src.integrations.llm.openrouter_embeddings import (
    OPENROUTER_EMBEDDINGS_URL,
    OpenRouterEmbeddingService,
)
from src.services.embedding_service import (
    EMBEDDING_DIMENSION,
    EmbeddingServiceError,
)


def _make_service(**kwargs) -> OpenRouterEmbeddingService:
    defaults = dict(
        model="openai/text-embedding-3-small",
        api_key="test-key",
        timeout=5,
        max_retries=2,
    )
    defaults.update(kwargs)
    return OpenRouterEmbeddingService(**defaults)


def _embedding_response(vector: list[float]) -> dict:
    return {"data": [{"embedding": vector, "index": 0}], "model": "test"}


# ---------------------------------------------------------------------------
# Успешные запросы
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_embed_returns_normalized_vector_of_target_dimension() -> None:
    raw = [1.0] * EMBEDDING_DIMENSION
    respx.post(OPENROUTER_EMBEDDINGS_URL).mock(
        return_value=httpx.Response(200, json=_embedding_response(raw))
    )

    service = _make_service()
    vector = await service.embed("Падение с лестницы")

    assert len(vector) == EMBEDDING_DIMENSION
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == pytest.approx(1.0, abs=1e-9)


@pytest.mark.asyncio
@respx.mock
async def test_embed_truncates_larger_vectors() -> None:
    raw = [0.5] * 1536  # модель вернула полную размерность
    respx.post(OPENROUTER_EMBEDDINGS_URL).mock(
        return_value=httpx.Response(200, json=_embedding_response(raw))
    )

    service = _make_service()
    vector = await service.embed("текст")
    assert len(vector) == EMBEDDING_DIMENSION


@pytest.mark.asyncio
@respx.mock
async def test_embed_pads_smaller_vectors() -> None:
    raw = [0.7] * 256
    respx.post(OPENROUTER_EMBEDDINGS_URL).mock(
        return_value=httpx.Response(200, json=_embedding_response(raw))
    )

    service = _make_service()
    vector = await service.embed("текст")
    assert len(vector) == EMBEDDING_DIMENSION
    assert vector[300] == 0.0  # дополнено нулями


@pytest.mark.asyncio
@respx.mock
async def test_embed_sends_dimensions_param() -> None:
    route = respx.post(OPENROUTER_EMBEDDINGS_URL).mock(
        return_value=httpx.Response(200, json=_embedding_response([1.0] * EMBEDDING_DIMENSION))
    )

    service = _make_service()
    await service.embed("текст")

    import json
    payload = json.loads(route.calls[0].request.content)
    assert payload["dimensions"] == EMBEDDING_DIMENSION
    assert payload["model"] == "openai/text-embedding-3-small"


@pytest.mark.asyncio
@respx.mock
async def test_embed_retries_without_dimensions_on_400() -> None:
    """Если модель не принимает dimensions — повтор без параметра."""
    route = respx.post(OPENROUTER_EMBEDDINGS_URL)
    route.side_effect = [
        httpx.Response(400, json={"error": "dimensions not supported"}),
        httpx.Response(200, json=_embedding_response([1.0] * 768)),
    ]

    service = _make_service()
    vector = await service.embed("текст")

    assert len(vector) == EMBEDDING_DIMENSION
    assert service._supports_dimensions is False

    import json
    second_payload = json.loads(route.calls[1].request.content)
    assert "dimensions" not in second_payload


# ---------------------------------------------------------------------------
# Ошибки и retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_embed_retries_on_429_then_succeeds(monkeypatch) -> None:
    # Без реального sleep
    async def _no_sleep(_attempt):
        return None
    monkeypatch.setattr(OpenRouterEmbeddingService, "_backoff", staticmethod(_no_sleep))

    route = respx.post(OPENROUTER_EMBEDDINGS_URL)
    route.side_effect = [
        httpx.Response(429, json={"error": "rate limit"}),
        httpx.Response(200, json=_embedding_response([1.0] * EMBEDDING_DIMENSION)),
    ]

    service = _make_service()
    vector = await service.embed("текст")
    assert len(vector) == EMBEDDING_DIMENSION
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_embed_raises_after_exhausted_retries(monkeypatch) -> None:
    async def _no_sleep(_attempt):
        return None
    monkeypatch.setattr(OpenRouterEmbeddingService, "_backoff", staticmethod(_no_sleep))

    respx.post(OPENROUTER_EMBEDDINGS_URL).mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )

    service = _make_service(max_retries=2)
    with pytest.raises(EmbeddingServiceError):
        await service.embed("текст")


@pytest.mark.asyncio
async def test_embed_raises_without_api_key() -> None:
    service = OpenRouterEmbeddingService(model="m", api_key="", timeout=5, max_retries=1)
    with pytest.raises(EmbeddingServiceError):
        await service.embed("текст")


@pytest.mark.asyncio
@respx.mock
async def test_embed_raises_on_malformed_response() -> None:
    respx.post(OPENROUTER_EMBEDDINGS_URL).mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    service = _make_service()
    with pytest.raises(EmbeddingServiceError):
        await service.embed("текст")


@pytest.mark.asyncio
async def test_embed_empty_text_returns_zero_vector() -> None:
    service = _make_service()
    vector = await service.embed("   ")
    assert vector == [0.0] * EMBEDDING_DIMENSION


# ---------------------------------------------------------------------------
# Фолбэк в репозитории
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repository_falls_back_to_local_on_provider_error() -> None:
    from unittest.mock import AsyncMock

    from src.db.repository import RCARepository
    from src.services.embedding_service import EMBEDDING_MODEL_NAME

    class FailingService:
        model_name = "openai/text-embedding-3-small"
        dimension = EMBEDDING_DIMENSION

        async def embed(self, text: str) -> list[float]:
            raise EmbeddingServiceError("network down")

    repo = RCARepository(AsyncMock(), embedding_service=FailingService())
    vector, model_name, dimension = await repo._embed("Падение с лестницы")

    assert model_name == EMBEDDING_MODEL_NAME  # локальный фолбэк
    assert dimension == EMBEDDING_DIMENSION
    assert len(vector) == EMBEDDING_DIMENSION
    assert any(v != 0 for v in vector)


@pytest.mark.asyncio
async def test_repository_uses_async_provider_result() -> None:
    from unittest.mock import AsyncMock

    from src.db.repository import RCARepository

    class AsyncOkService:
        model_name = "external/test-model"
        dimension = EMBEDDING_DIMENSION

        async def embed(self, text: str) -> list[float]:
            vec = [0.0] * EMBEDDING_DIMENSION
            vec[0] = 1.0
            return vec

    repo = RCARepository(AsyncMock(), embedding_service=AsyncOkService())
    vector, model_name, dimension = await repo._embed("текст")

    assert model_name == "external/test-model"
    assert vector[0] == 1.0
