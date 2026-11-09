"""Cloudflare Workers AI OpenAI-compatible request URL and body (mocked HTTP)."""

from __future__ import annotations

import json

import httpx
import pytest

from forensics.llm_client import ChatMessage, LLMClient, _cloudflare_chat_completions_url


def test_cloudflare_chat_completions_url() -> None:
    url = _cloudflare_chat_completions_url(
        "https://api.cloudflare.com/client/v4",
        "d26d5e92e6f884bdfd7b5e8b0ceddec4",
    )
    assert url == (
        "https://api.cloudflare.com/client/v4/accounts/"
        "d26d5e92e6f884bdfd7b5e8b0ceddec4/ai/v1/chat/completions"
    )
    assert "/ai/run/" not in url
    assert "%40" not in url


@pytest.mark.asyncio
async def test_cloudflare_post_chat_completions_payload() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    account_id = "d26d5e92e6f884bdfd7b5e8b0ceddec4"
    model = "@cf/zai-org/glm-4.7-flash"
    client = LLMClient(
        api_key="test-token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id=account_id,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
        api_kind="cloudflare",
    )
    try:
        await client.chat(
            model=model,
            messages=[
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="Hello"),
            ],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
    finally:
        await client.aclose()

    assert seen["url"] == _cloudflare_chat_completions_url(
        "https://api.cloudflare.com/client/v4", account_id
    )
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == model
    assert body["stream"] is False
    assert body["messages"] == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 512
    assert body["response_format"] == {"type": "json_object"}
