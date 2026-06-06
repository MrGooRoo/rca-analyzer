"""CSRF-middleware для cookie-based auth (signed double-submit).

Проверяет небезопасные HTTP-методы (POST/PUT/PATCH/DELETE), когда запрос
аутентифицирован через cookie. Освобождаются:

  * safe-методы (GET/HEAD/OPTIONS/TRACE);
  * bootstrap-эндпоинт refresh — у клиента может не быть валидной csrf-cookie
    после перезагрузки страницы до первого успешного refresh-ответа;
  * любой настраиваемый exempt-путь;
  * запросы с ``Authorization: Bearer ...`` и без access-cookie — такие
    запросы не подвержены CSRF (браузер не шлёт кастомные заголовки
    cross-origin без CORS), поэтому Swagger "Authorize" и curl работают
    без CSRF-токена.

Защита login/register (двухфазный CSRF-токен):
  /login и /register удалены из DEFAULT_EXEMPT_PATHS. Они принимают
  анонимные POST-запросы (без access-cookie), но при успехе устанавливают
  auth-cookie. Поэтому CSRF проверяется на них всегда, даже при отсутствии
  существующей сессии. Frontend получает csrf-cookie через GET /api/v1/auth/csrf
  перед отправкой login/register.

Поведение управляется переменными окружения:
  CSRF_PROTECTION_ENABLED  (default "true")
  CSRF_EXEMPT_PATHS        (CSV доп. путей, опционально)
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.auth.cookies import ACCESS_COOKIE_NAME
from src.auth.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    is_valid_csrf_token,
    tokens_match,
)

SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Пути, для которых CSRF не требуется (точное совпадение path).
# /login и /register убраны из exempt — теперь они защищены двухфазным
# CSRF-токеном: frontend сначала вызывает GET /api/v1/auth/csrf (safe),
# получает csrf-cookie, и отправляет её в заголовке X-CSRF-Token.
# /refresh остаётся exempt, чтобы авто-refresh после перезагрузки страницы
# мог восстановить сессию без предварительного запроса CSRF-токена.
DEFAULT_EXEMPT_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/api/v1/auth/refresh",
    }
)

# Пути, доступные без access-cookie, но устанавливающие auth-cookie.
# Они должны проходить CSRF-проверку даже при отсутствии сессии.
LOGIN_LIKE_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    }
)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_exempt(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


class CSRFMiddleware(BaseHTTPMiddleware):
    """Signed double-submit CSRF protection."""

    def __init__(
        self,
        app,
        *,
        enabled: bool | None = None,
        exempt_paths: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = (
            _env_flag("CSRF_PROTECTION_ENABLED", True) if enabled is None else enabled
        )
        configured = _parse_exempt(os.environ.get("CSRF_EXEMPT_PATHS"))
        extra = frozenset(exempt_paths or ())
        self.exempt_paths = DEFAULT_EXEMPT_PATHS | configured | extra

    def _is_exempt(self, request: Request) -> bool:
        if not self.enabled:
            return True
        if request.method.upper() in SAFE_METHODS:
            return True
        if request.url.path in self.exempt_paths:
            return True

        # Bearer-режим без access-cookie не подвержен CSRF.
        has_access_cookie = request.cookies.get(ACCESS_COOKIE_NAME) is not None
        auth_header = request.headers.get("authorization", "")
        is_bearer = auth_header.lower().startswith("bearer ")
        if is_bearer and not has_access_cookie:
            return True

        # Если нет access-cookie — это анонимный запрос без сессии.
        # Для большинства эндпоинтов CSRF не имеет смысла (нечего защищать).
        # Но login/register доступны анонимно и при успехе устанавливают
        # auth-cookie — они должны проходить CSRF-проверку.
        if not has_access_cookie:
            return request.url.path not in LOGIN_LIKE_PATHS

        return False

    @staticmethod
    def _reject(detail: str) -> Response:
        return JSONResponse(status_code=403, content={"detail": detail})

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if self._is_exempt(request):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if cookie_token is None:
            return self._reject("CSRF cookie missing")
        if header_token is None:
            return self._reject(f"CSRF header '{CSRF_HEADER_NAME}' missing")
        if not is_valid_csrf_token(cookie_token):
            return self._reject("CSRF token invalid")
        if not tokens_match(cookie_token, header_token):
            return self._reject("CSRF token mismatch")

        return await call_next(request)
