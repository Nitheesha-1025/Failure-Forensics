# Pipeline runs (Phase 4)

Phase 4 connects **user-owned documents** to the **existing pipeline** and **TraceStore** without migrating trace data to PostgreSQL.

## What is a pipeline run?

A **pipeline run** is one execution of the AI pipeline for a stored document. Metadata lives in PostgreSQL (`pipeline_runs`). Trace payloads (spans, inputs, outputs) remain in the existing **TraceStore** (SQLite index + JSON files).

```text
User → Document → Pipeline Run (PostgreSQL) ──trace_id──► TraceStore
```

## Relationships

```text
users
  └── documents
        └── pipeline_runs (many per document)
```

Each run references:

- `user_id` — owner (must match document owner)
- `document_id` — source document
- `trace_id` — ID in TraceStore after execution (null if parsing failed before pipeline)

## Run statuses

| Status | Meaning |
|--------|---------|
| `queued` | Reserved for future async execution |
| `running` | Run record created; work in progress |
| `completed` | Pipeline finished with OK trace and final output |
| `failed` | Parse failure, pipeline error, or non-OK trace |

## Document `processing_status`

Reflects the **latest run attempt**, not permanent document state:

- `uploaded` — after Phase 3 upload
- `processing` — while a run is executing
- `completed` — last run succeeded
- `failed` — last run failed (user may run again)

## API (Bearer JWT required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/documents/{document_id}/runs` | Parse document text, run pipeline, save trace |
| `GET` | `/v1/documents/{document_id}/runs` | Paginated run history for owned document |
| `GET` | `/v1/runs/{run_id}` | Single run metadata (owner only) |

Legacy **`POST /v1/runs`** (raw text, no auth) is unchanged.

## Execution model

Phase 4 runs **synchronously** in the HTTP request: suitable for the current 4-step pipeline with mocked/real LLM calls. The service layer is structured so background execution can be added later without changing route signatures.

Flow:

1. Load owned document
2. Create `pipeline_runs` row (`running`)
3. Extract text via Phase 3 parsers
4. Call existing `run_pipeline(document_id=doc.id, raw_text=...)`
5. `TraceStore.save_trace(trace)`
6. Update run with `trace_id`, status, duration, safe error message

## Trace association

`run_pipeline` returns `TraceRecord` with `trace_id`. That value is copied to `pipeline_runs.trace_id`. Use existing endpoints to inspect traces:

- `GET /v1/traces/{trace_id}`

## Phase 5+

Trace persistence architecture (PostgreSQL migration, per-user trace ACLs) will be addressed separately. Phase 4 only stores the **reference** in PostgreSQL.
