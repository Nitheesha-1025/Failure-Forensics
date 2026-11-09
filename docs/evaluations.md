# Evaluations

User-owned **evaluation cases** (`user_eval_cases` in PostgreSQL) capture a reviewed failure for later **regression** checks.

## Creating a case

Requirements:

1. User owns the trace (`pipeline_runs`)
2. Human **feedback** exists for that trace
3. **Analysis** stored in TraceStore
4. Intake **raw_text** available on the trace

Create via `POST /v1/evaluations` with `{ "trace_id": "..." }` or **Save to evaluations** in the UI. At most one case per user per trace.

Stored fields include: human decision/comment, snapshot of expected root-cause span, document/run references, input text snapshot.

## Regression

`POST /v1/evaluations/{case_id}/run` (synchronous):

1. Re-runs `run_pipeline` on saved `raw_text`
2. Runs `analyze_trace` on the new trace
3. Compares root-cause span ID when decision is `confirmed` (`passed` true/false)
4. For `overridden`, result is informational (`passed` null)

Does **not** overwrite the original stored trace or analysis.

## API

See [api.md](api.md) — `/v1/evaluations` routes.

## UI

- `/evaluations` — list, run regression, delete
- `/evaluations/:id` — detail

Legacy TraceStore cases from flagging: `GET /v1/eval/cases` (scoped to owned traces). See [architecture.md](architecture.md).
