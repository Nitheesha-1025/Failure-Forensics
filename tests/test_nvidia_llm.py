"""NVIDIA NIM (Muse Glimmer) via OpenAI-compatible chat/completions (mocked HTTP)."""

from __future__ import annotations

import json

import httpx
import pytest

from forensics.config import Settings
from forensics.llm_client import (
    ChatMessage,
    LLMClient,
    LLMError,
    LLMQuotaExhaustedError,
    _RetryableError,
)
from forensics.llm_config import (
    NVIDIA_API_BASE_URL,
    NVIDIA_DEFAULT_MODEL,
    LLMConfigurationError,
    build_llm_client,
    resolve_llm_settings,
)


def _nvidia_settings(**overrides: object) -> Settings:
    base = {
        "llm_provider": "nvidia",
        "nvidia_api_key": "nvidia-test-key",
        "nvidia_base_url": NVIDIA_API_BASE_URL,
        "nvidia_model": NVIDIA_DEFAULT_MODEL,
        "opencode_zen_api_key": "",
        "cloudflare_account_id": "",
        "cloudflare_api_token": "",
        "openai_api_key": "",
    }
    base.update(overrides)
    return Settings(**base)


def test_resolve_nvidia_requires_api_key() -> None:
    with pytest.raises(LLMConfigurationError, match="NVIDIA_API_KEY"):
        resolve_llm_settings(_nvidia_settings(nvidia_api_key=""))


def test_resolve_nvidia_model_and_base_url() -> None:
    resolved = resolve_llm_settings(_nvidia_settings())
    assert resolved.provider == "nvidia"
    assert resolved.base_url == NVIDIA_API_BASE_URL
    assert resolved.judge_model == NVIDIA_DEFAULT_MODEL


def test_build_llm_client_nvidia_api_kind() -> None:
    resolved = resolve_llm_settings(_nvidia_settings())
    client = build_llm_client(resolved, settings=_nvidia_settings())
    assert client.api_kind == "nvidia"


@pytest.mark.asyncio
async def test_nvidia_chat_completions_success() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"fields": {}, "confidence": 0.9}',
                            "reasoning_content": "thinking only",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

    resolved = resolve_llm_settings(_nvidia_settings())
    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        client=transport,
        max_retries=0,
        api_kind="nvidia",
        nvidia_output_token_floor=1024,
        nvidia_output_token_ceiling=8192,
    )
    try:
        resp = await client.chat(
            model=NVIDIA_DEFAULT_MODEL,
            messages=[ChatMessage(role="user", content="extract")],
            max_tokens=200,
            response_format={"type": "json_object"},
        )
    finally:
        await client.aclose()

    assert resp.content == '{"fields": {}, "confidence": 0.9}'
    assert seen["url"] == f"{NVIDIA_API_BASE_URL}/chat/completions"
    assert seen["auth"] == "Bearer nvidia-test-key"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == NVIDIA_DEFAULT_MODEL
    assert body["stream"] is False
    assert body["top_p"] == 0.95
    assert body["max_tokens"] == 1024
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_nvidia_empty_answer_with_reasoning_raises() -> None:
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "reasoning_content": "chain-of-thought only",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        )
    )
    client = LLMClient(
        api_key="k",
        base_url=NVIDIA_API_BASE_URL,
        client=transport,
        max_retries=0,
        api_kind="nvidia",
    )
    try:
        with pytest.raises(LLMError, match="empty content") as ei:
            await client.chat(
                model=NVIDIA_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
        assert "chain-of-thought" not in str(ei.value)
        assert "reasoning_content_present=True" in str(ei.value)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_nvidia_http_401_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, text="unauthorized")

    client = LLMClient(
        api_key="bad",
        base_url=NVIDIA_API_BASE_URL,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=2,
        api_kind="nvidia",
    )
    try:
        with pytest.raises(LLMError) as ei:
            await client.chat(
                model=NVIDIA_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
        assert ei.value.status == 401
    finally:
        await client.aclose()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_nvidia_http_402_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(402, text="payment required")

    client = LLMClient(
        api_key="k",
        base_url=NVIDIA_API_BASE_URL,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=3,
        api_kind="nvidia",
    )
    try:
        with pytest.raises(LLMError) as ei:
            await client.chat(
                model=NVIDIA_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
        assert ei.value.status == 402
    finally:
        await client.aclose()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_nvidia_rate_limit_retries() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="rate limit", headers={"Retry-After": "0"})

    client = LLMClient(
        api_key="k",
        base_url=NVIDIA_API_BASE_URL,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=2,
        api_kind="nvidia",
    )
    try:
        with pytest.raises(_RetryableError):
            await client.chat(
                model=NVIDIA_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_nvidia_503_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, text="unavailable")
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

    client = LLMClient(
        api_key="k",
        base_url=NVIDIA_API_BASE_URL,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=2,
        api_kind="nvidia",
    )
    try:
        resp = await client.chat(
            model=NVIDIA_DEFAULT_MODEL,
            messages=[ChatMessage(role="user", content="x")],
        )
    finally:
        await client.aclose()
    assert resp.content == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_nvidia_timeout_is_retryable() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timed out", request=request)

    client = LLMClient(
        api_key="k",
        base_url=NVIDIA_API_BASE_URL,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=1,
        api_kind="nvidia",
    )
    try:
        with pytest.raises(_RetryableError):
            await client.chat(
                model=NVIDIA_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_nvidia_malformed_json_response() -> None:
    client = LLMClient(
        api_key="k",
        base_url=NVIDIA_API_BASE_URL,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, text="not-json"))
        ),
        max_retries=0,
        api_kind="nvidia",
    )
    try:
        with pytest.raises(LLMError, match="malformed JSON"):
            await client.chat(
                model=NVIDIA_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_nvidia_quota_429_not_retried() -> None:
    calls = {"n": 0}
    body = json.dumps(
        {
            "error": {
                "message": "You exceeded your current quota.",
                "status": "RESOURCE_EXHAUSTED",
            }
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text=body)

    client = LLMClient(
        api_key="k",
        base_url=NVIDIA_API_BASE_URL,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=3,
        api_kind="nvidia",
    )
    try:
        with pytest.raises(LLMQuotaExhaustedError):
            await client.chat(
                model=NVIDIA_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()
    assert calls["n"] == 1
