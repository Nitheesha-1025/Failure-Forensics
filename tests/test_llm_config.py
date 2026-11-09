from __future__ import annotations

import json

import httpx
import pytest

from forensics.config import Settings
from forensics.llm_client import ChatMessage, LLMClient, _cloudflare_chat_completions_url
from forensics.llm_config import (
    CLOUDFLARE_API_BASE_URL,
    CLOUDFLARE_DEFAULT_MODEL,
    LLMConfigurationError,
    build_llm_client,
    resolve_llm_settings,
)


def test_resolve_cloudflare_when_credentials_set() -> None:
    resolved = resolve_llm_settings(
        Settings(
            cloudflare_account_id="acc-123",
            cloudflare_api_token="cf-token",
            cloudflare_model=CLOUDFLARE_DEFAULT_MODEL,
            opencode_zen_api_key="",
            llm_provider="cloudflare",
            openai_api_key="",
        )
    )
    assert resolved.provider == "cloudflare"
    assert resolved.api_key == "cf-token"
    assert resolved.account_id == "acc-123"
    assert resolved.base_url == CLOUDFLARE_API_BASE_URL
    assert resolved.judge_model == CLOUDFLARE_DEFAULT_MODEL
    assert resolved.supports_json_response_format is True


def test_resolve_openai_when_forced() -> None:
    resolved = resolve_llm_settings(
        Settings(
            cloudflare_account_id="acc-123",
            cloudflare_api_token="cf-token",
            llm_provider="openai",
            openai_api_key="sk-test",
        )
    )
    assert resolved.provider == "openai"
    assert resolved.api_key == "sk-test"
    assert resolved.extraction_model == "gpt-4o-mini"
    assert resolved.supports_json_response_format is True


def test_cloudflare_requires_credentials_when_forced() -> None:
    with pytest.raises(LLMConfigurationError, match="CLOUDFLARE_ACCOUNT_ID"):
        resolve_llm_settings(
            Settings(
                llm_provider="cloudflare",
                cloudflare_account_id="",
                cloudflare_api_token="",
            )
        )


@pytest.mark.asyncio
async def test_cloudflare_client_posts_to_chat_completions() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth_bearer"] = request.headers.get("Authorization")
        body = json.loads(request.content)
        seen["body"] = body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "{}"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            },
        )

    resolved = resolve_llm_settings(
        Settings(
            cloudflare_account_id="acc-xyz",
            cloudflare_api_token="cf-secret",
            cloudflare_model=CLOUDFLARE_DEFAULT_MODEL,
            llm_provider="cloudflare",
        )
    )
    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LLMClient(
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        account_id=resolved.account_id,
        client=transport,
        max_retries=0,
        api_kind="cloudflare",
        supports_json_response_format=True,
    )
    try:
        await client.chat(
            model=resolved.judge_model,
            messages=[
                ChatMessage(role="system", content="sys"),
                ChatMessage(role="user", content="hi"),
            ],
            response_format={"type": "json_object"},
        )
    finally:
        await client.aclose()

    url = str(seen["url"])
    assert url == _cloudflare_chat_completions_url(CLOUDFLARE_API_BASE_URL, "acc-xyz")
    assert seen["auth_bearer"] == "Bearer cf-secret"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body.get("model") == CLOUDFLARE_DEFAULT_MODEL
    assert body.get("stream") is False
    assert body.get("response_format") == {"type": "json_object"}


def test_resolve_nvidia_when_forced() -> None:
    from forensics.llm_config import NVIDIA_API_BASE_URL, NVIDIA_DEFAULT_MODEL

    resolved = resolve_llm_settings(
        Settings(
            llm_provider="nvidia",
            nvidia_api_key="nv-secret",
            nvidia_model=NVIDIA_DEFAULT_MODEL,
            opencode_zen_api_key="zen-key",
            cloudflare_account_id="acc",
            cloudflare_api_token="cf",
        )
    )
    assert resolved.provider == "nvidia"
    assert resolved.api_key == "nv-secret"
    assert resolved.base_url == NVIDIA_API_BASE_URL
    assert resolved.judge_model == NVIDIA_DEFAULT_MODEL


def test_build_llm_client_uses_cloudflare_api_kind() -> None:
    resolved = resolve_llm_settings(
        Settings(
            cloudflare_account_id="acc",
            cloudflare_api_token="tok",
            llm_provider="cloudflare",
        )
    )
    client = build_llm_client(
        resolved,
        settings=Settings(cloudflare_account_id="acc", cloudflare_api_token="tok"),
    )
    assert client.api_kind == "cloudflare"
