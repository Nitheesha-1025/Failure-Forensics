# Architecture

## Purpose

**failure-forensics** instruments a multi-step LLM pipeline, persists a structured **trace** per run, and uses an LLM-as-judge **backward trace analyzer** to suggest which step first broke. A React UI lets users upload documents, run the pipeline, inspect spans, review analysis, save **evaluation cases**, and view **analytics**.

## High-level diagram

```text
┌──────────────┐     JWT      ┌─────────────────┐
│ React (Vite) │ ───────────► │ FastAPI /v1     │
└──────────────┘              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │ PostgreSQL   │   │ TraceStore   │   │ Upload files │
            │ users, docs, │   │ SQLite index │   │ UPLOAD_DIR   │
            │ runs,        │   │ + JSON traces│   │              │
            │ feedback,    │   │ + analyses   │   │              │
            │ eval cases   │   └──────────────┘   └──────────────┘
            └──────────────┘
```

## Pipeline (in-process)

```text
intake → extraction → classification → summarization
   │         │              │                │
   └─ @traced spans → TraceRecord → TraceStore
```

## Ownership

PostgreSQL `pipeline_runs` links `user_id` + `trace_id`. Trace APIs check that link before reading TraceStore. See [trace-integration.md](trace-integration.md).

## Two eval mechanisms

1. **Legacy TraceStore eval** — flag a trace (`POST /v1/traces/{id}/flag`); cases live in TraceStore SQLite. Listing is **user-scoped** via owned trace IDs.
2. **User eval cases (PostgreSQL)** — created from human feedback on a reviewed trace; regression re-runs pipeline + analyzer on saved input. See [evaluations.md](evaluations.md).

## Frontend routes

| Path | Purpose |
|------|---------|
| `/` | Landing |
| `/login`, `/register` | Auth |
| `/dashboard` | Home after login |
| `/documents`, `/upload`, `/documents/:id` | Documents |
| `/documents/:documentId/runs/:runId/trace` | Trace explorer + analysis + feedback |
| `/evaluations`, `/evaluations/:id` | Evaluation cases |
| `/analytics` | User metrics |

## Design records

- [ADR-001: Decorator instrumentation](ADR-001-decorator-vs-context-manager.md)
- [ADR-002: Trace storage](ADR-002-trace-storage.md)
- [ADR-003: Root-cause strategy](ADR-003-root-cause-strategy.md)
