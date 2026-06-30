"""
Юнит-тесты для auth cookies.

Проверка: _cookie_kwargs не добавляет ключ 'expires' с относительным значением,
который интерпретируется как Unix-timestamp 1970 года.
"""
from datetime import timedelta

from src.auth.cookies import _cookie_kwargs


def test_cookie_kwargs_no_expires_key():
    """
    _cookie_kwargs должен возвращать словарь WITHOUT ключа 'expires'.
    Starlette вычислит корректный Expires из max_age сам.
    """
    ttl = timedelta(minutes=15)
    kwargs = _cookie_kwargs(ttl)

    assert "expires" not in kwargs, (
        "Ключ 'expires' в cookie-kwargs интерпретируется браузером как "
        "абсолютный Unix-timestamp. Передача max_age (относительные секунды) "
        "приведёт к истечению cookie в 1970 году."
    )


def test_cookie_kwargs_has_required_keys():
    """В kwargs должны быть стандартные безопасные флаги."""
    kwargs = _cookie_kwargs(timedelta(minutes=15))

    assert kwargs["httponly"] is True
    assert kwargs["samesite"] in {"lax", "strict", "none"}
    assert kwargs["max_age"] == 900  # 15 минут