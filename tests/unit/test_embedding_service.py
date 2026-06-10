from __future__ import annotations

import pytest

from src.domain.models import CauseNode, MethodologyType, RCAResult, Recommendation
from src.services.embedding_service import (
    EMBEDDING_DIMENSION,
    LocalHashEmbeddingService,
    build_result_embedding_text,
    cosine_similarity,
)


def test_local_hash_embedding_is_deterministic_and_normalized() -> None:
    service = LocalHashEmbeddingService()
    text = "Работник упал с лестницы из-за мокрой ступени"

    first = service.embed(text)
    second = service.embed(text)

    assert first == second
    assert len(first) == EMBEDDING_DIMENSION
    assert cosine_similarity(first, first) == pytest.approx(1.0)


def test_related_incident_texts_are_closer_than_unrelated() -> None:
    service = LocalHashEmbeddingService()

    query = service.embed("Падение работника с лестницы, мокрая ступень, травма ноги")
    related = service.embed("Сотрудник поскользнулся на влажной ступени лестницы и упал")
    unrelated = service.embed("Перегрев электродвигателя насоса из-за отказа вентилятора")

    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_build_result_embedding_text_includes_summary_causes_and_recommendations() -> None:
    node = CauseNode(id="rc1", text="Не очищалась мокрая лестница", category="workplace", level=0)
    rec = Recommendation(
        id="r1",
        text="Ввести регулярную уборку ступеней",
        priority="high",
        category="process",
        cause_id="rc1",
    )
    result = RCAResult(
        result_id="res-1",
        incident_id="inc-1",
        methodology=MethodologyType.FIVE_WHY,
        created_at="2026-06-10T10:00:00",
        immediate_causes=[],
        contributing_causes=[],
        root_causes=[node],
        causal_tree=[node],
        summary="Падение на лестнице из-за скользкой поверхности",
        recommendations=[rec],
        model_used="test-model",
        tokens_used=100,
        confidence_avg=0.8,
    )

    text = build_result_embedding_text(result)

    assert "Падение на лестнице" in text
    assert "Не очищалась мокрая лестница" in text
    assert "Ввести регулярную уборку" in text
