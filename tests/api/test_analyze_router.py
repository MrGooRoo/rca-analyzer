"""
Интеграционные тесты FastAPI-роутера.
AnalysisService мокируется — реальных LLM-вызовов нет.
Запуск: pytest tests/api/test_analyze_router.py
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from src.api.app import app
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import (
    CauseNode,
    LLMResponseValidationError,
    MethodologyNotSupportedError,
    MethodologyType,
    RCAResult,
    Recommendation,
)


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

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
    rec  = Recommendation(id="r1", text="Убрать воду", priority="high", category="immediate", cause_id="n1")
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
    """Клиент с переопределёнными зависимостями (auth + db)."""
    app.dependency_overrides[get_db] = _override_db()
    app.dependency_overrides[get_current_user] = _override_user(TEST_USER)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:

    @pytest.mark.asyncio
    async def test_post_analyze_success(self, async_client, valid_request_payload, mock_rca_result):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze = AsyncMock(return_value=mock_rca_result)

            response = await async_client.post("/api/v1/analyze", json=valid_request_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["result_id"] == "test-uuid-001"
        assert data["methodology"] == "five_why"
        assert len(data["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_post_analyze_unsupported_methodology(self, async_client, valid_request_payload):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze = AsyncMock(
                side_effect=MethodologyNotSupportedError("bowtie не реализован")
            )
            response = await async_client.post("/api/v1/analyze", json=valid_request_payload)

        assert response.status_code == 400
        assert "bowtie" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_post_analyze_llm_error(self, async_client, valid_request_payload):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze = AsyncMock(
                side_effect=LLMResponseValidationError("невалидный JSON")
            )
            response = await async_client.post("/api/v1/analyze", json=valid_request_payload)

        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, async_client):
        with patch("src.api.routes.analyze.RCARepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_result = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo
            response = await async_client.get("/api/v1/results/nonexistent-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_result_found(self, async_client, valid_request_payload, mock_rca_result):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze = AsyncMock(return_value=mock_rca_result)
            await async_client.post("/api/v1/analyze", json=valid_request_payload)

        with patch("src.api.routes.analyze.RCARepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_result = AsyncMock(return_value=mock_rca_result)
            MockRepo.return_value = mock_repo
            response = await async_client.get("/api/v1/results/test-uuid-001")

        assert response.status_code == 200
        assert response.json()["result_id"] == "test-uuid-001"

    @pytest.mark.asyncio
    async def test_list_methodologies(self, async_client):
        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.supported_methodologies.return_value = [MethodologyType.FIVE_WHY]
            response = await async_client.get("/api/v1/methodologies")

        assert response.status_code == 200
        assert "five_why" in response.json()["supported"]

    @pytest.mark.asyncio
    async def test_healthcheck(self, async_client):
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_validation_error_missing_title(self, async_client, valid_request_payload):
        del valid_request_payload["incident"]["title"]
        response = await async_client.post("/api/v1/analyze", json=valid_request_payload)
        assert response.status_code == 422
