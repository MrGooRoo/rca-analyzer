"""Тесты API поиска похожих инцидентов."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import MethodologyType, SimilarIncident

TEST_USER = UserInfo(
    user_id="user-001",
    email="user@test.com",
    display_name="User",
    role="user",
)

ADMIN_USER = UserInfo(
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


def _similar_item() -> SimilarIncident:
    return SimilarIncident(
        result_id="res-001",
        incident_id="inc-001",
        methodology=MethodologyType.FIVE_WHY,
        created_at=datetime(2026, 6, 10, 10, 0),
        summary="Похожее падение на лестнице из-за мокрой ступени",
        similarity=0.82,
        confidence_avg=0.9,
        root_causes_preview=["Не очищалась мокрая лестница"],
        recommendations_preview=["Регулярная уборка ступеней"],
        user_id=TEST_USER.user_id,
    )


@pytest.mark.asyncio
async def test_find_similar_incidents_success_for_user(async_client) -> None:
    with patch("src.api.routes.analyze.RCARepository") as MockRepo:
        repo = AsyncMock()
        repo.backfill_missing_embeddings = AsyncMock(return_value=0)
        repo.find_similar_incidents = AsyncMock(return_value=[_similar_item()])
        MockRepo.return_value = repo

        response = await async_client.get(
            "/api/v1/incidents/similar",
            params={"text": "Падение с лестницы на мокрой ступени", "limit": 3},
        )

    assert response.status_code == 200
    data = response.json()
    assert data[0]["similarity"] == 0.82
    assert data[0]["methodology"] == "five_why"
    repo.backfill_missing_embeddings.assert_awaited_once_with(user_id=TEST_USER.user_id, limit=100)
    repo.find_similar_incidents.assert_awaited_once()
    assert repo.find_similar_incidents.await_args.kwargs["user_id"] == TEST_USER.user_id
    assert repo.find_similar_incidents.await_args.kwargs["limit"] == 3


@pytest.mark.asyncio
async def test_find_similar_incidents_admin_searches_all_users(async_client) -> None:
    app.dependency_overrides[get_current_user] = _override_user(ADMIN_USER)

    with patch("src.api.routes.analyze.RCARepository") as MockRepo:
        repo = AsyncMock()
        repo.backfill_missing_embeddings = AsyncMock(return_value=0)
        repo.find_similar_incidents = AsyncMock(return_value=[])
        MockRepo.return_value = repo

        response = await async_client.get(
            "/api/v1/incidents/similar",
            params={"text": "Пожар на производственном участке"},
        )

    assert response.status_code == 200
    repo.backfill_missing_embeddings.assert_awaited_once_with(user_id=None, limit=100)
    assert repo.find_similar_incidents.await_args.kwargs["user_id"] is None


@pytest.mark.asyncio
async def test_find_similar_incidents_validation_error(async_client) -> None:
    response = await async_client.get("/api/v1/incidents/similar", params={"text": "x"})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/incidents/similar — текст в теле запроса (фикс HTTP 431)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_similar_incidents_success(async_client) -> None:
    with patch("src.api.routes.analyze.RCARepository") as MockRepo:
        repo = AsyncMock()
        repo.backfill_missing_embeddings = AsyncMock(return_value=0)
        repo.find_similar_incidents = AsyncMock(return_value=[_similar_item()])
        MockRepo.return_value = repo

        response = await async_client.post(
            "/api/v1/incidents/similar",
            json={"text": "Падение с лестницы на мокрой ступени", "limit": 3},
        )

    assert response.status_code == 200
    data = response.json()
    assert data[0]["similarity"] == 0.82
    repo.backfill_missing_embeddings.assert_awaited_once_with(user_id=TEST_USER.user_id, limit=100)
    assert repo.find_similar_incidents.await_args.kwargs["limit"] == 3


@pytest.mark.asyncio
async def test_post_similar_incidents_long_text_no_431(async_client) -> None:
    """Длинный текст (как из DOCX-описаний) должен работать через POST без 431."""
    long_text = "Работник упал со стремянки при выполнении работ на высоте. " * 80
    long_text = long_text[:5000]

    with patch("src.api.routes.analyze.RCARepository") as MockRepo:
        repo = AsyncMock()
        repo.backfill_missing_embeddings = AsyncMock(return_value=0)
        repo.find_similar_incidents = AsyncMock(return_value=[])
        MockRepo.return_value = repo

        response = await async_client.post(
            "/api/v1/incidents/similar",
            json={"text": long_text, "limit": 5},
        )

    assert response.status_code == 200
    assert repo.find_similar_incidents.await_args.kwargs["text"] == long_text


@pytest.mark.asyncio
async def test_post_similar_incidents_passes_excludes(async_client) -> None:
    with patch("src.api.routes.analyze.RCARepository") as MockRepo:
        repo = AsyncMock()
        repo.backfill_missing_embeddings = AsyncMock(return_value=0)
        repo.find_similar_incidents = AsyncMock(return_value=[])
        MockRepo.return_value = repo

        response = await async_client.post(
            "/api/v1/incidents/similar",
            json={
                "text": "Возгорание в цехе покраски",
                "exclude_result_id": "res-42",
                "exclude_incident_id": "inc-42",
            },
        )

    assert response.status_code == 200
    kwargs = repo.find_similar_incidents.await_args.kwargs
    assert kwargs["exclude_result_id"] == "res-42"
    assert kwargs["exclude_incident_id"] == "inc-42"


@pytest.mark.asyncio
async def test_post_similar_incidents_validation_error(async_client) -> None:
    response = await async_client.post("/api/v1/incidents/similar", json={"text": "x"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_similar_incidents_text_too_long_rejected(async_client) -> None:
    response = await async_client.post(
        "/api/v1/incidents/similar",
        json={"text": "а" * 5001},
    )
    assert response.status_code == 422
