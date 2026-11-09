# Analytics

`GET /v1/analytics/summary` returns aggregates for the **authenticated user only**.

## Metrics (from stored data)

| Field | Source |
|--------|--------|
| `total_documents` | PostgreSQL `documents` |
| `total_runs`, `completed_runs`, `failed_runs` | PostgreSQL `pipeline_runs` |
| `analyzed_traces` | User run `trace_id`s with analysis in TraceStore |
| `feedback_confirmed`, `feedback_overridden` | PostgreSQL `analysis_feedback` |
| `evaluation_cases` | PostgreSQL `user_eval_cases` |
| `top_root_causes` | Top expected root-cause **span names** from eval cases (up to 5) |

No mock data; empty accounts return zeros.

## UI

Route `/analytics` — summary cards and top root-causes table.

## API

Bearer JWT required. See [api.md](api.md).
