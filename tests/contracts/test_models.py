"""
Контрактные тесты — проверяют, что модели соответствуют docs/contracts.md.

Запуск: pytest tests/contracts/
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.domain.models import (
    AnalysisRequest,
    CauseNode,
    IncidentInput,
    MethodologyType,
    RCAResult,
    Recommendation,
)


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_incident() -> dict:
    return {
        "title": "Падение работника с лестницы",
        "description": "Работник поскользнулся на мокрой ступени и упал с высоты 2 м.",
        "incident_date": "2026-06-01T09:30:00",
        "location": "Цех №3, отметка +6м",
        "incident_type": "injury",
        "severity": "moderate",
    }


@pytest.fixture
def valid_cause_node() -> dict:
    return {
        "id": "node-001",
        "text": "Отсутствие нескользящего покрытия",
        "category": "среда",
        "level": 2,
        "parent_id": "node-000",
        "confidence": 0.87,
    }


@pytest.fixture
def valid_recommendation() -> dict:
    return {
        "id": "rec-001",
        "text": "Установить нескользящее покрытие на все ступени",
        "priority": "high",
        "category": "immediate",
        "cause_id": "node-001",
        "responsible": "Начальник цеха",
    }


# ---------------------------------------------------------------------------
# IncidentInput
# ---------------------------------------------------------------------------

class TestIncidentInput:
    def test_valid(self, valid_incident):
        obj = IncidentInput(**valid_incident)
        assert obj.title == valid_incident["title"]
        assert obj.incident_type == "injury"
        assert obj.severity == "moderate"

    def test_defaults(self, valid_incident):
        obj = IncidentInput(**valid_incident)
        assert obj.photo_urls == []
        assert obj.victims_list == []
        assert obj.victims is None


# ---------------------------------------------------------------------------
# AnalysisRequest
# ---------------------------------------------------------------------------

class TestAnalysisRequest:
    def test_defaults(self, valid_incident):
        # We need to explicitly provide methodology since it's required according to model
        # Wait, AnalysisRequest in src/domain/models.py: methodology: MethodologyType
        req = AnalysisRequest(incident=valid_incident, methodology=MethodologyType.RCA_SYSTEMIC)
        assert req.methodology == MethodologyType.RCA_SYSTEMIC
        assert req.language == "ru"
        assert req.detail_level == 2

    def test_detail_level_bounds(self, valid_incident):
        with pytest.raises(ValidationError):
            AnalysisRequest(incident=valid_incident, methodology=MethodologyType.RCA_SYSTEMIC, detail_level=0)
        with pytest.raises(ValidationError):
            AnalysisRequest(incident=valid_incident, methodology=MethodologyType.RCA_SYSTEMIC, detail_level=4)

    def test_all_methodologies(self, valid_incident):
        for m in MethodologyType:
            req = AnalysisRequest(incident=valid_incident, methodology=m)
            assert req.methodology == m


# ---------------------------------------------------------------------------
# CauseNode
# ---------------------------------------------------------------------------

class TestCauseNode:
    def test_valid(self, valid_cause_node):
        node = CauseNode(**valid_cause_node)
        assert node.confidence == 0.87
        assert node.level == 2

    def test_root_node_no_parent(self, valid_cause_node):
        valid_cause_node["parent_id"] = None
        node = CauseNode(**valid_cause_node)
        assert node.parent_id is None


# ---------------------------------------------------------------------------
# RCAResult
# ---------------------------------------------------------------------------

class TestRCAResult:
    def test_valid(self, valid_cause_node, valid_recommendation):
        result = RCAResult(
            result_id="res-001",
            incident_id="inc-001",
            methodology=MethodologyType.FIVE_WHY,
            created_at=datetime.now(),
            immediate_causes=[CauseNode(**valid_cause_node)],
            contributing_causes=[],
            root_causes=[CauseNode(**{**valid_cause_node, "id": "root-001", "level": 2})],
            causal_tree=[CauseNode(**valid_cause_node)],
            summary="Анализ выявил системную причину в отсутствии процедуры осмотра.",
            recommendations=[Recommendation(**valid_recommendation)],
            model_used="openai/gpt-4o",
            tokens_used=1240,
            confidence_avg=0.84,
        )
        assert result.result_id == "res-001"
        assert len(result.root_causes) == 1
        assert result.confidence_avg == 0.84
