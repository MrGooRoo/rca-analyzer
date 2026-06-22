"""
Тесты AnalysisService.
LLM и PromptRenderer мокируются — реальных HTTP-вызовов нет.
Запуск: pytest tests/unit/test_analysis_service.py
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import (
    AnalysisRequest,
    IncidentInput,
    LLMSettings,
    MethodologyNotSupportedError,
    MethodologyType,
    MultiAnalysisResponse,
    RCAResult,
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
    async def test_analyze_uses_conductor_when_settings_provided(self, request_obj, valid_llm_payload):
        service = AnalysisService(
            llm_client=_mock_llm(valid_llm_payload),
            prompt_renderer=_mock_renderer(),
        )
        settings = LLMSettings(
            draft_model="draft-model",
            verifier_model="verifier-model",
            quality_threshold=0.7,
            verification_scheme="threshold",
        )
        expected = RCAResult(
            result_id="r1",
            incident_id="",
            methodology=MethodologyType.FIVE_WHY,
            created_at=datetime(2026, 6, 1, 10, 0),
            immediate_causes=[],
            contributing_causes=[],
            root_causes=[],
            causal_tree=[],
            summary="Conductor result",
            recommendations=[],
            model_used="draft-model -> verifier-model",
            tokens_used=100,
            confidence_avg=0.9,
        )

        with patch("src.services.analysis_service.LLMConductor") as MockConductor:
            conductor = MockConductor.return_value
            conductor.analyze = AsyncMock(return_value=expected)
            result = await service.analyze(request_obj, llm_settings=settings)

        assert result is expected
        MockConductor.assert_called_once()
        conductor.analyze.assert_awaited_once()

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

    @pytest.mark.asyncio
    async def test_analyze_stream_yields_stage_events_and_result(self, request_obj, valid_llm_payload):
        service = AnalysisService(
            llm_client=_mock_llm(valid_llm_payload),
            prompt_renderer=_mock_renderer(),
        )
        events = []
        async for event in service.analyze_stream(request_obj):
            events.append(event)

        assert events[0]["status"] == "started"
        assert events[0]["methodology"] == "five_why"
        assert events[0]["name"] == "5 Почему"

        stages = [e for e in events if e["status"] == "stage"]
        assert len(stages) == 3
        assert stages[0]["stage"] == "preparing"
        assert stages[1]["stage"] == "llm"
        assert stages[2]["stage"] == "parsing"
        assert stages[0]["percent"] < stages[1]["percent"] < stages[2]["percent"]

        assert events[-1]["status"] == "done"
        assert isinstance(events[-1]["result"], RCAResult)

    @pytest.mark.asyncio
    async def test_analyze_stream_error_event_for_unsupported_methodology(self, request_obj, valid_llm_payload):
        request_obj.methodology = "nonexistent_methodology"  # type: ignore[assignment]
        service = AnalysisService(
            llm_client=_mock_llm(valid_llm_payload),
            prompt_renderer=_mock_renderer(),
        )
        events = []
        async for event in service.analyze_stream(request_obj):
            events.append(event)

        assert events[-1]["status"] == "error"
        assert events[-1]["code"] == 400

    @pytest.mark.asyncio
    async def test_analyze_stream_error_event_for_llm_failure(self, request_obj):
        failing_llm = MagicMock()
        failing_llm.__aenter__ = AsyncMock(return_value=failing_llm)
        failing_llm.__aexit__ = AsyncMock(return_value=False)
        failing_llm.complete = AsyncMock(side_effect=Exception("LLM unavailable"))

        service = AnalysisService(
            llm_client=failing_llm,
            prompt_renderer=_mock_renderer(),
        )
        events = []
        async for event in service.analyze_stream(request_obj):
            events.append(event)

        assert events[-1]["status"] == "error"
        assert events[-1]["code"] == 500


class TestAnalyzeMulti:

    @pytest.mark.asyncio
    async def test_all_success(self, request_obj, valid_llm_payload):
        """Все методологии возвращают результат."""
        service = AnalysisService(
            llm_client=_mock_llm(valid_llm_payload),
            prompt_renderer=_mock_renderer(),
        )
        incident = IncidentInput(
            title="Test", description="Test",
            incident_type="injury", severity="moderate",
        )
        multi_req = MagicMock()
        multi_req.methodologies = [MethodologyType.FIVE_WHY, MethodologyType.ISHIKAWA]
        multi_req.language = "ru"
        multi_req.detail_level = 2
        multi_req.incident = incident

        resp = await service.analyze_multi(multi_req)

        assert isinstance(resp, MultiAnalysisResponse)
        assert len(resp.results) == 2
        assert len(resp.failures) == 0
        # Все результаты получают одинаковый incident_id
        assert resp.results[0].incident_id == resp.results[1].incident_id

    @pytest.mark.asyncio
    async def test_partial_failure(self, request_obj, valid_llm_payload):
        """Одна методология успешна, одна падает."""
        failing_llm = MagicMock()
        failing_llm.__aenter__ = AsyncMock(return_value=failing_llm)
        failing_llm.__aexit__ = AsyncMock(return_value=False)

        # Первый вызов успешен, второй — падает
        failing_llm.complete = AsyncMock(side_effect=[
            valid_llm_payload,  # five_why успех
            Exception("LLM timeout"),  # ishikawa падает
        ])

        with patch("src.services.analysis_service.OpenRouterClient", return_value=failing_llm):
            service = AnalysisService(
                prompt_renderer=_mock_renderer(),
            )
            incident = IncidentInput(
                title="Test", description="Test",
                incident_type="injury", severity="moderate",
            )
            multi_req = MagicMock()
            multi_req.methodologies = [MethodologyType.FIVE_WHY, MethodologyType.ISHIKAWA]
            multi_req.language = "ru"
            multi_req.detail_level = 2
            multi_req.incident = incident

            resp = await service.analyze_multi(multi_req)

        assert len(resp.results) == 1
        assert len(resp.failures) == 1
        assert resp.results[0].methodology == MethodologyType.FIVE_WHY
        assert resp.failures[0].methodology == MethodologyType.ISHIKAWA
        assert "LLM timeout" in resp.failures[0].error

    @pytest.mark.asyncio
    async def test_all_fail(self, request_obj):
        """Все методологии падают — пустой results, все ошибки в failures."""
        failing_llm = MagicMock()
        failing_llm.__aenter__ = AsyncMock(return_value=failing_llm)
        failing_llm.__aexit__ = AsyncMock(return_value=False)
        failing_llm.complete = AsyncMock(
            side_effect=Exception("LLM unavailable")
        )

        with patch("src.services.analysis_service.OpenRouterClient", return_value=failing_llm):
            service = AnalysisService(
                prompt_renderer=_mock_renderer(),
            )
            incident = IncidentInput(
                title="Test", description="Test",
                incident_type="injury", severity="moderate",
            )
            multi_req = MagicMock()
            multi_req.methodologies = [MethodologyType.FIVE_WHY, MethodologyType.ISHIKAWA]
            multi_req.language = "ru"
            multi_req.detail_level = 2
            multi_req.incident = incident

            resp = await service.analyze_multi(multi_req)

        assert len(resp.results) == 0
        assert len(resp.failures) == 2

    @pytest.mark.asyncio
    async def test_failure_sanitization(self, request_obj):
        """Ошибка с длинным traceback санитизируется (≤200 символов)."""
        failing_llm = MagicMock()
        failing_llm.__aenter__ = AsyncMock(return_value=failing_llm)
        failing_llm.__aexit__ = AsyncMock(return_value=False)
        long_error = "x" * 500
        failing_llm.complete = AsyncMock(
            side_effect=Exception(long_error)
        )

        with patch("src.services.analysis_service.OpenRouterClient", return_value=failing_llm):
            service = AnalysisService(
                prompt_renderer=_mock_renderer(),
            )
            incident = IncidentInput(
                title="Test", description="Test",
                incident_type="injury", severity="moderate",
            )
            multi_req = MagicMock()
            multi_req.methodologies = [MethodologyType.FIVE_WHY]
            multi_req.language = "ru"
            multi_req.detail_level = 2
            multi_req.incident = incident

            resp = await service.analyze_multi(multi_req)

        assert len(resp.failures) == 1
        assert len(resp.failures[0].error) <= 203  # 200 + "..."

