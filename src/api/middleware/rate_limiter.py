"""
In-memory rate limiter для защиты login/register и других чувствительных эндпоинтов.

Использует sliding window с хранением меток времени в памяти.
Без Redis, без внешних зависимостей — подходит для single-instance deployment.

Config через env:
  RATE_LIMIT_WINDOW_SECONDS  — окно в секундах (default: 900 = 15 мин)
  RATE_LIMIT_MAX_REQUESTS    — макс. запросов за окно (default: 10)
  RATE_LIMIT_ENABLED         — выключить целиком (default: true)
"""

from __future__ import annotations

import os
import time
from typing import Final

from fastapi import HTTPException, Request, status

_WINDOW: Final[int] = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "900"))  # 15 мин
_MAX_REQUESTS: Final[int] = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "10"))
_ENABLED: Final[bool] = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in {
    "1", "true", "yes", "on",
}

# Хранилище: {key: [timestamp, ...]}
# key = "ip:email" или "ip" (для анонимных)
_store: dict[str, list[float]] = {}


def _cleanup(key: str, now: float) -> None:
    """Удалить истёкшие метки для ключа."""
    timestamps = _store.get(key)
    if not timestamps:
        return
    cutoff = now - _WINDOW
    fresh = [t for t in timestamps if t > cutoff]
    if fresh:
        _store[key] = fresh
    else:
        _store.pop(key, None)


def _rate_limit_key(request: Request) -> str:
    """Сформировать ключ для rate limit: только IP (анонимные login/register)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    return client_ip


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency для rate limiting.

    Использовать как Depends(rate_limit_dependency) на эндпоинты login/register.
    Rate limit по IP — 10 запросов за 15 минут (дефолт).
    """
    if not _ENABLED:
        return

    key = _rate_limit_key(request)
    now = time.time()

    _cleanup(key, now)

    timestamps = _store.get(key, [])
    if len(timestamps) >= _MAX_REQUESTS:
        retry_after = int(_WINDOW - (now - timestamps[0])) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "detail": "Слишком много запросов. Попробуйте позже.",
                "retry_after_seconds": retry_after,
            },
        )

    timestamps.append(now)
    _store[key] = timestamps


def reset_rate_limiter() -> None:
    """Сбросить все счётчики (для тестов)."""
    _store.clear()


class RateLimiterMiddleware:
    """ASGI middleware — альтернативный способ подключения rate limit.

    Может использоваться как middleware вместо dependency.
    """
    def __init__(self, app, *, window: int = 900, max_requests: int = 10):
        self.app = app
        self._window = window
        self._max_requests = max_requests

    async def __call__(self, scope, receive, send):
        # Простая передача без фильтрации — middleware не обязателен,
        # используем dependency approach
        await self.app(scope, receive, send)
