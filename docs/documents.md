# Document management (Phase 3)

Phase 3 adds **user-owned document upload and metadata** in PostgreSQL plus **local filesystem** binary storage. It does **not** run the AI pipeline or write to `TraceStore` yet (Phase 4+).

## Supported types

| Extension | MIME (expected) | Validation |
|-----------|-----------------|------------|
| `.pdf` | `application/pdf` | `%PDF-` header |
| `.docx` | OOXML Word | ZIP containing `word/document.xml` |
| `.txt` | `text/plain` | UTF-8, no NUL bytes |
| `.md` | `text/markdown` (also accepts `text/plain`) | UTF-8, no NUL bytes |

Extensions and content are both checked. Filenames are sanitized; directory components are stripped.

## Upload limits

- Configured via `MAX_UPLOAD_SIZE_MB` (default **25**).
- Oversized uploads return **413**.

## API (all require `Authorization: Bearer <token>`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/documents` | Multipart upload (`file` field) |
| `GET` | `/v1/documents` | Paginated list (`page`, `page_size` ≤ 100) |
| `GET` | `/v1/documents/{id}` | Metadata only |
| `GET` | `/v1/documents/{id}/text` | Normalized extracted text (parsing only) |
| `DELETE` | `/v1/documents/{id}` | Delete metadata + stored file |

Responses never include filesystem paths or internal storage keys.

## Processing status

New uploads are stored with `processing_status=uploaded`. Other values (`processing`, `completed`, `failed`) are reserved for Phase 4 pipeline runs.

## Storage architecture

```
DocumentStorage (interface)
        ↓
LocalDocumentStorage
        ↓
UPLOAD_DIR/<user_id>/<document_id>   (opaque blob, no original extension)
```

The database stores an opaque `storage_key` (`<user_id>/<document_id>`). A future S3 backend can implement the same interface without changing routes.

## Text extraction

`documents/parsers.py` uses **pypdf** (PDF) and **python-docx** (DOCX). Plain text and Markdown are decoded as UTF-8. This is **not** wired to `run_pipeline` in Phase 3.

## Security

- **Authentication:** JWT from Phase 2 on every document route.
- **Authorization:** Queries always filter by `user_id`. Other users' IDs return **404** (no existence leak).
- **Upload safety:** Size limits, type sniffing, sanitized filenames, UUID storage keys, path traversal checks on keys.
- **Secrets:** Never returned in API payloads.

## Local development

1. Ensure Phase 2 Postgres + migrations: `alembic upgrade head`.
2. Set `UPLOAD_DIR` (default `./uploads`).
3. Register/login, then upload with curl:

```bash
curl -X POST http://localhost:8090/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@invoice.pdf"
```

Docker Compose mounts `/data/uploads` for the API service.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `UPLOAD_DIR` | `./uploads` | Local document blob directory |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum upload size |

See also [`authentication.md`](authentication.md) and [`database.md`](database.md).
