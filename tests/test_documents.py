from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from forensics.api.app import AppState, create_app
from forensics.config import Settings
from forensics.db.base import Base
from forensics.db.session import create_db_engine, create_session_factory
from forensics.documents import DocumentService, LocalDocumentStorage
from forensics.documents.validation import sanitize_filename
from forensics.pipeline import Pipeline
from forensics.storage import TraceStore

from .conftest import make_llm_client


def _minimal_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _minimal_docx(text: str = "Hello from docx") -> bytes:
    doc = DocxDocument()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _auth_headers(client: TestClient, email: str, password: str = "securepass1") -> dict[str, str]:
    client.post("/v1/auth/register", json={"email": email, "password": password})
    token = client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def doc_client(tmp_path: Path) -> TestClient:
    upload_dir = tmp_path / "uploads"
    settings = Settings(
        database_url="",
        jwt_secret="test-jwt-secret-for-unit-tests-only",
        openai_api_key="test",
        upload_dir=upload_dir,
        max_upload_size_mb=25,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})

    llm = make_llm_client(handler)
    pipeline = Pipeline(
        client=llm,
        extraction_model="gpt-4o-mini",
        classification_model="gpt-4o-mini",
        summarization_model="gpt-4o-mini",
        labels=["billing"],
    )
    store = TraceStore(tmp_path / "f.sqlite3", tmp_path / "traces")
    state = AppState(pipeline=pipeline, store=store, judge_model="gpt-4o")
    app = create_app(state, settings=settings)
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    storage = LocalDocumentStorage(upload_dir)
    app.state.document_service = DocumentService(storage, settings)
    return TestClient(app)


def test_upload_txt_authenticated(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "u1@example.com")
    r = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("notes.txt", b"Hello document world", "text/plain")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["filename"] == "notes.txt"
    assert body["file_type"] == "txt"
    assert body["processing_status"] == "uploaded"
    assert "storage" not in body
    assert "path" not in body


def test_upload_unauthenticated_fails(doc_client: TestClient) -> None:
    r = doc_client.post(
        "/v1/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 401


def test_upload_unsupported_extension(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "u2@example.com")
    r = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_upload_empty_file(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "u3@example.com")
    r = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_oversized_file(doc_client: TestClient, tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads2"
    settings = Settings(
        database_url="",
        jwt_secret="test-jwt-secret-for-unit-tests-only",
        openai_api_key="test",
        upload_dir=upload_dir,
        max_upload_size_mb=1,
    )
    app = doc_client.app
    storage = LocalDocumentStorage(upload_dir)
    app.state.document_service = DocumentService(storage, settings)

    headers = _auth_headers(doc_client, "big@example.com")
    payload = b"x" * (1024 * 1024 + 1)
    r = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("big.txt", payload, "text/plain")},
    )
    assert r.status_code == 413


def test_list_only_own_documents(doc_client: TestClient) -> None:
    h_a = _auth_headers(doc_client, "owner_a@example.com")
    h_b = _auth_headers(doc_client, "owner_b@example.com")
    doc_client.post(
        "/v1/documents",
        headers=h_a,
        files={"file": ("a.txt", b"aaa", "text/plain")},
    )
    doc_client.post(
        "/v1/documents",
        headers=h_b,
        files={"file": ("b.txt", b"bbb", "text/plain")},
    )
    list_a = doc_client.get("/v1/documents", headers=h_a).json()
    list_b = doc_client.get("/v1/documents", headers=h_b).json()
    assert list_a["total"] == 1
    assert list_b["total"] == 1
    assert list_a["items"][0]["filename"] == "a.txt"
    assert list_b["items"][0]["filename"] == "b.txt"


def test_get_document_owner_only(doc_client: TestClient) -> None:
    headers_a = _auth_headers(doc_client, "detail_a@example.com")
    headers_b = _auth_headers(doc_client, "detail_b@example.com")
    created = doc_client.post(
        "/v1/documents",
        headers=headers_a,
        files={"file": ("secret.txt", b"secret", "text/plain")},
    ).json()
    doc_id = created["id"]
    assert doc_client.get(f"/v1/documents/{doc_id}", headers=headers_a).status_code == 200
    assert doc_client.get(f"/v1/documents/{doc_id}", headers=headers_b).status_code == 404
    assert doc_client.get(f"/v1/documents/{doc_id}").status_code == 401


def test_delete_document_owner_only(doc_client: TestClient) -> None:
    headers_a = _auth_headers(doc_client, "del_a@example.com")
    headers_b = _auth_headers(doc_client, "del_b@example.com")
    doc_id = doc_client.post(
        "/v1/documents",
        headers=headers_a,
        files={"file": ("gone.txt", b"bye", "text/plain")},
    ).json()["id"]
    assert doc_client.delete(f"/v1/documents/{doc_id}", headers=headers_b).status_code == 404
    assert doc_client.delete(f"/v1/documents/{doc_id}", headers=headers_a).status_code == 204
    assert doc_client.get(f"/v1/documents/{doc_id}", headers=headers_a).status_code == 404


def test_path_traversal_filename_sanitized(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "path@example.com")
    r = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("../../evil.txt", b"safe content", "text/plain")},
    )
    assert r.status_code == 201
    assert r.json()["filename"] == "evil.txt"


def test_sanitize_filename_strips_directory_components() -> None:
    assert sanitize_filename("../../evil.txt") == "evil.txt"
    assert sanitize_filename(r"..\windows\doc.txt") == "doc.txt"


def test_pdf_docx_md_upload_and_text_extraction(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "types@example.com")
    pdf_id = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("file.pdf", _minimal_pdf(), "application/pdf")},
    ).json()["id"]
    docx_id = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("file.docx", _minimal_docx("Invoice total $50"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    ).json()["id"]
    md_id = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("readme.md", b"# Title\n\nBody", "text/markdown")},
    ).json()["id"]

    docx_text = doc_client.get(f"/v1/documents/{docx_id}/text", headers=headers).json()
    assert "Invoice" in docx_text["text"]
    md_text = doc_client.get(f"/v1/documents/{md_id}/text", headers=headers).json()
    assert "Title" in md_text["text"]
    assert doc_client.get(f"/v1/documents/{pdf_id}/text", headers=headers).status_code in (
        200,
        422,
    )


def test_fake_pdf_rejected(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "fakepdf@example.com")
    r = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert r.status_code == 400


def test_fake_docx_rejected(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "fakedocx@example.com")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("not-word.txt", "nope")
    r = doc_client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("fake.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 400


def test_pagination(doc_client: TestClient) -> None:
    headers = _auth_headers(doc_client, "pages@example.com")
    for i in range(3):
        doc_client.post(
            "/v1/documents",
            headers=headers,
            files={"file": (f"p{i}.txt", f"doc{i}".encode(), "text/plain")},
        )
    page1 = doc_client.get("/v1/documents?page=1&page_size=2", headers=headers).json()
    assert page1["total"] == 3
    assert page1["total_pages"] == 2
    assert len(page1["items"]) == 2
