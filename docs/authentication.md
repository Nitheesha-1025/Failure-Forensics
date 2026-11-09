# Authentication

JWT-based user accounts live in PostgreSQL. Trace payloads remain in **TraceStore** (SQLite + JSON files); access is enforced via `pipeline_runs` ownership.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/auth/register` | No | Create account (email + password) |
| `POST` | `/v1/auth/login` | No | Returns Bearer access token |
| `GET` | `/v1/auth/me` | Bearer JWT | Current user profile |

Most `/v1/*` resource routes require **Bearer JWT** and enforce **owner-only** access. Exceptions: auth register/login; `POST /v1/runs` is public only when no database is configured (see [trace-integration.md](trace-integration.md)).

## Passwords

Passwords are hashed with **Argon2** before storage. API responses never include `password` or `password_hash`.

Registration requires passwords of at least 8 characters.

## JWT access tokens

- Signed with `JWT_SECRET` (HS256 by default).
- Payload includes `sub` (user id), `exp`, `iat`, and `type=access`.
- Send as `Authorization: Bearer <token>` on protected routes.
- Default lifetime: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (60).

There is no refresh-token flow in Phase 2; clients obtain a new token via `/v1/auth/login`.

## Configuration

| Variable | Required for auth | Purpose |
|----------|-------------------|---------|
| `DATABASE_URL` | Yes | PostgreSQL SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `JWT_SECRET` | Yes | HMAC secret for signing tokens |
| `JWT_ALGORITHM` | No | Default `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default `60` |
| `APPLICATION_SECRET` | No | Reserved for future session/cookie use |

Aliases `FORENSICS_DATABASE_URL` and `FORENSICS_JWT_SECRET` are also accepted.

If `DATABASE_URL` or `JWT_SECRET` is missing, auth endpoints return **503** with a safe message.

## Example

```bash
curl -s -X POST http://localhost:8090/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"your-secure-password"}'

curl -s -X POST http://localhost:8090/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"your-secure-password"}'

curl -s http://localhost:8090/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

## Security notes

- Use a long random `JWT_SECRET` in production (≥32 characters when `DATABASE_URL` is set; placeholder values are rejected at startup).
- Do not commit `.env` or secrets to version control.
- Login failures use a generic message (`Invalid email or password`) to avoid account enumeration on passwords.
