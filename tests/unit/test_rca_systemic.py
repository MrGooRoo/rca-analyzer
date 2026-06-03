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
from src.domain.methodologies.rca_systemic import RcaSystemicRunner


@pytest.fixture
def runner():
    return RcaSystemicRunner()


@pytest.fixture
def request_obj():
    incident = IncidentInput(
        title="Падение рабочего с высоты 4 метра",
        description="Рабочий упал с лесав в результате отсутствия перекрытия проема и нарушения требований безопасности.",
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
                "text": "Отсутствие инструктажа по работе на высоте