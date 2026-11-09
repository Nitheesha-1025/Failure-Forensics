# ADR-002: SQLite index + per-trace JSON files (not all-in-one SQLite)

**Status:** Accepted

## Context

We need to store thousands of traces per day, each containing four spans with full input/output payloads. Two storage shapes:

1. Everything in SQLite (one row per span, JSON columns for input/output).
2. SQLite for a narrow searchable index (`trace_id`, status, started_at, flagged); the bulky payload lives in a JSON file per trace on disk.

## Decision

Option 2: SQLite for the index, JSON files for full payloads.

## Consequences

**Why this is the right choice:**

- **Listing and filtering stay fast.** The `traces` index has 9 columns and ~100 bytes per row. A 100K-trace history is 10 MB — trivially fast to scan, even with `LIKE` queries.
- **Reading a single trace is cheap.** One `SELECT` returns a path; one `read_text` returns the JSON. There's no SQLite parsing of a large `TEXT` column.
- **Schema migrations are easier.** The bulky payload is JSON validated by Pydantic on read; bumping `TraceRecord.schema_version` lets us evolve fields without `ALTER TABLE` dances.
- **Backups are easier.** Copying the `traces/` directory + the SQLite file is enough. There's no risk of half-loaded JSON columns or partial WAL state confusing a downstream consumer.
- **Atomic writes are simple.** `flag_and_promote_to_eval` rewrites the JSON first (cheap), then runs a single SQLite transaction that updates the flag and inserts the eval case. If the transaction fails, we restore the original JSON content. There's no cross-table partial state we have to clean up.

**Trade-offs:**

- We have two storage backends to back up. Mitigated by keeping them under the same parent directory and documenting it.
- Queries that need to filter on something inside a span's input/output (e.g. "all traces where extraction returned an empty `customer` field") aren't possible without reading every JSON file. We accept that — those queries are exploratory and belong in a notebook, not in a hot API path. If they become hot, we add an `attributes` view in SQLite that mirrors a few selected fields per trace.
- Renaming or moving the `traces/` directory invalidates the `payload_path` column. We document this as "don't move it without re-pointing the index."

## Alternatives considered

- **Postgres + JSONB.** The right answer at large scale; overkill at the spec's "1K–10K traces/day" target. Migration path is straightforward when needed: the `TraceRecord` schema becomes a Postgres table with JSONB columns; the file-based reader becomes a one-shot importer.
- **Trace blob store (S3 / GCS) + index.** Same as Postgres — right at scale, wrong for a v0 that should run from `pip install -e .`.
- **Time-series DB (ClickHouse, TimescaleDB).** Ideal for high-cardinality dashboards. Defer until "I want to chart median quality across the last 30 days" becomes a real ask, not a hypothetical one.

## Revisit if

- A user reports that listing or filtering takes more than a second on their dataset.
- We grow past ~50K traces and the `traces/` directory becomes unwieldy on the filesystem (consider sub-directory sharding by date).
- A team needs to query inside span payloads regularly.
