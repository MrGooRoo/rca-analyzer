"""
API-тесты для эндпоинтов /sessions и session_id в /analyze.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import (
    AnalysisSession,
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

TEST_ADMIN = UserInfo(
    user_id="admin-001",
    email="admin@test.com",
    display_name="Admin",
    role="admin",
)


def _override_user(user: UserInfo):
    async def _dep() -> UserInfo:
        return user
    return _dep


def _override_db():
    async def _dep():
        yield AsyncMock()
    return _dep


@pytest.fixture
async def async_client():
    app.dependency_overrides[get_db] = _override_db()
    app.dependency_overrides[get_current_user] = _override_user(TEST_USER)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def _mock_result(
    result_id: str = "test-uuid-001",
    incident_id: str = "inc-001",
    session_id: str | None = "sess-001",
    methodology: MethodologyType = MethodologyType.FIVE_WHY,
) -> RCAResult:
    node = CauseNode(id="n1", text="Причина", category="среда", level=0, confidence=0.9)
    rec = Recommendation(id="r1", text="Действие", priority="high",
                          category="immediate", cause_id="n1")
    return RCAResult(
        result_id=result_id,
        incident_id=incident_id,
        session_id=session_id,
        methodology=methodology,
        created_at=datetime(2026, 6, 13, 10, 0),
        immediate_causes=[node],
        contributing_causes=[],
        root_causes=[node],
        causal_tree=[node],
        summary="Тестовый анализ.",
        recommendations=[rec],
        model_used="test-model",
        tokens_used=500,
        confidence_avg=0.9,
    )


def _mock_session(session_id: str = "sess-001") -> AnalysisSession:
    return AnalysisSession(
        id=session_id,
        created_at=datetime(2026, 6, 13, 10, 0),
        user_id="test-user-001",
        user_display_name="Test User",
        user_email="test@test.com",
        incident_title="Падение с лестницы",
        incident_description="Работник упал",
        incident_date=datetime(2026, 6, 13, 9, 0),
        incident_location="Цех №1",
        incident_type="injury",
        incident_severity="moderate",
        results=[_mock_result(session_id=session_id)],
    )


class TestSessionsEndpoints:

    @pytest.mark.asyncio
    async def test_list_sessions(self, async_client):
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.list_sessions = AsyncMock(return_value=[_mock_session()])
            MockRepo.return_value = mock_repo

            response = await async_client.get("/api/v1/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "sess-001"
        assert data[0]["incident_title"] == "Падение с лестницы"

    @pytest.mark.asyncio
    async def test_get_session(self, async_client):
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_session = AsyncMock(return_value=_mock_session())
            MockRepo.return_value = mock_repo

            response = await async_client.get("/api/v1/sessions/sess-001")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "sess-001"
        assert len(data["results"]) == 1
        assert data["results"][0]["session_id"] == "sess-001"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, async_client):
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_session = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = await async_client.get("/api/v1/sessions/nonexistent")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_compare_by_session_id(self, async_client):
        from src.domain.models import ComparisonResult

        r1 = _mock_result(result_id="r-1", session_id="sess-multi",
                           methodology=MethodologyType.FIVE_WHY)
        r2 = _mock_result(result_id="r-2", session_id="sess-multi",
                           methodology=MethodologyType.ISHIKAWA)

        comparison = ComparisonResult(
            incident_id="inc-001",
            results=[r1, r2],
            common_recommendations=[],
            differing_causes={"five_why": ["Причина 1"], "ishikawa": ["Причина 2"]},
            summary="Сравнение 2 методик.",
        )

        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo, \
             patch("src.api.routes.analyze._service") as mock_service:
            mock_repo = AsyncMock()
            from src.domain.models import AnalysisSession
            mock_session = AnalysisSession(
                id="sess-multi",
                created_at=datetime(2026, 6, 13, 10, 0),
                user_id="test-user-001",
                incident_title="Сравнение",
                incident_description="Сравнение методик",
                results=[r1, r2],
            )
            mock_repo.get_session = AsyncMock(return_value=mock_session)
            MockRepo.return_value = mock_repo

            mock_service.compare.return_value = comparison

            response = await async_client.get(
                "/api/v1/results/compare?session_id=sess-multi"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["incident_id"] == "inc-001"
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_compare_no_params(self, async_client):
        """Без session_id и incident_id — 400."""
        response = await async_client.get("/api/v1/results/compare")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_analyze_returns_session_id(self, async_client):
        """Одиночный анализ должен вернуть session_id."""
        valid_payload = {
            "incident": {
                "title": "Падение",
                "description": "Упал",
                "incident_date": "2026-06-01T09:30:00",
                "location": "Цех",
                "incident_type": "injury",
                "severity": "moderate",
            },
            "methodology": "five_why",
            "language": "ru",
            "detail_level": 2,
        }

        # Мок AnalysisService.analyze → возвращает RCAResult с session_id=None
        # (session_id проставится в роутере через repo.create_session)
        mock_result = _mock_result(session_id=None)

        with patch("src.api.routes.analyze._service") as mock_service, \
             patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_service.analyze = AsyncMock(return_value=mock_result)

            mock_repo = AsyncMock()
            mock_session_orm = AsyncMock()
            mock_session_orm.id = "sess-new-001"
            mock_repo.create_session = AsyncMock(return_value=mock_session_orm)
            mock_repo.save_result = AsyncMock()
            MockRepo.return_value = mock_repo

            response = await async_client.post("/api/v1/analyze", json=valid_payload)

        assert response.status_code == 201
        # Проверяем что create_session был вызван
        mock_repo.create_session.assert_called_once()
        # Проверяем что save_result получил session_id
        call_kwargs = mock_repo.save_result.call_args
        assert call_kwargs.kwargs.get("session_id") == "sess-new-001" or \
               (len(call_kwargs.args) > 2 and call_kwargs.args[2] == "sess-new-001")
