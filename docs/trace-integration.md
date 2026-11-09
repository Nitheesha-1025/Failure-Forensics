# Traces & integration

Trace retrieval is scoped to **user-owned pipeline runs** while **TraceStore** remains the system of record for trace payloads.

## Architecture

```text
Authenticated User
      ↓
Document (PostgreSQL)
      ↓
Pipeline Run (PostgreSQL, trace_id)
      ↓
TraceStore (SQLite index + JSON files)
      ↓
TraceRecord + SpanRecord
```

PostgreSQL stores **who** may access **which** `trace_id`. TraceStore stores **what** happened in the pipeline.

## Ownership rule

Access is granted only when:

```sql
pipeline_runs.user_id = current_user.id
AND pipeline_runs.trace_id = :trace_id
```

Knowing a `trace_id` UUID is **not** authorization.

## Authentication

These endpoints require `Authorization: Bearer <JWT>`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/runs/{run_id}/trace` | **Preferred:** trace for an owned pipeline run |
| `GET` | `/v1/traces/{trace_id}` | Same trace if owned via `pipeline_runs` |
| `GET` | `/v1/traces` | List traces for the current user (from their runs) |
| `POST` | `/v1/traces/{trace_id}/analyze` | Analyze owned trace |
| `GET` | `/v1/traces/{trace_id}/analysis` | Fetch stored analysis (owned) |
| `POST` | `/v1/traces/{trace_id}/flag` | Flag owned trace |

Cross-user access returns **404** (no existence leak).

## Legacy developer endpoint

`POST /v1/runs` accepts raw text and persists a trace. When PostgreSQL auth is configured, this endpoint **requires JWT**. Traces created here are **not** linked to `pipeline_runs` until the user runs the pipeline via `POST /v1/documents/{id}/runs`; unlinked traces are not visible in user-scoped trace APIs.

## Span fields exposed

API responses mirror existing models:

- **Trace:** `trace_id`, `schema_version`, `started_at`, `ended_at`, `duration_ms`, `status`, `spans`, `final_output`, `flagged`, `flag_reason`
- **Span:** `span_id`, `trace_id`, `name`, timestamps, `duration_ms`, `status`, `error`, `confidence`, `input`, `output`, `attributes`

There is **no** separate token field on spans. Token usage is not recorded in `SpanRecord` today; `attributes` may include `model` when set by pipeline steps. Parent/child span relationships are not modeled.

## Sensitive data

Traces may contain document text in span inputs/outputs. Only return traces to the owning user. Do not log full trace payloads at INFO level in production.

## UI

The React Trace Explorer loads **`GET /v1/runs/{run_id}/trace`** at `/documents/{documentId}/runs/{runId}/trace`.

## Related

- [failure-analysis.md](failure-analysis.md), [feedback.md](feedback.md)
- Legacy eval listing: `GET /v1/eval/cases` (user-scoped)
