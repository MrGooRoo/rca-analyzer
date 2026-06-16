"""
Тесты методики 5 Почему.
Запуск: pytest tests/unit/test_five_why.py
"""

from datetime import datetime

import pytest

from src.domain.methodologies.base import UNASSIGNED_INCIDENT_ID
from src.domain.methodologies.five_why import FiveWhyRunner
from src.domain.models import (
    AnalysisRequest,
    IncidentInput,
    LLMResponseValidationError,
    MethodologyType,
)

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> FiveWhyRunner:
    return FiveWhyRunner()


@pytest.fixture
def request_obj() -> AnalysisRequest:
    incident = IncidentInput(
        title="Падение работника с лестницы",
        description="Работник поскользнулся на мокрой ступени и упал с высоты 2 м.",
        incident_date=datetime(2026, 6, 1, 9, 30),
        location="Цех №3",
        incident_type="injury",
        severity="moderate",
    )
    return AnalysisRequest(incident=incident, methodology=MethodologyType.FIVE_WHY)


@pytest.fixture
def valid_llm_response() -> dict:
    return {
        "immediate_causes": [
            {
                "id": "node-1",
                "text": "Работник поскользнулся на мокрой ступени",
                "category": "среда",
                "level": 0,
                "parent_id": None,
                "confidence": 0.95,
            }
        ],
        "contributing_causes": [
            {
                "id": "node-2",
                "text": "На ступенях отсутствует противоскользящее покрытие",
                "category": "среда",
                "level": 1,
                "parent_id": "node-1",
                "confidence": 0.88,
            },
            {
                "id": "node-3",
                "text": "Плановый осмотр не проводился 2 месяца",
                "category": "процесс",
                "level": 2,
                "parent_id": "node-2",
                "confidence": 0.80,
            },
        ],
        "root_causes": [
            {
                "id": "node-4",
                "text": "Отсутствует регламент плановых осмотров оборудования и инфраструктуры",
                "category": "управление",
                "level": 3,
                "parent_id": "node-3",
                "confidence": 0.75,
            }
        ],
        "summary": "Корневая причина — отсутствие системы плановых осмотров.",
        "recommendations": [
            {
                "id": "rec-1",
                "text": "Установить нескользящее покрытие",
                "priority": "high",
                "category": "immediate",
                "cause_id": "node-1",
                "responsible": "Начальник цеха",
            },
            {
                "id": "rec-2",
                "text": "Разработать регламент плановых осмотров",
                "priority": "high",
                "category": "systemic",
                "cause_id": "node-4",
                "responsible": "ОТ и ТБ",
            },
        ],
        "_meta": {"model": "openai/gpt-4o", "tokens": 980},
    }


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

class TestFiveWhyRunner:
    def test_methodology_type(self, runner):
        assert runner.methodology_type == MethodologyType.FIVE_WHY

    def test_prompt_template_name(self, runner):
        assert runner.get_prompt_template_name() == "five_why.j2"

    @pytest.mark.asyncio
    async def test_run_returns_rca_result(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)

        assert result.methodology == MethodologyType.FIVE_WHY
        assert len(result.immediate_causes) == 1
        assert len(result.contributing_causes) == 2
        assert len(result.root_causes) == 1
        assert len(result.recommendations) == 2
        assert result.summary == valid_llm_response["summary"]
        assert result.model_used == "openai/gpt-4o"
        assert result.tokens_used == 980

    @pytest.mark.asyncio
    async def test_causal_chain_is_linked(self, runner, request_obj, valid_llm_response):
        """Цепочка должна быть линейно связана: первый узел parent_id=None."""
        result = await runner.run(request_obj, valid_llm_response)

        chain = result.causal_tree
        assert chain[0].parent_id is None
        for i in range(1, len(chain)):
            assert chain[i].parent_id == chain[i - 1].id

    @pytest.mark.asyncio
    async def test_confidence_avg(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)
        expected = round((0.95 + 0.88 + 0.80 + 0.75) / 4, 3)
        assert result.confidence_avg == expected

    @pytest.mark.asyncio
    async def test_missing_required_key_raises(self, runner, request_obj, valid_llm_response):
        del valid_llm_response["root_causes"]
        with pytest.raises(LLMResponseValidationError, match="root_causes"):
            await runner.run(request_obj, valid_llm_response)

    @pytest.mark.asyncio
    async def test_missing_node_text_raises(self, runner, request_obj, valid_llm_response):
        del valid_llm_response["immediate_causes"][0]["text"]
        with pytest.raises(LLMResponseValidationError):
            await runner.run(request_obj, valid_llm_response)

    @pytest.mark.asyncio
    async def test_incident_id_unassigned_without_date(self, runner, valid_llm_response):
        """incident_id не должен зависеть от incident_date (раньше был str(date) → 'None')."""
        incident = IncidentInput(
            title="Инцидент без даты",
            description="Описание инцидента без указания даты происшествия.",
            incident_type="injury",
            severity="moderate",
        )
        request_obj = AnalysisRequest(incident=incident, methodology=MethodologyType.FIVE_WHY)
        result = await runner.run(request_obj, valid_llm_response)
        assert result.incident_id == UNASSIGNED_INCIDENT_ID

    @pytest.mark.asyncio
    async def test_empty_contributing_causes(self, runner, request_obj, valid_llm_response):
        """5 Почему допускает пустой список промежуточных."""
        valid_llm_response["contributing_causes"] = []
        result = await runner.run(request_obj, valid_llm_response)
        assert result.contributing_causes == []
        assert len(result.causal_tree) == 2  # immediate + root
