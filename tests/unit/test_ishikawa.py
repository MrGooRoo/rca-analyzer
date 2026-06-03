"""
Тесты методики «Диаграмма Исикавы».
Запуск: pytest tests/unit/test_ishikawa.py
"""

from datetime import datetime

import pytest

from src.domain.models import (
    AnalysisRequest,
    IncidentInput,
    LLMResponseValidationError,
    MethodologyType,
)
from src.domain.methodologies.ishikawa import IshikawaRunner


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> IshikawaRunner:
    return IshikawaRunner()


@pytest.fixture
def request_obj() -> AnalysisRequest:
    incident = IncidentInput(
        title="Разлив химического реагента",
        description="Произошёл разлив серной кислоты из повреждённого трубопровода в цехе.",
        incident_date=datetime(2026, 6, 1, 14, 0),
        location="Химический цех №2",
        incident_type="spill",
        severity="major",
    )
    return AnalysisRequest(incident=incident, methodology=MethodologyType.ISHIKAWA)


@pytest.fixture
def valid_llm_response() -> dict:
    return {
        "immediate_causes": [
            {
                "id": "head-1",
                "text": "Разлив серной кислоты из трубопровода",
                "category": "оборудование",
                "level": 0,
                "parent_id": None,
                "confidence": 0.97,
            }
        ],
        "contributing_causes": [
            {
                "id": "node-m1",
                "text": "Оператор не провёл проверку состояния трубопровода",
                "category": "человек",
                "level": 1,
                "parent_id": "head-1",
                "confidence": 0.85,
            },
            {
                "id": "node-m2",
                "text": "Трубопровод выработал ресурс (15 лет эксплуатации)",
                "category": "машина",
                "level": 1,
                "parent_id": "head-1",
                "confidence": 0.90,
            },
            {
                "id": "node-m3",
                "text": "Регламент ТО не обновлялся 3 года",
                "category": "метод",
                "level": 1,
                "parent_id": "head-1",
                "confidence": 0.80,
            },
        ],
        "root_causes": [
            {
                "id": "root-1",
                "text": "Отсутствие системы мониторинга ресурса трубопроводов",
                "category": "управление",
                "level": 2,
                "parent_id": "node-m2",
                "confidence": 0.78,
            },
            {
                "id": "root-2",
                "text": "Культура безопасности не предусматривает инициативных проверок",
                "category": "управление",
                "level": 2,
                "parent_id": "node-m1",
                "confidence": 0.72,
            },
        ],
        "summary": (
            "Корневые причины разлива — отсутствие системы мониторинга ресурса "
            "трубопроводов и слабая культура безопасности. "
            "Необходимо внедрить риск-ориентированное ТО и пересмотреть регламенты."
        ),
        "recommendations": [
            {
                "id": "rec-1",
                "text": "Заменить трубопровод, выработавший ресурс",
                "priority": "high",
                "category": "immediate",
                "cause_id": "node-m2",
                "responsible": "Главный механик",
            },
            {
                "id": "rec-2",
                "text": "Внедрить систему мониторинга состояния трубопроводов",
                "priority": "high",
                "category": "systemic",
                "cause_id": "root-1",
                "responsible": "Служба ОТиПБ",
            },
            {
                "id": "rec-3",
                "text": "Обновить регламент ТО с учётом риск-ориентированного подхода",
                "priority": "medium",
                "category": "short_term",
                "cause_id": "node-m3",
                "responsible": "Технический директор",
            },
        ],
        "_meta": {"model": "openai/gpt-4o", "tokens": 1120},
    }


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

class TestIshikawaRunner:
    def test_methodology_type(self, runner):
        assert runner.methodology_type == MethodologyType.ISHIKAWA

    def test_prompt_template_name(self, runner):
        assert runner.get_prompt_template_name() == "ishikawa.j2"

    @pytest.mark.asyncio
    async def test_run_returns_rca_result(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)

        assert result.methodology == MethodologyType.ISHIKAWA
        assert len(result.immediate_causes) == 1
        assert len(result.contributing_causes) == 3
        assert len(result.root_causes) == 2
        assert len(result.recommendations) == 3
        assert result.model_used == "openai/gpt-4o"
        assert result.tokens_used == 1120

    @pytest.mark.asyncio
    async def test_causal_tree_contains_all_nodes(self, runner, request_obj, valid_llm_response):
        """causal_tree должен содержать все узлы из immediate + contributing + root."""
        result = await runner.run(request_obj, valid_llm_response)
        assert len(result.causal_tree) == 1 + 3 + 2  # 6 всего

    @pytest.mark.asyncio
    async def test_contributing_nodes_linked_to_head(self, runner, request_obj, valid_llm_response):
        """Узлы без parent_id в contributing должны получить parent_id головы."""
        valid_llm_response["contributing_causes"][0]["parent_id"] = None
        result = await runner.run(request_obj, valid_llm_response)
        head_id = result.immediate_causes[0].id
        assert result.contributing_causes[0].parent_id == head_id

    @pytest.mark.asyncio
    async def test_confidence_avg(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)
        all_confidences = [0.97, 0.85, 0.90, 0.80, 0.78, 0.72]
        expected = round(sum(all_confidences) / len(all_confidences), 3)
        assert result.confidence_avg == expected

    @pytest.mark.asyncio
    async def test_missing_contributing_causes_key_raises(self, runner, request_obj, valid_llm_response):
        del valid_llm_response["contributing_causes"]
        with pytest.raises(LLMResponseValidationError, match="contributing_causes"):
            await runner.run(request_obj, valid_llm_response)

    @pytest.mark.asyncio
    async def test_missing_node_text_raises(self, runner, request_obj, valid_llm_response):
        del valid_llm_response["contributing_causes"][0]["text"]
        with pytest.raises(LLMResponseValidationError):
            await runner.run(request_obj, valid_llm_response)

    @pytest.mark.asyncio
    async def test_empty_root_causes_allowed(self, runner, request_obj, valid_llm_response):
        """Допускаем пустые root_causes (LLM не нашла глубинных причин)."""
        valid_llm_response["root_causes"] = []
        result = await runner.run(request_obj, valid_llm_response)
        assert result.root_causes == []
        assert len(result.causal_tree) == 4  # immediate + 3 contributing

    @pytest.mark.asyncio
    async def test_missing_rec_cause_id_raises(self, runner, request_obj, valid_llm_response):
        del valid_llm_response["recommendations"][0]["cause_id"]
        with pytest.raises(LLMResponseValidationError):
            await runner.run(request_obj, valid_llm_response)
