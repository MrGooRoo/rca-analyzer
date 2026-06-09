"""
Клиент OpenRouter для вызова LLM.

Особенности:
- Автоматический retry с exponential backoff (tenacity)
- Валидация минимального JSON-формата (contracts.md раздел 6)
- Снятие маркдаун-забора ```json ... ``` перед парсингом
- Поддержка нескольких моделей через переменную окружения
- Все HTTP-ошибки оборачиваются в LLMResponseValidationError
- response_format json_object не передаётся моделям из _NO_JSON_FORMAT_MODELS

Переменные окружения (settings.py / .env):
    OPENROUTER_API_KEY      — обязательно
    OPENROUTER_MODEL        — по умолчанию openai/gpt-4o-mini
    OPENROUTER_TIMEOUT      — секунды, по умолчанию 120
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
_DEFAULT_REQUIRED_KEYS: frozenset[str] = frozenset({"summary", "recommendations"})

# Регулярка для снятия markdown-забора ```json ... ```
_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)

# Модели, которые не поддерживают response_format={"type": "json_object"}
_NO_JSON_FORMAT_MODELS: frozenset[str] = frozenset({
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-4-scout:free",
    "meta-llama/llama-4-maverick:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen3-8b:free",
    "qwen/qwen3-14b:free",
    "qwen/qwen3-30b-a3b:free",
})


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
        fallback_models: list[str] | None = None,
        timeout:     int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.api_key     = api_key     or os.environ.get("OPENROUTER_API_KEY", "")
        self.primary_model = model     or os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
        
        if fallback_models is None:
            fb_env = os.getenv("OPENROUTER_FALLBACK_MODELS", "")
            if fb_env:
                self.fallback_models = [m.strip() for m in fb_env.split(",") if m.strip()]
            else:
                self.fallback_models = [
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "qwen/qwen3-30b-a3b:free",
                ]
        else:
            self.fallback_models = fallback_models
            
        self.timeout     = timeout     or int(os.getenv("OPENROUTER_TIMEOUT", "120"))
        self.max_retries = max_retries or int(os.getenv("OPENROUTER_MAX_RETRIES", "3"))

        self._http: httpx.AsyncClient | None = None
        self.current_model = self.primary_model

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
        return self.current_model

    async def complete(
        self,
        system_prompt: str,
        user_prompt:   str,
        *,
        temperature:   float = 0.2,
        max_tokens:    int   = 8192,
        required_keys: frozenset[str] | set[str] | None = None,
    ) -> dict:
        """
        Отправить запрос к LLM и вернуть валидированный dict.

        Args:
            required_keys: обязательные ключи в ответе LLM.
                           None → используется _DEFAULT_REQUIRED_KEYS.
                           Передайте пустой set() чтобы отключить валидацию ключей.
        """
        _required = _DEFAULT_REQUIRED_KEYS if required_keys is None else frozenset(required_keys)

        try:
            raw = await self._complete_with_fallbacks(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                required_keys=_required,
            )
        except RetryError as exc:
            if exc.last_attempt and exc.last_attempt.exception():
                orig_exc = exc.last_attempt.exception()
                if isinstance(orig_exc, LLMResponseValidationError):
                    raise orig_exc from exc
            raise LLMResponseValidationError(
                f"Не удалось получить валидный ответ ни от одной модели (включая fallbacks): {exc}"
            ) from exc
        except Exception as exc:
            raise LLMResponseValidationError(
                f"Не удалось получить валидный ответ ни от одной модели (включая fallbacks): {exc}"
            ) from exc
            
        return raw

    async def _complete_with_fallbacks(
        self,
        system_prompt: str,
        user_prompt:   str,
        temperature:   float,
        max_tokens:    int,
        required_keys: frozenset[str],
    ) -> dict:
        models_to_try = [self.primary_model] + self.fallback_models
        
        last_error = None
        for model in models_to_try:
            self.current_model = model
            logger.info(f"[OpenRouter] Попытка вызова модели: {model}")
            try:
                return await self._complete_with_retry(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    required_keys=required_keys,
                )
            except RetryError as exc:
                if exc.last_attempt and exc.last_attempt.exception():
                    last_error = exc.last_attempt.exception()
                else:
                    last_error = exc
                logger.warning(f"[OpenRouter] Модель {model} не справилась (RetryError): {last_error}")
                continue
            except LLMResponseValidationError as exc:
                logger.warning(f"[OpenRouter] Модель {model} не справилась: {exc}")
                last_error = exc
                continue
                
        if last_error:
            raise last_error
        raise LLMResponseValidationError("Список моделей пуст")

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

        payload: dict[str, Any] = {
            "model":       self.current_model,
            "temperature": temperature,
            "max_tokens":  max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        }

        # response_format json_object поддерживают не все модели
        if self.current_model not in _NO_JSON_FORMAT_MODELS:
            payload["response_format"] = {"type": "json_object"}

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
            "model":  self.current_model,
            "tokens": usage.get("total_tokens", 0),
        }

        logger.info(
            "[OpenRouter] ← model=%s tokens=%d keys=%s",
            self.current_model,
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
