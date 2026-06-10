"""
Тесты AnalysisService.
LLM и PromptRenderer мокируются — реальных HTTP-вызовов нет.
Запуск: pytest tests/unit/test_analysis_service.py
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import (
    AnalysisRequest,
    IncidentInput,
    MethodologyNotSupportedError,
    MethodologyType,
)
from src.services.analysis_service import AnalysisService


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

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
def valid_llm_payload() -> dict:
    return {
        "immediate_causes":    [{"id": "n1", "text": "Мокрый пол", "category": "среда", "level": 0, "confidence": 0.9}],
        "contributing_causes": [{"id": "n2", "text": "Нет уборки", "category": "процесс", "level": 1, "confidence": 0.8}],
        "root_causes":         [{"id": "n3", "text": "Нет регламента", "category": "управление", "level": 2, "confidence": 0.75}],
        "summary":             "Корневая причина — отсутствие регламента уборки.",
        "recommendations":     [{"id": "r1", "text": "Ввести регламент", "priority": "high", "category": "systemic", "cause_id": "n3"}],
        "_meta":               {"model": "openai/gpt-4o", "tokens": 700},
    }


def _mock_llm(payload: dict) -> MagicMock:
    """Создать мок OpenRouterClient, возвращающий payload."""
    client_instance = AsyncMock()
    client_instance.complete = AsyncMock(return_value=payload)
    mock_llm = MagicMock()
    mock_llm.__aenter__ = AsyncMock(return_value=client_instance)
    mock_llm.__aexit__  = AsyncMock(return_value=False)
    return mock_llm


def _mock_renderer(system: str = "sys", user: str = "usr") -> MagicMock:
    renderer = MagicMock()
    renderer.render = MagicMock(return_value=(system, user))
    return renderer


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

class TestAnalysisService:

    @pytest.mark.asyncio
    async def test_analyze_returns_rca_result(self, request_obj, valid_llm_payload):
        service = AnalysisService(
            llm_client=_mock_llm(valid_llm_payload),
            prompt_renderer=_mock_renderer(),
        )
        result = await service.analyze(request_obj)

        assert result.methodology == MethodologyType.FIVE_WHY
        assert len(result.root_causes) == 1
        assert result.root_causes[0].text == "Нет регламента"
        assert len(result.recommendations) == 1
        assert result.confidence_avg > 0

    @pytest.mark.asyncio
    async def test_prompt_renderer_called_with_correct_template(self, request_obj, valid_llm_payload):
        renderer = _mock_renderer()
        service = AnalysisService(
            llm_client=_mock_llm(valid_llm_payload),
            prompt_renderer=renderer,
        )
        await service.analyze(request_obj)

        renderer.render.assert_called_once_with(
            template_name="five_why.j2",
            request=request_obj,
        )

    @pytest.mark.asyncio
    async def test_unsupported_methodology_raises(self, request_obj, valid_llm_payload):
        """Все 5 методик реализованы — несуществующая должна вызывать ошибку."""
        request_obj.methodology = "nonexistent_methodology"  # type: ignore[assignment]
        service = AnalysisService(
            llm_client=_mock_llm(valid_llm_payload),
            prompt_renderer=_mock_renderer(),
        )
        # Несуществующая методика — ValueError при создании enum,
        # либо MethodologyNotSupportedError если как-то передана.
        with pytest.raises((MethodologyNotSupportedError, ValueError)):
            await service.analyze(request_obj)

    def test_supported_methodologies(self):
        supported = AnalysisService.supported_methodologies()
        assert MethodologyType.FIVE_WHY in supported

    @pytest.mark.asyncio
    async def test_llm_client_used_as_context_manager(self, request_obj, valid_llm_payload):
        mock_llm = _mock_llm(valid_llm_payload)
        service = AnalysisService(
            llm_client=mock_llm,
            prompt_renderer=_mock_renderer(),
        )
        await service.analyze(request_obj)

        mock_llm.__aenter__.assert_called_once()
        mock_llm.__aexit__.assert_called_once()
