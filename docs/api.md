# API reference

Base URL: `http://localhost:8090` (default). All JSON unless noted.

**Auth column:** `None` = public when configured; `Bearer` = JWT required; `Bearer*` = required when PostgreSQL auth is wired (`DATABASE_URL` set).

Full route implementations: `src/forensics/api/`.

## Meta

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Liveness: `{"status":"ok"}` |

## Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/auth/register` | None | Create user (email, password ≥8) |
| `POST` | `/v1/auth/login` | None | Returns `access_token`, `token_type`, `expires_in` |
| `GET` | `/v1/auth/me` | Bearer | Current user profile |

## Documents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/documents` | Bearer | Multipart upload (PDF, DOCX, TXT, MD) |
| `GET` | `/v1/documents` | Bearer | Paginated list (`page`, `page_size` ≤100) |
| `GET` | `/v1/documents/{document_id}` | Bearer | Metadata (owner only) |
| `GET` | `/v1/documents/{document_id}/text` | Bearer | Extracted text (owner only) |
| `DELETE` | `/v1/documents/{document_id}` | Bearer | Delete file + row (owner only) |

## Pipeline runs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/documents/{document_id}/runs` | Bearer | Parse doc, run pipeline, persist trace + run row |
| `GET` | `/v1/documents/{document_id}/runs` | Bearer | Run history (owner only) |
| `GET` | `/v1/runs/{run_id}` | Bearer | Run metadata (owner only) |
| `GET` | `/v1/runs/{run_id}/trace` | Bearer | Full trace for run (owner only) |

## Legacy pipeline (raw text)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/runs` | Bearer* | Run pipeline on `document_id` + `raw_text`; saves trace. **Requires JWT when DB is configured.** Without DB, public for CLI-style use. Trace not linked to a user until a document run exists. |

## Traces & analysis

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/v1/traces` | Bearer | List trace summaries for user's runs (`limit` 1–100, `only_flagged`) |
| `GET` | `/v1/traces/{trace_id}` | Bearer | Trace detail (owner via `pipeline_runs`) |
| `POST` | `/v1/traces/{trace_id}/analyze` | Bearer | Run LLM judge; store analysis |
| `GET` | `/v1/traces/{trace_id}/analysis` | Bearer | Stored `RootCauseAnalysis` |
| `POST` | `/v1/traces/{trace_id}/flag` | Bearer | Flag trace; legacy TraceStore eval case |
| `GET` | `/v1/eval/cases` | Bearer | Legacy eval cases for **owned traces only** (`limit` 1–100) |

## Human feedback

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/traces/{trace_id}/feedback` | Bearer | Upsert review (`confirmed` / `overridden`, optional comment) |
| `GET` | `/v1/traces/{trace_id}/feedback` | Bearer | Get current user's feedback |

Requires stored analysis. One feedback row per user per trace.

## User evaluations (PostgreSQL)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/evaluations` | Bearer | Body: `{ "trace_id" }` — requires feedback + analysis |
| `GET` | `/v1/evaluations` | Bearer | List cases for current user |
| `GET` | `/v1/evaluations/{case_id}` | Bearer | Case detail (owner only) |
| `DELETE` | `/v1/evaluations/{case_id}` | Bearer | Delete case (owner only) |
| `POST` | `/v1/evaluations/{case_id}/run` | Bearer | Synchronous regression (pipeline + analyze; compare root cause) |

## Analytics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/v1/analytics/summary` | Bearer | User-scoped counts (documents, runs, feedback, eval cases, top root-cause names) |

## Errors

- **401** — missing/invalid JWT on protected routes
- **404** — not found or cross-user access (no IDOR leak)
- **503** — database or auth not configured

See [authentication.md](authentication.md) and [trace-integration.md](trace-integration.md).
