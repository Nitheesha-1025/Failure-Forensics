"""Trace recorder + `@traced` decorator.

Why this exists separately from OpenTelemetry SDK: OTel produces spans for
*everything* and emits them to a collector. We need spans we can keep around in
our own SQLite/JSON store, with full input/output payloads attached, so the
backward-trace analyzer can reason about each step's transformation. We still
expose the OTel context for compatibility (so downstream OTel collectors can
also consume it), but the source of truth is our own `TraceRecord`.

The `@traced` decorator is the one-liner per step the spec asks for. It works
with both sync and async functions, captures inputs/outputs by Pydantic
serialization (no opaque blobs), and records errors as `StepStatus.ERROR`
without losing the partial output.
"""

from __future__ import annotations

import asyncio
import contextvars
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from pydantic import BaseModel

from ..models import SpanRecord, StepStatus

P = ParamSpec("P")
R = TypeVar("R")

_current: contextvars.ContextVar[TraceRecorder | None] = contextvars.ContextVar(
    "forensics_trace_recorder", default=None
)


class SpanContext:
    """Lightweight handle the decorator passes back to the user.

    A step can call `ctx.set_confidence(0.7)` or `ctx.set_attribute(...)` mid-run
    to enrich its span. We deliberately don't expose the SpanRecord directly —
    that's owned by the recorder and only finalized when the step returns.
    """

    __slots__ = ("_attrs", "_confidence")

    def __init__(self) -> None:
        self._attrs: dict[str, Any] = {}
        self._confidence: float | None = None

    def set_confidence(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        self._confidence = value

    def set_attribute(self, key: str, value: Any) -> None:
        self._attrs[key] = value

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(self._attrs)

    @property
    def confidence(self) -> float | None:
        return self._confidence


class TraceRecorder:
    """Per-trace collector.

    Lives for one pipeline run. Use as `async with recorder.trace(...) as r:`.
    Spans append in arrival order; the decorator chases the recorder via
    a `contextvars.ContextVar`, so async tasks branched mid-pipeline share it.
    """

    def __init__(self, trace_id: str | None = None):
        self.trace_id = trace_id or uuid.uuid4().hex
        self._spans: list[SpanRecord] = []
        self._started_at: datetime | None = None
        self._ended_at: datetime | None = None
        self._status: StepStatus = StepStatus.OK
        self._final: dict[str, Any] | None = None

    @property
    def spans(self) -> list[SpanRecord]:
        return list(self._spans)

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def ended_at(self) -> datetime | None:
        return self._ended_at

    @property
    def status(self) -> StepStatus:
        return self._status

    @property
    def final_output(self) -> dict[str, Any] | None:
        return self._final

    def set_final_output(self, payload: BaseModel | dict[str, Any] | None) -> None:
        if isinstance(payload, BaseModel):
            self._final = payload.model_dump(mode="json")
        else:
            self._final = payload

    @asynccontextmanager
    async def trace(self):  # type: ignore[no-untyped-def]
        token = _current.set(self)
        self._started_at = datetime.now(UTC)
        try:
            yield self
        except Exception:
            self._status = StepStatus.ERROR
            raise
        finally:
            self._ended_at = datetime.now(UTC)
            _current.reset(token)

    def _add_span(self, span: SpanRecord) -> None:
        self._spans.append(span)


def _serialize(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return repr(obj)


def traced(name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator: wrap any sync or async function to emit a SpanRecord.

    Usage:

        @traced("extraction")
        async def extract(intake: IntakeOutput, ctx: SpanContext) -> ExtractionOutput:
            ctx.set_confidence(0.8)
            ...

    The wrapped function may optionally take a final keyword-only argument
    `ctx: SpanContext`. If present, we inject a fresh context per call so the
    function can enrich the span. If absent, we just record inputs/outputs.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        span_name = name or func.__name__
        is_coro = asyncio.iscoroutinefunction(func)

        if is_coro:

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                rec = _current.get()
                if rec is None:
                    return cast(R, await cast(Any, func)(*args, **kwargs))
                ctx = SpanContext()
                wants_ctx = "ctx" in func.__code__.co_varnames
                if wants_ctx:
                    cast(dict[str, Any], kwargs)["ctx"] = ctx
                started = datetime.now(UTC)
                t0 = time.perf_counter()
                status = StepStatus.OK
                error: str | None = None
                output_payload: Any = None
                try:
                    output_payload = await cast(Any, func)(*args, **kwargs)
                    return cast(R, output_payload)
                except Exception as exc:
                    status = StepStatus.ERROR
                    error = f"{type(exc).__name__}: {exc}"
                    raise
                finally:
                    rec._add_span(
                        SpanRecord(
                            span_id=uuid.uuid4().hex,
                            trace_id=rec.trace_id,
                            name=span_name,
                            started_at=started,
                            ended_at=datetime.now(UTC),
                            duration_ms=int((time.perf_counter() - t0) * 1000),
                            status=status,
                            error=error,
                            confidence=ctx.confidence,
                            input=_serialize(_input_snapshot(func, args, kwargs)),
                            output=_serialize(output_payload) if output_payload is not None else {},
                            attributes=ctx.attributes,
                        )
                    )

            return cast(Callable[P, R], async_wrapper)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            rec = _current.get()
            if rec is None:
                return func(*args, **kwargs)
            ctx = SpanContext()
            wants_ctx = "ctx" in func.__code__.co_varnames
            if wants_ctx:
                cast(dict[str, Any], kwargs)["ctx"] = ctx
            started = datetime.now(UTC)
            t0 = time.perf_counter()
            status = StepStatus.OK
            error: str | None = None
            output_payload: Any = None
            try:
                output_payload = func(*args, **kwargs)
                return cast(R, output_payload)
            except Exception as exc:
                status = StepStatus.ERROR
                error = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                rec._add_span(
                    SpanRecord(
                        span_id=uuid.uuid4().hex,
                        trace_id=rec.trace_id,
                        name=span_name,
                        started_at=started,
                        ended_at=datetime.now(UTC),
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                        status=status,
                        error=error,
                        confidence=ctx.confidence,
                        input=_serialize(_input_snapshot(func, args, kwargs)),
                        output=_serialize(output_payload) if output_payload is not None else {},
                        attributes=ctx.attributes,
                    )
                )

        return sync_wrapper

    return decorator


def _input_snapshot(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Best-effort serialization of inputs.

    We deliberately drop the `ctx` argument from the snapshot — it is
    instrumentation, not data, and including it causes recursion via repr.
    """
    code = func.__code__
    names = code.co_varnames[: code.co_argcount]
    bound: dict[str, Any] = {}
    for i, value in enumerate(args):
        if i < len(names):
            bound[names[i]] = value
    bound.update({k: v for k, v in kwargs.items() if k != "ctx"})
    bound.pop("ctx", None)
    return bound


def get_current_recorder() -> TraceRecorder | None:
    return _current.get()
