# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] — Initial release

### Added
- Strict Pydantic contracts for the 4-step example pipeline (`IntakeOutput`, `ExtractionOutput`, `ClassificationOutput`, `SummarizationOutput`).
- `@traced` decorator with automatic input/output snapshots, `SpanContext` enrichment, async + sync support.
- `TraceRecorder` and versioned `TraceRecord` (schema v1).
- `TraceStore`: SQLite index + per-trace JSON files, atomic `flag_and_promote_to_eval`.
- Backward-trace analyzer (`analyze_trace`): per-span LLM-as-judge with parallel dispatch, "first quality cliff" root-cause selection, error-status short-circuit.
- FastAPI gateway (`/v1/runs`, `/v1/traces`, `/v1/traces/{id}/analyze`, `/v1/traces/{id}/flag`, `/v1/eval/cases`, `/health`).
- Streamlit `forensics.explorer` with side-by-side per-span panels and root-cause highlighting.
- Click CLI: `forensics run`, `forensics serve`, `forensics traces`.
- 50+-test pytest suite with `httpx.MockTransport` doubles, mypy strict, ruff lint, ≥80 % coverage gate.
- Dockerfile + docker-compose with optional Streamlit profile, three architecture decision records.
