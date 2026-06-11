"""
Тесты PDF-экспорта (pdf_export_service.generate_pdf).

Проверяют, что для каждой методики генерируется валидный PDF
с кириллицей и без падений. Содержимое (текст) не парсим — это
бинарный формат; проверяем сигнатуру, ненулевой размер и устойчивость
к разным методикам, включая bowtie и пустые секции.

Запуск: pytest tests/unit/test_pdf_export_service.py
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.models import (
    CauseNode,
    MethodologyType,
    RCAResult,
    Recommendation,
)
from src.services.pdf_export_service import generate_pdf


def _make_result(methodology: MethodologyType, *, with_recs: bool = True) -> RCAResult:
    n1 = CauseNode(id="n1", text="Мокрый пол после уборки", category="среда",
                   level=0, confidence=0.9)
    n2 = CauseNode(id="n2", text="Нет регламента уборки", category="управление",
                   level=1, confidence=0.7)
    recs = []
    if with_recs:
        recs = [
            Recommendation(id="r1", text="Ввести регламент влажной уборки вне смены",
                           priority="high", category="long_term", cause_id="n2",
                           responsible="Начальник цеха"),
            Recommendation(id="r2", text="Установить нескользящее покрытие",
                           priority="medium", category="short_term", cause_id="n1"),
        ]
    return RCAResult(
        result_id="abcd1234-uuid-0001",
        incident_id="inc-1",
        methodology=methodology,
        created_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        immediate_causes=[n1],
        contributing_causes=[n1],
        root_causes=[n2],
        causal_tree=[n1, n2],
        summary="Корневая причина — отсутствие регламента уборки.",
        recommendations=recs,
        model_used="openai/gpt-4o-mini",
        tokens_used=951,
        confidence_avg=0.8,
    )


ALL_METHODOLOGIES = list(MethodologyType)


@pytest.mark.parametrize("methodology", ALL_METHODOLOGIES, ids=lambda m: m.value)
def test_generate_pdf_returns_valid_pdf(methodology: MethodologyType) -> None:
    result = _make_result(methodology)
    pdf_bytes = generate_pdf(result)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF", "Должна быть PDF-сигнатура"
    assert pdf_bytes.rstrip().endswith(b"%%EOF"), "PDF должен корректно завершаться"
    assert len(pdf_bytes) > 1000


def test_generate_pdf_without_recommendations() -> None:
    result = _make_result(MethodologyType.FIVE_WHY, with_recs=False)
    pdf_bytes = generate_pdf(result)
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_bowtie_with_categorized_nodes() -> None:
    """Bowtie со специальными category=BOWTIE:* рендерится по крыльям."""
    result = _make_result(MethodologyType.BOWTIE)
    result.causal_tree = [
        CauseNode(id="h", text="Работа на высоте", category="BOWTIE:HAZARD",
                  level=-1, confidence=0.9),
        CauseNode(id="t", text="Скользкая поверхность", category="BOWTIE:THREAT",
                  level=1, confidence=0.85),
        CauseNode(id="pb", text="Ограждение зоны", category="BOWTIE:PREVENTION",
                  level=1, confidence=0.2),  # деградированный барьер
        CauseNode(id="c", text="Перелом конечности", category="BOWTIE:CONSEQUENCE",
                  level=1, confidence=0.8),
        CauseNode(id="mb", text="Аптечка", category="BOWTIE:MITIGATION",
                  level=1, confidence=0.7),
    ]
    pdf_bytes = generate_pdf(result)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000


def test_generate_pdf_handles_long_text() -> None:
    """Длинный текст рекомендаций/причин не должен ломать генерацию."""
    long_text = "Очень длинная причина. " * 50
    result = _make_result(MethodologyType.ISHIKAWA)
    result.root_causes = [
        CauseNode(id="x", text=long_text, category="метод", level=2, confidence=0.6)
    ]
    result.recommendations = [
        Recommendation(id="r", text=long_text, priority="high",
                       category="long_term", cause_id="x")
    ]
    pdf_bytes = generate_pdf(result)
    assert pdf_bytes[:4] == b"%PDF"
