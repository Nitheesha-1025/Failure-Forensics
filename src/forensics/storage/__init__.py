"""Persistence: SQLite for queryable index, JSON files for full trace payloads."""

from .store import TraceStore

__all__ = ["TraceStore"]
