"""Security-focused integration tests (Phase 12)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from forensics.auth.jwt_tokens import create_access_token
from forensics.config import Settings
from forensics.db.models import User

from .conftest import auth_headers, upload_txt
from .test_analysis_feedback import _trace_with_analysis


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/v1/documents"),
        ("GET", "/v1/analytics/summary"),
        ("GET", "/v1/evaluations"),
        ("GET", "/v1/eval/cases"),
        ("GET", "/v1/traces"),
    ],
)
def test_protected_endpoints_require_auth(
    run_client: TestClient, method: str, path: str
) -> None:
    r = run_client.request(method, path)
    assert r.status_code == 401


def test_invalid_jwt_rejected(run_client: TestClient) -> None:
    headers = {"Authorization": "Bearer not.a.valid.jwt"}
    assert run_client.get("/v1/auth/me", headers=headers).status_code == 401


def test_expired_jwt_rejected(run_client: TestClient) -> None:
    auth_headers(run_client, "expired@example.com")
    session_factory = run_client.app.state.session_factory
    db = session_factory()
    try:
        user = db.scalars(select(User).where(User.email == "expired@example.com")).one()
        secret = run_client.app.state.settings.jwt_secret
        token = create_access_token(
            subject=user.id,
            secret=secret,
            expires_minutes=-60,
        )
    finally:
        db.close()
    assert (
        run_client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 401
    )


def test_malformed_authorization_scheme(run_client: TestClient) -> None:
    assert (
        run_client.get(
            "/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        ).status_code
        == 401
    )


def test_inactive_user_rejected(run_client: TestClient) -> None:
    headers = auth_headers(run_client, "inactive@example.com")
    session_factory = run_client.app.state.session_factory
    db = session_factory()
    try:
        user = db.scalars(select(User).where(User.email == "inactive@example.com")).one()
        user.is_active = False
        db.commit()
    finally:
        db.close()
    assert run_client.get("/v1/auth/me", headers=headers).status_code == 401


def test_user_a_cannot_access_user_b_run_metadata(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "run_meta_a@example.com")
    h_b = auth_headers(run_client, "run_meta_b@example.com")
    doc_b = upload_txt(run_client, h_b, "rb.txt", b"billing")
    run_b = run_client.post(f"/v1/documents/{doc_b}/runs", headers=h_b).json()
    assert run_client.get(f"/v1/runs/{run_b['id']}", headers=h_a).status_code == 404


def test_user_a_cannot_access_user_b_evaluations(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "eval_sec_a@example.com")
    headers_b, trace_id = _trace_with_analysis(run_client, "eval_sec_b@example.com")
    run_client.post(
        f"/v1/traces/{trace_id}/feedback",
        headers=headers_b,
        json={"decision": "confirmed"},
    )
    case_id = run_client.post(
        "/v1/evaluations",
        headers=headers_b,
        json={"trace_id": trace_id},
    ).json()["id"]
    assert run_client.get(f"/v1/evaluations/{case_id}", headers=h_a).status_code == 404
    assert run_client.get("/v1/evaluations", headers=h_a).json()["total"] == 0


def test_legacy_eval_cases_not_visible_cross_user(run_client: TestClient) -> None:
    h_a = auth_headers(run_client, "legacy_eval_a@example.com")
    h_b = auth_headers(run_client, "legacy_eval_b@example.com")
    doc_b = upload_txt(run_client, h_b, "le.txt", b"billing refund")
    trace_b = run_client.post(f"/v1/documents/{doc_b}/runs", headers=h_b).json()["trace_id"]
    run_client.post(
        f"/v1/traces/{trace_b}/flag",
        headers=h_b,
        json={"trace_id": trace_b, "reason": "bad output"},
    )
    b_cases = run_client.get("/v1/eval/cases", headers=h_b).json()
    assert len(b_cases) >= 1
    a_cases = run_client.get("/v1/eval/cases", headers=h_a).json()
    assert a_cases == []


def test_legacy_eval_cases_unauthenticated(run_client: TestClient) -> None:
    assert run_client.get("/v1/eval/cases").status_code == 401


def test_legacy_runs_unauthenticated_when_db_enabled(run_client: TestClient) -> None:
    assert (
        run_client.post(
            "/v1/runs",
            json={"document_id": "x", "raw_text": "hello world"},
        ).status_code
        == 401
    )


def test_jwt_secret_validation_with_database_url() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            database_url="postgresql+psycopg://u:p@localhost/db",
            jwt_secret="change-me-to-a-long-random-string",
            openai_api_key="test",
        )


def test_public_legacy_run_without_database(tmp_path) -> None:
    """CLI-style app without PostgreSQL may still call POST /v1/runs without JWT."""
    from forensics.api.app import AppState, create_app
    from forensics.config import Settings
    from forensics.pipeline import Pipeline
    from forensics.storage import TraceStore

    from .conftest import make_llm_client, orchestration_handler

    settings = Settings(
        database_url="",
        jwt_secret="test-jwt-secret-for-unit-tests-only",
        openai_api_key="test",
    )
    llm = make_llm_client(orchestration_handler())
    pipeline = Pipeline(
        client=llm,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing"],
    )
    store = TraceStore(tmp_path / "f.sqlite3", tmp_path / "traces")
    app = create_app(
        AppState(pipeline=pipeline, store=store, judge_model="gpt-4o"),
        settings=settings,
    )
    client = TestClient(app)
    r = client.post(
        "/v1/runs",
        json={"document_id": "doc-1", "raw_text": "please refund $120 billing"},
    )
    assert r.status_code == 200
