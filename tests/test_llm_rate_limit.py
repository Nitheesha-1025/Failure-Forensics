from __future__ import annotations

import json

import httpx
import pytest

from forensics.llm_client import (
    ChatMessage,
    LLMClient,
    LLMError,
    LLMQuotaExhaustedError,
    _RetryableError,
)


@pytest.mark.asyncio
async def test_quota_429_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.dumps(
            {
                "error": {
                    "code": 429,
                    "message": "You exceeded your current quota.",
                    "status": "RESOURCE_EXHAUSTED",
                }
            }
        )
        return httpx.Response(429, text=body)

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(api_key="k", client=transport, max_retries=3, api_kind="openai")
    try:
        with pytest.raises(LLMQuotaExhaustedError):
            await client.chat(
                model="gpt-4o-mini", messages=[ChatMessage(role="user", content="x")]
            )
    finally:
        await client.aclose()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_http_402_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(402, text="payment required")

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(api_key="k", client=transport, max_retries=3, api_kind="openai")
    try:
        with pytest.raises(LLMError) as ei:
            await client.chat(
                model="gpt-4o-mini", messages=[ChatMessage(role="user", content="x")]
            )
        assert ei.value.status == 402
    finally:
        await client.aclose()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_transient_429_retries_then_raises() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="rate limit", headers={"Retry-After": "0"})

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(api_key="k", client=transport, max_retries=2, api_kind="openai")
    try:
        with pytest.raises(_RetryableError) as ei:
            await client.chat(
                model="gpt-4o-mini", messages=[ChatMessage(role="user", content="x")]
            )
        assert ei.value.status == 429
    finally:
        await client.aclose()
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_503_is_retryable() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(api_key="k", client=transport, max_retries=2, api_kind="openai")
    try:
        resp = await client.chat(
            model="gpt-4o-mini", messages=[ChatMessage(role="user", content="x")]
        )
    finally:
        await client.aclose()
    assert resp.content == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_cloudflare_empty_result_raises_llm_error() -> None:
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": ""},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
    )
    client = LLMClient(
        api_key="k",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=transport,
        max_retries=0,
        api_kind="cloudflare",
    )
    try:
        with pytest.raises(LLMError, match="empty content"):
            await client.chat(
                model="@cf/meta/llama-3.1-8b-instruct",
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cloudflare_success_false_raises() -> None:
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "success": False,
                    "errors": [{"message": "model input invalid"}],
                },
            )
        )
    )
    client = LLMClient(
        api_key="k",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=transport,
        max_retries=0,
        api_kind="cloudflare",
    )
    try:
        with pytest.raises(LLMError, match="model input invalid"):
            await client.chat(
                model="@cf/meta/llama-3.1-8b-instruct",
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_cloudflare_malformed_json_body() -> None:
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="not-json"))
    )
    client = LLMClient(
        api_key="k",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=transport,
        max_retries=0,
        api_kind="cloudflare",
    )
    try:
        with pytest.raises(LLMError, match="malformed JSON"):
            await client.chat(
                model="@cf/meta/llama-3.1-8b-instruct",
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()
