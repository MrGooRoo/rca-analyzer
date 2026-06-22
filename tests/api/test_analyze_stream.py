"""
Интеграционные тесты SSE-роутера /api/v1/analyze-stream.
AnalysisService и RCARepository мокируются — реальных LLM-вызовов нет.
Запуск: pytest tests/api/test_analyze_stream.py
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import (
    CauseNode,
    MethodologyType,
    RCAResult,
    Recommendation,
)

TEST_USER = UserInfo(
    user_id="test-user-001",
    email="test@test.com",
    display_name="Test User",
    role="user",
)


def _override_user(user: UserInfo = TEST_USER):
    async def _dep() -> UserInfo:
        return user
    return _dep


def _override_db():
    async def _dep():
        yield AsyncMock()
    return _dep


@pytest.fixture
def valid_request_payload() -> dict:
    return {
        "incident": {
            "title": "Падение работника с лестницы",
            "description": "Работник поскользнулся на мокрой ступени и упал с высоты 2 м.",
            "incident_date": "2026-06-01T09:30:00",
            "location": "Цех №3",
            "incident_type": "injury",
            "severity": "moderate",
        },
        "methodology": "five_why",
        "language": "ru",
        "detail_level": 2,
    }


@pytest.fixture
def mock_rca_result() -> RCAResult:
    node = CauseNode(id="n1", text="Мокрый пол", category="среда", level=0, confidence=0.9)
    rec = Recommendation(id="r1", text="Убрать воду", priority="high", category="immediate", cause_id="n1")
    return RCAResult(
        result_id="test-uuid-001",
        incident_id="inc-001",
        methodology=MethodologyType.FIVE_WHY,
        created_at=datetime(2026, 6, 1, 10, 0),
        immediate_causes=[node],
        contributing_causes=[],
        root_causes=[node],
        causal_tree=[node],
        summary="Корневая причина — скользкий пол.",
        recommendations=[rec],
        model_used="openai/gpt-4o",
        tokens_used=500,
        confidence_avg=0.9,
    )


@pytest.fixture
async def async_client():
    app.dependency_overrides[get_db] = _override_db()
    app.dependency_overrides[get_current_user] = _override_user(TEST_USER)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


class _Session:
    id = "session-001"


def _mock_service_stream(result: RCAResult):
    async def _gen(_request):
        yield {"status": "started", "methodology": "five_why", "name": "5 Почему"}
        yield {"status": "stage", "stage": "preparing", "percent": 10, "message": "Подготовка промпта"}
        yield {"status": "stage", "stage": "llm", "percent": 40, "message": "Ожидание ответа от модели"}
        yield {"status": "stage", "stage": "parsing", "percent": 80, "message": "Обработка результата"}
        yield {"status": "done", "result": result}
    return _gen


def _mock_service_error():
    async def _gen(_request):
        yield {"status": "started", "methodology": "five_why", "name": "5 Почему"}
        yield {"status": "stage", "stage": "llm", "percent": 40, "message": "Ожидание ответа от модели"}
        yield {"status": "error", "message": "LLM не вернул валидный ответ.", "code": 502}
    return _gen


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


class TestAnalyzeStreamEndpoint:

    @pytest.mark.asyncio
    async def test_stream_success(self, async_client, valid_request_payload, mock_rca_result):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze_stream = _mock_service_stream(mock_rca_result)

            with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
                mock_repo = AsyncMock()
                mock_repo.create_session = AsyncMock(return_value=_Session())
                MockRepo.return_value = mock_repo

                response = await async_client.post("/api/v1/analyze-stream", json=valid_request_payload)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        events = _parse_sse(response.text)
        statuses = [e["status"] for e in events]
        assert "started" in statuses
        assert "done" in statuses
        assert statuses[-1] == "done"
        assert events[-1]["result"]["result_id"] == "test-uuid-001"
        assert events[-1]["result"]["session_id"] == "session-001"

        mock_repo.create_session.assert_awaited_once()
        mock_repo.save_result.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stream_error_event(self, async_client, valid_request_payload):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze_stream = _mock_service_error()

            with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
                mock_repo = AsyncMock()
                mock_repo.create_session = AsyncMock(return_value=_Session())
                MockRepo.return_value = mock_repo

                response = await async_client.post("/api/v1/analyze-stream", json=valid_request_payload)

        events = _parse_sse(response.text)
        assert any(e.get("status") == "error" for e in events)
        assert not any(e.get("status") == "done" for e in events)
        mock_repo.save_result.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_validation_error_missing_title(self, async_client, valid_request_payload):
        del valid_request_payload["incident"]["title"]
        response = await async_client.post("/api/v1/analyze-stream", json=valid_request_payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_stream_events_include_stages(self, async_client, valid_request_payload, mock_rca_result):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze_stream = _mock_service_stream(mock_rca_result)

            with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
                mock_repo = AsyncMock()
                mock_repo.create_session = AsyncMock(return_value=_Session())
                MockRepo.return_value = mock_repo

                response = await async_client.post("/api/v1/analyze-stream", json=valid_request_payload)

        events = _parse_sse(response.text)
        stages = [e for e in events if e.get("status") == "stage"]
        assert len(stages) >= 3
        percents = [s["percent"] for s in stages]
        assert percents == sorted(percents)
        assert all(0 <= p <= 100 for p in percents)
