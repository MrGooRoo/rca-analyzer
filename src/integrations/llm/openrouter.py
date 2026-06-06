"""
Клиент OpenRouter для вызова LLM.

Особенности:
- Автоматический retry с exponential backoff (tenacity)
- Валидация минимального JSON-формата (contracts.md раздел 6)
- Снятие маркдаун-забора ```json ... ``` перед парсингом
- Поддержка нескольких моделей через переменную окружения
- Все HTTP-ошибки оборачиваются в LLMResponseValidationError

Переменные окружения (settings.py / .env):
    OPENROUTER_API_KEY      — обязательно
    OPENROUTER_MODEL        — по умолчанию openai/gpt-4o-mini
    OPENROUTER_TIMEOUT      — секунды, по умолчанию 60
    OPENROUTER_MAX_RETRIES  — по умолчанию 3
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.models import LLMResponseValidationError

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Минимально необходимые ключи (по умолчанию) для RCA-методологий.
# Для других вызовов (upload, etc.) передайте required_keys явно.
_DEFAULT_REQUIRED_KEYS: frozenset[str] = frozenset({"summary", "recommendations"})

# Регулярка для снятия markdown-забора ```json ... ```
_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


class OpenRouterClient:
    """
    Асинхронный клиент для OpenRouter API.

    Использование:
        async with OpenRouterClient() as client:
            result = await client.complete(system_prompt, user_prompt)
    """

    def __init__(
        self,
        api_key:     str | None = None,
        model:       str | None = None,
        timeout:     int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.api_key     = api_key     or os.environ["OPENROUTER_API_KEY"]
        self.model       = model       or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.timeout     = timeout     or int(os.getenv("OPENROUTER_TIMEOUT", "60"))
        self.max_retries = max_retries or int(os.getenv("OPENROUTER_MAX_RETRIES", "3"))

        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenRouterClient":
        self._http = httpx.AsyncClient(
            base_url=OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://github.com/MrGooRoo/rca-analyzer",
                "X-Title":       "RCA Analyzer",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    @property
    def model_name(self) -> str:
        return self.model

    async def complete(
        self,
        system_prompt: str,
        user_prompt:   str,
        *,
        temperature:   float = 0.2,
        max_tokens:    int   = 4096,
        required_keys: frozenset[str] | set[str] | None = None,
    ) -> dict:
        """
        Отправить запрос к LLM и вернуть валидированный dict.

        Args:
            required_keys: обязательные ключи в ответе LLM.
                           None → используется _DEFAULT_REQUIRED_KEYS ({"summary", "recommendations"}).
                           Передайте пустой set() чтобы отключить валидацию ключей.
        """
        _required = _DEFAULT_REQUIRED_KEYS if required_keys is None else frozenset(required_keys)

        try:
            raw = await self._complete_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                required_keys=_required,
            )
        except RetryError as exc:
            raise LLMResponseValidationError(
                f"LLM не вернул валидный ответ после {self.max_retries} попыток."
            ) from exc
        return raw

    async def _complete_with_retry(
        self,
        system_prompt: str,
        user_prompt:   str,
        temperature:   float,
        max_tokens:    int,
        required_keys: frozenset[str],
    ) -> dict:

        @retry(
            retry=retry_if_exception_type((
                httpx.TransportError,
                httpx.TimeoutException,
                LLMResponseValidationError,
            )),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            reraise=False,
        )
        async def _inner() -> dict:
            return await self._call_api(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                required_keys=required_keys,
            )

        return await _inner()

    async def _call_api(
        self,
        *,
        system_prompt: str,
        user_prompt:   str,
        temperature:   float,
        max_tokens:    int,
        required_keys: frozenset[str],
    ) -> dict:
        if self._http is None:
            raise RuntimeError("Клиент используется вне контекстного менеджера.")

        payload = {
            "model":       self.model,
            "temperature": temperature,
            "max_tokens":  max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        }

        response = await self._http.post("/chat/completions", json=payload)

        if response.status_code == 429:
            logger.warning("[OpenRouter] Rate limit — retry...")
            raise httpx.TransportError("Rate limit 429")

        if response.status_code >= 500:
            logger.error("[OpenRouter] Ошибка сервера %d", response.status_code)
            raise httpx.TransportError(f"Server error {response.status_code}")

        response.raise_for_status()
        data = response.json()

        if "choices" not in data:
            err = data.get("error", {})
            err_msg = err.get("message") or err.get("code") or str(data)
            logger.error("[OpenRouter] Нет 'choices': %s", str(data)[:300])
            raise LLMResponseValidationError(
                f"OpenRouter вернул ответ без 'choices': {err_msg}"
            )

        content = data["choices"][0]["message"]["content"]
        usage   = data.get("usage", {})

        parsed = self._parse_and_validate(content, required_keys=required_keys)
        parsed["_meta"] = {
            "model":  self.model,
            "tokens": usage.get("total_tokens", 0),
        }

        logger.info(
            "[OpenRouter] ← model=%s tokens=%d keys=%s",
            self.model,
            parsed["_meta"]["tokens"],
            [k for k in parsed if not k.startswith("_")],
        )

        return parsed

    def _parse_and_validate(self, content: str, *, required_keys: frozenset[str]) -> dict:
        content = self._strip_markdown_fence(content)

        try:
            parsed: dict = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("[OpenRouter] Невалидный JSON: %.200s", content)
            raise LLMResponseValidationError(
                f"LLM вернул невалидный JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise LLMResponseValidationError(
                f"LLM вернул {type(parsed).__name__}, ожидался dict."
            )

        if required_keys:
            missing = required_keys - set(parsed.keys())
            if missing:
                logger.warning("[OpenRouter] Отсутствуют ключи: %s", missing)
                raise LLMResponseValidationError(
                    f"Ответ LLM не содержит обязательных ключей: {missing}"
                )

        return parsed

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        m = _MD_FENCE_RE.match(content.strip())
        return m.group(1) if m else content
