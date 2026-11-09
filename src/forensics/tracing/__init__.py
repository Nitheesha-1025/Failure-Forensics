"""Decorator-based span instrumentation. One-liner per pipeline step."""

from .recorder import SpanContext, TraceRecorder, traced

__all__ = ["SpanContext", "TraceRecorder", "traced"]
