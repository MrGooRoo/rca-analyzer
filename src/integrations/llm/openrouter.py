"""
\u041a\u043b\u0438\u0435\u043d\u0442 OpenRouter \u0434\u043b\u044f \u0432\u044b\u0437\u043e\u0432\u0430 LLM.

\u041e\u0441\u043e\u0431\u0435\u043d\u043d\u043e\u0441\u0442\u0438:
- \u0410\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439 retry \u0441 exponential backoff (tenacity)
- \u0412\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u044f \u043c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u043e\u0433\u043e JSON-\u0444\u043e\u0440\u043c\u0430\u0442\u0430 (contracts.md \u0440\u0430\u0437\u0434\u0435\u043b 6)
- \u0421\u043d\u044f\u0442\u0438\u0435 \u043c\u0430\u0440\u043a\u0434\u0430\u0443\u043d-\u0437\u0430\u0431\u043e\u0440\u0430 ```json ... ``` \u043f\u0435\u0440\u0435\u0434 \u043f\u0430\u0440\u0441\u0438\u043d\u0433\u043e\u043c
- \u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u0438\u0445 \u043c\u043e\u0434\u0435\u043b\u0435\u0439 \u0447\u0435\u0440\u0435\u0437 \u043f\u0435\u0440\u0435\u043c\u0435\u043d\u043d\u0443\u044e \u043e\u043a\u0440\u0443\u0436\u0435\u043d\u0438\u044f
- \u0412\u0441\u0435 HTTP-\u043e\u0448\u0438\u0431\u043a\u0438 \u043e\u0431\u043e\u0440\u0430\u0447\u0438\u0432\u0430\u044e\u0442\u0441\u044f \u0432 LLMResponseValidationError

\u041f\u0435\u0440\u0435\u043c\u0435\u043d\u043d\u044b\u0435 \u043e\u043a\u0440\u0443\u0436\u0435\u043d\u0438\u044f (settings.py / .env):
    OPENROUTER_API_KEY      \u2014 \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e
    OPENROUTER_MODEL        \u2014 \u043f\u043e \u0443\u043c\u043e\u043b\u0447\u0430\u043d\u0438\u044e openai/gpt-4o-mini
    OPENROUTER_TIMEOUT      \u2014 \u0441\u0435\u043a\u0443\u043d\u0434\u044b, \u043f\u043e \u0443\u043c\u043e\u043b\u0447\u0430\u043d\u0438\u044e 60
    OPENROUTER_MAX_RETRIES  \u2014 \u043f\u043e \u0443\u043c\u043e\u043b\u0447\u0430\u043d\u0438\u044e 3
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

# \u041c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u043e \u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c\u044b\u0435 \u043a\u043b\u044e\u0447\u0438 \u0432\u043e \u0432\u0441\u0435\u0445 \u043c\u0435\u0442\u043e\u0434\u0438\u043a\u0430\u0445 (contracts.md \u0440\u0430\u0437\u0434\u0435\u043b 6)
# \u041f\u0435\u0440-\u043c\u0435\u0442\u043e\u0434\u0438\u043a\u0430-\u0441\u043f\u0435\u0446\u0438\u0444\u0438\u0447\u043d\u044b\u0435 \u043a\u043b\u044e\u0447\u0438 (top_event, barriers) \u043f\u0440\u043e\u0432\u0435\u0440\u044f\u044e\u0442\u0441\u044f \u0432 runner'\u0430\u0445
_REQUIRED_RESPONSE_KEYS = {
    "immediate_causes",
    "root_causes",
    "summary",
    "recommendations",
}

# \u0420\u0435\u0433\u0443\u043b\u044f\u0440\u043a\u0430 \u0434\u043b\u044f \u0441\u043d\u044f\u0442\u0438\u044f markdown-\u0437\u0430\u0431\u043e\u0440\u0430 ```json ... ```
_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


class OpenRouterClient:
    """
    \u0410\u0441\u0438\u043d\u0445\u0440\u043e\u043d\u043d\u044b\u0439 \u043a\u043b\u0438\u0435\u043d\u0442 \u0434\u043b\u044f OpenRouter API.

    \u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435:
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
        """\u0418\u043c\u044f \u043c\u043e\u0434\u0435\u043b\u0438 (\u0434\u043b\u044f \u0442\u0435\u0441\u0442\u043e\u0432 \u0438 \u043b\u043e\u0433\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f)."""
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
        \u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441 \u043a LLM \u0438 \u0432\u0435\u0440\u043d\u0443\u0442\u044c \u0432\u0430\u043b\u0438\u0434\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439 dict.

        Returns:
            dict \u2014 \u0440\u0430\u0437\u043e\u0431\u0440\u0430\u043d\u043d\u044b\u0439 JSON + \u043a\u043b\u044e\u0447 _meta.

        Raises:
            LLMResponseValidationError: JSON \u043d\u0435\u0432\u0430\u043b\u0438\u0434\u0435\u043d \u0438\u043b\u0438 \u043e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u044e\u0442 \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u043a\u043b\u044e\u0447\u0438.
        """
        try:
            raw = await self._complete_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except RetryError as exc:
            original = exc.last_attempt.exception()
            msg = str(original) if original else f"LLM \u043d\u0435 \u043e\u0442\u0432\u0435\u0442\u0438\u043b \u0432\u0430\u043b\u0438\u0434\u043d\u044b\u043c JSON \u043f\u043e\u0441\u043b\u0435 {self.max_retries} \u043f\u043e\u043f\u044b\u0442\u043e\u043a."
            raise LLMResponseValidationError(msg) from exc
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
        """\u0412\u044b\u0437\u043e\u0432 LLM \u0441 retry/backoff \u0447\u0435\u0440\u0435\u0437 tenacity."""

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
        """\u041e\u0434\u0438\u043d HTTP-\u0437\u0430\u043f\u0440\u043e\u0441 \u043a OpenRouter."""
        if self._http is None:
            raise RuntimeError("OpenRouterClient \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442\u0441\u044f \u0432\u043d\u0435 \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0433\u043e \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0430.")

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

        logger.debug("[OpenRouter] \u2192 model=%s tokens_max=%d", self.model, max_tokens)

        response = await self._http.post("/chat/completions", json=payload)

        if response.status_code == 429:
            logger.warning("[OpenRouter] Rate limit \u2014 retry...")
            raise httpx.TransportError("Rate limit 429")

        if response.status_code >= 500:
            logger.error("[OpenRouter] \u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0440\u0432\u0435\u0440\u0430 %d", response.status_code)
            raise httpx.TransportError(f"Server error {response.status_code}")

        response.raise_for_status()

        data    = response.json()
        content = data["choices"][0]["message"]["content"]
        usage   = data.get("usage", {})

        parsed = self._parse_and_validate(content)
        parsed["_meta"] = {
            "model":  self.model,
            "tokens": usage.get("total_tokens", 0),
        }

        logger.info(
            "[OpenRouter] \u2190 model=%s tokens=%d keys=%s",
            self.model,
            parsed["_meta"]["tokens"],
            [k for k in parsed if not k.startswith("_")],
        )

        return parsed

    def _parse_and_validate(self, content: str) -> dict:
        """
        \u0420\u0430\u0437\u043e\u0431\u0440\u0430\u0442\u044c JSON \u0438 \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u043c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439 \u043d\u0430\u0431\u043e\u0440 \u043a\u043b\u044e\u0447\u0435\u0439.

        \u0421\u043d\u0438\u043c\u0430\u0435\u0442 \u0437\u0430\u0431\u043e\u0440 ```json...``` \u0435\u0441\u043b\u0438 LLM \u0432\u0435\u0440\u043d\u0443\u043b\u0430 markdown.
        """
        content = self._strip_markdown_fence(content)

        try:
            parsed: dict = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("[OpenRouter] \u041d\u0435\u0432\u0430\u043b\u0438\u0434\u043d\u044b\u0439 JSON: %.200s", content)
            raise LLMResponseValidationError(
                f"LLM \u0432\u0435\u0440\u043d\u0443\u043b \u043d\u0435\u0432\u0430\u043b\u0438\u0434\u043d\u044b\u0439 JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise LLMResponseValidationError(
                f"LLM \u0432\u0435\u0440\u043d\u0443\u043b {type(parsed).__name__}, \u043e\u0436\u0438\u0434\u0430\u043b\u0441\u044f dict."
            )

        missing = _REQUIRED_RESPONSE_KEYS - set(parsed.keys())
        if missing:
            logger.warning("[OpenRouter] \u041e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u044e\u0442 \u043a\u043b\u044e\u0447\u0438: %s", missing)
            raise LLMResponseValidationError(
                f"\u041e\u0442\u0432\u0435\u0442 LLM \u043d\u0435 \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u0442 \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u043a\u043b\u044e\u0447\u0435\u0439: {missing}"
            )

        return parsed

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        """\u0423\u0434\u0430\u043b\u044f\u0435\u0442 ```json...``` \u0437\u0430\u0431\u043e\u0440 \u0435\u0441\u043b\u0438 LLM \u0432\u0435\u0440\u043d\u0443\u043b markdown \u0432\u043c\u0435\u0441\u0442\u043e \u0447\u0438\u0441\u0442\u043e\u0433\u043e JSON."""
        m = _MD_FENCE_RE.match(content.strip())
        return m.group(1) if m else content
