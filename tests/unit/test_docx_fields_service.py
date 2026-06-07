"""
Тесты стратегии обрезки текста в docx_fields_service (_trim_text).

Цель: убедиться, что ключевые разделы отчёта (в первую очередь
«Установленные факты») гарантированно попадают в срез, отправляемый в LLM,
даже в очень длинных документах, где раздел находится в «мёртвой зоне»
между head и tail.

Запуск: pytest tests/unit/test_docx_fields_service.py
"""

from __future__ import annotations

from src.services.docx_fields_service import (
    HEAD_CHUNK,
    TAIL_CHUNK,
    _find_section_spans,
    _merge_spans,
    _trim_text,
)


def test_short_text_passes_through_unchanged() -> None:
    text = "Короткий отчёт об инциденте."
    trimmed, was_trimmed = _trim_text(text)
    assert was_trimmed is False
    assert trimmed == text


def test_text_at_threshold_not_trimmed() -> None:
    text = "X" * (HEAD_CHUNK + TAIL_CHUNK)
    trimmed, was_trimmed = _trim_text(text)
    assert was_trimmed is False
    assert trimmed == text


def test_long_text_is_trimmed_and_keeps_head_and_tail() -> None:
    text = "H" * 20_000 + "T" * 20_000
    trimmed, was_trimmed = _trim_text(text)
    assert was_trimmed is True
    assert len(trimmed) < len(text)
    assert trimmed.startswith("H")
    assert trimmed.rstrip("\n").endswith("T")
    assert "пропущено" in trimmed


def test_established_facts_in_head_is_captured() -> None:
    text = "Установленные факты: причина — отказ оборудования. " * 100 + "A" * 160_000
    trimmed, _ = _trim_text(text)
    assert "Установленные факты" in trimmed


def test_established_facts_in_tail_is_captured() -> None:
    text = "A" * 160_000 + "Установленные факты: причина — отказ оборудования. " * 100
    trimmed, _ = _trim_text(text)
    assert "Установленные факты" in trimmed


def test_established_facts_in_dead_zone_is_captured() -> None:
    """Главный регрессионный тест: раздел в середине длинного документа.

    Старая стратегия head+tail теряла такой раздел; новая — обязана его найти.
    """
    pre = "A" * 78_000
    facts = "Установленные факты: комиссия установила следующее. " * 40
    post = "B" * 85_000
    text = pre + facts + post

    trimmed, was_trimmed = _trim_text(text)
    assert was_trimmed is True
    assert "Установленные факты" in trimmed
    # Захватывается осмысленный кусок раздела, а не одно слово.
    assert "комиссия установила" in trimmed


def test_multiple_sections_in_dead_zone_are_all_captured() -> None:
    text = (
        "A" * 40_000
        + "Обстоятельства несчастного случая: работник упал с высоты. "
        + "B" * 40_000
        + "Причины несчастного случая: отсутствие ограждения. "
        + "C" * 40_000
        + "Установленные факты: нарушение требований охраны труда. "
        + "D" * 40_000
    )
    trimmed, _ = _trim_text(text)
    assert "Обстоятельства несчастного случая" in trimmed
    assert "Причины несчастного случая" in trimmed
    assert "Установленные факты" in trimmed


def test_section_search_is_case_insensitive() -> None:
    text = "A" * 50_000 + "УСТАНОВЛЕННЫЕ ФАКТЫ: всё установлено. " * 30 + "B" * 50_000
    trimmed, _ = _trim_text(text)
    assert "УСТАНОВЛЕННЫЕ ФАКТЫ" in trimmed


def test_merge_spans_merges_overlapping_ranges() -> None:
    spans = [(0, 100), (50, 150), (200, 300), (290, 400)]
    merged = _merge_spans(spans)
    assert merged == [(0, 150), (200, 400)]


def test_merge_spans_keeps_disjoint_ranges() -> None:
    spans = [(0, 100), (500, 600)]
    merged = _merge_spans(spans)
    assert merged == [(0, 100), (500, 600)]


def test_merge_spans_empty() -> None:
    assert _merge_spans([]) == []


def test_find_section_spans_returns_positions() -> None:
    text = "prefix " + "Установленные факты: текст." + " suffix"
    spans = _find_section_spans(text)
    assert len(spans) >= 1
    start, end = spans[0]
    assert text.lower()[start:].startswith("установленные факты")
    assert end > start


def test_trimmed_text_is_substantially_smaller_than_huge_input() -> None:
    text = "A" * 165_000 + "Установленные факты: вывод комиссии. " * 50
    trimmed, _ = _trim_text(text)
    # Срез должен быть заметно меньше исходника, но содержать ключевой раздел.
    assert len(trimmed) < len(text) // 3
    assert "Установленные факты" in trimmed
