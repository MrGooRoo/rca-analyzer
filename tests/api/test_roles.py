"""Тесты ролевой модели (admin / user).

Не требуют БД: используют реальный app-стек с замоканными зависимостями.
Проверяют:
  1. Обычный user видит только свои результаты.
  2. Admin видит все результаты.
  3. Обычный user НЕ может получить чужой результат (403).
  4. Admin может получить чужой результат.
  5. Обычный user НЕ может удалить чужой результат (403).
  6. Admin может удалить чужой результат.
  7. Обычный user НЕ может редактировать рекомендацию чужого результата (403).
  8. Admin может редактировать рекомендацию чужого результата.
  9. Обычный user может получить свой результат.
  10. Обычный user может удалить свой результат.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import (
    CauseNode,
    MethodologyType,
    RCAResult,
    Recommendation,
)

USER_A = UserInfo(user_id="user-aaa", email="a@test.com", display_name="User A", role="user")
USER_B = UserInfo(user_id="user-bbb", email="b@test.com", display_name="User B", role="user")
ADMIN = UserInfo(user_id="admin-001", email="admin@test.com", display_name="Admin", role="admin")

_CSRF = generate_csrf_token()


def _result(result_id: str = "res-1", user_id: str = "user-aaa") -> RCAResult:
    node = CauseNode(id="n1", text="cause", category="env", level=0, confidence=0.9)
    rec = Recommendation(
        id="r1", text="fix it", priority="high", category="immediate", cause_id="n1"
    )
    return RCAResult(
        result_id=result_id,
        incident_id="inc-1",
        user_id=user_id,
        methodology=MethodologyType.FIVE_WHY,
        created_at=datetime(2026, 6, 1, 10, 0),
        immediate_causes=[node],
        contributing_causes=[],
        root_causes=[node],
        causal_tree=[node],
        summary="Root cause found.",
        recommendations=[rec],
        model_used="openai/gpt-4o",
        tokens_used=500,
        confidence_avg=0.9,
    )


def _override_user(user: UserInfo):
    """Override get_current_user для конкретного пользователя."""
    async def _dep() -> UserInfo:
        return user
    return _dep


def _override_db():
    async def _dep():
        yield AsyncMock()
    return _dep


def _setup(user: UserInfo):
    app.dependency_overrides[get_db] = _override_db()
    app.dependency_overrides[get_current_user] = _override_user(user)


def _teardown():
    app.dependency_overrides.clear()


def _client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={CSRF_COOKIE_NAME: _CSRF, "access_token": "fake"},
    )


# ---------------------------------------------------------------------------
# GET /results — список
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_list_results_filters_by_user_id():
    """Обычный user: list_results вызывается с его user_id."""
    _setup(USER_A)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_results = AsyncMock(return_value=[_result()])

            async with _client() as c:
                r = await c.get(
                    "/api/v1/results",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 200
            # Проверяем, что фильтрация по user_id была вызвана
            mock_repo.list_results.assert_called_once()
            call_kwargs = mock_repo.list_results.call_args
            assert call_kwargs.kwargs.get("user_id") == USER_A.user_id
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_list_results_no_user_filter():
    """Admin: list_results вызывается с user_id=None (видит всё)."""
    _setup(ADMIN)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_results = AsyncMock(return_value=[_result()])

            async with _client() as c:
                r = await c.get(
                    "/api/v1/results",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 200
            call_kwargs = mock_repo.list_results.call_args
            assert call_kwargs.kwargs.get("user_id") is None
    finally:
        _teardown()


# ---------------------------------------------------------------------------
# GET /results/{id} — детали
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_can_get_own_result():
    """User A может получить свой результат."""
    _setup(USER_A)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-aaa"))

            async with _client() as c:
                r = await c.get(
                    "/api/v1/results/res-1",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 200
            assert r.json()["result_id"] == "res-1"
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_user_cannot_get_other_users_result():
    """User A не может получить результат User B."""
    _setup(USER_A)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-bbb"))

            async with _client() as c:
                r = await c.get(
                    "/api/v1/results/res-1",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 403
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_get_any_result():
    """Admin может получить результат любого пользователя."""
    _setup(ADMIN)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-bbb"))

            async with _client() as c:
                r = await c.get(
                    "/api/v1/results/res-1",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 200
    finally:
        _teardown()


# ---------------------------------------------------------------------------
# DELETE /results/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_delete_other_users_result():
    """User A не может удалить результат User B."""
    _setup(USER_A)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-bbb"))
            mock_repo.delete_result = AsyncMock(return_value=True)

            async with _client() as c:
                r = await c.delete(
                    "/api/v1/results/res-1",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 403
            mock_repo.delete_result.assert_not_called()
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_user_can_delete_own_result():
    """User A может удалить свой результат."""
    _setup(USER_A)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-aaa"))
            mock_repo.delete_result = AsyncMock(return_value=True)

            async with _client() as c:
                r = await c.delete(
                    "/api/v1/results/res-1",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 204
            mock_repo.delete_result.assert_called_once_with("res-1")
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_delete_any_result():
    """Admin может удалить результат любого пользователя."""
    _setup(ADMIN)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-bbb"))
            mock_repo.delete_result = AsyncMock(return_value=True)

            async with _client() as c:
                r = await c.delete(
                    "/api/v1/results/res-1",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 204
            mock_repo.delete_result.assert_called_once_with("res-1")
    finally:
        _teardown()


# ---------------------------------------------------------------------------
# PATCH /results/{id}/recommendations/{rec_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_update_rec_of_other_users_result():
    """User A не может обновить рекомендацию результата User B."""
    _setup(USER_A)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-bbb"))

            async with _client() as c:
                r = await c.patch(
                    "/api/v1/results/res-1/recommendations/r1",
                    json={"status": "closed"},
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 403
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_update_rec_of_any_result():
    """Admin может обновить рекомендацию любого результата."""
    _setup(ADMIN)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-bbb"))
            mock_repo.update_recommendation_status = AsyncMock(return_value=True)

            async with _client() as c:
                r = await c.patch(
                    "/api/v1/results/res-1/recommendations/r1",
                    json={"status": "closed"},
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 200
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_owner_can_update_own_rec():
    """Владелец результата может обновить статус своей рекомендации."""
    _setup(USER_A)
    try:
        with patch("src.services.analysis_persistence_service.RCARepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_result = AsyncMock(return_value=_result(user_id="user-aaa"))
            mock_repo.update_recommendation_status = AsyncMock(return_value=True)

            async with _client() as c:
                r = await c.patch(
                    "/api/v1/results/res-1/recommendations/r1",
                    json={"status": "closed"},
                    headers={CSRF_HEADER_NAME: _CSRF},
                )
            assert r.status_code == 200
            assert r.json() == {"ok": True}
    finally:
        _teardown()
