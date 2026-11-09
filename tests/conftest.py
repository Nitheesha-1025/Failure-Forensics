from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from forensics.api.app import AppState, create_app
from forensics.config import Settings
from forensics.db.base import Base
from forensics.db.session import create_db_engine, create_session_factory
from forensics.documents import DocumentService, LocalDocumentStorage
from forensics.llm_client import LLMClient
from forensics.models import (
    SpanRecord,
    StepStatus,
    TraceRecord,
)
from forensics.pipeline import Pipeline
from forensics.pipeline_runs import PipelineRunService
from forensics.storage import TraceStore
from forensics.traces import TraceAccessService


def orchestration_handler() -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sys_msg = next(
            (m["content"] for m in body["messages"] if m["role"] == "system"), ""
        )
        if "structured fields" in sys_msg.lower():
            return chat_response(
                '{"fields": {"amount": "$10"}, "confidence": 0.9}'
            )
        if "document classifier" in sys_msg.lower():
            return chat_response(
                '{"label": "billing", "confidence": 0.9, "rationale": "x"}'
            )
        if "concise" in sys_msg.lower():
            return chat_response("Summary of billing doc.")
        return chat_response("ok")

    return handler


def auth_headers(client: TestClient, email: str, password: str = "securepass1") -> dict[str, str]:
    client.post("/v1/auth/register", json={"email": email, "password": password})
    token = client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload_txt(client: TestClient, headers: dict[str, str], name: str, body: bytes) -> str:
    doc = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": (name, body, "text/plain")},
    )
    assert doc.status_code == 201
    return doc.json()["id"]


@pytest.fixture
def run_client(tmp_path: Path) -> TestClient:
    upload_dir = tmp_path / "uploads"
    traces_dir = tmp_path / "traces"
    settings = Settings(
        database_url="",
        jwt_secret="test-jwt-secret-for-unit-tests-only",
        openai_api_key="test",
        upload_dir=upload_dir,
        db_path=tmp_path / "f.sqlite3",
        traces_dir=traces_dir,
    )
    llm = make_llm_client(orchestration_handler())
    pipeline = Pipeline(
        client=llm,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing", "bug_report"],
    )
    store = TraceStore(settings.db_path, settings.traces_dir)
    state = AppState(pipeline=pipeline, store=store, judge_model="gpt-4o")
    app = create_app(state, settings=settings)
    wire_sqlite_platform(app, tmp_path, upload_dir=upload_dir)
    return TestClient(app)


def wire_sqlite_platform(app, tmp_path: Path, *, upload_dir: Path | None = None) -> None:
    """Attach in-memory PostgreSQL stand-in + document/run/trace services to a test app."""
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    uploads = upload_dir or (tmp_path / "uploads")
    settings = app.state.settings
    document_service = DocumentService(LocalDocumentStorage(uploads), settings)
    app.state.document_service = document_service
    app.state.pipeline_run_service = PipelineRunService(document_service)
    app.state.trace_access_service = TraceAccessService()


@pytest.fixture
def store(tmp_path: Path) -> TraceStore:
    return TraceStore(tmp_path / "f.sqlite3", tmp_path / "traces")


def make_span(
    *,
    span_id: str,
    trace_id: str,
    name: str,
    status: StepStatus = StepStatus.OK,
    confidence: float | None = 0.9,
    duration_ms: int = 50,
    output: dict | None = None,
    input_: dict | None = None,
) -> SpanRecord:
    started = datetime.now(UTC)
    return SpanRecord(
        span_id=span_id,
        trace_id=trace_id,
        name=name,
        started_at=started,
        ended_at=started,
        duration_ms=duration_ms,
        status=status,
        confidence=confidence,
        input=input_ or {},
        output=output or {},
    )


def make_trace(*, trace_id: str = "t1", spans: list[SpanRecord] | None = None) -> TraceRecord:
    started = datetime.now(UTC)
    spans_list = spans or [
        make_span(span_id="s1", trace_id=trace_id, name="intake",
                  input_={"raw_text": "hello"}, output={"raw_text": "hello"}),
        make_span(span_id="s2", trace_id=trace_id, name="extraction"),
        make_span(span_id="s3", trace_id=trace_id, name="classification",
                  output={"label": "billing"}),
        make_span(span_id="s4", trace_id=trace_id, name="summarization"),
    ]
    return TraceRecord(
        trace_id=trace_id,
        started_at=started,
        ended_at=started,
        duration_ms=200,
        status=StepStatus.OK,
        spans=spans_list,
        final_output={"summary": "ok"},
    )


def make_llm_client(handler) -> LLMClient:
    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LLMClient(api_key="test", client=transport, max_retries=0)


def chat_response(content: str, prompt_tokens: int = 5, completion_tokens: int = 5) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        },
    )


def cloudflare_response(
    content: str,
    *,
    prompt_tokens: int = 5,
    completion_tokens: int = 5,
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "cf-mock",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        },
    )
