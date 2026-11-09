from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from forensics.api.app import AppState, create_app
from forensics.config import Settings
from forensics.db.base import Base
from forensics.db.session import create_db_engine, create_session_factory
from forensics.pipeline import Pipeline
from forensics.storage import TraceStore

from .conftest import make_llm_client


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        database_url="",
        jwt_secret="test-jwt-secret-for-unit-tests-only",
        openai_api_key="test",
    )


@pytest.fixture
def auth_client(tmp_path, auth_settings: Settings) -> TestClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})

    client = make_llm_client(handler)
    pipeline = Pipeline(
        client=client,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing"],
    )
    store = TraceStore(tmp_path / "f.sqlite3", tmp_path / "traces")
    state = AppState(pipeline=pipeline, store=store, judge_model="gpt-4o")
    app = create_app(state, settings=auth_settings)
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    return TestClient(app)


def test_register_and_login(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/v1/auth/register",
        json={"email": "alice@example.com", "password": "securepass1"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert "password" not in body
    assert "password_hash" not in body

    login = auth_client.post(
        "/v1/auth/login",
        json={"email": "alice@example.com", "password": "securepass1"},
    )
    assert login.status_code == 200
    token_body = login.json()
    assert token_body["token_type"] == "bearer"
    assert token_body["access_token"]
    assert token_body["expires_in"] > 0


def test_me_requires_authentication(auth_client: TestClient) -> None:
    r = auth_client.get("/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_current_user(auth_client: TestClient) -> None:
    auth_client.post(
        "/v1/auth/register",
        json={"email": "bob@example.com", "password": "securepass1"},
    )
    login = auth_client.post(
        "/v1/auth/login",
        json={"email": "bob@example.com", "password": "securepass1"},
    ).json()
    r = auth_client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "bob@example.com"


def test_login_invalid_credentials(auth_client: TestClient) -> None:
    auth_client.post(
        "/v1/auth/register",
        json={"email": "carol@example.com", "password": "securepass1"},
    )
    r = auth_client.post(
        "/v1/auth/login",
        json={"email": "carol@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_register_duplicate_email(auth_client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "securepass1"}
    assert auth_client.post("/v1/auth/register", json=payload).status_code == 201
    r = auth_client.post("/v1/auth/register", json=payload)
    assert r.status_code == 409


def test_register_weak_password_rejected(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/v1/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert r.status_code == 422


def test_me_rejects_invalid_token(auth_client: TestClient) -> None:
    r = auth_client.get(
        "/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert r.status_code == 401


def test_legacy_pipeline_run_requires_auth_when_database_wired(auth_client: TestClient) -> None:
    """When auth DB is enabled, POST /v1/runs requires JWT (trace APIs already do)."""
    assert auth_client.get("/health").status_code == 200
    assert auth_client.get("/v1/traces").status_code == 401
    assert (
        auth_client.post(
            "/v1/runs",
            json={"document_id": "doc-1", "raw_text": "hello"},
        ).status_code
        == 401
    )


def test_auth_unavailable_without_database(tmp_path) -> None:
    settings = Settings(
        database_url="",
        jwt_secret="secret",
        openai_api_key="test",
    )
    client = make_llm_client(lambda _req: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}], "usage": {}}))
    pipeline = Pipeline(
        client=client,
        extraction_model="m",
        classification_model="m",
        summarization_model="m",
        labels=["billing"],
    )
    store = TraceStore(tmp_path / "f.sqlite3", tmp_path / "traces")
    app = create_app(AppState(pipeline=pipeline, store=store, judge_model="gpt-4o"), settings=settings)
    tc = TestClient(app)
    r = tc.post("/v1/auth/register", json={"email": "x@example.com", "password": "securepass1"})
    assert r.status_code == 503
