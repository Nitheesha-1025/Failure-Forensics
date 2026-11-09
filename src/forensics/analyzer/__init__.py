"""Backward-trace analyzer: critique each span, find the first quality cliff."""

from .judge import critique_span_async
from .root_cause import analyze_trace

__all__ = ["analyze_trace", "critique_span_async"]
