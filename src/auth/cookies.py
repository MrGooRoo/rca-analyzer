"""Утилиты для работы с auth-cookie."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Final

from fastapi import Response

ACCESS_COOKIE_NAME: Final[str] = os.environ.get("ACCESS_COOKIE_NAME", "access_token")
REFRESH_COOKIE_NAME: Final[str] = os.environ.get("REFRESH_COOKIE_NAME", "refresh_token")
COOKIE_DOMAIN: Final[str | None] = os.environ.get("AUTH_COOKIE_DOMAIN") or None
COOKIE_PATH: Final[str] = os.environ.get("AUTH_COOKIE_PATH", "/")
allowed: Final[set[str]] = {"lax", "strict", "none"}
_raw = os.environ.get("AUTH_COOKIE_SAMESITE", "lax").lower()
COOKIE_SAMESITE: Final[str] = _raw if _raw in allowed else "lax"
COOKIE_SECURE: Final[bool] = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _cookie_kwargs(ttl: timedelta) -> dict:
    max_age = int(ttl.total_seconds())
    return {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "path": COOKIE_PATH,
        "domain": COOKIE_DOMAIN,
        "max_age": max_age,
        "expires": max_age,
    }


def set_access_cookie(response: Response, token: str, ttl: timedelta) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        **_cookie_kwargs(ttl),
    )


def set_refresh_cookie(response: Response, token: str, ttl: timedelta) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        **_cookie_kwargs(ttl),
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path=COOKIE_PATH, domain=COOKIE_DOMAIN)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=COOKIE_PATH, domain=COOKIE_DOMAIN)
