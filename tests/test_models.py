from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forensics.models import SpanRecord, StepStatus, TraceRecord


def test_trace_rejects_misaligned_span_trace_id() -> None:
    started = datetime.now(UTC)
    span = SpanRecord(
        span_id="s1",
        trace_id="WRONG",
        name="intake",
        started_at=started,
        ended_at=started,
        duration_ms=10,
        status=StepStatus.OK,
    )
    with pytest.raises(ValidationError, match="trace_id"):
        TraceRecord(
            trace_id="t1",
            started_at=started,
            ended_at=started,
            duration_ms=10,
            status=StepStatus.OK,
            spans=[span],
        )


def test_trace_rejects_negative_duration() -> None:
    started = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TraceRecord(
            trace_id="t1",
            started_at=started,
            ended_at=started,
            duration_ms=-5,
            status=StepStatus.OK,
        )


def test_span_record_rejects_invalid_confidence() -> None:
    started = datetime.now(UTC)
    with pytest.raises(ValidationError):
        SpanRecord(
            span_id="s1",
            trace_id="t1",
            name="intake",
            started_at=started,
            ended_at=started,
            duration_ms=10,
            status=StepStatus.OK,
            confidence=1.5,
        )
