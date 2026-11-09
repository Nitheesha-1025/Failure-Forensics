from __future__ import annotations

import json

import httpx
import pytest

from forensics.llm_client import ChatMessage, LLMClient, LLMError
from forensics.logging import configure, get_logger


@pytest.mark.asyncio
async def test_llm_client_returns_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(api_key="k", client=transport, max_retries=0)
    try:
        resp = await client.chat(
            model="gpt-4o-mini", messages=[ChatMessage(role="user", content="x")]
        )
    finally:
        await client.aclose()
    assert resp.content == "hi"
    assert resp.prompt_tokens == 3


@pytest.mark.asyncio
async def test_llm_client_raises_on_400() -> None:
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(400, text="bad"))
    )
    client = LLMClient(api_key="k", client=transport, max_retries=0)
    try:
        with pytest.raises(LLMError) as ei:
            await client.chat(
                model="gpt-4o-mini", messages=[ChatMessage(role="user", content="x")]
            )
        assert ei.value.status == 400
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_openai_client_sends_json_response_format() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(api_key="k", client=transport, max_retries=0)
    try:
        await client.chat(
            model="gpt-4o-mini",
            messages=[ChatMessage(role="user", content="x")],
            response_format={"type": "json_object"},
        )
    finally:
        await client.aclose()
    body = captured["body"]
    assert isinstance(body, dict)
    assert body.get("response_format") == {"type": "json_object"}


def test_logging_configure_idempotent() -> None:
    configure("INFO")
    configure("DEBUG")  # second call is a no-op
    log = get_logger("t")
    log.info("ok")
