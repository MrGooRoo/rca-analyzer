"""
Тесты SSE-эндпоинта POST /api/v1/analyze-multi-stream.
AnalysisService и RCARepository мокируются — реальных LLM/БД нет.
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.models import UserInfo
from src.auth.service import get_current_user
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


class TestAnalyzeMultiStream:

    @pytest.mark.asyncio
    async def test_stream_happy_path(self, async_client, multi_payload):
        results_by_method = {
            MethodologyType.FIVE_WHY: _make_result(MethodologyType.FIVE_WHY, "r-five"),
            MethodologyType.ISHIKAWA: _make_result(MethodologyType.ISHIKAWA, "r-ish"),
        }

        async def fake_analyze(single):
            return results_by_method[single.methodology]

        mock_session = MagicMock()
        mock_session.id = "session-001"

        with (
            patch("src.api.routes.analyze._service") as mock_service,
            patch("src.api.routes.analyze.AsyncSessionLocal") as mock_session_local,
            patch("src.api.routes.analyze.RCARepository") as MockRepo,
        ):
            mock_service.analyze = AsyncMock(side_effect=fake_analyze)

            mock_db = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_db
            mock_cm.__aexit__.return_value = None
            mock_session_local.return_value = mock_cm

            mock_repo = AsyncMock()
            mock_repo.create_session = AsyncMock(return_value=mock_session)
            mock_repo.save_result = AsyncMock()
            MockRepo.return_value = mock_repo

            response = await async_client.post(
                "/api/v1/analyze-multi-stream",
                json=multi_payload,
            )

        assert response.status_code == 200
        events = _parse_sse(response.text)
        statuses = [e["status"] for e in events]

        assert statuses[0] == "started"
        assert statuses.count("progress") == 2
        assert statuses[-1] == "done"
        assert len(events[-1]["results"]) == 2

    @pytest.mark.asyncio
    async def test_stream_save_failure_not_in_done(self, async_client, multi_payload):
        result_ok = _make_result(MethodologyType.FIVE_WHY, "r-ok")
        result_fail = _make_result(MethodologyType.ISHIKAWA, "r-fail")

        async def fake_analyze(single):
            if single.methodology == MethodologyType.FIVE_WHY:
                return result_ok
            return result_fail

        mock_session = MagicMock()
        mock_session.id = "session-002"
        save_calls = 0

        async def fake_save(result, **kwargs):
            nonlocal save_calls
            save_calls += 1
            if result.result_id == "r-fail":
                raise RuntimeError("db unavailable")

        with (
            patch("src.api.routes.analyze._service") as mock_service,
            patch("src.api.routes.analyze.AsyncSessionLocal") as mock_session_local,
            patch("src.api.routes.analyze.RCARepository") as MockRepo,
        ):
            mock_service.analyze = AsyncMock(side_effect=fake_analyze)

            mock_db = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_db
            mock_cm.__aexit__.return_value = None
            mock_session_local.return_value = mock_cm

            mock_repo = AsyncMock()
            mock_repo.create_session = AsyncMock(return_value=mock_session)
            mock_repo.save_result = AsyncMock(side_effect=fake_save)
            MockRepo.return_value = mock_repo

            response = await async_client.post(
                "/api/v1/analyze-multi-stream",
                json=multi_payload,
            )

        events = _parse_sse(response.text)
        error_ones = [e for e in events if e["status"] == "error_one"]
        done = next(e for e in events if e["status"] == "done")

        assert len(error_ones) == 1
        assert error_ones[0]["message"] == "Не удалось сохранить результат в базе данных"
        assert len(done["results"]) == 1
        assert done["results"][0]["result_id"] == "r-ok"
        assert save_calls == 2

    @pytest.mark.asyncio
    async def test_stream_analysis_error_sanitized(self, async_client, multi_payload):
        async def fake_analyze(single):
            raise RuntimeError("secret internal sql error")

        mock_session = MagicMock()
        mock_session.id = "session-003"

        with (
            patch("src.api.routes.analyze._service") as mock_service,
            patch("src.api.routes.analyze.AsyncSessionLocal") as mock_session_local,
            patch("src.api.routes.analyze.RCARepository") as MockRepo,
        ):
            mock_service.analyze = AsyncMock(side_effect=fake_analyze)

            mock_db = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_db
            mock_cm.__aexit__.return_value = None
            mock_session_local.return_value = mock_cm

            mock_repo = AsyncMock()
            mock_repo.create_session = AsyncMock(return_value=mock_session)
            MockRepo.return_value = mock_repo

            response = await async_client.post(
                "/api/v1/analyze-multi-stream",
                json=multi_payload,
            )

        events = _parse_sse(response.text)
        error_ones = [e for e in events if e["status"] == "error_one"]

        assert len(error_ones) == 2
        for event in error_ones:
            assert event["message"] == "Ошибка анализа методики"
            assert "sql" not in event["message"].lower()

        assert events[-1]["status"] == "error"
