"""Unit tests for HttpChatLLMClient (OpenAI-compatible HTTP)."""

import httpx
import pytest

from cinemind.llm.client import HttpChatLLMClient, LLMResponse


@pytest.mark.asyncio
async def test_chat_completions_create_parses_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="http://test.local/v1/", transport=transport) as http:
        client = HttpChatLLMClient(http)
        resp = await client.chat_completions_create(
            "test-model",
            [{"role": "user", "content": "hi"}],
            temperature=0.5,
            max_tokens=100,
        )
    assert isinstance(resp, LLMResponse)
    assert resp.content == "hello"
    assert resp.usage == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


@pytest.mark.asyncio
async def test_chat_completions_create_maps_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="nope")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="http://test.local/v1/", transport=transport) as http:
        client = HttpChatLLMClient(http)
        with pytest.raises(ValueError, match="401"):
            await client.chat_completions_create("m", [{"role": "user", "content": "x"}])
