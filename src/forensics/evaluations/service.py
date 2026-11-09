from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analyzer import analyze_trace
from ..db.models import PipelineRun, User
from ..db.models.analysis_feedback import AnalysisFeedback
from ..db.models.user_eval_case import UserEvalCase
from ..models import TraceRecord
from ..pipeline import Pipeline, run_pipeline
from ..storage import TraceStore
from ..traces import TraceAccessService
from .schemas import RegressionRunResponse, UserEvalCasePublic


class EvalCaseNotFoundError(Exception):
    pass


class EvalCaseAlreadyExistsError(Exception):
    pass


class FeedbackRequiredError(Exception):
    pass


class EvalInputUnavailableError(Exception):
    pass


def _raw_text_from_trace(trace: TraceRecord) -> str:
    intake = next((s for s in trace.spans if s.name == "intake"), None)
    if intake is None:
        raise EvalInputUnavailableError()
    raw = intake.input.get("raw_text") or intake.output.get("raw_text")
    if not isinstance(raw, str) or not raw.strip():
        raise EvalInputUnavailableError()
    return raw


def _span_name(trace: TraceRecord, span_id: str | None) -> str | None:
    if not span_id:
        return None
    span = next((s for s in trace.spans if s.span_id == span_id), None)
    return span.name if span else None


class UserEvalCaseService:
    def __init__(self, *, access: TraceAccessService) -> None:
        self._access = access

    def create_from_trace(
        self,
        db: Session,
        *,
        user: User,
        trace_id: str,
        store: TraceStore,
    ) -> UserEvalCase:
        self._access.require_trace_access(db, user_id=user.id, trace_id=trace_id)
        feedback = db.scalar(
            select(AnalysisFeedback).where(
                AnalysisFeedback.user_id == user.id,
                AnalysisFeedback.trace_id == trace_id,
            )
        )
        if feedback is None:
            raise FeedbackRequiredError()
        existing = db.scalar(
            select(UserEvalCase).where(
                UserEvalCase.user_id == user.id,
                UserEvalCase.trace_id == trace_id,
            )
        )
        if existing is not None:
            raise EvalCaseAlreadyExistsError()
        trace = store.get_trace(trace_id)
        if trace is None:
            raise EvalCaseNotFoundError()
        analysis = store.get_analysis(trace_id)
        if analysis is None:
            raise EvalCaseNotFoundError()
        raw_text = _raw_text_from_trace(trace)
        run = db.scalar(
            select(PipelineRun)
            .where(
                PipelineRun.user_id == user.id,
                PipelineRun.trace_id == trace_id,
            )
            .limit(1)
        )
        now = datetime.now(UTC)
        row = UserEvalCase(
            user_id=user.id,
            trace_id=trace_id,
            feedback_id=feedback.id,
            document_id=run.document_id if run else None,
            pipeline_run_id=run.id if run else None,
            raw_text=raw_text,
            human_decision=feedback.decision,
            human_comment=feedback.comment,
            expected_root_cause_span_id=analysis.root_cause_span_id,
            expected_root_cause_span_name=_span_name(trace, analysis.root_cause_span_id),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def list_for_user(self, db: Session, *, user: User) -> tuple[list[UserEvalCase], int]:
        total = db.scalar(
            select(func.count()).select_from(UserEvalCase).where(UserEvalCase.user_id == user.id)
        )
        rows = db.scalars(
            select(UserEvalCase)
            .where(UserEvalCase.user_id == user.id)
            .order_by(UserEvalCase.created_at.desc())
        ).all()
        return list(rows), int(total or 0)

    def get_owned(self, db: Session, *, user: User, case_id: str) -> UserEvalCase:
        row = db.scalar(
            select(UserEvalCase).where(
                UserEvalCase.id == case_id,
                UserEvalCase.user_id == user.id,
            )
        )
        if row is None:
            raise EvalCaseNotFoundError()
        return row

    def delete(self, db: Session, *, user: User, case_id: str) -> None:
        row = self.get_owned(db, user=user, case_id=case_id)
        db.delete(row)
        db.commit()

    async def run_regression(
        self,
        db: Session,
        *,
        user: User,
        case_id: str,
        pipeline: Pipeline,
        store: TraceStore,
        judge_model: str,
        judge_concurrency: int = 1,
    ) -> RegressionRunResponse:
        case = self.get_owned(db, user=user, case_id=case_id)
        doc_id = case.document_id or case.trace_id
        _final, trace = await run_pipeline(
            pipeline,
            document_id=doc_id,
            raw_text=case.raw_text,
        )
        analysis = await analyze_trace(
            trace,
            client=pipeline.client,
            judge_model=judge_model,
            concurrency=judge_concurrency,
        )
        actual_id = analysis.root_cause_span_id
        actual_name = _span_name(trace, actual_id)
        passed: bool | None
        message: str
        if case.human_decision == "confirmed":
            passed = actual_id == case.expected_root_cause_span_id
            message = (
                "Regression matched the stored root-cause span."
                if passed
                else "Regression root-cause span differs from the stored expectation."
            )
        else:
            passed = None
            message = (
                "Human overrode the original diagnosis; comparison is informational only."
            )
        return RegressionRunResponse(
            eval_case_id=case.id,
            passed=passed,
            human_decision=case.human_decision,
            expected_root_cause_span_id=case.expected_root_cause_span_id,
            expected_root_cause_span_name=case.expected_root_cause_span_name,
            actual_root_cause_span_id=actual_id,
            actual_root_cause_span_name=actual_name,
            message=message,
        )


def eval_case_public(row: UserEvalCase) -> UserEvalCasePublic:
    return UserEvalCasePublic.model_validate(row)
