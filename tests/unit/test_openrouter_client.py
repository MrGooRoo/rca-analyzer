"""
Тесты OpenRouterClient (с моком httpx).
Запуск: pytest tests/unit/test_openrouter_client.py
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models import LLMResponseValidationError
from src.integrations.llm.openrouter import OpenRouterClient

_VALID_PAYLOAD = {
    "immediate_causes": [{"id": "1", "text": "test", "category": "ч", "level": 0,
                          "parent_id": None, "confidence": 0.9}],
    "root_causes":       [{"id": "2", "text": "root", "category": "у", "level": 1,
                          "parent_id": "1", "confidence": 0.8}],
    "summary":           "Test summary",
    "recommendations":   [{"id": "r1", "text": "fix it", "priority": "high",
                          "category": "immediate", "cause_id": "2"}],
}


@pytest.fixture(autouse=True)
async def reset_shared_client():
    """Сбросить общий httpx-клиент между тестами, чтобы изоляция не ломалась."""
    await OpenRouterClient.close_shared()
    yield
    await OpenRouterClient.close_shared()


def _make_httpx_response(payload: dict, status: int = 200):
    """Собрать mock httpx.Response с заданным пейлоадом."""
    content = json.dumps({
        "choices": [{"message": {"content": json.dumps(payload)}}],
        "usage":   {"total_tokens": 500},
    })
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json.loads(content)
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def client():
    return OpenRouterClient(api_key="test-key", model="openai/gpt-4o", max_retries=1)


class TestOpenRouterClient:
    def test_model_name_property(self, client):
        assert client.model_name == "openai/gpt-4o"

    @pytest.mark.asyncio
    async def test_complete_happy_path(self, client):
        mock_resp = _make_httpx_response(_VALID_PAYLOAD)

        async with client:
            client._http = AsyncMock()
            client._http.post = AsyncMock(return_value=mock_resp)
            result = await client.complete("sys", "usr")

        assert result["summary"] == "Test summary"
        assert result["_meta"]["model"] == "openai/gpt-4o"
        assert result["_meta"]["tokens"] == 500

    @pytest.mark.asyncio
    async def test_complete_strips_markdown_fence(self, client):
        fenced = f"```json\n{json.dumps(_VALID_PAYLOAD)}\n```"
        resp_data = {
            "choices": [{"message": {"content": fenced}}],
            "usage":   {"total_tokens": 100},
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = resp_data
        mock_resp.raise_for_status = MagicMock()

        async with client:
            client._http = AsyncMock()
            client._http.post = AsyncMock(return_value=mock_resp)
            result = await client.complete("sys", "usr")

        assert result["summary"] == "Test summary"

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self, client):
        bad = {"choices": [{"message": {"content": "not json at all"}}], "usage": {}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = bad
        mock_resp.raise_for_status = MagicMock()

        async with client:
            client._http = AsyncMock()
            client._http.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(LLMResponseValidationError, match="JSON"):
                await client.complete("sys", "usr")

    @pytest.mark.asyncio
    async def test_missing_required_keys_raises(self, client):
        partial = {"summary": "ok", "recommendations": []}  # missing immediate_causes, root_causes
        mock_resp = _make_httpx_response(partial)

        async with client:
            client._http = AsyncMock()
            client._http.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(LLMResponseValidationError):
                await client.complete("sys", "usr", required_keys={"immediate_causes"})

    @pytest.mark.asyncio
    async def test_non_dict_json_raises(self, client):
        arr_resp = {"choices": [{"message": {"content": json.dumps([1, 2, 3])}}], "usage": {}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = arr_resp
        mock_resp.raise_for_status = MagicMock()

        async with client:
            client._http = AsyncMock()
            client._http.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(LLMResponseValidationError, match="dict"):
                await client.complete("sys", "usr")

    @pytest.mark.asyncio
    async def test_rate_limit_raises_transport_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 429

        async with client:
            client._http = AsyncMock()
            client._http.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(LLMResponseValidationError):
                await client.complete("sys", "usr")

    @pytest.mark.asyncio
    async def test_server_error_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        async with client:
            client._http = AsyncMock()
            client._http.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(LLMResponseValidationError):
                await client.complete("sys", "usr")

    def test_strip_markdown_fence_extracts_json(self, client):
        payload = '{"key": "value"}'
        fenced  = f"```json\n{payload}\n```"
        assert client._strip_markdown_fence(fenced) == payload

    def test_strip_markdown_fence_passthrough_plain(self, client):
        plain = '{"key": "value"}'
        assert client._strip_markdown_fence(plain) == plain

    @pytest.mark.asyncio
    async def test_shared_client_reused_between_instances(self):
        """Несколько OpenRouterClient должны переиспользовать один httpx-клиент."""
        c1 = OpenRouterClient(api_key="k1", model="m1")
        c2 = OpenRouterClient(api_key="k2", model="m2")

        async with c1:
            shared_http = c1._http
            assert shared_http is not None
            assert OpenRouterClient._shared_refs == 1

            async with c2:
                assert c2._http is shared_http
                assert OpenRouterClient._shared_refs == 2

            # c2 вышел, но клиент остаётся открытым из-за c1
            assert OpenRouterClient._shared_refs == 1
            assert OpenRouterClient._shared_http is shared_http

        # c1 вышел — клиент должен закрыться
        assert OpenRouterClient._shared_refs == 0
        assert OpenRouterClient._shared_http is None
