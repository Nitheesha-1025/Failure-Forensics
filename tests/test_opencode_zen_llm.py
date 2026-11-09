"""OpenCode Zen via Anthropic SDK (mocked; no live HTTP)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import httpx2
import pytest
from anthropic import APIStatusError, APITimeoutError, AsyncAnthropic
from httpx2 import MockTransport

from forensics.config import Settings
from forensics.llm_client import (
    ChatMessage,
    LLMClient,
    LLMError,
    _RetryableError,
    opencode_zen_messages_url,
)
from forensics.llm_config import (
    OPENCODE_ZEN_BASE_URL,
    OPENCODE_ZEN_DEFAULT_MODEL,
    LLMConfigurationError,
    build_llm_client,
    resolve_llm_settings,
)


def _zen_message_mock(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    usage = MagicMock()
    usage.input_tokens = 12
    usage.output_tokens = 8
    message = MagicMock()
    message.content = [block]
    message.usage = usage
    message.stop_reason = "end_turn"
    return message


def _zen_client_with_mock(create_mock: AsyncMock) -> tuple[LLMClient, AsyncMock]:
    anthropic = MagicMock()
    anthropic.messages.create = create_mock
    client = LLMClient(
        api_key="zen-test-key",
        base_url=OPENCODE_ZEN_BASE_URL,
        max_retries=0,
        api_kind="zen",
        anthropic_client=anthropic,
    )
    return client, create_mock


def test_resolve_zen_requires_api_key() -> None:
    with pytest.raises(LLMConfigurationError, match="OPENCODE_ZEN_API_KEY"):
        resolve_llm_settings(
            Settings(
                llm_provider="zen",
                opencode_zen_api_key="",
                cloudflare_account_id="",
                cloudflare_api_token="",
            )
        )


def test_resolve_zen_model_and_base_url() -> None:
    resolved = resolve_llm_settings(
        Settings(
            llm_provider="zen",
            opencode_zen_api_key="k",
            opencode_zen_base_url=OPENCODE_ZEN_BASE_URL,
            opencode_zen_model=OPENCODE_ZEN_DEFAULT_MODEL,
            cloudflare_account_id="",
            cloudflare_api_token="",
        )
    )
    assert resolved.provider == "zen"
    assert resolved.base_url == OPENCODE_ZEN_BASE_URL
    assert resolved.judge_model == OPENCODE_ZEN_DEFAULT_MODEL


def test_build_llm_client_zen_api_kind() -> None:
    resolved = resolve_llm_settings(
        Settings(
            llm_provider="zen",
            opencode_zen_api_key="k",
            cloudflare_account_id="",
            cloudflare_api_token="",
        )
    )
    client = build_llm_client(
        resolved,
        settings=Settings(opencode_zen_api_key="k", request_timeout_s=45.0),
    )
    assert client.api_kind == "zen"


@pytest.mark.asyncio
async def test_zen_messages_create_payload() -> None:
    create = AsyncMock(return_value=_zen_message_mock("hello"))
    client, _ = _zen_client_with_mock(create)
    try:
        resp = await client.chat(
            model=OPENCODE_ZEN_DEFAULT_MODEL,
            messages=[
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="Hi"),
            ],
        )
    finally:
        await client.aclose()

    assert resp.content == "hello"
    assert resp.prompt_tokens == 12
    kwargs = create.await_args.kwargs
    assert kwargs["model"] == OPENCODE_ZEN_DEFAULT_MODEL
    assert kwargs["messages"] == [{"role": "user", "content": "Hi"}]
    assert kwargs["system"] == "You are helpful."
    assert kwargs["max_tokens"] == 1024
    assert "temperature" not in kwargs


@pytest.mark.asyncio
async def test_zen_json_prompt_adds_system_suffix() -> None:
    create = AsyncMock(return_value=_zen_message_mock('{"ok": true}'))
    client, _ = _zen_client_with_mock(create)
    try:
        await client.chat(
            model=OPENCODE_ZEN_DEFAULT_MODEL,
            messages=[ChatMessage(role="user", content="x")],
            response_format={"type": "json_object"},
        )
    finally:
        await client.aclose()
    system = create.await_args.kwargs.get("system", "")
    assert "JSON" in system


@pytest.mark.asyncio
async def test_zen_empty_content_blocks_raises() -> None:
    empty = _zen_message_mock("")
    empty.content[0].text = ""
    create = AsyncMock(return_value=empty)
    client, _ = _zen_client_with_mock(create)
    try:
        with pytest.raises(LLMError, match="empty content") as ei:
            await client.chat(
                model=OPENCODE_ZEN_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
        assert "block_types" in str(ei.value)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_zen_malformed_sdk_response_raises() -> None:
    bad = MagicMock()
    bad.content = [{"type": "tool_use", "id": "call-1", "name": "fn"}]
    bad.usage = MagicMock(input_tokens=0, output_tokens=0)
    bad.stop_reason = "end_turn"
    create = AsyncMock(return_value=bad)
    client, _ = _zen_client_with_mock(create)
    try:
        with pytest.raises(LLMError, match="empty content"):
            await client.chat(
                model=OPENCODE_ZEN_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_zen_http_401_not_retried() -> None:
    response = httpx.Response(
        401,
        request=httpx.Request("POST", f"{OPENCODE_ZEN_BASE_URL}/messages"),
        text='{"error":{"message":"invalid"}}',
    )
    create = AsyncMock(
        side_effect=APIStatusError(
            message="unauthorized",
            response=response,
            body=None,
        )
    )
    client = LLMClient(
        api_key="bad",
        base_url=OPENCODE_ZEN_BASE_URL,
        max_retries=2,
        api_kind="zen",
        anthropic_client=MagicMock(messages=MagicMock(create=create)),
    )
    try:
        with pytest.raises(LLMError) as ei:
            await client.chat(
                model=OPENCODE_ZEN_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
        assert ei.value.status == 401
        assert create.await_count == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_zen_rate_limit_retries_then_fails() -> None:
    response = httpx.Response(
        429,
        request=httpx.Request("POST", f"{OPENCODE_ZEN_BASE_URL}/messages"),
        text="rate limited",
        headers={"Retry-After": "0"},
    )
    create = AsyncMock(
        side_effect=APIStatusError(
            message="rate limited",
            response=response,
            body=None,
        )
    )
    client = LLMClient(
        api_key="k",
        base_url=OPENCODE_ZEN_BASE_URL,
        max_retries=2,
        api_kind="zen",
        anthropic_client=MagicMock(messages=MagicMock(create=create)),
    )
    try:
        with pytest.raises(_RetryableError):
            await client.chat(
                model=OPENCODE_ZEN_DEFAULT_MODEL,
                messages=[ChatMessage(role="user", content="x")],
            )
        assert create.await_count == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_zen_timeout_is_retryable() -> None:
    create = AsyncMock(side_effect=[APITimeoutError("timed out"), _zen_message_mock("ok")])
    client = LLMClient(
        api_key="k",
        base_url=OPENCODE_ZEN_BASE_URL,
        max_retries=1,
        api_kind="zen",
        anthropic_client=MagicMock(messages=MagicMock(create=create)),
    )
    try:
        resp = await client.chat(
            model=OPENCODE_ZEN_DEFAULT_MODEL,
            messages=[ChatMessage(role="user", content="x")],
        )
    finally:
        await client.aclose()
    assert resp.content == "ok"
    assert create.await_count == 2


@pytest.mark.asyncio
async def test_zen_posts_to_messages_endpoint() -> None:
    """SDK must POST to https://opencode.ai/zen/v1/messages (not …/v1/v1/messages)."""
    seen: dict[str, object] = {}
    expected_url = opencode_zen_messages_url(OPENCODE_ZEN_BASE_URL)

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": OPENCODE_ZEN_DEFAULT_MODEL,
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 3, "output_tokens": 2},
            },
        )

    anthropic = AsyncAnthropic(
        api_key="zen-test-key",
        base_url="https://opencode.ai/zen",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=MockTransport(handler)),
    )
    client = LLMClient(
        api_key="zen-test-key",
        base_url=OPENCODE_ZEN_BASE_URL,
        max_retries=0,
        api_kind="zen",
        anthropic_client=anthropic,
    )
    try:
        resp = await client.chat(
            model=OPENCODE_ZEN_DEFAULT_MODEL,
            messages=[
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="Hello"),
            ],
            max_tokens=256,
        )
    finally:
        await client.aclose()

    assert resp.content == "ok"
    assert seen["url"] == expected_url
    assert expected_url == "https://opencode.ai/zen/v1/messages"
    assert "/v1/v1/" not in str(seen["url"])

    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers.get("x-api-key") == "zen-test-key"
    assert headers.get("anthropic-version")

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == OPENCODE_ZEN_DEFAULT_MODEL
    assert body["max_tokens"] == 256
    assert body["system"] == "You are helpful."
    assert body["messages"] == [{"role": "user", "content": "Hello"}]
    assert "temperature" not in body
