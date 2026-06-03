"""
Тесты методики Fault Tree Analysis.
Запуск: pytest tests/unit/test_fta.py
"""

from datetime import datetime

import pytest

from src.domain.models import (
    AnalysisRequest,
    IncidentInput,
    LLMResponseValidationError,
    MethodologyType,
)
from src.domain.methodologies.fta import FaultTreeRunner


@pytest.fixture
def runner():
    return FaultTreeRunner()


@pytest.fixture
def request_obj():
    incident = IncidentInput(
        title="Отказ предохранительного клапана сброса давления",
        description="Предохранительный клапан не сработал при аварийном росте давления в газопроводе.",
        incident_date=datetime(2026, 5, 15, 9, 30),
        location="Компрессорная станция №3",
        incident_type="equipment",
        severity="critical",
    )
    return AnalysisRequest(incident=incident, methodology=MethodologyType.FTA)


@pytest.fixture
def valid_llm_response():
    return {
        "top_event": {
            "id": "top-1",
            "text": "Отказ предохранительного клапана",
            "gate": "OR",
            "level": 0,
            "parent_id": None,
            "confidence": 0.99,
        },
        "immediate_causes": [
            {
                "id": "imm-1",
                "text": "Засорение пилота клапана",
                "gate": "AND",
                "level": 1,
                "parent_id": "top-1",
                "confidence": 0.88,
            },
            {
                "id": "imm-2",
                "text": "Отсутствие питания электромагнита привода",
                "gate": "AND",
                "level": 1,
                "parent_id": "top-1",
                "confidence": 0.85,
            },
        ],
        "contributing_causes": [
            {
                "id": "cont-1",
                "text": "Износ уплотнительного кольца",
                "gate": "BASIC",
                "level": 2,
                "parent_id": "imm-1",
                "confidence": 0.82,
            },
            {
                "id": "cont-2",
                "text": "Несплановое превышение давления в системе",
                "gate": "OR",
                "level": 2,
                "parent_id": "imm-2",
                "confidence": 0.79,
            },
        ],
        "root_causes": [
            {
                "id": "root-1",
                "text": "Выход из строя электромагнитной катушки (СРОК истёк)",
                "gate": "BASIC",
                "level": 3,
                "parent_id": "imm-2",
                "confidence": 0.75,
            },
        ],
        "summary": (
            "Дерево отказов показывает одновременный отказ двух независимых подсистем (AND-затвор). "
            "Корневая причина — истекший срок службы элементов без замены и износ плавающего уплотнения."
        ),
        "recommendations": [
            {
                "id": "rec-1",
                "text": "Заменить пилот клапана и уплотнительное кольцо",
                "priority": "high",
                "category": "immediate",
                "cause_id": "cont-1",
                "responsible": "Механик",
            },
        ],
        "_meta": {"model": "openai/gpt-4o", "tokens": 980},
    }


class TestFaultTreeRunner:
    def test_methodology_type(self, runner):
        assert runner.methodology_type == MethodologyType.FTA

    def test_prompt_template_name(self, runner):
        assert runner.get_prompt_template_name() == "fta.j2"

    @pytest.mark.asyncio
    async def test_run_returns_rca_result(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)
        assert result.methodology == MethodologyType.FTA
        # immediate = top_node + 2 immediate_causes
        assert len(result.immediate_causes) == 3
        assert len(result.contributing_causes) == 2
        assert len(result.root_causes) == 1
        assert result.model_used == "openai/gpt-4o"
        assert result.tokens_used == 980

    @pytest.mark.asyncio
    async def test_causal_tree_total_nodes(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)
        # top(1) + immediate(2) + contributing(2) + root(1) = 6
        assert len(result.causal_tree) == 6

    @pytest.mark.asyncio
    async def test_gate_stored_in_category(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)
        top = result.causal_tree[0]
        assert top.category == "FTA:OR"
        imm = result.immediate_causes[1]  # first real immediate
        assert imm.category == "FTA:AND"

    @pytest.mark.asyncio
    async def test_immediate_linked_to_top_when_no_parent(self, runner, request_obj, valid_llm_response):
        valid_llm_response["immediate_causes"][0]["parent_id"] = None
        result = await runner.run(request_obj, valid_llm_response)
        top_id = result.causal_tree[0].id
        assert result.immediate_causes[1].parent_id == top_id

    @pytest.mark.asyncio
    async def test_missing_top_event_raises(self, runner, request_obj, valid_llm_response):
        del valid_llm_response["top_event"]
        with pytest.raises(LLMResponseValidationError, match="top_event"):
            await runner.run(request_obj, valid_llm_response)

    @pytest.mark.asyncio
    async def test_top_event_not_dict_raises(self, runner, request_obj, valid_llm_response):
        valid_llm_response["top_event"] = "not a dict"
        with pytest.raises(LLMResponseValidationError):
            await runner.run(request_obj, valid_llm_response)

    @pytest.mark.asyncio
    async def test_missing_node_text_raises(self, runner, request_obj, valid_llm_response):
        del valid_llm_response["immediate_causes"][0]["text"]
        with pytest.raises(LLMResponseValidationError):
            await runner.run(request_obj, valid_llm_response)

    @pytest.mark.asyncio
    async def test_confidence_avg(self, runner, request_obj, valid_llm_response):
        result = await runner.run(request_obj, valid_llm_response)
        vals = [0.99, 0.88, 0.85, 0.82, 0.79, 0.75]
        expected = round(sum(vals) / len(vals), 3)
        assert result.confidence_avg == expected
