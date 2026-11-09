# Database (PostgreSQL)

Phase 2 introduces a **PostgreSQL** database for application metadata (users). Pipeline traces continue to use the existing **TraceStore** (SQLite index + JSON files under `FORENSICS_DB_PATH` / `FORENSICS_TRACES_DIR`).

## Connection

Set `DATABASE_URL` for SQLAlchemy, for example:

```text
postgresql+psycopg://forensics:forensics@localhost:5432/forensics
```

Docker Compose starts Postgres and wires this URL for the `api` service.

## Schema (Phase 2)

### `users`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID string (36) | Primary key |
| `email` | string(320) | Unique, indexed |
| `password_hash` | string(512) | Argon2 hash |
| `is_active` | boolean | Default true |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### `documents` (Phase 3)

| Column | Notes |
|--------|-------|
| `id` | UUID string, primary key |
| `user_id` | FK → `users.id`, indexed |
| `filename` / `original_filename` | Sanitized display names |
| `file_type` | `pdf`, `docx`, `txt`, `md` |
| `mime_type` | Detected/expected MIME |
| `file_size` | Bytes |
| `storage_key` | Opaque key (unique), not exposed via API |
| `processing_status` | `uploaded`, `processing`, `completed`, `failed` |
| `created_at` / `updated_at` | Timestamps |

Migration: `20260408_0002_create_documents.py`.

### `pipeline_runs` (Phase 4)

| Column | Notes |
|--------|-------|
| `id` | UUID string, primary key |
| `user_id` | FK → `users.id` |
| `document_id` | FK → `documents.id` |
| `trace_id` | Reference to TraceStore trace (nullable if parse fails pre-pipeline) |
| `status` | `queued`, `running`, `completed`, `failed` |
| `started_at` / `completed_at` / `duration_ms` | Timing |
| `error_message` | Safe user-facing error (nullable) |
| `created_at` | Row creation time |

Migration: `20260408_0003_create_pipeline_runs.py`.

Trace **payloads** remain in TraceStore. Phase 5+ may address trace persistence in PostgreSQL separately.

## Migrations (Alembic)

From the project root, with `DATABASE_URL` set:

```bash
pip install -e .
alembic upgrade head
```

Create a new revision after model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Initial migration: `alembic/versions/20260401_0001_create_users.py`.

## Local development

1. Start Postgres (`docker compose up postgres -d` or a local install).
2. Copy `.env.example` to `.env` and set `DATABASE_URL` and `JWT_SECRET`.
3. Run `alembic upgrade head`.
4. Start the API: `forensics serve`.

## Tests

Auth tests use in-memory SQLite (`sqlite+pysqlite:///:memory:`) with `Base.metadata.create_all` for speed. CI and production should use PostgreSQL.
