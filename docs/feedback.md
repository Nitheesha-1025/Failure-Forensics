# Human feedback

Phase 9 stores structured human review in PostgreSQL (`analysis_feedback`), one row per **user** per **trace**.

## Decisions

- `confirmed` — agree with stored root-cause analysis
- `overridden` — disagree (optional comment)

Requires a stored analysis (`GET /v1/traces/{trace_id}/analysis` must exist).

## API

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/v1/traces/{trace_id}/feedback` | Bearer (owned trace) |
| `GET` | `/v1/traces/{trace_id}/feedback` | Bearer (owned trace) |

## UI

Trace Explorer → **Human review** in the failure analysis panel. **Save to evaluations** creates a PostgreSQL eval case when feedback exists. See [evaluations.md](evaluations.md).

## Legacy flagging

`POST /v1/traces/{trace_id}/flag` still writes TraceStore `flagged` + legacy `EvalCase`. Prefer user eval cases for regression workflows tied to explicit human judgment.
