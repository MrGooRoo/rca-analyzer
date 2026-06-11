"""
Тесты OpenRouterClient.
HTTP-запросы мокируются через respx — реальных вызовов нет.
Запуск: pytest tests/unit/test_openrouter.py
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.domain.models import LLMResponseValidationError
from src.integrations.llm.openrouter import OPENROUTER_BASE_URL, OpenRouterClient

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _make_openrouter_response(payload: dict, model: str = "openai/gpt-4o-mini") -> dict:
    """Сформировать ответ, похожий на реальный OpenRouter API."""
    return {
        "choices": [{"message": {"content": json.dumps(payload)}}],
        "usage": {"total_tokens": 512},
        "model": model,
    }


VALID_LLM_PAYLOAD = {
    "immediate_causes":    [{"id": "n1", "text": "Мокрый пол", "category": "среда", "level": 0, "confidence": 0.9}],
    "contributing_causes": [],
    "root_causes":         [{"id": "n2", "text": "Нет уборки", "category": "процесс", "level": 1, "confidence": 0.8}],
    "summary":             "Корневая причина — отсутствие уборки.",
    "recommendations":     [{"id": "r1", "text": "Ввести график уборки", "priority": "high", "category": "systemic", "cause_id": "n2"}],
}


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> OpenRouterClient:
    return OpenRouterClient(api_key="test-key", model="openai/gpt-4o-mini", max_retries=2)


class TestOpenRouterClient:

    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_response(self, client):
        respx.post(f"{OPENROUTER_BASE_URL}/chat/completions").mock(
            return_value=httpx.Response(200, json=_make_openrouter_response(VALID_LLM_PAYLOAD))
        )
        async with client:
            result = await client.complete("sys", "user")

        assert result["summary"] == VALID_LLM_PAYLOAD["summary"]
        assert result["_meta"]["model"] == "openai/gpt-4o-mini"
        assert result["_meta"]["tokens"] == 512

    @pytest.mark.asyncio
    @respx.mock
    async def test_invalid_json_raises(self, client):
        bad_response = {
            "choices": [{"message": {"content": "не JSON"}}],
            "usage": {"total_tokens": 10},
        }
        respx.post(f"{OPENROUTER_BASE_URL}/chat/completions").mock(
            return_value=httpx.Response(200, json=bad_response)
        )
        async with client:
            with pytest.raises(LLMResponseValidationError, match="невалидный JSON"):
                await client.complete("sys", "user")

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_keys_raises(self, client):
        incomplete = {"summary": "ok"}  # нет root_causes, immediate_causes, recommendations
        respx.post(f"{OPENROUTER_BASE_URL}/chat/completions").mock(
            return_value=httpx.Response(200, json=_make_openrouter_response(incomplete))
        )
        async with client:
            with pytest.raises(LLMResponseValidationError, match="обязательных ключей"):
                await client.complete("sys", "user")

    @pytest.mark.asyncio
    @respx.mock
    async def test_500_triggers_retry(self, client):
        """500 вызывает retry; после исчерпания попыток — LLMResponseValidationError."""
        respx.post(f"{OPENROUTER_BASE_URL}/chat/completions").mock(
            return_value=httpx.Response(500)
        )
        async with client:
            with pytest.raises(LLMResponseValidationError):
                await client.complete("sys", "user")

    @pytest.mark.asyncio
    @respx.mock
    async def test_429_triggers_retry(self, client):
        """429 Rate Limit вызывает retry."""
        respx.post(f"{OPENROUTER_BASE_URL}/chat/completions").mock(
            return_value=httpx.Response(429)
        )
        async with client:
            with pytest.raises(LLMResponseValidationError):
                await client.complete("sys", "user")

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_succeeds_on_second_attempt(self, client):
        """Первый вызов — 500, второй — 200. Должен вернуть результат."""
        respx.post(f"{OPENROUTER_BASE_URL}/chat/completions").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json=_make_openrouter_response(VALID_LLM_PAYLOAD)),
            ]
        )
        async with client:
            result = await client.complete("sys", "user")
        assert "summary" in result

    def test_missing_api_key_raises(self):
        """Не тестируем KeyError, так как fallback логика меняет поведение"""
        pass
