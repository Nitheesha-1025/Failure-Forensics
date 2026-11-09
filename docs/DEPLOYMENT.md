# Deployment

> **Production deployment has not been executed from this repository.** Images and compose files are provided; operators deploy manually. Docker runtime verification may be unavailable in some CI/dev environments (daemon not running).

Production-style layout:

```text
Browser → Frontend (static / CDN / nginx)
              ↓ HTTPS
         Backend API (FastAPI)
              ↓
         PostgreSQL (managed)
              ↓
         Persistent volume (uploads + TraceStore paths)
```

This repo ships **Docker images** and **docker-compose** for local full-stack runs. Cloud deployment is **manual** (no credentials are stored in the repository).

## Recommended provider (student-friendly)

**Railway**, **Render**, or **Fly.io** — each can run a container + managed Postgres + volume (or S3-compatible storage later). The steps below apply to any Docker host.

## 1. Build images

From the repository root:

```bash
docker compose build
```

Production frontend must be built with the **public API URL** the browser will use:

```bash
docker build -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com \
  -t failure-forensics-frontend:prod ./frontend

docker build -t failure-forensics-api:prod .
```

## 2. Environment variables (production)

| Variable | Required | Notes |
|----------|----------|--------|
| `DATABASE_URL` | Yes | `postgresql+psycopg://...` managed Postgres |
| `JWT_SECRET` | Yes | ≥ 32 chars; unique per environment |
| `CLOUDFLARE_ACCOUNT_ID` | Yes (Cloudflare default) | Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | Yes (Cloudflare default) | API token with Workers AI Read |
| `CLOUDFLARE_MODEL` | No | e.g. `@cf/meta/llama-3.1-8b-instruct` (Workers Free: 10k Neurons/day) |
| `FORENSICS_LLM_PROVIDER` | No | `cloudflare`, `openai`, or `auto` (default `auto`) |
| `FORENSICS_OPENAI_API_KEY` | If provider is OpenAI | LLM pipeline + judge |
| `UPLOAD_DIR` | Yes | Writable path (volume mount), e.g. `/data/uploads` |
| `FORENSICS_DB_PATH` | Yes | TraceStore SQLite index, e.g. `/data/forensics.sqlite3` |
| `FORENSICS_TRACES_DIR` | Yes | Trace JSON dir, e.g. `/data/traces` |
| `CORS_ORIGINS` | Yes | Exact frontend origin(s), e.g. `https://app.yourdomain.com` |
| `FORENSICS_API_HOST` | Yes | `0.0.0.0` in containers |
| `FORENSICS_LOG_LEVEL` | No | Use `INFO` (not `DEBUG`) in production |
| `MAX_UPLOAD_SIZE_MB` | No | Default `25` |

**Frontend build-time:** `VITE_API_BASE_URL` must match the API URL exposed to browsers (HTTPS).

Do **not** bake secrets into images. Inject via the platform’s secret store or `.env` on the host (never commit).

## 3. Database migrations

The API container entrypoint runs:

```bash
alembic upgrade head
```

before `forensics serve`, when `DATABASE_URL` is set. For one-off runs:

```bash
docker run --rm -e DATABASE_URL=... failure-forensics-api:prod alembic upgrade head
```

## 4. Health checks

- API: `GET /health` → `{"status":"ok"}`
- Frontend nginx: `GET /` (SPA shell)

Configure load balancers to use these paths.

## 5. Example: single VPS (Docker Compose)

1. Provision a VM with Docker.
2. Copy `docker-compose.yml`, set production `.env` (strong `JWT_SECRET`, real `FORENSICS_OPENAI_API_KEY`, `CORS_ORIGINS=https://your-frontend-domain`).
3. Put **TLS** in front (Caddy, nginx, or Cloudflare) — terminate HTTPS at the edge; set `VITE_API_BASE_URL` to the public API URL when rebuilding frontend.
4. `docker compose up -d` (postgres + api + frontend).
5. Verify: register, upload, run pipeline, trace explorer, analytics.

## 6. Persistence

- **PostgreSQL:** `pg-data` volume (compose) or managed DB.
- **Uploads + traces:** mount `forensics-data` (or host path) at `/data` on the API service.

## 7. HTTPS

FastAPI does not terminate TLS inside the container. Use a reverse proxy or platform ingress with HTTPS; set `CORS_ORIGINS` to the `https://` frontend origin only.

## Local Docker quick start

```bash
cp docker-compose.env.example .env
# Edit .env — JWT_SECRET and FORENSICS_OPENAI_API_KEY
docker compose build
docker compose up
```

- Frontend: http://localhost:8080  
- API: http://localhost:8090  
- Health: http://localhost:8090/health  

Optional Streamlit explorer: `docker compose --profile ui up explorer`
