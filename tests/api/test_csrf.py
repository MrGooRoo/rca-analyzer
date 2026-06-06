"""Тесты CSRF-middleware (signed double-submit).

Не требуют БД: используют изолированное FastAPI-приложение с тестовыми
маршрутами и тем же CSRFMiddleware, что и прод. Логика middleware зависит
только от cookie/headers, а не от роутеров RCA.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

from src.api.middleware.csrf import CSRFMiddleware
from src.auth.cookies import ACCESS_COOKIE_NAME
from src.auth.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
    is_valid_csrf_token,
    set_csrf_cookie,
    tokens_match,
)


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(CSRFMiddleware, enabled=True)

    @application.post("/api/v1/protected")
    async def protected() -> dict:
        return {"ok": True}

    @application.get("/api/v1/safe")
    async def safe() -> dict:
        return {"ok": True}

    @application.get("/api/v1/auth/csrf")
    async def csrf(response: Response) -> dict:
        set_csrf_cookie(response)
        return {"csrf_token": "set"}

    @application.post("/api/v1/auth/login")
    async def login(response: Response) -> dict:
        set_csrf_cookie(response)
        return {"ok": True}

    return application


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- unit: token helpers -----------------------------------------------------

def test_generate_token_is_valid() -> None:
    token = generate_csrf_token()
    assert is_valid_csrf_token(token)


def test_tampered_token_invalid() -> None:
    token = generate_csrf_token()
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert not is_valid_csrf_token(tampered)


def test_garbage_token_invalid() -> None:
    assert not is_valid_csrf_token("no-separator")
    assert not is_valid_csrf_token("")
    assert not is_valid_csrf_token(None)


def test_tokens_match() -> None:
    t = generate_csrf_token()
    assert tokens_match(t, t)
    assert not tokens_match(t, t + "x")
    assert not tokens_match(None, t)


# --- integration: middleware -------------------------------------------------

@pytest.mark.asyncio
async def test_safe_method_no_csrf_required(app: FastAPI) -> None:
    async with _client(app) as c:
        r = await c.get("/api/v1/safe", cookies={ACCESS_COOKIE_NAME: "x"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_path_now_requires_csrf(app: FastAPI) -> None:
    """Login больше не exempt — без CSRF-токена 403."""
    async with _client(app) as c:
        r = await c.post("/api/v1/auth/login")
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


@pytest.mark.asyncio
async def test_csrf_endpoint_returns_token(app: FastAPI) -> None:
    """GET /api/v1/auth/csrf устанавливает csrf-cookie (safe-метод)."""
    async with _client(app) as c:
        r = await c.get("/api/v1/auth/csrf")
    assert r.status_code == 200
    assert CSRF_COOKIE_NAME in r.cookies
    cookie = r.cookies[CSRF_COOKIE_NAME]
    assert is_valid_csrf_token(cookie)


@pytest.mark.asyncio
async def test_login_with_csrf_token_succeeds(app: FastAPI) -> None:
    """Двухфазный CSRF: GET /csrf → POST /login с X-CSRF-Token."""
    async with _client(app) as c:
        # Phase 1: получить CSRF-cookie
        r1 = await c.get("/api/v1/auth/csrf")
        assert r1.status_code == 200
        csrf = r1.cookies.get(CSRF_COOKIE_NAME)
        assert csrf
        assert is_valid_csrf_token(csrf)

        # Phase 2: login с CSRF-заголовком
        r2 = await c.post(
            "/api/v1/auth/login",
            cookies={ACCESS_COOKIE_NAME: "x"},
            headers={CSRF_HEADER_NAME: csrf},
        )
    assert r2.status_code == 200
    assert CSRF_COOKIE_NAME in r2.cookies
    assert is_valid_csrf_token(r2.cookies[CSRF_COOKIE_NAME])


@pytest.mark.asyncio
async def test_anonymous_post_not_blocked(app: FastAPI) -> None:
    # Нет access-cookie -> нечего защищать -> пропускаем.
    async with _client(app) as c:
        r = await c.post("/api/v1/protected")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_bearer_without_cookie_exempt(app: FastAPI) -> None:
    async with _client(app) as c:
        r = await c.post(
            "/api/v1/protected",
            headers={"Authorization": "Bearer sometoken"},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cookie_auth_missing_csrf_rejected(app: FastAPI) -> None:
    async with _client(app) as c:
        r = await c.post("/api/v1/protected", cookies={ACCESS_COOKIE_NAME: "x"})
    assert r.status_code == 403
    assert "CSRF cookie missing" in r.json()["detail"]


@pytest.mark.asyncio
async def test_cookie_auth_missing_header_rejected(app: FastAPI) -> None:
    token = generate_csrf_token()
    async with _client(app) as c:
        r = await c.post(
            "/api/v1/protected",
            cookies={ACCESS_COOKIE_NAME: "x", CSRF_COOKIE_NAME: token},
        )
    assert r.status_code == 403
    assert "header" in r.json()["detail"]


@pytest.mark.asyncio
async def test_cookie_auth_mismatch_rejected(app: FastAPI) -> None:
    token = generate_csrf_token()
    other = generate_csrf_token()
    async with _client(app) as c:
        r = await c.post(
            "/api/v1/protected",
            cookies={ACCESS_COOKIE_NAME: "x", CSRF_COOKIE_NAME: token},
            headers={CSRF_HEADER_NAME: other},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cookie_auth_invalid_signature_rejected(app: FastAPI) -> None:
    bad = "fake.deadbeef"
    async with _client(app) as c:
        r = await c.post(
            "/api/v1/protected",
            cookies={ACCESS_COOKIE_NAME: "x", CSRF_COOKIE_NAME: bad},
            headers={CSRF_HEADER_NAME: bad},
        )
    assert r.status_code == 403
    assert "invalid" in r.json()["detail"]


@pytest.mark.asyncio
async def test_cookie_auth_valid_csrf_passes(app: FastAPI) -> None:
    token = generate_csrf_token()
    async with _client(app) as c:
        r = await c.post(
            "/api/v1/protected",
            cookies={ACCESS_COOKIE_NAME: "x", CSRF_COOKIE_NAME: token},
            headers={CSRF_HEADER_NAME: token},
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_disabled_middleware_passes_through() -> None:
    application = FastAPI()
    application.add_middleware(CSRFMiddleware, enabled=False)

    @application.post("/api/v1/protected")
    async def protected() -> dict:
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as c:
        r = await c.post("/api/v1/protected", cookies={ACCESS_COOKIE_NAME: "x"})
    assert r.status_code == 200
