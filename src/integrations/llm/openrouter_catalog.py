"""Public OpenRouter models catalog client for admin model picker (P17)."""

from __future__ import annotations

import asyncio
import os
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from src.domain.models import OpenRouterModelInfo

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

_DEFAULT_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE_TTL_SECONDS = int(
    os.getenv("OPENROUTER_MODELS_CACHE_TTL_SECONDS", str(_DEFAULT_CACHE_TTL_SECONDS))
)
_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OPENROUTER_MODELS_TIMEOUT", "20"))
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500

_cache_lock: asyncio.Lock | None = None
_cache_expires_at: float = 0.0
_cache_payload: list[dict[str, Any]] | None = None


class OpenRouterCatalogError(RuntimeError):
    """Raised when OpenRouter catalog cannot be fetched or parsed."""


def _lock() -> asyncio.Lock:
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


def clear_openrouter_models_cache() -> None:
    """Clear in-memory cache. Primarily useful for tests."""
    global _cache_expires_at, _cache_payload
    _cache_expires_at = 0.0
    _cache_payload = None


async def fetch_openrouter_models(
    *,
    search: str | None = None,
    free_only: bool = False,
    limit: int = _DEFAULT_LIMIT,
    force_refresh: bool = False,
) -> list[OpenRouterModelInfo]:
    """
    Fetch OpenRouter models catalog, filter it and return UI-safe model metadata.

    The public catalog does not require exposing OPENROUTER_API_KEY to the browser. We keep a
    server-side in-memory cache to avoid hitting OpenRouter on every admin page load.
    """
    raw_models = await _get_raw_catalog(force_refresh=force_refresh)
    models = [_model_info_from_raw(item) for item in raw_models]

    query = (search or "").strip().lower()
    if query:
        models = [
            model
            for model in models
            if query in model.id.lower() or (model.name and query in model.name.lower())
        ]

    if free_only:
        models = [model for model in models if model.is_free]

    safe_limit = max(1, min(limit, _MAX_LIMIT))
    return models[:safe_limit]


async def _get_raw_catalog(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    global _cache_expires_at, _cache_payload

    now = time.monotonic()
    if not force_refresh and _cache_payload is not None and now < _cache_expires_at:
        return _cache_payload

    async with _lock():
        now = time.monotonic()
        if not force_refresh and _cache_payload is not None and now < _cache_expires_at:
            return _cache_payload

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(OPENROUTER_MODELS_URL)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise OpenRouterCatalogError(f"Не удалось получить каталог OpenRouter: {exc}") from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise OpenRouterCatalogError("OpenRouter вернул каталог в неожиданном формате")

        # Keep only dict items, so a malformed single item cannot break the admin UI.
        _cache_payload = [item for item in data if isinstance(item, dict)]
        _cache_expires_at = time.monotonic() + _CACHE_TTL_SECONDS
        return _cache_payload


def _model_info_from_raw(item: dict[str, Any]) -> OpenRouterModelInfo:
    model_id = str(item.get("id") or "").strip()
    name = item.get("name")
    pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}

    prompt_price = _price_per_1m(pricing.get("prompt", 0))  # type: ignore[union-attr]
    completion_price = _price_per_1m(pricing.get("completion", 0))  # type: ignore[union-attr]
    is_free = model_id.endswith(":free") or (
        prompt_price == 0.0 and completion_price == 0.0
    )

    return OpenRouterModelInfo(
        id=model_id,
        name=str(name) if name else None,
        context_length=_int_or_none(item.get("context_length")),
        prompt_price_per_1m=prompt_price,
        completion_price_per_1m=completion_price,
        is_free=is_free,
    )


def _price_per_1m(value: Any) -> float | None:
    if value is None:
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if price < 0:
        return None
    return float(price * Decimal(1_000_000))


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
