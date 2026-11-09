"""Cloudflare OpenAI-compatible chat/completions response parsing (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest

from forensics.llm_client import ChatMessage, LLMClient, LLMError


def _cf_client(handler: object) -> LLMClient:
    return LLMClient(
        api_key="test-token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
        api_kind="cloudflare",
    )


def _chat_completion_payload(content: object, *, finish_reason: str = "stop") -> dict:
    return {
        "id": "cf-test",
        "object": "chat.completion",
        "model": "@cf/zai-org/glm-4.7-flash",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


@pytest.mark.asyncio
async def test_parse_top_level_message_content() -> None:
    client = _cf_client(
        lambda r: httpx.Response(
            200,
            json=_chat_completion_payload('{"quality": 0.9, "reason": "ok"}'),
        )
    )
    try:
        resp = await client.chat(
            model="@cf/zai-org/glm-4.7-flash",
            messages=[ChatMessage(role="user", content="judge this")],
        )
    finally:
        await client.aclose()
    assert "quality" in resp.content
    assert resp.prompt_tokens == 10
    assert resp.completion_tokens == 20


@pytest.mark.asyncio
async def test_parse_message_content_parts_array() -> None:
    client = _cf_client(
        lambda r: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "part-one "},
                                {"type": "text", "text": "part-two"},
                            ],
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )
    try:
        resp = await client.chat(
            model="@cf/zai-org/glm-4.7-flash",
            messages=[ChatMessage(role="user", content="x")],
        )
    finally:
        await client.aclose()
    assert resp.content == "part-one part-two"


@pytest.mark.asyncio
async def test_empty_content_includes_structural_diagnostics() -> None:
    client = _cf_client(
        lambda r: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "internal chain only",
                        },
                    }
                ],
            },
        )
    )
    try:
        with pytest.raises(LLMError, match="empty content") as ei:
            await client.chat(
                model="@cf/zai-org/glm-4.7-flash",
                messages=[ChatMessage(role="user", content="x")],
            )
        msg = str(ei.value)
        assert "finish_reason='stop'" in msg
        assert "reasoning_content_present=True" in msg
        assert "internal chain" not in msg
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_length_finish_reason_noted_in_error() -> None:
    client = _cf_client(
        lambda r: httpx.Response(
            200,
            json=_chat_completion_payload("", finish_reason="length"),
        )
    )
    try:
        with pytest.raises(LLMError, match="max_tokens") as ei:
            await client.chat(
                model="@cf/zai-org/glm-4.7-flash",
                messages=[ChatMessage(role="user", content="x")],
            )
        assert "finish_reason='length'" in str(ei.value)
    finally:
        await client.aclose()
