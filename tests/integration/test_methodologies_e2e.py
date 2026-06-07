"""
E2E-тесты всех 5 методологий RCA через AnalysisService.

Прогоняется ПОЛНЫЙ конвейер для каждой методики:

    AnalysisRequest
        → PromptRenderer (реальные Jinja2-шаблоны configs/prompts/*.j2)
        → FakeLLMClient (контракт-точный JSON, БЕЗ сети)
        → MethodologyRunner (реальный парсинг raw dict → RCAResult)
        → RCAResult

Мокируется только сетевой вызов LLM. Всё остальное — настоящий код,
поэтому тесты ловят регрессии в рендеринге промптов, парсинге ответа
и сборке результата по каждой методике.

Запуск: pytest tests/integration/test_methodologies_e2e.py
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.domain.models import (
    AnalysisRequest,
    IncidentInput,
    MethodologyType,
    RCAResult,
)
from src.services.analysis_service import AnalysisService

# ---------------------------------------------------------------------------
# Фейковый LLM-клиент: возвращает заранее заданный JSON без обращения к сети.
# Совместим с протоколом OpenRouterClient (async context manager + complete()).
# ---------------------------------------------------------------------------


class FakeLLMClient:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls: list[tuple[str, str]] = []

    async def __aenter__(self) -> FakeLLMClient:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        **_kwargs: object,
    ) -> dict:
        # Фиксируем, что промпты действительно отрендерены и непустые.
        self.calls.append((system_prompt, user_prompt))
        # Добавляем _meta, как реальный клиент (используется runner'ами).
        payload = dict(self._payload)
        payload.setdefault("_meta", {"model": "fake/model", "tokens": 123})
        return payload


# ---------------------------------------------------------------------------
# Общая фикстура инцидента
# ---------------------------------------------------------------------------


@pytest.fixture
def incident() -> IncidentInput:
    return IncidentInput(
        title="Падение работника с лестницы",
        description="Работник поскользнулся на мокрой ступени и упал с высоты 2 м.",
        incident_date=datetime(2026, 6, 1, 9, 30),
        location="Цех №3",
        incident_type="injury",
        severity="moderate",
        equipment="Приставная лестница",
        conditions="Мокрый пол после уборки",
    )


# ---------------------------------------------------------------------------
# Контракт-точные ответы LLM для каждой методики
# ---------------------------------------------------------------------------


def _five_why_payload() -> dict:
    return {
        "immediate_causes": [
            {"id": "i1", "text": "Работник упал с лестницы", "category": "человек",
             "confidence": 0.9},
        ],
        "contributing_causes": [
            {"id": "c1", "text": "Ступень была мокрой", "category": "среда",
             "confidence": 0.85},
            {"id": "c2", "text": "Уборку провели без ограждения зоны", "category": "метод",
             "confidence": 0.8},
        ],
        "root_causes": [
            {"id": "r1", "text": "Отсутствует регламент уборки в рабочее время",
             "category": "управление", "confidence": 0.75},
        ],
        "summary": "Корневая причина — отсутствие регламента уборки.",
        "recommendations": [
            {"id": "rec1", "text": "Ввести регламент влажной уборки вне смены",
             "priority": "high", "category": "long_term", "cause_id": "r1"},
        ],
    }


def _ishikawa_payload() -> dict:
    return {
        "immediate_causes": [
            {"id": "head", "text": "Травма при падении", "category": "эффект",
             "level": 0, "confidence": 0.9},
        ],
        "contributing_causes": [
            {"id": "b1", "text": "Нарушение техники безопасности", "category": "человек",
             "level": 1, "confidence": 0.8},
            {"id": "b2", "text": "Мокрый пол", "category": "среда",
             "level": 1, "confidence": 0.8},
            {"id": "b3", "text": "Нет регламента уборки", "category": "метод",
             "level": 1, "confidence": 0.7},
        ],
        "root_causes": [
            {"id": "rr1", "text": "Слабый контроль охраны труда", "category": "управление",
             "level": 2, "parent_id": "b1", "confidence": 0.7},
        ],
        "summary": "Причины сгруппированы по категориям 6M.",
        "recommendations": [
            {"id": "rec1", "text": "Усилить контроль ОТ", "priority": "medium",
             "category": "long_term", "cause_id": "rr1"},
        ],
    }


def _rca_systemic_payload() -> dict:
    return {
        "immediate_causes": [
            {"id": "i1", "text": "Небезопасное действие: проход по мокрому полу",
             "category": "небезопасные действия", "confidence": 0.85},
        ],
        "contributing_causes": [
            {"id": "c1", "text": "Отсутствие предупреждающих знаков",
             "category": "предшествующие условия", "confidence": 0.8},
        ],
        "root_causes": [
            {"id": "r1", "text": "Недостаточный надзор за уборкой",
             "category": "надзор и управление", "confidence": 0.75},
        ],
        "barriers": [
            {"id": "bar1", "text": "Ограждение зоны уборки", "category": "barrier",
             "status": "absent", "confidence": 0.7},
        ],
        "summary": "Сбой системных барьеров безопасности.",
        "recommendations": [
            {"id": "rec1", "text": "Внедрить процедуру ограждения зон уборки",
             "priority": "high", "category": "long_term", "cause_id": "r1"},
        ],
    }


def _fta_payload() -> dict:
    return {
        "top_event": {"id": "top", "text": "Падение работника", "gate": "OR",
                      "confidence": 0.9},
        "immediate_causes": [
            {"id": "g1", "text": "Потеря равновесия", "gate": "OR", "parent_id": "top",
             "confidence": 0.85},
        ],
        "root_causes": [
            {"id": "b1", "text": "Мокрая ступень", "gate": "BASIC", "parent_id": "g1",
             "confidence": 0.8},
            {"id": "b2", "text": "Отсутствие нескользящего покрытия", "gate": "BASIC",
             "parent_id": "g1", "confidence": 0.75},
        ],
        "summary": "Базовые события: мокрая ступень и отсутствие покрытия.",
        "recommendations": [
            {"id": "rec1", "text": "Установить нескользящее покрытие", "priority": "high",
             "category": "long_term", "cause_id": "b2"},
        ],
    }


def _bowtie_payload() -> dict:
    return {
        "hazard": {"id": "hz", "text": "Работа на высоте", "confidence": 0.9},
        "top_event": {"id": "top", "text": "Падение с лестницы", "confidence": 0.9},
        "threats": [
            {"id": "t1", "text": "Скользкая поверхность", "confidence": 0.85},
        ],
        "prevention_barriers": [
            {"id": "pb1", "text": "Ограждение зоны уборки", "parent_id": "t1",
             "confidence": 0.8},
        ],
        "consequences": [
            {"id": "cq1", "text": "Перелом конечности", "confidence": 0.85},
        ],
        "mitigation_barriers": [
            {"id": "mb1", "text": "Аптечка и первая помощь", "parent_id": "cq1",
             "confidence": 0.8},
        ],
        "summary": "Bowtie: угроза → top-event → последствия с барьерами.",
        "recommendations": [
            {"id": "rec1", "text": "Проверять барьеры предотвращения ежесменно",
             "priority": "high", "category": "long_term", "cause_id": "t1"},
        ],
    }


PAYLOADS = {
    MethodologyType.FIVE_WHY: _five_why_payload,
    MethodologyType.ISHIKAWA: _ishikawa_payload,
    MethodologyType.RCA_SYSTEMIC: _rca_systemic_payload,
    MethodologyType.FTA: _fta_payload,
    MethodologyType.BOWTIE: _bowtie_payload,
}

ALL_METHODOLOGIES = list(PAYLOADS.keys())


# ---------------------------------------------------------------------------
# Общий E2E-прогон для всех методик (smoke + базовые инварианты RCAResult)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("methodology", ALL_METHODOLOGIES, ids=lambda m: m.value)
async def test_full_pipeline_produces_valid_result(
    methodology: MethodologyType,
    incident: IncidentInput,
) -> None:
    payload = PAYLOADS[methodology]()
    fake = FakeLLMClient(payload)
    service = AnalysisService(llm_client=fake)

    request = AnalysisRequest(methodology=methodology, incident=incident)
    result = await service.analyze(request)

    # Тип результата и методика
    assert isinstance(result, RCAResult)
    assert result.methodology == methodology

    # Промпты были отрендерены и переданы в LLM (system + user, непустые)
    assert len(fake.calls) == 1
    system_prompt, user_prompt = fake.calls[0]
    assert system_prompt.strip()
    assert user_prompt.strip()
    # Реальный рендер подставил данные инцидента в промпт
    assert incident.title in user_prompt or incident.title in system_prompt

    # Базовые инварианты результата
    assert result.result_id
    assert result.summary
    assert len(result.recommendations) >= 1
    assert len(result.causal_tree) >= 1
    assert 0.0 <= result.confidence_avg <= 1.0
    assert result.model_used == "fake/model"
    assert result.tokens_used == 123

    # Каждая рекомендация ссылается на существующую причину или непустой cause_id
    for rec in result.recommendations:
        assert rec.text
        assert rec.cause_id


@pytest.mark.parametrize("methodology", ALL_METHODOLOGIES, ids=lambda m: m.value)
async def test_causal_tree_nodes_are_consistent(
    methodology: MethodologyType,
    incident: IncidentInput,
) -> None:
    """Все узлы causal_tree имеют корректные поля и уникальные id."""
    service = AnalysisService(llm_client=FakeLLMClient(PAYLOADS[methodology]()))
    result = await service.analyze(
        AnalysisRequest(methodology=methodology, incident=incident)
    )

    ids = [n.id for n in result.causal_tree]
    assert len(ids) == len(set(ids)), "id узлов в causal_tree должны быть уникальны"

    for node in result.causal_tree:
        assert node.id
        assert node.text
        assert isinstance(node.level, int)
        assert 0.0 <= node.confidence <= 1.0


# ---------------------------------------------------------------------------
# Методика-специфичные проверки
# ---------------------------------------------------------------------------


async def test_five_why_builds_linear_chain(incident: IncidentInput) -> None:
    service = AnalysisService(llm_client=FakeLLMClient(_five_why_payload()))
    result = await service.analyze(
        AnalysisRequest(methodology=MethodologyType.FIVE_WHY, incident=incident)
    )
    # 5 Почему — линейная цепочка: уровни идут 0,1,2,... и parent_id связаны
    chain = result.causal_tree
    assert chain[0].parent_id is None
    for i in range(1, len(chain)):
        assert chain[i].level == i
        assert chain[i].parent_id == chain[i - 1].id


async def test_ishikawa_groups_by_categories(incident: IncidentInput) -> None:
    service = AnalysisService(llm_client=FakeLLMClient(_ishikawa_payload()))
    result = await service.analyze(
        AnalysisRequest(methodology=MethodologyType.ISHIKAWA, incident=incident)
    )
    categories = {n.category for n in result.contributing_causes}
    # Несколько разных категорий 6M (человек/среда/метод)
    assert len(categories) >= 2


async def test_rca_systemic_includes_barriers(incident: IncidentInput) -> None:
    service = AnalysisService(llm_client=FakeLLMClient(_rca_systemic_payload()))
    result = await service.analyze(
        AnalysisRequest(methodology=MethodologyType.RCA_SYSTEMIC, incident=incident)
    )
    # Барьеры попадают в root_causes/causal_tree как отдельные узлы
    texts = " ".join(n.text for n in result.causal_tree).lower()
    assert "ограждение" in texts


async def test_fta_marks_basic_events_as_root(incident: IncidentInput) -> None:
    service = AnalysisService(llm_client=FakeLLMClient(_fta_payload()))
    result = await service.analyze(
        AnalysisRequest(methodology=MethodologyType.FTA, incident=incident)
    )
    # Базовые события (BASIC gate) — это корневые причины
    assert len(result.root_causes) >= 1
    for node in result.root_causes:
        assert "BASIC" in node.category.upper()


async def test_bowtie_has_threats_and_consequences(incident: IncidentInput) -> None:
    service = AnalysisService(llm_client=FakeLLMClient(_bowtie_payload()))
    result = await service.analyze(
        AnalysisRequest(methodology=MethodologyType.BOWTIE, incident=incident)
    )
    texts = " ".join(n.text for n in result.causal_tree).lower()
    # Левое крыло (угроза) и правое крыло (последствие) присутствуют
    assert "скользкая" in texts  # threat
    assert "перелом" in texts    # consequence


# ---------------------------------------------------------------------------
# Error-path: невалидный ответ LLM → LLMResponseValidationError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("methodology", ALL_METHODOLOGIES, ids=lambda m: m.value)
async def test_invalid_llm_response_raises(
    methodology: MethodologyType,
    incident: IncidentInput,
) -> None:
    """Если LLM вернул ответ без обязательных ключей — должна быть ошибка валидации."""
    from src.domain.models import LLMResponseValidationError

    # Пустой ответ заведомо не содержит обязательных ключей методики.
    service = AnalysisService(llm_client=FakeLLMClient({}))
    request = AnalysisRequest(methodology=methodology, incident=incident)

    with pytest.raises(LLMResponseValidationError):
        await service.analyze(request)


# ---------------------------------------------------------------------------
# Покрытие: реестр методик в сервисе совпадает с тестируемым набором
# ---------------------------------------------------------------------------


def test_all_supported_methodologies_are_covered() -> None:
    supported = set(AnalysisService.supported_methodologies())
    assert supported == set(ALL_METHODOLOGIES), (
        "В сервисе появилась методика без E2E-теста "
        f"(или наоборот): {supported ^ set(ALL_METHODOLOGIES)}"
    )
