"""User-owned evaluation cases (Phase 10)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user, get_db
from ..db.models import User
from ..evaluations.schemas import (
    CreateEvalCaseRequest,
    RegressionRunResponse,
    UserEvalCaseListResponse,
    UserEvalCasePublic,
)
from ..evaluations.service import (
    EvalCaseAlreadyExistsError,
    EvalCaseNotFoundError,
    EvalInputUnavailableError,
    FeedbackRequiredError,
    UserEvalCaseService,
    eval_case_public,
)
from ..traces import TraceAccessDeniedError
from .trace_deps import app_state, trace_access_service, trace_store

if TYPE_CHECKING:
    from ..config import Settings
    from .app import AppState

router = APIRouter(prefix="/v1/evaluations", tags=["evaluations"])


def _eval_service(request: Request) -> UserEvalCaseService:
    return UserEvalCaseService(access=trace_access_service(request))


@router.post("", response_model=UserEvalCasePublic, status_code=status.HTTP_201_CREATED)
def create_eval_case(
    body: CreateEvalCaseRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserEvalCasePublic:
    service = _eval_service(request)
    store = trace_store(request)
    try:
        row = service.create_from_trace(
            db, user=current_user, trace_id=body.trace_id, store=store
        )
    except TraceAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    except FeedbackRequiredError as exc:
        raise HTTPException(
            status_code=400,
            detail="Submit human feedback on this trace before creating an evaluation case",
        ) from exc
    except EvalCaseAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="Evaluation case already exists") from exc
    except EvalInputUnavailableError as exc:
        raise HTTPException(
            status_code=422,
            detail="Trace intake input is not available for evaluation",
        ) from exc
    except EvalCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    return eval_case_public(row)


@router.get("", response_model=UserEvalCaseListResponse)
def list_eval_cases(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserEvalCaseListResponse:
    service = _eval_service(request)
    items, total = service.list_for_user(db, user=current_user)
    return UserEvalCaseListResponse(
        items=[eval_case_public(r) for r in items],
        total=total,
    )


@router.get("/{case_id}", response_model=UserEvalCasePublic)
def get_eval_case(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserEvalCasePublic:
    service = _eval_service(request)
    try:
        row = service.get_owned(db, user=current_user, case_id=case_id)
    except EvalCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation case not found") from exc
    return eval_case_public(row)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_eval_case(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    service = _eval_service(request)
    try:
        service.delete(db, user=current_user, case_id=case_id)
    except EvalCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation case not found") from exc


@router.post("/{case_id}/run", response_model=RegressionRunResponse)
async def run_eval_regression(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RegressionRunResponse:
    service = _eval_service(request)
    state = cast("AppState", app_state(request))
    settings = cast("Settings", request.app.state.settings)
    store = trace_store(request)
    try:
        return await service.run_regression(
            db,
            user=current_user,
            case_id=case_id,
            pipeline=state.pipeline,
            store=store,
            judge_model=state.judge_model,
            judge_concurrency=settings.judge_concurrency,
        )
    except EvalCaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation case not found") from exc
