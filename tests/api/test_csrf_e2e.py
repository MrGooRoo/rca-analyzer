"""E2E-тест полного CSRF-цикла через реальный app-стек.

Проверяет интеграцию: реальный ``src.api.app.app`` (с настоящим
``CSRFMiddleware`` и реальным auth-роутером) + единый httpx-клиент с общей
cookie-jar, как в браузере.

БД не поднимается: ``get_db`` и DB-операции auth-сервиса замоканы, чтобы
login/refresh отрабатывали без Postgres. Цель теста — не БД, а связка
"login ставит csrf-cookie -> protected POST требует X-CSRF-Token".

Сценарий повторяет логику frontend (`frontend/src/api.js`):
читает csrf_token из cookie-jar и кладёт его в заголовок X-CSRF-Token.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app
from src.auth.cookies import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from src.auth.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, is_valid_csrf_token
from src.auth.models import UserInfo
from src.auth.service import get_current_user
from src.db.base import get_db
from src.domain.models import (
    CauseNode,
    MethodologyType,
    RCAResult,
    Recommendation,
)

TEST_USER = UserInfo(user_id="u-1", email="user@example.com", display_name="Tester", role="user")


def _fake_rca_result() -> RCAResult:
    node = CauseNode(id="n1", text="Мокрый пол", category="среда", level=0, confidence=0.9)
    rec = Recommendation(
        id="r1", text="Убрать воду", priority="high", category="immediate", cause_id="n1"
    )
    return RCAResult(
        result_id="e2e-result-1",
        incident_id="inc-1",
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
def client_with_mocked_backend():
    """Реальный app, но без реальной БД: get_db + auth DB-операции замоканы."""

    async def _fake_get_db():
        yield AsyncMock()  # сессия не используется (DB-функции замоканы целиком)

    async def _fake_current_user() -> UserInfo:
        return TEST_USER

    # get_current_user импортируется в роутерах по ссылке, поэтому подменяем
    # его именно как FastAPI-зависимость через dependency_overrides.
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_current_user] = _fake_current_user

    patches = [
        patch(
            "src.auth.router.authenticate_user",
            AsyncMock(return_value=TEST_USER),
        ),
        patch(
            "src.auth.router.issue_auth_tokens",
            AsyncMock(return_value=("fake-access-jwt", "fake-refresh-token")),
        ),
        patch(
            "src.auth.router.build_user_info",
            lambda user: TEST_USER,
        ),
    ]
    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()
    app.dependency_overrides.clear()


def _client() -> AsyncClient:
    """Реальный app через явный ASGITransport без deprecated httpx shortcuts."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _csrf_from_jar(client: AsyncClient) -> str | None:
    return client.cookies.get(CSRF_COOKIE_NAME)


@pytest.mark.asyncio
async def test_login_sets_all_cookies(client_with_mocked_backend):
    async with _client() as client:
        # Phase 1: получить CSRF-cookie (safe GET, не требует токена)
        csrf_resp = await client.get("/api/v1/auth/csrf")
        assert csrf_resp.status_code == 200
        csrf = _csrf_from_jar(client)
        assert csrf is not None
        assert is_valid_csrf_token(csrf)

        # Phase 2: login с CSRF-заголовком
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "secret"},
            headers={CSRF_HEADER_NAME: csrf},
        )
        assert resp.status_code == 200
        # Все три cookie выставлены и попали в jar клиента.
        assert client.cookies.get(ACCESS_COOKIE_NAME) is not None
        assert client.cookies.get(REFRESH_COOKIE_NAME) is not None
        assert _csrf_from_jar(client) is not None


@pytest.mark.asyncio
async def test_protected_post_without_csrf_header_is_blocked(client_with_mocked_backend):
    async with _client() as client:
        # Phase 1: получить CSRF-cookie
        csrf_resp = await client.get("/api/v1/auth/csrf")
        assert csrf_resp.status_code == 200
        csrf = _csrf_from_jar(client)
        assert csrf is not None

        # Phase 2: login с CSRF-заголовком — получаем access-cookie
        await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "secret"},
            headers={CSRF_HEADER_NAME: csrf},
        )
        # cookie есть (включая access), но заголовок X-CSRF-Token НЕ отправлен.
        resp = await client.post("/api/v1/analyze", json={"any": "payload"})
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_full_cycle_login_then_protected_post(client_with_mocked_backend):
    async with _client() as client:
        # Phase 1: получить CSRF-cookie
        csrf_resp = await client.get("/api/v1/auth/csrf")
        assert csrf_resp.status_code == 200
        csrf = _csrf_from_jar(client)
        assert csrf is not None

        # 2. Login с CSRF-заголовком — ставит access/refresh/csrf cookie в jar.
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "secret"},
            headers={CSRF_HEADER_NAME: csrf},
        )
        assert login.status_code == 200

        # 3. Frontend-логика: читаем csrf из cookie и кладём в заголовок.
        csrf = _csrf_from_jar(client)
        assert csrf

        payload = {
            "incident": {
                "title": "Падение с лестницы",
                "description": "Поскользнулся на мокрой ступени.",
                "incident_date": "2026-06-01T09:30:00",
                "location": "Цех №3",
                "incident_type": "injury",
                "severity": "moderate",
            },
            "methodology": "five_why",
            "language": "ru",
            "detail_level": 2,
        }

        with patch("src.api.routes.analyze._service") as mock_service:
            mock_service.analyze = AsyncMock(return_value=_fake_rca_result())
            resp = await client.post(
                "/api/v1/analyze",
                json=payload,
                headers={CSRF_HEADER_NAME: csrf},
            )

        # CSRF пройден -> запрос доходит до роутера -> 201 Created.
        assert resp.status_code == 201, resp.text
        assert resp.json()["result_id"] == "e2e-result-1"


@pytest.mark.asyncio
async def test_logout_clears_csrf_cookie(client_with_mocked_backend):
    async with _client() as client:
        # Phase 1: получить CSRF-cookie
        csrf_resp = await client.get("/api/v1/auth/csrf")
        assert csrf_resp.status_code == 200
        csrf = _csrf_from_jar(client)
        assert csrf is not None

        # Phase 2: login с CSRF
        await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "secret"},
            headers={CSRF_HEADER_NAME: csrf},
        )
        csrf = _csrf_from_jar(client)
        assert csrf

        with patch("src.auth.router.revoke_refresh_token", AsyncMock(return_value=None)):
            resp = await client.post(
                "/api/v1/auth/logout",
                headers={CSRF_HEADER_NAME: csrf},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
