"""TraceStore: SQLite index + per-trace JSON files.

Why split storage in two: the trace JSON can grow large (full input/output for
every span). Putting everything in SQLite makes queries slow as JSON columns
balloon. Keeping the index narrow (`trace_id`, timestamps, status, flagged)
in SQLite and offloading the bulky payload to a JSON file on disk gives us
fast list/filter and cheap full-trace reads — which is what the explorer
actually needs.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..models import (
    EvalCase,
    FailureFlag,
    RootCauseAnalysis,
    TraceRecord,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    n_spans INTEGER NOT NULL,
    flagged INTEGER NOT NULL DEFAULT 0,
    flag_reason TEXT,
    payload_path TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS traces_started_idx ON traces (started_at DESC);
CREATE INDEX IF NOT EXISTS traces_flagged_idx ON traces (flagged, started_at DESC);

CREATE TABLE IF NOT EXISTS analyses (
    trace_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    root_cause_span_id TEXT,
    root_cause_explanation TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES traces (trace_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS eval_cases (
    case_id TEXT PRIMARY KEY,
    source_trace_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    expected_label TEXT,
    expected_summary TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS eval_source_idx ON eval_cases (source_trace_id);
"""


class TraceStore:
    def __init__(self, db_path: Path, traces_dir: Path):
        self._db_path = db_path
        self._traces_dir = traces_dir
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._traces_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn: sqlite3.Connection = sqlite3.connect(self._db_path, isolation_level=None)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Traces
    # ------------------------------------------------------------------

    def save_trace(self, trace: TraceRecord) -> Path:
        payload_path = self._traces_dir / f"{trace.trace_id}.json"
        payload_path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO traces
                (trace_id, started_at, ended_at, duration_ms, status, n_spans,
                 flagged, flag_reason, payload_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.trace_id,
                    trace.started_at.isoformat(),
                    trace.ended_at.isoformat(),
                    trace.duration_ms,
                    trace.status.value,
                    len(trace.spans),
                    1 if trace.flagged else 0,
                    trace.flag_reason,
                    str(payload_path),
                ),
            )
        return payload_path

    def get_trace(self, trace_id: str) -> TraceRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_path FROM traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
        if row is None:
            return None
        path = Path(row[0])
        if not path.exists():
            return None
        return TraceRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list_traces(
        self, *, limit: int = 50, only_flagged: bool = False
    ) -> list[dict[str, object]]:
        sql = (
            "SELECT trace_id, started_at, ended_at, duration_ms, status, n_spans, "
            "flagged, flag_reason FROM traces"
        )
        params: tuple[object, ...] = ()
        if only_flagged:
            sql += " WHERE flagged = 1"
        sql += " ORDER BY started_at DESC LIMIT ?"
        params = (*params, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        cols = [
            "trace_id",
            "started_at",
            "ended_at",
            "duration_ms",
            "status",
            "n_spans",
            "flagged",
            "flag_reason",
        ]
        return [dict(zip(cols, r, strict=True)) for r in rows]

    # ------------------------------------------------------------------
    # Failure flags + atomic eval-case creation
    # ------------------------------------------------------------------

    def flag_and_promote_to_eval(
        self,
        flag: FailureFlag,
    ) -> EvalCase | None:
        """Atomically: flag the trace, optionally derive an EvalCase, write both."""
        trace = self.get_trace(flag.trace_id)
        if trace is None:
            raise KeyError(f"trace not found: {flag.trace_id}")

        trace_after = trace.model_copy(
            update={"flagged": True, "flag_reason": flag.reason},
            deep=True,
        )
        eval_case = _maybe_eval_case(flag, trace_after)

        # Two-phase write: file first (rewrite full JSON), then SQLite transaction
        # that updates `flagged` AND inserts the eval case in one go. If the
        # SQLite transaction fails, we re-write the original file to roll back.
        original_payload = (self._traces_dir / f"{flag.trace_id}.json").read_text(
            encoding="utf-8"
        )
        try:
            self.save_trace(trace_after)  # rewrites the JSON payload
            with self._connect() as conn:
                conn.execute("BEGIN")
                try:
                    conn.execute(
                        "UPDATE traces SET flagged = 1, flag_reason = ? WHERE trace_id = ?",
                        (flag.reason, flag.trace_id),
                    )
                    if eval_case is not None:
                        conn.execute(
                            """
                            INSERT INTO eval_cases
                            (case_id, source_trace_id, created_at, raw_text,
                             expected_label, expected_summary, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                eval_case.case_id,
                                eval_case.source_trace_id,
                                eval_case.created_at.isoformat(),
                                eval_case.raw_text,
                                eval_case.expected_label,
                                eval_case.expected_summary,
                                eval_case.notes,
                            ),
                        )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
        except Exception:
            # Roll back the JSON rewrite to keep the on-disk state consistent.
            (self._traces_dir / f"{flag.trace_id}.json").write_text(
                original_payload, encoding="utf-8"
            )
            raise

        return eval_case

    def list_eval_cases(self, limit: int = 100) -> list[EvalCase]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT case_id, source_trace_id, created_at, raw_text,
                       expected_label, expected_summary, notes
                FROM eval_cases ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: list[EvalCase] = []
        for case_id, src, created, raw_text, exp_label, exp_summary, notes in rows:
            out.append(
                EvalCase(
                    case_id=case_id,
                    source_trace_id=src,
                    raw_text=raw_text,
                    expected_label=exp_label,
                    expected_summary=exp_summary,
                    notes=notes,
                    created_at=__import__("datetime").datetime.fromisoformat(created),
                )
            )
        return out

    # ------------------------------------------------------------------
    # Analyses
    # ------------------------------------------------------------------

    def save_analysis(self, analysis: RootCauseAnalysis) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analyses
                (trace_id, created_at, judge_model, root_cause_span_id,
                 root_cause_explanation, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.trace_id,
                    analysis.created_at.isoformat(),
                    analysis.judge_model,
                    analysis.root_cause_span_id,
                    analysis.root_cause_explanation,
                    analysis.model_dump_json(),
                ),
            )

    def get_analysis(self, trace_id: str) -> RootCauseAnalysis | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM analyses WHERE trace_id = ?", (trace_id,)
            ).fetchone()
        if row is None:
            return None
        return RootCauseAnalysis.model_validate_json(row[0])


def _maybe_eval_case(flag: FailureFlag, trace: TraceRecord) -> EvalCase | None:
    """Build an EvalCase from a flagged trace if intake metadata is available."""
    intake_span = next((s for s in trace.spans if s.name == "intake"), None)
    if intake_span is None:
        return None
    raw_text = intake_span.input.get("raw_text") or intake_span.output.get("raw_text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    classification_span = next((s for s in trace.spans if s.name == "classification"), None)
    expected_label = None
    if classification_span is not None and isinstance(classification_span.output.get("label"), str):
        # The current label is wrong by definition (the trace was flagged), so
        # we leave expected_label blank for human review unless the flag itself
        # supplied an `expected_output` to use as a label hint.
        expected_label = None
    return EvalCase(
        case_id=uuid.uuid4().hex,
        source_trace_id=flag.trace_id,
        raw_text=raw_text,
        expected_label=expected_label,
        expected_summary=flag.expected_output,
        notes=flag.reason,
    )
