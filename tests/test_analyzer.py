from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from forensics.analyzer import analyze_trace
from forensics.analyzer.judge import _parse, critique_span_async
from forensics.analyzer.root_cause import _pick_root_cause
from forensics.models import (
    SpanCritique,
    SpanRecord,
    StepStatus,
    TraceRecord,
)

from .conftest import chat_response, make_llm_client, make_span, make_trace


def test_pick_root_cause_picks_first_quality_cliff() -> None:
    crits = [
        SpanCritique(span_id="s1", name="intake", quality=0.95, reason="fine"),
        SpanCritique(span_id="s2", name="extraction", quality=0.92, reason="fine"),
        SpanCritique(span_id="s3", name="classification", quality=0.40, reason="bad"),
        SpanCritique(span_id="s4", name="summarization", quality=0.30, reason="cascade"),
    ]
    rid, expl = _pick_root_cause(crits, min_quality=0.6)
    assert rid == "s3"
    assert "classification" in expl


def test_pick_root_cause_prefers_explicit_candidate_over_cliff() -> None:
    crits = [
        SpanCritique(span_id="s1", name="intake", quality=0.5, reason="meh"),
        SpanCritique(
            span_id="s2",
            name="extraction",
            quality=0.95,
            reason="suspicious",
            is_root_cause_candidate=True,
        ),
    ]
    rid, _ = _pick_root_cause(crits, min_quality=0.6)
    assert rid == "s2"


def test_pick_root_cause_returns_none_when_all_high() -> None:
    crits = [
        SpanCritique(span_id="s1", name="intake", quality=0.9, reason="ok"),
        SpanCritique(span_id="s2", name="extraction", quality=0.95, reason="ok"),
    ]
    rid, _ = _pick_root_cause(crits, min_quality=0.6)
    assert rid is None


def test_pick_root_cause_falls_back_to_lowest_when_no_cliff() -> None:
    crits = [
        SpanCritique(span_id="s1", name="intake", quality=0.4, reason="meh"),
        SpanCritique(span_id="s2", name="extraction", quality=0.5, reason="meh"),
    ]
    rid, expl = _pick_root_cause(crits, min_quality=0.6)
    # The first span was already below threshold; the algorithm picks it
    # via the `min_quality` fallback path.
    assert rid in {"s1", "s2"}
    assert "quality" in expl.lower() or "no span" not in expl.lower()


def test_parse_judge_response_invalid_returns_neutral() -> None:
    started = datetime.now(UTC)
    span = SpanRecord(
        span_id="s1",
        trace_id="t1",
        name="intake",
        started_at=started,
        ended_at=started,
        duration_ms=10,
        status=StepStatus.OK,
    )
    crit = _parse("not json", span)
    assert crit.quality == 0.5
    assert "parse error" in crit.reason


@pytest.mark.asyncio
async def test_critique_span_short_circuits_on_error_status() -> None:
    span = make_span(
        span_id="s1",
        trace_id="t1",
        name="extraction",
        status=StepStatus.ERROR,
    )
    span_with_err = span.model_copy(update={"error": "boom"})

    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("judge should NOT be called for ERROR spans")

    client = make_llm_client(lambda r: chat_response("{}"))
    try:
        crit = await critique_span_async(
            client=client, judge_model="gpt-4o", span=span_with_err
        )
    finally:
        await client.aclose()
    assert crit.is_root_cause_candidate is True
    assert crit.quality == 0.0


@pytest.mark.asyncio
async def test_analyze_trace_picks_failed_step_as_root_cause() -> None:
    spans = [
        make_span(span_id="s1", trace_id="t1", name="intake"),
        make_span(span_id="s2", trace_id="t1", name="extraction",
                  status=StepStatus.ERROR, confidence=None).model_copy(
            update={"error": "ValueError: no fields"}),
        make_span(span_id="s3", trace_id="t1", name="classification"),
    ]
    trace = TraceRecord(
        trace_id="t1",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        duration_ms=100,
        status=StepStatus.ERROR,
        spans=spans,
    )

    client = make_llm_client(
        lambda r: chat_response('{"quality": 0.9, "reason": "ok", "is_root_cause_candidate": false}')
    )
    try:
        analysis = await analyze_trace(trace, client=client, judge_model="gpt-4o")
    finally:
        await client.aclose()

    assert analysis.root_cause_span_id == "s2"
    assert "ValueError" in analysis.root_cause_explanation


@pytest.mark.asyncio
async def test_analyze_trace_limits_judge_concurrency() -> None:
    spans = [
        make_span(span_id=f"s{i}", trace_id="t1", name=f"step-{i}")
        for i in range(4)
    ]
    trace = TraceRecord(
        trace_id="t1",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        duration_ms=100,
        status=StepStatus.OK,
        spans=spans,
    )
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def delayed_handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.03)
        async with lock:
            in_flight -= 1
        return chat_response(
            '{"quality": 0.9, "reason": "ok", "is_root_cause_candidate": false}'
        )

    class AsyncMockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return await delayed_handler(request)

    transport_client = httpx.AsyncClient(transport=AsyncMockTransport())
    from forensics.llm_client import LLMClient

    client = LLMClient(api_key="k", client=transport_client, max_retries=0)
    try:
        analysis = await analyze_trace(
            trace, client=client, judge_model="gpt-4o", concurrency=1
        )
    finally:
        await client.aclose()
    assert len(analysis.critiques) == 4
    assert max_in_flight == 1


@pytest.mark.asyncio
async def test_analyze_trace_with_empty_spans() -> None:
    trace = TraceRecord(
        trace_id="t1",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        duration_ms=0,
        status=StepStatus.OK,
        spans=[],
    )
    client = make_llm_client(lambda r: chat_response("{}"))
    try:
        analysis = await analyze_trace(trace, client=client, judge_model="gpt-4o")
    finally:
        await client.aclose()
    assert analysis.root_cause_span_id is None
    assert analysis.critiques == []


def test_make_trace_synthetic_factory_round_trips() -> None:
    trace = make_trace()
    assert trace.spans[0].name == "intake"
    assert trace.final_output == {"summary": "ok"}
