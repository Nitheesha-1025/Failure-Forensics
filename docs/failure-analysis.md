# Failure analysis

After a pipeline run, each step's inputs/outputs are stored in **TraceStore**. The **backward-trace analyzer** runs an LLM-as-judge over spans and picks a **root cause span** (first significant quality cliff; see [ADR-003](ADR-003-root-cause-strategy.md)).

## API

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/v1/traces/{trace_id}/analyze` | Bearer (owned trace) |
| `GET` | `/v1/traces/{trace_id}/analysis` | Bearer (owned trace) |

Analysis is persisted in TraceStore and returned as `RootCauseAnalysis` (critiques per span, `root_cause_span_id`, explanation).

## UI

Trace Explorer → **Failure analysis** panel: load saved analysis or run analyze. Uses the same endpoints.

## Configuration

- `FORENSICS_JUDGE_MODEL` (default `gpt-4o`)
- `FORENSICS_OPENAI_API_KEY` required for analyze

Human **feedback** is separate and does not re-run the analyzer. See [feedback.md](feedback.md).
