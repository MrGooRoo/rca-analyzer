"""
Тесты качества локальных эмбеддингов v2 (стемминг + HSE-синонимы)
и фабрики get_embedding_service().
"""

from __future__ import annotations

import pytest

from src.services.embedding_service import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    LocalHashEmbeddingService,
    cosine_similarity,
    get_embedding_service,
    reset_embedding_service_cache,
)


@pytest.fixture
def service() -> LocalHashEmbeddingService:
    return LocalHashEmbeddingService()


def test_model_name_is_v2(service: LocalHashEmbeddingService) -> None:
    assert service.model_name == EMBEDDING_MODEL_NAME == "local/hash-ngrams-v2"
    assert service.dimension == EMBEDDING_DIMENSION


# ---------------------------------------------------------------------------
# Синонимы без общих слов: концептный словарь
# ---------------------------------------------------------------------------

def test_synonyms_without_shared_words_are_similar(service: LocalHashEmbeddingService) -> None:
    """«Стремянка» и «лестница» не имеют общих слов и n-грамм,
    но должны сближаться через концепт ladder + fall."""
    a = service.embed("Работник упал со стремянки")
    b = service.embed("Падение сотрудника с лестницы")
    unrelated = service.embed("Перегрев электродвигателя насоса из-за отказа вентилятора")

    sim_related = cosine_similarity(a, b)
    sim_unrelated = cosine_similarity(a, unrelated)

    assert sim_related > sim_unrelated
    assert sim_related > 0.15


def test_fire_synonyms(service: LocalHashEmbeddingService) -> None:
    a = service.embed("Возгорание в цехе покраски")
    b = service.embed("Пожар на участке окраски, задымление")
    c = service.embed("Порез пальца при работе с ножом")

    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_electricity_synonyms(service: LocalHashEmbeddingService) -> None:
    a = service.embed("Поражение электрическим током при работе в щитовой")
    b = service.embed("Удар током из-за повреждённого кабеля, короткое замыкание")
    c = service.embed("Падение груза при разгрузке самосвала")

    assert cosine_similarity(a, b) > cosine_similarity(a, c)


# ---------------------------------------------------------------------------
# Стемминг словоформ
# ---------------------------------------------------------------------------

def test_word_forms_are_closer_with_stemming(service: LocalHashEmbeddingService) -> None:
    """Разные словоформы одного слова должны давать высокую похожесть."""
    a = service.embed("неисправность тормозов погрузчика")
    b = service.embed("неисправные тормоза погрузчиков")

    assert cosine_similarity(a, b) > 0.5


def test_determinism_preserved(service: LocalHashEmbeddingService) -> None:
    text = "Оператор получил ожог руки горячим паром"
    assert service.embed(text) == service.embed(text)


def test_vector_is_normalized(service: LocalHashEmbeddingService) -> None:
    vec = service.embed("Утечка газа в котельной, загазованность помещения")
    norm = sum(v * v for v in vec) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Фабрика провайдера
# ---------------------------------------------------------------------------

def test_factory_returns_local_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDINGS_PROVIDER", raising=False)
    reset_embedding_service_cache()
    svc = get_embedding_service()
    assert isinstance(svc, LocalHashEmbeddingService)


def test_factory_returns_openrouter_when_configured(monkeypatch) -> None:
    from src.integrations.llm.openrouter_embeddings import OpenRouterEmbeddingService

    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small")
    reset_embedding_service_cache()

    svc = get_embedding_service()
    assert isinstance(svc, OpenRouterEmbeddingService)
    assert svc.model_name == "openai/text-embedding-3-small"
    assert svc.dimension == EMBEDDING_DIMENSION

    reset_embedding_service_cache()


def test_factory_caches_instances(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")
    reset_embedding_service_cache()
    assert get_embedding_service() is get_embedding_service()
    reset_embedding_service_cache()


# ---------------------------------------------------------------------------
# Адаптивный порог похожести
# ---------------------------------------------------------------------------

def test_default_threshold_local(monkeypatch) -> None:
    from src.services.embedding_service import default_similarity_threshold

    monkeypatch.delenv("SIMILARITY_THRESHOLD", raising=False)
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")
    assert default_similarity_threshold() == pytest.approx(0.15)


def test_default_threshold_neural_providers(monkeypatch) -> None:
    from src.services.embedding_service import default_similarity_threshold

    monkeypatch.delenv("SIMILARITY_THRESHOLD", raising=False)
    for provider in ("huggingface", "hf", "openrouter"):
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", provider)
        assert default_similarity_threshold() == pytest.approx(0.55)


def test_threshold_env_override(monkeypatch) -> None:
    from src.services.embedding_service import default_similarity_threshold

    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.42")
    assert default_similarity_threshold() == pytest.approx(0.42)

    monkeypatch.setenv("SIMILARITY_THRESHOLD", "not-a-number")
    assert default_similarity_threshold() == pytest.approx(0.15)
