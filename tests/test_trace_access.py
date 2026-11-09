from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from forensics.db.models import PipelineRun, RunStatus

from .conftest import auth_headers, upload_txt


def test_user_a_can_fetch_own_run_trace(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "trace_owner@example.com")
    doc_id = upload_txt(run_client, headers, "owned.txt", b"billing refund $5")
    run = run_client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()
    r = run_client.get(f"/v1/runs/{run['id']}/trace", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == run["id"]
    assert body["document_id"] == doc_id
    assert body["trace"]["trace_id"] == run["trace_id"]
    assert len(body["trace"]["spans"]) >= 1


def test_user_a_cannot_fetch_user_b_run_trace(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "trace_a@example.com")
    h_b = auth_headers(run_client, "trace_b@example.com")
    doc_b = upload_txt(run_client, h_b, "b.txt", b"billing")
    run_b = run_client.post(f"/v1/documents/{doc_b}/runs", headers=h_b).json()
    assert run_client.get(f"/v1/runs/{run_b['id']}/trace", headers=h_a).status_code == 404


def test_user_a_cannot_fetch_user_b_trace_by_trace_id(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "trace_by_id_a@example.com")
    h_b = auth_headers(run_client, "trace_by_id_b@example.com")
    doc_b = upload_txt(run_client, h_b, "secret.txt", b"billing private")
    run_b = run_client.post(f"/v1/documents/{doc_b}/runs", headers=h_b).json()
    trace_id = run_b["trace_id"]
    assert run_client.get(f"/v1/traces/{trace_id}", headers=h_a).status_code == 404


def test_trace_endpoints_require_auth(run_client: TestClient) -> None:
    assert run_client.get("/v1/traces").status_code == 401
    assert run_client.get("/v1/traces/any-id").status_code == 401


def test_get_run_trace_not_found(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "missing_run@example.com")
    assert (
        run_client.get(
            "/v1/runs/00000000-0000-0000-0000-000000000099/trace",
            headers=headers,
        ).status_code
        == 404
    )


def test_run_without_trace_id(run_client: TestClient, tmp_path: Path) -> None:
    headers = auth_headers(run_client, "no_trace@example.com")
    doc_id = upload_txt(run_client, headers, "x.txt", b"billing")
    run = run_client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()
    session_factory = run_client.app.state.session_factory
    db = session_factory()
    try:
        row = db.get(PipelineRun, run["id"])
        assert row is not None
        row.trace_id = None
        row.status = RunStatus.FAILED.value
        db.commit()
    finally:
        db.close()
    r = run_client.get(f"/v1/runs/{run['id']}/trace", headers=headers)
    assert r.status_code == 404


def test_trace_id_in_store_but_owned_by_other_user(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "idor_a@example.com")
    h_b = auth_headers(run_client, "idor_b@example.com")
    doc_b = upload_txt(run_client, h_b, "idor.txt", b"billing")
    trace_id = run_client.post(f"/v1/documents/{doc_b}/runs", headers=h_b).json()["trace_id"]
    assert run_client.get(f"/v1/traces/{trace_id}", headers=h_a).status_code == 404


def _run_and_trace_id(client: TestClient, headers: dict[str, str]) -> str:
    doc_id = upload_txt(client, headers, "doc.txt", b"billing refund")
    return client.post(f"/v1/documents/{doc_id}/runs", headers=headers).json()["trace_id"]


def test_user_a_cannot_analyze_user_b_trace(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "analyze_a@example.com")
    h_b = auth_headers(run_client, "analyze_b@example.com")
    trace_b = _run_and_trace_id(run_client, h_b)
    assert (
        run_client.post(f"/v1/traces/{trace_b}/analyze", headers=h_a).status_code == 404
    )


def test_user_a_can_analyze_own_trace(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "analyze_own@example.com")
    trace_id = _run_and_trace_id(run_client, headers)
    r = run_client.post(f"/v1/traces/{trace_id}/analyze", headers=headers)
    assert r.status_code == 200
    assert r.json()["trace_id"] == trace_id


def test_user_a_cannot_get_user_b_stored_analysis(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "get_analysis_a@example.com")
    h_b = auth_headers(run_client, "get_analysis_b@example.com")
    trace_b = _run_and_trace_id(run_client, h_b)
    assert run_client.post(f"/v1/traces/{trace_b}/analyze", headers=h_b).status_code == 200
    assert run_client.get(f"/v1/traces/{trace_b}/analysis", headers=h_a).status_code == 404


def test_user_a_cannot_flag_user_b_trace(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "flag_a@example.com")
    h_b = auth_headers(run_client, "flag_b@example.com")
    trace_b = _run_and_trace_id(run_client, h_b)
    r = run_client.post(
        f"/v1/traces/{trace_b}/flag",
        headers=h_a,
        json={"trace_id": trace_b, "reason": "should not work"},
    )
    assert r.status_code == 404


def test_list_traces_scoped_to_user(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "list_a@example.com")
    h_b = auth_headers(run_client, "list_b@example.com")
    doc_a = upload_txt(run_client, h_a, "la.txt", b"billing")
    doc_b = upload_txt(run_client, h_b, "lb.txt", b"billing")
    run_client.post(f"/v1/documents/{doc_a}/runs", headers=h_a)
    run_client.post(f"/v1/documents/{doc_b}/runs", headers=h_b)
    listed_a = run_client.get("/v1/traces", headers=h_a).json()
    listed_b = run_client.get("/v1/traces", headers=h_b).json()
    assert len(listed_a) == 1
    assert len(listed_b) == 1
    assert listed_a[0]["document_id"] == doc_a
    assert listed_b[0]["document_id"] == doc_b
