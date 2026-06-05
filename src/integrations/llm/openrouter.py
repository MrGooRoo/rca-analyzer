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

# Минимально необходимые ключи во ВСЕХ методиках (contracts.md раздел 6).
# Примечание: immediate_causes / root_causes УБРАНЫ — Bowtie строит их
# внутри runner'а из hazard/threats/consequences, а не возвращает напрямую.
# Пер-методика-специфичная валидация выполняется в соответствующих runner'ах.
_REQUIRED_RESPONSE_KEYS = {
    "summary",
    "recommendations",
}

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

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """Имя модели (для тестов и логирования)."""
        return self.model

    async def complete(
        self,
        system_prompt: str,
        user_prompt:   str,
        *,
        temperature: float = 0.2,
        max_tokens:  int   = 4096,
    ) -> dict:
        """
        Отправить запрос к LLM и вернуть валидированный dict.

        Returns:
            dict — разобранный JSON + ключ _meta.

        Raises:
            LLMResponseValidationError: JSON невалиден или отсутствуют обязательные ключи.
        """
        try:
            raw = await self._complete_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except RetryError as exc:
            raise LLMResponseValidationError(
                f"LLM не вернул валидный ответ после {self.max_retries} попыток."
            ) from exc
        return raw

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _complete_with_retry(
        self,
        system_prompt: str,
        user_prompt:   str,
        temperature:   float,
        max_tokens:    int,
    ) -> dict:
        """Вызов LLM с retry/backoff через tenacity."""

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
            )

        return await _inner()

    async def _call_api(
        self,
        *,
        system_prompt: str,
        user_prompt:   str,
        temperature:   float,
        max_tokens:    int,
    ) -> dict:
        """Один HTTP-запрос к OpenRouter."""
        if self._http is None:
            raise RuntimeError("OpenRouterClient используется вне контекстного менеджера.")

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

        logger.debug("[OpenRouter] → model=%s tokens_max=%d", self.model, max_tokens)

        response = await self._http.post("/chat/completions", json=payload)

        if response.status_code == 429:
            logger.warning("[OpenRouter] Rate limit — retry...")
            raise httpx.TransportError("Rate limit 429")

        if response.status_code >= 500:
            logger.error("[OpenRouter] Ошибка сервера %d", response.status_code)
            raise httpx.TransportError(f"Server error {response.status_code}")

        response.raise_for_status()

        data = response.json()

        # OpenRouter может вернуть HTTP 200 с полем 'error' вместо 'choices'
        # (например: модель перегружена, квота исчерпана, провайдер недоступен).
        # В этом случае KeyError на data["choices"] приводил к необработанному краху.
        # Теперь явно извлекаем сообщение и бросаем LLMResponseValidationError,
        # чтобы tenacity мог сделать retry.
        if "choices" not in data:
            err = data.get("error", {})
            err_msg = (
                err.get("message")
                or err.get("code")
                or str(data)
            )
            logger.error(
                "[OpenRouter] Нет 'choices' в ответе (HTTP 200). error=%s full=%s",
                err_msg,
                str(data)[:300],
            )
            raise LLMResponseValidationError(
                f"OpenRouter вернул ответ без 'choices': {err_msg}"
            )

        content = data["choices"][0]["message"]["content"]
        usage   = data.get("usage", {})

        parsed = self._parse_and_validate(content)
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

    def _parse_and_validate(self, content: str) -> dict:
        """
        Разобрать JSON и проверить минимальный набор ключей.

        Снимает забор ```json...``` если LLM вернула markdown.
        """
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

        missing = _REQUIRED_RESPONSE_KEYS - set(parsed.keys())
        if missing:
            logger.warning("[OpenRouter] Отсутствуют ключи: %s", missing)
            raise LLMResponseValidationError(
                f"Ответ LLM не содержит обязательных ключей: {missing}"
            )

        return parsed

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        """Удаляет ```json...``` забор если LLM вернула markdown вместо чистого JSON."""
        m = _MD_FENCE_RE.match(content.strip())
        return m.group(1) if m else content
