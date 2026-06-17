"""Tests for admin-managed P17 LLM settings endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import LLMSettings

USER = UserInfo(user_id="user-001", email="user@test.com", display_name="User", role="user")
ADMIN = UserInfo(user_id="admin-001", email="admin@test.com", display_name="Admin", role="admin")

_CSRF = generate_csrf_token()


def _override_user(user: UserInfo):
    async def _dep() -> UserInfo:
        return user
    return _dep


def _setup(user: UserInfo):
    async def _db_dep():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _db_dep
    app.dependency_overrides[get_current_user] = _override_user(user)


def _teardown():
    app.dependency_overrides.clear()


def _client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={CSRF_COOKIE_NAME: _CSRF, "access_token": "fake"},
    )


@pytest.mark.asyncio
async def test_user_cannot_get_llm_settings():
    _setup(USER)
    try:
        async with _client() as c:
            r = await c.get("/api/v1/admin/llm-settings", headers={CSRF_HEADER_NAME: _CSRF})
        assert r.status_code == 403
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_get_llm_settings():
    _setup(ADMIN)
    try:
        settings = LLMSettings(
            draft_model="nvidia/nemotron-3-super-120b-a12b:free",
            verifier_model="openai/gpt-oss-20b",
            quality_threshold=0.7,
            verification_scheme="threshold",
            updated_by="admin@test.com",
        )
        with patch("src.api.routes.admin.LLMSettingsRepository") as MockRepo:
            MockRepo.return_value.get = AsyncMock(return_value=settings)
            async with _client() as c:
                r = await c.get("/api/v1/admin/llm-settings", headers={CSRF_HEADER_NAME: _CSRF})

        assert r.status_code == 200
        data = r.json()
        assert data["draft_model"] == "nvidia/nemotron-3-super-120b-a12b:free"
        assert data["verifier_model"] == "openai/gpt-oss-20b"
        assert data["quality_threshold"] == 0.7
        assert data["verification_scheme"] == "threshold"
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_update_llm_settings():
    _setup(ADMIN)
    try:
        payload = {
            "draft_model": "openai/gpt-oss-120b:free",
            "verifier_model": "openai/gpt-oss-20b",
            "quality_threshold": 0.65,
            "verification_scheme": "threshold",
        }
        saved = LLMSettings(**payload, updated_by=ADMIN.email)

        with patch("src.api.routes.admin.LLMSettingsRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.upsert = AsyncMock(return_value=saved)

            async with _client() as c:
                r = await c.put(
                    "/api/v1/admin/llm-settings",
                    json=payload,
                    headers={CSRF_HEADER_NAME: _CSRF},
                )

        assert r.status_code == 200
        assert r.json()["updated_by"] == ADMIN.email
        args, kwargs = mock_repo.upsert.await_args
        assert args[0].draft_model == "openai/gpt-oss-120b:free"
        assert kwargs["updated_by"] == ADMIN.email
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_llm_settings_requires_verifier_when_threshold_enabled():
    _setup(ADMIN)
    try:
        async with _client() as c:
            r = await c.put(
                "/api/v1/admin/llm-settings",
                json={
                    "draft_model": "openai/gpt-oss-120b:free",
                    "verifier_model": "",
                    "quality_threshold": 0.65,
                    "verification_scheme": "threshold",
                },
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 422
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_llm_settings_allows_empty_verifier_when_disabled():
    _setup(ADMIN)
    try:
        payload = {
            "draft_model": "openai/gpt-oss-120b:free",
            "verifier_model": "",
            "quality_threshold": 0.65,
            "verification_scheme": "disabled",
        }
        saved = LLMSettings(
            draft_model="openai/gpt-oss-120b:free",
            verifier_model=None,
            quality_threshold=0.65,
            verification_scheme="disabled",
            updated_by=ADMIN.email,
        )

        with patch("src.api.routes.admin.LLMSettingsRepository") as MockRepo:
            MockRepo.return_value.upsert = AsyncMock(return_value=saved)
            async with _client() as c:
                r = await c.put(
                    "/api/v1/admin/llm-settings",
                    json=payload,
                    headers={CSRF_HEADER_NAME: _CSRF},
                )

        assert r.status_code == 200
        assert r.json()["verifier_model"] is None
        assert r.json()["verification_scheme"] == "disabled"
    finally:
        _teardown()
