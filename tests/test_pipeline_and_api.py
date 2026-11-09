from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from forensics.api.app import AppState, create_app
from forensics.config import Settings
from forensics.pipeline import Pipeline, run_pipeline
from forensics.pipeline.steps import (
    _parse_classification,
    _parse_extraction,
    _to_float,
)
from forensics.storage import TraceStore

from .conftest import chat_response, make_llm_client, wire_sqlite_platform


def _orchestration_handler() -> object:
    """Returns a handler that gives plausible JSON for each step in turn."""
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sys_msg = next(
            (m["content"] for m in body["messages"] if m["role"] == "system"), ""
        )
        if "structured fields" in sys_msg.lower():
            return chat_response(
                '{"fields": {"customer": "alice", "amount": "$120"}, "confidence": 0.85}'
            )
        if "document classifier" in sys_msg.lower():
            return chat_response(
                '{"label": "billing", "confidence": 0.9, "rationale": "amount mentioned"}'
            )
        if "concise" in sys_msg.lower():
            return chat_response("Alice was charged $120 for billing.")
        state["i"] += 1
        return chat_response("ok")

    return handler


@pytest.mark.asyncio
async def test_run_pipeline_happy_path(tmp_path: Path) -> None:
    client = make_llm_client(_orchestration_handler())
    pipeline = Pipeline(
        client=client,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing", "bug_report", "feature_request"],
    )
    try:
        final, trace = await run_pipeline(
            pipeline,
            document_id="doc-1",
            raw_text="Hi, please refund $120 charged on Tuesday.",
        )
    finally:
        await client.aclose()

    assert final is not None
    assert trace.spans[0].name == "intake"
    assert any(s.name == "summarization" for s in trace.spans)
    assert trace.final_output is not None
    assert trace.status.value == "ok"


@pytest.mark.asyncio
async def test_run_pipeline_records_error_in_trace(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad")

    client = make_llm_client(handler)
    pipeline = Pipeline(
        client=client,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing"],
    )
    try:
        final, trace = await run_pipeline(
            pipeline, document_id="doc-2", raw_text="some text"
        )
    finally:
        await client.aclose()

    assert final is None
    assert trace.status.value == "error"


def test_parse_extraction_handles_garbage() -> None:
    fields, conf = _parse_extraction("not json")
    assert fields == {}
    assert conf == 0.5


def test_parse_classification_clamps_unknown_to_last_label() -> None:
    label, _, _ = _parse_classification(
        '{"label": "spam", "confidence": 0.9, "rationale": "x"}',
        labels=["billing", "bug_report"],
    )
    assert label == "bug_report"


def test_parse_classification_prefix_match() -> None:
    label, _, _ = _parse_classification(
        '{"label": "bil", "confidence": 0.7, "rationale": "x"}',
        labels=["billing", "bug_report"],
    )
    assert label == "billing"


def test_to_float_clamps_and_handles_garbage() -> None:
    assert _to_float("nope") == 0.5
    assert _to_float(2.0) == 1.0
    assert _to_float(-1.0) == 0.0


# ------------------------------ API tests ------------------------------


@pytest.fixture
def api_client(tmp_path: Path) -> TestClient:
    client = make_llm_client(_orchestration_handler())
    pipeline = Pipeline(
        client=client,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing", "bug_report"],
    )
    store = TraceStore(tmp_path / "f.sqlite3", tmp_path / "traces")
    state = AppState(pipeline=pipeline, store=store, judge_model="gpt-4o")
    settings = Settings(
        database_url="",
        jwt_secret="test-jwt-secret-for-unit-tests-only",
        openai_api_key="test",
    )
    app = create_app(state, settings=settings)
    wire_sqlite_platform(app, tmp_path)
    return TestClient(app)


def _auth(api_client: TestClient, email: str = "api@test.com") -> dict[str, str]:
    password = "securepass1"
    api_client.post("/v1/auth/register", json={"email": email, "password": password})
    token = api_client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _owned_trace_via_document(api_client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    doc_id = api_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("t.txt", b"please refund $120 billing", "text/plain")},
    ).json()["id"]
    run = api_client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()
    return run["trace_id"], run["id"]


def test_health(api_client: TestClient) -> None:
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_run_and_fetch_trace(api_client: TestClient) -> None:
    headers = _auth(api_client)
    r = api_client.post(
        "/v1/runs",
        headers=headers,
        json={"document_id": "doc-1", "raw_text": "please refund $120"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["trace"]["trace_id"]
    assert body["final_summary"] is not None

    assert api_client.get("/v1/traces").status_code == 401

    trace_id, run_id = _owned_trace_via_document(api_client, headers)
    listed = api_client.get("/v1/traces", headers=headers).json()
    assert any(item["trace_id"] == trace_id for item in listed)

    fetched = api_client.get(f"/v1/traces/{trace_id}", headers=headers).json()
    assert fetched["trace_id"] == trace_id
    via_run = api_client.get(f"/v1/runs/{run_id}/trace", headers=headers).json()
    assert via_run["trace"]["trace_id"] == trace_id


def test_get_unknown_trace_returns_404(api_client: TestClient) -> None:
    assert api_client.get("/v1/traces/does-not-exist").status_code == 401
    headers = _auth(api_client, "unknown@test.com")
    r = api_client.get("/v1/traces/does-not-exist", headers=headers)
    assert r.status_code == 404


def test_flag_trace_creates_eval_case(api_client: TestClient) -> None:
    headers = _auth(api_client, "flag@test.com")
    trace_id, _run_id = _owned_trace_via_document(api_client, headers)
    r = api_client.post(
        f"/v1/traces/{trace_id}/flag",
        headers=headers,
        json={"trace_id": trace_id, "reason": "wrong category", "expected_output": "billing"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["flagged"] is True
    assert body["eval_case_created"] is True

    cases = api_client.get("/v1/eval/cases", headers=headers).json()
    assert len(cases) >= 1
    assert all(c["source_trace_id"] == trace_id for c in cases)


def test_flag_with_mismatched_trace_id_rejected(api_client: TestClient) -> None:
    headers = _auth(api_client, "flag2@test.com")
    trace_id, _run_id = _owned_trace_via_document(api_client, headers)
    r = api_client.post(
        f"/v1/traces/{trace_id}/flag",
        headers=headers,
        json={"trace_id": "DIFFERENT", "reason": "x"},
    )
    assert r.status_code == 400
