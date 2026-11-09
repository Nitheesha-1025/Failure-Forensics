"""Authenticated pipeline runs for user-owned documents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user, get_db
from ..db.models import User
from ..documents.errors import DocumentNotFoundError
from ..pipeline_runs.errors import PipelineRunAlreadyInProgressError, PipelineRunNotFoundError
from ..pipeline_runs.schemas import PipelineRunListResponse, PipelineRunPublic
from ..pipeline_runs.service import PipelineRunService, paginate_total_pages
from ..traces import (
    RunTraceResponse,
    TraceAccessDeniedError,
    TraceNotAvailableError,
    TraceNotFoundError,
)
from .trace_deps import trace_access_service, trace_store

if TYPE_CHECKING:
    from .app import AppState

router = APIRouter(prefix="/v1", tags=["pipeline-runs"])

_MAX_PAGE_SIZE = 100


def _run_service(request: Request) -> PipelineRunService:
    service = getattr(request.app.state, "pipeline_run_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="pipeline runs are not configured",
        )
    return cast(PipelineRunService, service)


def _app_state(request: Request) -> AppState:
    return cast("AppState", request.app.state.app_state)


@router.post(
    "/documents/{document_id}/runs",
    response_model=PipelineRunPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_pipeline_run(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PipelineRunPublic:
    run_service = _run_service(request)
    state = _app_state(request)
    try:
        run = await run_service.execute_for_document(
            db,
            user=current_user,
            document_id=document_id,
            pipeline=state.pipeline,
            store=state.store,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except PipelineRunAlreadyInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A pipeline run is already in progress for this document. "
                "Wait for it to finish before starting another run."
            ),
        ) from exc
    return PipelineRunPublic.model_validate(run)


@router.get("/documents/{document_id}/runs", response_model=PipelineRunListResponse)
def list_document_pipeline_runs(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=_MAX_PAGE_SIZE),
) -> PipelineRunListResponse:
    run_service = _run_service(request)
    try:
        items, total = run_service.list_for_document(
            db,
            user=current_user,
            document_id=document_id,
            page=page,
            page_size=page_size,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    return PipelineRunListResponse(
        items=[PipelineRunPublic.model_validate(r) for r in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=paginate_total_pages(total, page_size),
    )


@router.get("/runs/{run_id}/trace", response_model=RunTraceResponse)
def get_pipeline_run_trace(
    run_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RunTraceResponse:
    run_service = _run_service(request)
    access = trace_access_service(request)
    store = trace_store(request)
    try:
        return access.get_trace_for_run(
            db,
            user=current_user,
            run_id=run_id,
            store=store,
            run_service=run_service,
        )
    except PipelineRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pipeline run not found") from exc
    except TraceNotAvailableError as exc:
        raise HTTPException(status_code=404, detail="Trace not available for this run") from exc
    except TraceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Pipeline run not found") from exc


@router.get("/runs/{run_id}", response_model=PipelineRunPublic)
def get_pipeline_run(
    run_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PipelineRunPublic:
    run_service = _run_service(request)
    try:
        run = run_service.get_owned(db, user=current_user, run_id=run_id)
    except PipelineRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pipeline run not found") from exc
    return PipelineRunPublic.model_validate(run)
