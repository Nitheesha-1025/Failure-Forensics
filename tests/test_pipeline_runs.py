from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from forensics.db.models import Document, PipelineRun, RunStatus
from forensics.pipeline import Pipeline

from .conftest import auth_headers, make_llm_client, upload_txt


def test_run_document_success(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "runner@example.com")
    doc_id = upload_txt(run_client, headers, "invoice.txt", b"Please refund $120 for billing.")
    r = run_client.post(f"/v1/documents/{doc_id}/runs", headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["document_id"] == doc_id
    assert body["status"] == "completed"
    assert body["trace_id"]
    assert body["duration_ms"] is not None

    doc = run_client.get(f"/v1/documents/{doc_id}", headers=headers).json()
    assert doc["processing_status"] == "completed"

    trace = run_client.get(f"/v1/runs/{body['id']}/trace", headers=headers).json()
    assert trace["trace"]["trace_id"] == body["trace_id"]


def test_run_requires_auth(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "noauth@example.com")
    doc_id = upload_txt(run_client, headers, "x.txt", b"hello billing")
    assert run_client.post(f"/v1/documents/{doc_id}/runs").status_code == 401


def test_run_other_users_document(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "run_a@example.com")
    h_b = auth_headers(run_client, "run_b@example.com")
    doc_id = upload_txt(run_client, h_a, "private.txt", b"secret billing")
    assert run_client.post(f"/v1/documents/{doc_id}/runs", headers=h_b).status_code == 404


def test_run_missing_document(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "missing@example.com")
    r = run_client.post("/v1/documents/00000000-0000-0000-0000-000000000099/runs", headers=headers)
    assert r.status_code == 404


def test_failed_pipeline_run(run_client: TestClient) -> None:
    def fail_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad")

    llm = make_llm_client(fail_handler)
    pipeline = Pipeline(
        client=llm,
        extraction_model="m",
        classification_model="m",
        summarization_model="m",
        labels=["billing"],
    )
    state = run_client.app.state.app_state
    state.pipeline = pipeline

    headers = auth_headers(run_client, "fail@example.com")
    doc_id = upload_txt(run_client, headers, "bad.txt", b"billing issue")
    r = run_client.post(f"/v1/documents/{doc_id}/runs", headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"
    assert body["error_message"]
    assert body["trace_id"]


def test_rejects_run_while_another_is_running(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "inprog@example.com")
    doc_id = upload_txt(run_client, headers, "busy.txt", b"billing $1")
    factory = run_client.app.state.session_factory
    with factory() as db:
        assert isinstance(db, Session)
        document = db.get(Document, doc_id)
        assert document is not None
        db.add(
            PipelineRun(
                id=str(uuid.uuid4()),
                user_id=document.user_id,
                document_id=doc_id,
                status=RunStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
        )
        db.commit()

    r = run_client.post(f"/v1/documents/{doc_id}/runs", headers=headers)
    assert r.status_code == 409
    assert "in progress" in r.json()["detail"].lower()


def test_multiple_runs_same_document(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "multi@example.com")
    doc_id = upload_txt(run_client, headers, "multi.txt", b"billing $1")
    ids: set[str] = set()
    traces: set[str] = set()
    for _ in range(3):
        run = run_client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()
        ids.add(run["id"])
        assert run["trace_id"]
        traces.add(run["trace_id"])
    assert len(ids) == 3
    assert len(traces) == 3
    history = run_client.get(f"/v1/documents/{doc_id}/runs", headers=headers).json()
    assert history["total"] == 3


def test_get_run_owner_only(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "get_a@example.com")
    h_b = auth_headers(run_client, "get_b@example.com")
    doc_id = upload_txt(run_client, h_a, "g.txt", b"billing")
    run_id = run_client.post(f"/v1/documents/{doc_id}/runs", headers=h_a).json()["id"]
    assert run_client.get(f"/v1/runs/{run_id}", headers=h_a).status_code == 200
    assert run_client.get(f"/v1/runs/{run_id}", headers=h_b).status_code == 404
    assert run_client.get(f"/v1/runs/{run_id}").status_code == 401


def test_run_history_isolated(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "hist_a@example.com")
    h_b = auth_headers(run_client, "hist_b@example.com")
    doc_a = upload_txt(run_client, h_a, "a.txt", b"billing")
    upload_txt(run_client, h_b, "b.txt", b"billing")
    run_client.post(f"/v1/documents/{doc_a}/runs", headers=h_a)
    assert run_client.get(f"/v1/documents/{doc_a}/runs", headers=h_b).status_code == 404


def test_legacy_post_runs_requires_auth_when_database_wired(run_client: TestClient) -> None:
    assert (
        run_client.post(
            "/v1/runs",
            json={"document_id": "legacy-1", "raw_text": "billing refund"},
        ).status_code
        == 401
    )
    headers = auth_headers(run_client, "legacy_run@example.com")
    r = run_client.post(
        "/v1/runs",
        headers=headers,
        json={"document_id": "legacy-1", "raw_text": "billing refund"},
    )
    assert r.status_code == 200
    assert r.json()["trace"]["trace_id"]
