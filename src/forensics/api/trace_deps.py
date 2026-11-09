"""Shared trace-access dependencies for API routes."""

from __future__ import annotations

from typing import cast

from fastapi import HTTPException, Request, status

from ..storage import TraceStore
from ..traces import TraceAccessService


def trace_access_service(request: Request) -> TraceAccessService:
    service = getattr(request.app.state, "trace_access_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="trace access is not configured",
        )
    return cast(TraceAccessService, service)


def app_state(request: Request) -> object:
    return request.app.state.app_state


def trace_store(request: Request) -> TraceStore:
    state = app_state(request)
    store = getattr(state, "store", None)
    return cast(TraceStore, store)
