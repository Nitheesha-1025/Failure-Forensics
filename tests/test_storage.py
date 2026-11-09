from __future__ import annotations

from datetime import UTC, datetime

import pytest

from forensics.models import (
    FailureFlag,
    RootCauseAnalysis,
    SpanCritique,
)
from forensics.storage import TraceStore

from .conftest import make_span, make_trace


def test_save_and_get_trace_roundtrips(store: TraceStore) -> None:
    trace = make_trace()
    store.save_trace(trace)
    loaded = store.get_trace(trace.trace_id)
    assert loaded is not None
    assert loaded.trace_id == trace.trace_id
    assert len(loaded.spans) == len(trace.spans)


def test_list_traces_orders_recent_first(store: TraceStore) -> None:
    import time

    store.save_trace(make_trace(trace_id="old"))
    time.sleep(0.01)
    store.save_trace(make_trace(trace_id="new"))
    rows = store.list_traces(limit=10)
    assert rows[0]["trace_id"] == "new"


def test_flag_and_promote_creates_eval_case(store: TraceStore) -> None:
    trace = make_trace(trace_id="flagme")
    store.save_trace(trace)
    flag = FailureFlag(
        trace_id="flagme",
        reason="wrong label",
        expected_output="billing",
        flagged_by="alice",
    )
    eval_case = store.flag_and_promote_to_eval(flag)
    assert eval_case is not None
    assert eval_case.source_trace_id == "flagme"
    assert eval_case.expected_summary == "billing"

    cases = store.list_eval_cases()
    assert len(cases) == 1
    assert cases[0].notes == "wrong label"

    after = store.get_trace("flagme")
    assert after is not None
    assert after.flagged is True
    assert after.flag_reason == "wrong label"


def test_flag_unknown_trace_raises(store: TraceStore) -> None:
    flag = FailureFlag(trace_id="missing", reason="x")
    with pytest.raises(KeyError):
        store.flag_and_promote_to_eval(flag)


def test_save_and_get_analysis_roundtrip(store: TraceStore) -> None:
    trace = make_trace()
    store.save_trace(trace)
    analysis = RootCauseAnalysis(
        trace_id=trace.trace_id,
        created_at=datetime.now(UTC),
        judge_model="gpt-4o",
        critiques=[
            SpanCritique(span_id="s1", name="intake", quality=0.9, reason="ok"),
        ],
        root_cause_span_id=None,
        root_cause_explanation="all clean",
    )
    store.save_analysis(analysis)
    back = store.get_analysis(trace.trace_id)
    assert back is not None
    assert back.judge_model == "gpt-4o"
    assert back.root_cause_explanation == "all clean"


def test_list_traces_only_flagged_filters(store: TraceStore) -> None:
    store.save_trace(make_trace(trace_id="a"))
    store.save_trace(make_trace(trace_id="b"))
    store.flag_and_promote_to_eval(FailureFlag(trace_id="a", reason="bad"))
    rows = store.list_traces(limit=10, only_flagged=True)
    assert {r["trace_id"] for r in rows} == {"a"}


def test_eval_case_skipped_when_intake_has_no_text(store: TraceStore) -> None:
    trace = make_trace(
        trace_id="empty",
        spans=[
            make_span(span_id="s1", trace_id="empty", name="intake",
                      input_={}, output={}),
        ],
    )
    store.save_trace(trace)
    flag = FailureFlag(trace_id="empty", reason="bad")
    eval_case = store.flag_and_promote_to_eval(flag)
    assert eval_case is None
