"""
Тесты методики «Системный RCA».
Запуск: pytest tests/unit/test_rca_systemic.py
"""

from datetime import datetime

import pytest

from src.domain.models import (
    AnalysisRequest,
    IncidentInput,
    LLMResponseValidationError,
    MethodologyType,
)

# ---------------------------------------------------------------------------
# Заглушка — RcaSystemicRunner ещё не реализован, пропускаем импорт
# ---------------------------------------------------------------------------
try:
    from src.domain.methodologies.rca_systemic import RcaSystemicRunner
    _RUNNER_AVAILABLE = True
except ImportError:
    _RUNNER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _RUNNER_AVAILABLE,
    reason="RcaSystemicRunner не реализован (запланировано)",
)


@pytest.fixture
def runner():
    return RcaSystemicRunner()


@pytest.fixture
def request_obj():
    incident = IncidentInput(
        title="Падение рабочего с высоты 4 метра",
        description=(
            "Рабочий упал с лесов в результате отсутствия перекрытия проёма "
            "и нарушения требований безопасности."
        ),
        incident_date=datetime(2026, 4, 10, 11, 0),
        location="Строительный объект Б",
        incident_type="injury",
        severity="major",
        victims=1,
    )
    return AnalysisRequest(incident=incident, methodology=MethodologyType.RCA_SYSTEMIC)


@pytest.fixture
def valid_llm_response():
    return {
        "immediate_causes": [
            {
                "id": "imm-1",
                "text": "Рабочий не использовал страховочный пояс",
                "category": "небезопасные действия",
                "level": 0,
                "parent_id": None,
                "confidence": 0.95,
            }
        ],
        "contributing_causes": [
            {
                "id": "cont-1",
                "text": "Отсутствие инструктажа по работе на высоте",
                "category": "организационные",
                "level": 1,
                "parent_id": "imm-1",
                "confidence": 0.85,
            }
        ],
        "root_causes": [
            {
                "id": "root-1",
                "text": "Системный сбой в управлении безопасностью",
                "category": "системные",
                "level": 2,
                "parent_id": "cont-1",
                "confidence": 0.80,
            }
        ],
        "barriers": [
            {
                "id": "bar-1",
                "barrier_type": "administrative",
                "description": "Обязательный инструктаж перед работой на высоте",
                "failed": True,
                "failure_reason": "Инструктаж не был проведён",
            }
        ],
        "summary": "Системный сбой в культуре безопасности привёл к падению.",
        "recommendations": [
            {
                "id": "rec-1",
                "text": "Внедрить обязательный инструктаж и контроль СИЗ",
                "priority": "high",
                "category": "immediate",
                "cause_id": "root-1",
            }
        ],
    }


class TestRcaSystemicRunner:
    def test_runner_instantiates(self, runner):
        assert runner is not None

    def test_validate_response_accepts_valid(self, runner, valid_llm_response):
        runner.validate_response(valid_llm_response)  # не должно бросать

    def test_validate_response_accepts_missing_barriers(self, runner, valid_llm_response):
        del valid_llm_response["barriers"]
        runner.validate_response(valid_llm_response)  # не должно бросать

    def test_validate_response_rejects_missing_root_causes(self, runner, valid_llm_response):
        del valid_llm_response["root_causes"]
        with pytest.raises(LLMResponseValidationError):
            runner.validate_response(valid_llm_response)
