"""CSRF-токены: signed double-submit cookie.

Механизм:
    На login/register/refresh сервер ставит НЕ-httpOnly cookie `csrf_token`
    со значением вида ``<random>.<hmac_sha256(random, JWT_SECRET)>``.

    Frontend читает эту cookie (она специально не httpOnly) и отправляет её
    значение в заголовке ``X-CSRF-Token`` при каждом небезопасном запросе
    (POST/PUT/PATCH/DELETE), выполняемом через cookie-based auth.

    Middleware (см. ``src/api/middleware/csrf.py``) проверяет, что:
      * cookie присутствует и валидна по подписи (HMAC),
      * заголовок присутствует,
      * значения cookie и заголовка совпадают (constant-time).

Почему signed (а не наивный double-submit):
    Подпись HMAC привязывает токен к серверному секрету, поэтому атакующий
    не может «подсадить» произвольную CSRF-cookie с поддомена и подобрать
    совпадающий заголовок — он не знает секрет и не сможет подписать значение.

Stateless: серверного хранилища CSRF-токенов нет (никаких новых таблиц).
"""

from __future__ import annotations

import hmac
import os
import secrets
from datetime import timedelta
from hashlib import sha256
from typing import Final

from fastapi import Response

from src.auth.cookies import (
    COOKIE_DOMAIN,
    COOKIE_PATH,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
)

CSRF_COOKIE_NAME: Final[str] = os.environ.get("CSRF_COOKIE_NAME", "csrf_token")
CSRF_HEADER_NAME: Final[str] = os.environ.get("CSRF_HEADER_NAME", "X-CSRF-Token")

# Секрет для подписи токена. По умолчанию переиспользуем JWT_SECRET,
# но допускаем отдельный CSRF_SECRET, если требуется ротация независимо.
_CSRF_SECRET: Final[str] = (
    os.environ.get("CSRF_SECRET")
    or os.environ.get("JWT_SECRET", "change-me-in-production-please")
)

# CSRF-cookie живёт столько же, сколько refresh-сессия, чтобы не "протухать"
# раньше, чем сама сессия (новый токен всё равно ставится на каждом login/refresh).
CSRF_TOKEN_TTL: Final[timedelta] = timedelta(
    days=int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "30"))
)

_SEPARATOR: Final[str] = "."


def _sign(random_part: str) -> str:
    digest = hmac.new(
        _CSRF_SECRET.encode(), random_part.encode(), sha256
    ).hexdigest()
    return digest


def generate_csrf_token() -> str:
    """Создать новый подписанный CSRF-токен: ``<random>.<hmac>``."""
    random_part = secrets.token_urlsafe(32)
    return f"{random_part}{_SEPARATOR}{_sign(random_part)}"


def is_valid_csrf_token(token: str | None) -> bool:
    """Проверить, что токен корректно подписан текущим секретом."""
    if not token or _SEPARATOR not in token:
        return False
    random_part, _, signature = token.rpartition(_SEPARATOR)
    if not random_part or not signature:
        return False
    expected = _sign(random_part)
    return hmac.compare_digest(expected, signature)


def tokens_match(cookie_token: str | None, header_token: str | None) -> bool:
    """Constant-time сравнение cookie- и header-токена."""
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    """Установить НЕ-httpOnly CSRF-cookie. Возвращает значение токена.

    httponly=False — обязательно, иначе frontend не сможет прочитать токен
    из ``document.cookie`` и положить его в заголовок.
    """
    token = token or generate_csrf_token()
    max_age = int(CSRF_TOKEN_TTL.total_seconds())
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,  # type: ignore[arg-type]
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN,
        max_age=max_age,
        expires=max_age,
    )
    return token


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(CSRF_COOKIE_NAME, path=COOKIE_PATH, domain=COOKIE_DOMAIN)
