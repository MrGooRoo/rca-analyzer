"""Тесты admin-роутера и seed.

Не требуют БД: используют реальный app-стек с замоканными зависимостями.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db

USER = UserInfo(user_id="user-001", email="user@test.com", display_name="User", role="user")
ADMIN = UserInfo(user_id="admin-001", email="admin@test.com", display_name="Admin", role="admin")

_CSRF = generate_csrf_token()


def _override_user(user: UserInfo):
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
# GET /api/v1/admin/users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_list_users():
    """Обычный user не может получить список пользователей."""
    _setup(USER)
    try:
        async with _client() as c:
            r = await c.get(
                "/api/v1/admin/users",
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 403
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_list_users():
    """Admin может получить список пользователей."""
    _setup(ADMIN)
    try:
        # Мокаем db.execute для SELECT users
        mock_user_orm = MagicMock()
        mock_user_orm.id = "user-001"
        mock_user_orm.email = "user@test.com"
        mock_user_orm.display_name = "User"
        mock_user_orm.role = "user"
        mock_user_orm.is_active = True

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_user_orm]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        async def _db_with_data():
            yield mock_db

        app.dependency_overrides[get_db] = _db_with_data

        async with _client() as c:
            r = await c.get(
                "/api/v1/admin/users",
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["email"] == "user@test.com"
        assert data[0]["role"] == "user"
    finally:
        _teardown()


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/users/{id}/role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_change_role():
    """Обычный user не может менять роли."""
    _setup(USER)
    try:
        async with _client() as c:
            r = await c.put(
                "/api/v1/admin/users/user-002/role",
                json={"role": "admin"},
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 403
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_cannot_demote_self():
    """Admin не может снять роль admin с самого себя."""
    _setup(ADMIN)
    try:
        async with _client() as c:
            r = await c.put(
                f"/api/v1/admin/users/{ADMIN.user_id}/role",
                json={"role": "user"},
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 400
        assert "самого себя" in r.json()["detail"]
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_invalid_role_rejected():
    """Невалидная роль отклоняется."""
    _setup(ADMIN)
    try:
        async with _client() as c:
            r = await c.put(
                "/api/v1/admin/users/user-002/role",
                json={"role": "superadmin"},
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 400
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_promote_user():
    """Admin может назначить роль admin другому пользователю."""
    _setup(ADMIN)
    try:
        mock_user_orm = MagicMock()
        mock_user_orm.id = "user-002"
        mock_user_orm.email = "other@test.com"
        mock_user_orm.display_name = "Other"
        mock_user_orm.role = "admin"  # после обновления
        mock_user_orm.is_active = True

        mock_db = AsyncMock()
        mock_db.get.return_value = mock_user_orm
        mock_db.execute.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        async def _db_with_data():
            yield mock_db

        app.dependency_overrides[get_db] = _db_with_data

        async with _client() as c:
            r = await c.put(
                "/api/v1/admin/users/user-002/role",
                json={"role": "admin"},
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
    finally:
        _teardown()


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_promotes_existing_user():
    """ensure_admin_exists промотирует зарегистрированного пользователя."""
    from src.auth.seed import ensure_admin_exists

    mock_user = MagicMock()
    mock_user.id = "u-1"
    mock_user.role = "user"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session.commit.return_value = None

    with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@test.com"}):
        await ensure_admin_exists(mock_session)

    # execute вызывается дважды: SELECT + UPDATE
    assert mock_session.execute.call_count == 2
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_seed_skips_when_no_env():
    """ensure_admin_exists ничего не делает без ADMIN_EMAIL."""
    from src.auth.seed import ensure_admin_exists

    mock_session = AsyncMock()

    with patch.dict("os.environ", {}, clear=False):
        # Убедимся, что ADMIN_EMAIL не задана
        import os
        os.environ.pop("ADMIN_EMAIL", None)
        await ensure_admin_exists(mock_session)

    mock_session.execute.assert_not_called()
