"""
Тесты SSE-эндпоинта POST /api/v1/analyze-multi-stream.
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


def _override_user(user: UserInfo):
    async def _dep() -> UserInfo:
        return user
    return _dep


def _override_db():
    async def _dep():
        yield AsyncMock()
    return _dep


def _make_result(methodology: MethodologyType, result_id: str) -> RCAResult:
    node = CauseNode(id="n1", text="Причина", category="среда", level=0, confidence=0.9)
    rec = Recommendation(
        id="r1", text="Мера", priority="high", category="immediate", cause_id="n1",
    )
    return RCAResult(
        result_id=result_id,
        incident_id="",
        methodology=methodology,
        created_at=datetime(2026, 6, 1, 10, 0),
        immediate_causes=[node],
        contributing_causes=[],
        root_causes=[node],
        causal_tree=[node],
        summary="Сводка",
        recommendations=[rec],
        model_used="test/model",
        tokens_used=100,
        confidence_avg=0.9,
    )


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        line = block.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@pytest.fixture
def multi_payload() -> dict:
    return {
        "incident": {
            "title": "Падение работника",
            "description": "Работник упал с лестницы при выполнении работ на высоте.",
            "incident_date": "2026-06-01T09:30:00",
            "location": "Цех №3",
            "incident_type": "injury",
            "severity": "moderate",
        },
        "methodologies": ["five_why", "ishikawa"],
        "language": "ru",
        "detail_level": 2,
    }


@pytest.fixture
async def async_client():
    app.dependency_overrides[get_current_user] = _override_user(TEST_USER)
    app.dependency_overrides[get_db] = _override_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


class TestAnalyzeMultiStream:

    @pytest.mark.asyncio
    async def test_stream_happy_path(self, async_client, multi_payload):
        """Тест проверяет SSE-поток: started → progress(2) → done с 2 результатами."""
        r1 = _make_result(MethodologyType.FIVE_WHY, "r-five")
        r2 = _make_result(MethodologyType.ISHIKAWA, "r-ish")

        async def fake_stream(request, user_id, llm_settings=None):
            yield "data: " + json.dumps({"status": "started", "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "progress", "methodology": "five_why", "done": 1, "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "progress", "methodology": "ishikawa", "done": 2, "total": 2}) + "\n\n"
            yield "data: " + json.dumps({
                "status": "done",
                "results": [r1.model_dump(mode="json"), r2.model_dump(mode="json")],
            }) + "\n\n"

        with patch("src.api.routes.analyze._persistence.stream_multi", fake_stream):
            response = await async_client.post(
                "/api/v1/analyze-multi-stream", json=multi_payload,
            )

        assert response.status_code == 200
        events = _parse_sse(response.text)
        statuses = [e["status"] for e in events]
        assert statuses == ["started", "progress", "progress", "done"]
        assert len(events[-1]["results"]) == 2

    @pytest.mark.asyncio
    async def test_stream_save_failure_not_in_done(self, async_client, multi_payload):
        """Одна методика сохраняется, другая нет — error_one, not in done."""
        r_ok = _make_result(MethodologyType.FIVE_WHY, "r-ok")

        async def fake_stream(request, user_id, llm_settings=None):
            yield "data: " + json.dumps({"status": "started", "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "error_one", "methodology": "ishikawa",
                              "message": "Не удалось сохранить результат в базе данных",
                              "done": 1, "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "progress", "methodology": "five_why",
                              "done": 2, "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "done", "results": [r_ok.model_dump(mode="json")]}) + "\n\n"

        with patch("src.api.routes.analyze._persistence.stream_multi", fake_stream):
            response = await async_client.post(
                "/api/v1/analyze-multi-stream", json=multi_payload,
            )

        events = _parse_sse(response.text)
        error_ones = [e for e in events if e["status"] == "error_one"]
        done = next(e for e in events if e["status"] == "done")
        assert len(error_ones) == 1
        assert error_ones[0]["message"] == "Не удалось сохранить результат в базе данных"
        assert len(done["results"]) == 1

    @pytest.mark.asyncio
    async def test_stream_analysis_error_sanitized(self, async_client, multi_payload):
        """Обе методики падают — все error_one, финальный error."""
        async def fake_stream(request, user_id, llm_settings=None):
            yield "data: " + json.dumps({"status": "started", "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "error_one", "methodology": "five_why",
                              "message": "Ошибка анализа методики", "done": 1, "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "error_one", "methodology": "ishikawa",
                              "message": "Ошибка анализа методики", "done": 2, "total": 2}) + "\n\n"
            yield "data: " + json.dumps({"status": "error",
                              "message": "Все методологии завершились с ошибкой."}) + "\n\n"

        with patch("src.api.routes.analyze._persistence.stream_multi", fake_stream):
            response = await async_client.post(
                "/api/v1/analyze-multi-stream", json=multi_payload,
            )

        events = _parse_sse(response.text)
        error_ones = [e for e in events if e["status"] == "error_one"]
        assert len(error_ones) == 2
        assert events[-1]["status"] == "error"
