"""
Тесты HFLocalEmbeddingService.

Юнит-тесты работают без скачивания модели (мокаем загрузку/инференс).
Интеграционный тест с реальной моделью помечен @pytest.mark.slow и
запускается только если transformers/torch установлены и есть кэш/сеть:
    pytest -m slow tests/unit/test_hf_local_embeddings.py
"""

from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from src.integrations.embeddings.hf_local import (
    DEFAULT_HF_MODEL,
    HFLocalEmbeddingService,
    _fit_dimension,
)
from src.services.embedding_service import (
    EMBEDDING_DIMENSION,
    EmbeddingServiceError,
    LocalHashEmbeddingService,
    get_embedding_service,
    reset_embedding_service_cache,
)


def _has_hf_stack() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# _fit_dimension
# ---------------------------------------------------------------------------

def test_fit_dimension_pads_and_normalizes() -> None:
    vec = _fit_dimension([3.0, 4.0], EMBEDDING_DIMENSION)
    assert len(vec) == EMBEDDING_DIMENSION
    assert vec[2:] == [0.0] * (EMBEDDING_DIMENSION - 2)
    norm = math.sqrt(sum(v * v for v in vec))
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_fit_dimension_truncates() -> None:
    vec = _fit_dimension([1.0] * 768, EMBEDDING_DIMENSION)
    assert len(vec) == EMBEDDING_DIMENSION
    norm = math.sqrt(sum(v * v for v in vec))
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_fit_dimension_zero_vector() -> None:
    vec = _fit_dimension([0.0] * 10, EMBEDDING_DIMENSION)
    assert vec == [0.0] * EMBEDDING_DIMENSION


# ---------------------------------------------------------------------------
# Конфигурация / фабрика
# ---------------------------------------------------------------------------

def test_default_model_and_naming() -> None:
    service = HFLocalEmbeddingService()
    assert service.hf_model_id == DEFAULT_HF_MODEL
    assert service.model_name == f"hf/{DEFAULT_HF_MODEL}"
    assert service.dimension == EMBEDDING_DIMENSION
    assert service._input_prefix == ""  # rubert-tiny2 — без префикса


def test_e5_models_get_query_prefix() -> None:
    service = HFLocalEmbeddingService(model="intfloat/multilingual-e5-small")
    assert service._input_prefix == "query: "


def test_factory_returns_hf_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_EMBEDDING_MODEL", "cointegrated/rubert-tiny2")
    reset_embedding_service_cache()

    svc = get_embedding_service()
    assert isinstance(svc, HFLocalEmbeddingService)
    assert svc.model_name == "hf/cointegrated/rubert-tiny2"

    # Кэшируется
    assert get_embedding_service() is svc
    reset_embedding_service_cache()


def test_factory_accepts_hf_alias(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hf")
    reset_embedding_service_cache()
    assert isinstance(get_embedding_service(), HFLocalEmbeddingService)
    reset_embedding_service_cache()


# ---------------------------------------------------------------------------
# Поведение без модели / ошибки
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_text_returns_zero_vector_without_loading_model() -> None:
    service = HFLocalEmbeddingService()
    vec = await service.embed("   ")
    assert vec == [0.0] * EMBEDDING_DIMENSION
    assert service._model is None  # модель не загружалась


@pytest.mark.asyncio
async def test_load_failure_raises_embedding_error() -> None:
    service = HFLocalEmbeddingService(model="nonexistent/model-404")
    with patch.object(
        HFLocalEmbeddingService,
        "_ensure_model",
        side_effect=EmbeddingServiceError("download failed"),
    ):
        with pytest.raises(EmbeddingServiceError):
            await service.embed("Падение с лестницы")


def test_load_error_is_cached() -> None:
    """Повторные вызовы не должны заново пытаться загрузить сломанную модель."""
    service = HFLocalEmbeddingService(model="nonexistent/model-404")
    service._load_error = RuntimeError("первая ошибка загрузки")

    with pytest.raises(EmbeddingServiceError, match="недоступна"):
        service._ensure_model()


@pytest.mark.asyncio
async def test_repository_falls_back_to_local_hash_on_hf_error() -> None:
    from unittest.mock import AsyncMock

    from src.db.repository import RCARepository

    service = HFLocalEmbeddingService(model="nonexistent/model-404")
    service._load_error = RuntimeError("no model")

    repo = RCARepository(AsyncMock(), embedding_service=service)
    vector, model_name, dimension = await repo._embed("Падение с лестницы")

    assert model_name == LocalHashEmbeddingService.model_name
    assert dimension == EMBEDDING_DIMENSION
    assert any(v != 0 for v in vector)


# ---------------------------------------------------------------------------
# Мокнутый инференс (без torch)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_uses_forward_and_fits_dimension() -> None:
    service = HFLocalEmbeddingService()

    with patch.object(HFLocalEmbeddingService, "_ensure_model"), \
         patch.object(HFLocalEmbeddingService, "_forward", return_value=[1.0] * 312):
        vec = await service.embed("Возгорание в цехе")

    assert len(vec) == EMBEDDING_DIMENSION
    norm = math.sqrt(sum(v * v for v in vec))
    assert norm == pytest.approx(1.0, abs=1e-9)
    assert vec[312:] == [0.0] * (EMBEDDING_DIMENSION - 312)


# ---------------------------------------------------------------------------
# Интеграционный тест с реальной моделью (опциональный)
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not _has_hf_stack(), reason="torch/transformers не установлены")
@pytest.mark.asyncio
async def test_real_model_semantic_quality() -> None:
    """Реальная rubert-tiny2: синонимы ближе, чем несвязанные тексты."""
    from src.services.embedding_service import cosine_similarity

    service = HFLocalEmbeddingService()
    try:
        a = await service.embed("Работник упал со стремянки")
        b = await service.embed("Падение сотрудника с лестницы")
        c = await service.embed("Перегрев электродвигателя насоса")
    except EmbeddingServiceError as exc:
        pytest.skip(f"модель недоступна (нет сети/кэша): {exc}")

    sim_related = cosine_similarity(a, b)
    sim_unrelated = cosine_similarity(a, c)

    assert len(a) == EMBEDDING_DIMENSION
    assert sim_related > sim_unrelated
    assert sim_related > 0.5
