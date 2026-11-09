"""Cloudflare Workers AI client and pipeline integration (mocked HTTP only)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from forensics.llm_client import ChatMessage, LLMClient, LLMError, LLMQuotaExhaustedError
from forensics.pipeline import Pipeline, run_pipeline

from .conftest import cloudflare_response


@pytest.mark.asyncio
async def test_cloudflare_successful_generation() -> None:
    client = LLMClient(
        api_key="token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: cloudflare_response("hello world")
            )
        ),
        max_retries=0,
        api_kind="cloudflare",
    )
    try:
        resp = await client.chat(
            model="@cf/meta/llama-3.1-8b-instruct",
            messages=[ChatMessage(role="user", content="hi")],
        )
    finally:
        await client.aclose()
    assert resp.content == "hello world"


@pytest.mark.asyncio
async def test_cloudflare_empty_response_raises() -> None:
    client = LLMClient(
        api_key="token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(
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
        ),
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
async def test_cloudflare_malformed_json_raises() -> None:
    client = LLMClient(
        api_key="token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, text="not-json"))
        ),
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


@pytest.mark.asyncio
async def test_cloudflare_auth_failure_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            401,
            json={
                "success": False,
                "errors": [{"code": 10000, "message": "Authentication error"}],
            },
        )

    client = LLMClient(
        api_key="bad",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=3,
        api_kind="cloudflare",
    )
    try:
        with pytest.raises(LLMError) as ei:
            await client.chat(
                model="@cf/meta/llama-3.1-8b-instruct",
                messages=[ChatMessage(role="user", content="x")],
            )
        assert ei.value.status == 401
    finally:
        await client.aclose()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_cloudflare_quota_exhausted_not_retried() -> None:
    calls = {"n": 0}
    body = json.dumps(
        {
            "success": False,
            "errors": [{"message": "Daily Neurons limit exceeded for free tier"}],
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text=body)

    client = LLMClient(
        api_key="token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=3,
        api_kind="cloudflare",
    )
    try:
        with pytest.raises(LLMQuotaExhaustedError):
            await client.chat(
                model="@cf/meta/llama-3.1-8b-instruct",
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_cloudflare_rate_limit_retries_then_fails() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="rate limited", headers={"Retry-After": "0"})

    client = LLMClient(
        api_key="token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=2,
        api_kind="cloudflare",
    )
    try:
        from forensics.llm_client import _RetryableError

        with pytest.raises(_RetryableError):
            await client.chat(
                model="@cf/meta/llama-3.1-8b-instruct",
                messages=[ChatMessage(role="user", content="x")],
            )
    finally:
        await client.aclose()
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_cloudflare_timeout_is_retryable() -> None:
    calls = {"n": 0}

    class FlakyTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ReadTimeout("timed out")
            return cloudflare_response("ok")

    client = LLMClient(
        api_key="token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc",
        client=httpx.AsyncClient(transport=FlakyTransport()),
        max_retries=1,
        api_kind="cloudflare",
    )
    try:
        resp = await client.chat(
            model="@cf/meta/llama-3.1-8b-instruct",
            messages=[ChatMessage(role="user", content="x")],
        )
    finally:
        await client.aclose()
    assert resp.content == "ok"
    assert calls["n"] == 2


def _cloudflare_orchestration_handler() -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        messages = body.get("messages") or []
        sys_msg = next(
            (m["content"] for m in messages if m.get("role") == "system"),
            "",
        )
        if "structured fields" in str(sys_msg).lower():
            return cloudflare_response(
                '{"fields": {"customer": "alice", "amount": "$120"}, "confidence": 0.85}'
            )
        if "document classifier" in str(sys_msg).lower():
            return cloudflare_response(
                '{"label": "billing", "confidence": 0.9, "rationale": "amount mentioned"}'
            )
        if "concise" in str(sys_msg).lower():
            return cloudflare_response("Alice was charged $120 for billing.")
        return cloudflare_response(
            '{"quality": 0.9, "reason": "ok", "is_root_cause_candidate": false}'
        )

    return handler


@pytest.mark.asyncio
async def test_pipeline_all_stages_via_cloudflare(tmp_path: Path) -> None:
    client = LLMClient(
        api_key="token",
        base_url="https://api.cloudflare.com/client/v4",
        account_id="acc-test",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(_cloudflare_orchestration_handler())
        ),
        max_retries=0,
        api_kind="cloudflare",
        supports_json_response_format=True,
    )
    pipeline = Pipeline(
        client=client,
        extraction_model="@cf/meta/llama-3.1-8b-instruct",
        classification_model="@cf/meta/llama-3.1-8b-instruct",
        summarization_model="@cf/meta/llama-3.1-8b-instruct",
        labels=["billing", "bug_report"],
    )
    try:
        final, trace = await run_pipeline(
            pipeline,
            document_id="doc-cf",
            raw_text="Hi, please refund $120 charged on Tuesday.",
        )
    finally:
        await client.aclose()

    assert final is not None
    assert trace.final_output is not None
    assert any(s.name == "extraction" for s in trace.spans)
    assert any(s.name == "classification" for s in trace.spans)
    assert any(s.name == "summarization" for s in trace.spans)
