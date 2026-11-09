"""HTTP routes: run pipeline, list/query traces, analyze, flag."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..analyzer import analyze_trace
from ..auth.deps import get_current_user, get_current_user_when_database_enabled, get_db
from ..config import Settings
from ..db.models import User
from ..feedback.schemas import AnalysisFeedbackPublic, SubmitAnalysisFeedbackRequest
from ..feedback.service import (
    AnalysisFeedbackNotFoundError,
    AnalysisFeedbackService,
    AnalysisNotStoredError,
    feedback_public,
)
from ..llm_client import LLMError
from ..models import (
    EvalCase,
    FailureFlag,
    RootCauseAnalysis,
    TraceRecord,
)
from ..pipeline import run_pipeline
from ..traces import TraceAccessDeniedError, TraceNotFoundError, trace_detail_from_record
from ..traces.schemas import TraceDetailPublic
from .llm_errors import http_exception_from_llm_error
from .trace_deps import app_state, trace_access_service, trace_store

if TYPE_CHECKING:
    from .app import AppState

router = APIRouter(prefix="/v1")


def _analysis_feedback_service(request: Request) -> AnalysisFeedbackService:
    access = trace_access_service(request)
    return AnalysisFeedbackService(access=access)


class RunRequest(BaseModel):
    document_id: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    trace_id: str | None = None


class RunResponse(BaseModel):
    trace: TraceRecord
    final_summary: str | None


@router.post("/runs", response_model=RunResponse, tags=["pipeline"])
async def create_run(
    req: RunRequest,
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user_when_database_enabled)],
) -> RunResponse:
    _ = current_user
    state: AppState = cast("AppState", request.app.state.app_state)
    final, trace = await run_pipeline(
        state.pipeline,
        document_id=req.document_id,
        raw_text=req.raw_text,
        trace_id=req.trace_id,
    )
    state.store.save_trace(trace)
    return RunResponse(trace=trace, final_summary=final.summary if final else None)


@router.get("/traces", tags=["traces"])
async def list_traces(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=50, ge=1, le=100),
    only_flagged: bool = False,
) -> list[dict[str, object]]:
    access = trace_access_service(request)
    store = trace_store(request)
    return access.list_trace_summaries_for_user(
        db,
        user=current_user,
        store=store,
        limit=limit,
        only_flagged=only_flagged,
    )


@router.get("/traces/{trace_id}", response_model=TraceDetailPublic, tags=["traces"])
async def get_trace(
    trace_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TraceDetailPublic:
    access = trace_access_service(request)
    store = trace_store(request)
    try:
        trace = access.get_trace_record(
            db, user=current_user, trace_id=trace_id, store=store
        )
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    except TraceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    return trace_detail_from_record(trace)


@router.post(
    "/traces/{trace_id}/analyze",
    response_model=RootCauseAnalysis,
    tags=["analysis"],
)
async def analyze(
    trace_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RootCauseAnalysis:
    state: AppState = cast("AppState", app_state(request))
    access = trace_access_service(request)
    store = trace_store(request)
    try:
        trace = access.get_trace_record(
            db, user=current_user, trace_id=trace_id, store=store
        )
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    except TraceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    settings = cast(Settings, request.app.state.settings)
    try:
        analysis = await analyze_trace(
            trace,
            client=state.pipeline.client,
            judge_model=state.judge_model,
            concurrency=settings.judge_concurrency,
        )
    except LLMError as exc:
        raise http_exception_from_llm_error(exc) from exc
    store.save_analysis(analysis)
    return analysis


@router.get(
    "/traces/{trace_id}/analysis",
    response_model=RootCauseAnalysis,
    tags=["analysis"],
)
async def get_existing_analysis(
    trace_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RootCauseAnalysis:
    access = trace_access_service(request)
    try:
        access.require_trace_access(db, user_id=current_user.id, trace_id=trace_id)
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    analysis = trace_store(request).get_analysis(trace_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="no analysis stored for that trace")
    return analysis


@router.post(
    "/traces/{trace_id}/feedback",
    response_model=AnalysisFeedbackPublic,
    tags=["feedback"],
)
def submit_analysis_feedback(
    trace_id: str,
    body: SubmitAnalysisFeedbackRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisFeedbackPublic:
    service = _analysis_feedback_service(request)
    store = trace_store(request)
    try:
        row = service.upsert(
            db,
            user=current_user,
            trace_id=trace_id,
            body=body,
            store=store,
        )
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    except AnalysisNotStoredError as exc:
        raise HTTPException(
            status_code=404,
            detail="no analysis stored for that trace",
        ) from exc
    return feedback_public(row)


@router.get(
    "/traces/{trace_id}/feedback",
    response_model=AnalysisFeedbackPublic,
    tags=["feedback"],
)
def get_analysis_feedback(
    trace_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisFeedbackPublic:
    service = _analysis_feedback_service(request)
    store = trace_store(request)
    try:
        row = service.get_for_user(
            db,
            user=current_user,
            trace_id=trace_id,
            store=store,
        )
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    except AnalysisNotStoredError as exc:
        raise HTTPException(
            status_code=404,
            detail="no analysis stored for that trace",
        ) from exc
    except AnalysisFeedbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Feedback not found") from exc
    return feedback_public(row)


@router.post("/traces/{trace_id}/flag", tags=["feedback"])
async def flag_trace(
    trace_id: str,
    flag: FailureFlag,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    state: AppState = cast("AppState", app_state(request))
    access = trace_access_service(request)
    try:
        access.require_trace_access(db, user_id=current_user.id, trace_id=trace_id)
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    if flag.trace_id != trace_id:
        raise HTTPException(
            status_code=400,
            detail=f"path trace_id={trace_id} disagrees with body trace_id={flag.trace_id}",
        )
    try:
        eval_case = state.store.flag_and_promote_to_eval(flag)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "flagged": True,
        "eval_case_created": eval_case is not None,
        "eval_case_id": eval_case.case_id if eval_case else None,
    }


@router.get("/eval/cases", response_model=list[EvalCase], tags=["feedback"])
async def list_legacy_eval_cases(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=100, ge=1, le=100),
) -> list[EvalCase]:
    """TraceStore eval cases from flagging; scoped to traces owned via pipeline_runs."""
    state: AppState = cast("AppState", request.app.state.app_state)
    access = trace_access_service(request)
    owned = access.owned_trace_ids(db, user_id=current_user.id)
    if not owned:
        return []
    cases = state.store.list_eval_cases(limit=500)
    filtered = [case for case in cases if case.source_trace_id in owned]
    return filtered[:limit]
