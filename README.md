# failure-forensics

**Observability and root-cause analysis for multi-step LLM pipelines** — trace every step, find where quality breaks, review with humans, and regression-check saved cases.

[![Tests](https://github.com/metehanulusoy/failure-forensics/actions/workflows/test.yml/badge.svg)](https://github.com/metehanulusoy/failure-forensics/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

> **Production deployment has not been executed yet.** Docker and deployment docs describe how to run and deploy; no live production URL is claimed.

---

## Problem

Multi-step AI pipelines (intake → extract → classify → summarize) often fail **without crashing**: downstream steps look fine while an early step silently degrades. Stack traces and raw logs make it hard to see **which step** broke first.

## What this system does

1. Runs a **four-step document pipeline** with per-step tracing (`@traced`).
2. Persists **traces** (SQLite index + JSON) and links runs to **users** in PostgreSQL.
3. Runs an **LLM-as-judge** analyzer to propose a **root-cause span**.
4. Provides a **React UI** for upload, runs, trace explorer, analysis, human feedback, evaluations, and analytics.
5. Supports **evaluation cases** and **synchronous regression** against saved human judgment.

## Key features

- Strict **Pydantic** contracts between pipeline steps
- **JWT authentication** and owner-scoped documents, runs, traces, feedback, eval cases, analytics
- **Document upload** (PDF, DOCX, TXT, Markdown) with validation and size limits
- **Trace explorer** with span timeline and failure analysis panel
- **Human feedback** (`confirmed` / `overridden`) stored in PostgreSQL
- **User evaluation cases** + regression runs (no separate LLM judge for eval)
- **Analytics dashboard** from real stored metrics
- **Docker Compose** for local full stack (frontend + API + Postgres)
- CLI: `forensics run`, `forensics serve`, `forensics traces`

## End-to-end workflow

Why this flow matters: each stage produces **durable artifacts** (file → run → trace → analysis → human label → eval case → regression metric → aggregate analytics), so debugging today becomes a **repeatable check** tomorrow.

```text
Upload document
      ↓
Pipeline run (POST /v1/documents/{id}/runs)
      ↓
Trace + spans (TraceStore, linked in pipeline_runs)
      ↓
Failure analysis (LLM judge → RootCauseAnalysis)
      ↓
Human review (feedback on trace)
      ↓
Evaluation case (snapshot + expected judgment)
      ↓
Regression (re-run pipeline + analyze, compare)
      ↓
Analytics (user-scoped counts & top root causes)
```

## Architecture

```text
┌─────────────┐   HTTPS/HTTP   ┌──────────────────┐
│ React (Vite)│ ─────────────► │ FastAPI  :8090   │
└─────────────┘   Bearer JWT   └────────┬─────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
       ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
       │ PostgreSQL  │          │ TraceStore  │          │ UPLOAD_DIR  │
       │ users, docs,│          │ SQLite +    │          │ (per-user   │
       │ runs,       │          │ trace JSON  │          │  UUID keys) │
       │ feedback,   │          │ analyses    │          └─────────────┘
       │ eval cases  │          └─────────────┘
       └─────────────┘
                    Pipeline (in-process, OpenAI)
              intake → extraction → classification → summarization
```

Details: [docs/architecture.md](docs/architecture.md) · ADRs in [docs/](docs/README.md).

## Tech stack

| Layer | Technology |
|--------|------------|
| API | FastAPI, Uvicorn, Pydantic v2 |
| Auth | JWT (PyJWT), Argon2 passwords |
| App DB | PostgreSQL, SQLAlchemy 2, Alembic |
| Traces | SQLite index + JSON files (TraceStore) |
| LLM | OpenAI-compatible HTTP (httpx) |
| Frontend | React 19, TypeScript, Vite, React Router |
| Tests | pytest, Vitest, ruff, mypy |
| Containers | Docker, docker-compose, nginx (frontend image) |

## Project structure

```text
failure-forensics/
├── src/forensics/          # Python package (API, pipeline, analyzer, storage)
├── frontend/               # React SPA
├── alembic/                # PostgreSQL migrations
├── tests/                  # Backend tests
├── docs/                   # Topic guides + API reference
├── docker/                 # API entrypoint (migrations + serve)
├── Dockerfile              # Backend image
├── frontend/Dockerfile     # Frontend image (nginx)
├── docker-compose.yml      # postgres + api + frontend
├── pyproject.toml
└── README.md
```

## Local setup

### Prerequisites

- Python 3.11+
- Node.js 20+ (for frontend dev)
- PostgreSQL (local or Docker)
- Cloudflare Workers AI credentials (Free plan) or OpenAI if using that provider

### Backend + database

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev,ui]"

cp .env.example .env
# Set DATABASE_URL, JWT_SECRET (≥32 chars), CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN

docker compose up postgres -d   # optional: only Postgres from compose
alembic upgrade head
forensics serve                 # http://localhost:8090
```

### Frontend (development)

```bash
cd frontend
cp .env.example .env            # VITE_API_BASE_URL=http://localhost:8090
npm install
npm run dev                     # http://localhost:5173
```

Set `CORS_ORIGINS` on the API to include your frontend origin (default includes `http://localhost:5173`).

### CLI-only trace run (no Postgres)

With empty `DATABASE_URL`, `forensics run` and unauthenticated `POST /v1/runs` remain available for local pipeline experiments.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | For multi-user app | `postgresql+psycopg://...` |
| `JWT_SECRET` | With DB | ≥32 chars; not a placeholder when DB set |
| `CLOUDFLARE_ACCOUNT_ID` | Yes (serve/run, default) | Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | Yes (serve/run, default) | API token with Workers AI Read |
| `CLOUDFLARE_MODEL` | No | Default `@cf/meta/llama-3.1-8b-instruct` (Free tier) |
| `FORENSICS_LLM_PROVIDER` | No | `cloudflare`, `openai`, or `auto` |
| `FORENSICS_OPENAI_API_KEY` | If provider is OpenAI | OpenAI API key |
| `UPLOAD_DIR` | No | Default `./uploads` |
| `MAX_UPLOAD_SIZE_MB` | No | Default `25` |
| `FORENSICS_DB_PATH` | No | TraceStore SQLite path |
| `FORENSICS_TRACES_DIR` | No | Per-trace JSON directory |
| `FORENSICS_*_MODEL` | No | Step + judge model names |
| `CORS_ORIGINS` | No | Comma-separated browser origins |
| `VITE_API_BASE_URL` | Frontend build/dev | API origin (no trailing slash) |

See [.env.example](.env.example), [frontend/.env.example](frontend/.env.example), [docker-compose.env.example](docker-compose.env.example).

## Database & migrations

PostgreSQL holds: `users`, `documents`, `pipeline_runs`, `analysis_feedback`, `user_eval_cases`.

```bash
alembic upgrade head
```

Migrations live in `alembic/versions/`. Details: [docs/database.md](docs/database.md).

Trace payloads and analyses remain in **TraceStore** (not migrated to Postgres).

## Docker setup

```bash
cp docker-compose.env.example .env
# Edit JWT_SECRET, CLOUDFLARE_ACCOUNT_ID, and CLOUDFLARE_API_TOKEN

docker compose build
docker compose up
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:8080 |
| API | http://localhost:8090 |
| Health | http://localhost:8090/health |

The API entrypoint runs **`alembic upgrade head`** before `forensics serve`. Volumes: `pg-data`, `forensics-data` (uploads + traces).

**Note:** Docker image build/up was not verified in every environment (Docker daemon may be unavailable). Follow the commands above on a machine with Docker installed.

Optional Streamlit explorer: `docker compose --profile ui up explorer`.

Full deployment guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## API overview

Complete reference: **[docs/api.md](docs/api.md)**.

| Area | Prefix | Auth |
|------|--------|------|
| Health | `/health` | None |
| Auth | `/v1/auth/*` | Mixed |
| Documents | `/v1/documents/*` | Bearer |
| Runs & traces | `/v1/documents/.../runs`, `/v1/runs/*`, `/v1/traces/*` | Bearer |
| Analysis & flag | `/v1/traces/{id}/analyze`, `/analysis`, `/flag` | Bearer |
| Feedback | `/v1/traces/{id}/feedback` | Bearer |
| Evaluations | `/v1/evaluations/*` | Bearer |
| Legacy eval list | `/v1/eval/cases` | Bearer (owned traces) |
| Analytics | `/v1/analytics/summary` | Bearer |
| Legacy raw run | `POST /v1/runs` | Bearer if DB configured |

## Authentication & security

- Passwords hashed with **Argon2**; JWT access tokens (HS256).
- **Owner-only** access for documents, runs, traces, analysis, feedback, evaluations, analytics (404 cross-user).
- Upload validation: extension, content checks, size cap, filename sanitization, UUID storage paths.
- **CORS** explicit via `CORS_ORIGINS`.
- Do not commit `.env` (see [.gitignore](.gitignore)).

Details: [docs/authentication.md](docs/authentication.md).

## Evaluation & analytics

- **Evaluations:** create from a reviewed trace; run regression synchronously. [docs/evaluations.md](docs/evaluations.md)
- **Analytics:** user-scoped summary from Postgres + TraceStore. [docs/analytics.md](docs/analytics.md)
- **Feedback:** [docs/feedback.md](docs/feedback.md) · **Analysis:** [docs/failure-analysis.md](docs/failure-analysis.md)

## Testing

**Backend** (repo root):

```bash
pytest
ruff check src tests
mypy src
```

**Frontend**:

```bash
cd frontend
npm test
npm run build
npm run lint
```

## Deployment instructions

1. Build images (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).
2. Provision **managed PostgreSQL** and a **volume** for `/data/uploads` and TraceStore paths.
3. Set production secrets (`JWT_SECRET`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `DATABASE_URL`, `CORS_ORIGINS`).
4. Build frontend with `VITE_API_BASE_URL` pointing at the public API URL (HTTPS).
5. Run migrations (`alembic upgrade head` or API container entrypoint).
6. Terminate TLS at a reverse proxy or platform ingress.

**Production deployment has not been executed yet.**

## Current limitations

- TraceStore remains **SQLite + files** (not in PostgreSQL).
- Regression is **one case at a time**, synchronous; LLM non-determinism affects pass/fail.
- `VITE_API_BASE_URL` is **build-time** for the frontend image.
- No refresh tokens; no rate limiting.
- Legacy `POST /v1/runs` without user linkage when used outside document runs.
- Docker end-to-end smoke tests depend on a local Docker daemon.

## Future improvements

- Migrate or replicate TraceStore to a shared durable backend
- Batch/async regression runner (if infrastructure added)
- Refresh tokens and optional OAuth
- Rate limiting and audit logging
- Object storage (S3) for uploads
- Recorded demo assets and hosted staging environment

## Demo / screenshots

<!-- Add screenshots or a short demo GIF here when available. No assets are bundled in this repository yet. -->

_Placeholder: link to a demo video or screenshots once captured._

## Documentation index

All guides: **[docs/README.md](docs/README.md)**

## License

MIT — see [LICENSE](LICENSE).
