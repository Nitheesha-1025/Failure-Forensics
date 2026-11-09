from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from forensics.api.app import AppState, create_app
from forensics.config import Settings
from forensics.pipeline import Pipeline
from forensics.storage import TraceStore

from .conftest import chat_response, wire_sqlite_platform


def _api_with_judge_handler(
    handler: object, tmp_path: Path, *, max_retries: int = 0
) -> TestClient:
    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    from forensics.llm_client import LLMClient

    client = LLMClient(api_key="test", client=transport, max_retries=max_retries)
    pipeline = Pipeline(
        client=client,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing"],
    )
    store = TraceStore(tmp_path / "f.sqlite3", tmp_path / "traces")
    state = AppState(pipeline=pipeline, store=store, judge_model="gpt-4o")
    settings = Settings(
        database_url="",
        jwt_secret="test-jwt-secret-for-unit-tests-only",
        openai_api_key="test",
        judge_concurrency=1,
    )
    app = create_app(state, settings=settings)
    wire_sqlite_platform(app, tmp_path)
    return TestClient(app)


def _auth(client: TestClient) -> dict[str, str]:
    email = "analyze-llm@test.com"
    password = "securepass1"
    client.post("/v1/auth/register", json={"email": email, "password": password})
    token = client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _trace_id(client: TestClient, headers: dict[str, str]) -> str:
    doc_id = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("t.txt", b"billing refund please", "text/plain")},
    ).json()["id"]
    run = client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()
    return run["trace_id"]


def test_analyze_returns_429_for_quota_exhaustion(tmp_path: Path) -> None:
    pipeline_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sys_msg = next(
            (m["content"] for m in body["messages"] if m["role"] == "system"), ""
        )
        if "structured fields" in sys_msg.lower():
            return chat_response('{"fields": {}, "confidence": 0.9}')
        if "document classifier" in sys_msg.lower():
            return chat_response(
                '{"label": "billing", "confidence": 0.9, "rationale": "x"}'
            )
        if "concise" in sys_msg.lower():
            return chat_response("summary")
        pipeline_calls["n"] += 1
        quota_body = json.dumps(
            {
                "error": {
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "Quota exceeded for metric",
                }
            }
        )
        return httpx.Response(429, text=quota_body)

    api = _api_with_judge_handler(handler, tmp_path)
    headers = _auth(api)
    trace_id = _trace_id(api, headers)
    resp = api.post(f"/v1/traces/{trace_id}/analyze", headers=headers)
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert "allowance" in detail.lower() or "neurons" in detail.lower()
    assert "sk-" not in detail
    assert pipeline_calls["n"] >= 1


def test_analyze_returns_429_after_rate_limit_retries(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sys_msg = next(
            (m["content"] for m in body["messages"] if m["role"] == "system"), ""
        )
        if "structured fields" in sys_msg.lower():
            return chat_response('{"fields": {}, "confidence": 0.9}')
        if "document classifier" in sys_msg.lower():
            return chat_response(
                '{"label": "billing", "confidence": 0.9, "rationale": "x"}'
            )
        if "concise" in sys_msg.lower():
            return chat_response("summary")
        return httpx.Response(429, text="too many requests", headers={"Retry-After": "0"})

    api = _api_with_judge_handler(handler, tmp_path, max_retries=2)
    headers = _auth(api)
    trace_id = _trace_id(api, headers)
    resp = api.post(f"/v1/traces/{trace_id}/analyze", headers=headers)
    assert resp.status_code == 429
    assert "rate-limited" in resp.json()["detail"].lower()
