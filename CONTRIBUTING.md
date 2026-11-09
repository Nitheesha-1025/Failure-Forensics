# Contributing

## Local setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make check
```

`make check` runs `ruff` + `mypy --strict` + `pytest --cov`. CI runs the same matrix on Python 3.11 and 3.12; PRs are blocked until coverage stays at or above **80 %**.

## Conventions

- **Conventional commits.** `feat(tracing): ...`, `fix(analyzer): ...`, `docs(adr): ...`.
- **No untyped public API.** `mypy --strict` will reject it.
- **All HTTP I/O in tests is mocked** with `httpx.MockTransport`. Real network calls in the test suite are not allowed.
- **Trace JSON schema changes are first-class.** If you add or rename a `TraceRecord` field, bump `schema_version` and document the migration story in [`docs/ADR-002-trace-storage.md`](docs/ADR-002-trace-storage.md).

## Code of conduct

Be kind. Disagreements are about the work, never about people.
