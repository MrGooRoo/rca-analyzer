"""Tests for P17 admin OpenRouter models catalog proxy."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, generate_csrf_token
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import OpenRouterModelInfo
from src.integrations.llm.openrouter_catalog import (
    OPENROUTER_MODELS_URL,
    OpenRouterCatalogError,
    clear_openrouter_models_cache,
    fetch_openrouter_models,
)

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
async def test_user_cannot_list_openrouter_models():
    _setup(USER)
    try:
        async with _client() as c:
            r = await c.get(
                "/api/v1/admin/openrouter/models",
                headers={CSRF_HEADER_NAME: _CSRF},
            )
        assert r.status_code == 403
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_admin_can_list_openrouter_models_with_filters():
    _setup(ADMIN)
    try:
        models = [
            OpenRouterModelInfo(
                id="openai/gpt-oss-20b",
                name="OpenAI: gpt-oss-20b",
                context_length=131072,
                prompt_price_per_1m=0.029,
                completion_price_per_1m=0.14,
                is_free=False,
            )
        ]
        with patch("src.api.routes.admin.fetch_openrouter_models") as mock_fetch:
            mock_fetch.return_value = models
            async with _client() as c:
                r = await c.get(
                    "/api/v1/admin/openrouter/models",
                    params={
                        "search": "gpt-oss",
                        "free_only": "false",
                        "limit": "10",
                        "force_refresh": "true",
                    },
                    headers={CSRF_HEADER_NAME: _CSRF},
                )

        assert r.status_code == 200
        assert r.json()[0]["id"] == "openai/gpt-oss-20b"
        mock_fetch.assert_awaited_once_with(
            search="gpt-oss",
            free_only=False,
            limit=10,
            force_refresh=True,
        )
    finally:
        _teardown()


@pytest.mark.asyncio
async def test_openrouter_catalog_error_returns_502():
    _setup(ADMIN)
    try:
        with patch("src.api.routes.admin.fetch_openrouter_models") as mock_fetch:
            mock_fetch.side_effect = OpenRouterCatalogError("catalog unavailable")
            async with _client() as c:
                r = await c.get(
                    "/api/v1/admin/openrouter/models",
                    headers={CSRF_HEADER_NAME: _CSRF},
                )

        assert r.status_code == 502
        assert "catalog unavailable" in r.json()["detail"]
    finally:
        _teardown()


@pytest.mark.asyncio
@respx.mock
async def test_fetch_openrouter_models_filters_prices_and_free_flag():
    clear_openrouter_models_cache()
    respx.get(OPENROUTER_MODELS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "openai/gpt-oss-20b",
                        "name": "OpenAI: gpt-oss-20b",
                        "context_length": 131072,
                        "pricing": {
                            "prompt": "0.000000029",
                            "completion": "0.00000014",
                        },
                    },
                    {
                        "id": "openai/gpt-oss-20b:free",
                        "name": "OpenAI: gpt-oss-20b (free)",
                        "context_length": 131072,
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                    {
                        "id": "anthropic/claude-haiku-4.5",
                        "name": "Anthropic: Claude Haiku 4.5",
                        "context_length": 200000,
                        "pricing": {"prompt": "0.000001", "completion": "0.000005"},
                    },
                ]
            },
        )
    )

    models = await fetch_openrouter_models(
        search="gpt-oss",
        free_only=False,
        limit=10,
        force_refresh=True,
    )

    assert [m.id for m in models] == ["openai/gpt-oss-20b", "openai/gpt-oss-20b:free"]
    assert models[0].prompt_price_per_1m == pytest.approx(0.029)
    assert models[0].completion_price_per_1m == pytest.approx(0.14)
    assert models[0].is_free is False
    assert models[1].is_free is True

    free_models = await fetch_openrouter_models(search="gpt-oss", free_only=True, limit=10)
    assert [m.id for m in free_models] == ["openai/gpt-oss-20b:free"]

    clear_openrouter_models_cache()
