from __future__ import annotations

import pytest

from forensics.models import StepStatus
from forensics.tracing import SpanContext, TraceRecorder, traced
from forensics.tracing.recorder import get_current_recorder


def test_traced_outside_recorder_runs_function_directly() -> None:
    @traced("noop")
    def f(x: int) -> int:
        return x + 1

    assert f(2) == 3


@pytest.mark.asyncio
async def test_async_traced_records_span() -> None:
    @traced("step")
    async def f(x: int, *, ctx: SpanContext) -> int:
        ctx.set_confidence(0.7)
        ctx.set_attribute("note", "ok")
        return x * 2

    rec = TraceRecorder()
    async with rec.trace():
        result = await f(3)

    assert result == 6
    assert len(rec.spans) == 1
    span = rec.spans[0]
    assert span.name == "step"
    assert span.confidence == pytest.approx(0.7)
    assert span.attributes["note"] == "ok"
    assert span.status is StepStatus.OK
    assert span.input == {"x": 3}
    assert span.output == 6


@pytest.mark.asyncio
async def test_traced_records_error_status_and_reraises() -> None:
    @traced("boom")
    async def boom() -> int:
        raise RuntimeError("nope")

    rec = TraceRecorder()
    with pytest.raises(RuntimeError):
        async with rec.trace():
            await boom()

    assert rec.status is StepStatus.ERROR
    assert len(rec.spans) == 1
    assert rec.spans[0].status is StepStatus.ERROR
    assert "nope" in (rec.spans[0].error or "")


@pytest.mark.asyncio
async def test_sync_traced_records_span() -> None:
    @traced()
    def f(a: int, b: int) -> int:
        return a + b

    rec = TraceRecorder()
    async with rec.trace():
        assert f(1, 2) == 3
    assert len(rec.spans) == 1
    assert rec.spans[0].name == "f"


@pytest.mark.asyncio
async def test_get_current_recorder_returns_active_one() -> None:
    rec = TraceRecorder()
    async with rec.trace():
        assert get_current_recorder() is rec
    assert get_current_recorder() is None


def test_span_context_rejects_invalid_confidence() -> None:
    ctx = SpanContext()
    with pytest.raises(ValueError):
        ctx.set_confidence(1.2)
