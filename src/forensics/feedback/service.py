"""Persist human review of stored root-cause analysis."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import User
from ..db.models.analysis_feedback import AnalysisFeedback, FeedbackDecision
from ..storage import TraceStore
from ..traces import TraceAccessService
from .schemas import AnalysisFeedbackPublic, SubmitAnalysisFeedbackRequest


class AnalysisFeedbackNotFoundError(Exception):
    pass


class AnalysisNotStoredError(Exception):
    pass


class AnalysisFeedbackService:
    def __init__(self, *, access: TraceAccessService) -> None:
        self._access = access

    def _require_trace_and_analysis(
        self,
        db: Session,
        *,
        user: User,
        trace_id: str,
        store: TraceStore,
    ) -> None:
        self._access.require_trace_access(db, user_id=user.id, trace_id=trace_id)
        if store.get_analysis(trace_id) is None:
            raise AnalysisNotStoredError()

    def get_for_user(
        self,
        db: Session,
        *,
        user: User,
        trace_id: str,
        store: TraceStore,
    ) -> AnalysisFeedback:
        self._require_trace_and_analysis(db, user=user, trace_id=trace_id, store=store)
        row = db.scalar(
            select(AnalysisFeedback).where(
                AnalysisFeedback.user_id == user.id,
                AnalysisFeedback.trace_id == trace_id,
            )
        )
        if row is None:
            raise AnalysisFeedbackNotFoundError()
        return row

    def upsert(
        self,
        db: Session,
        *,
        user: User,
        trace_id: str,
        body: SubmitAnalysisFeedbackRequest,
        store: TraceStore,
    ) -> AnalysisFeedback:
        self._require_trace_and_analysis(db, user=user, trace_id=trace_id, store=store)
        decision = FeedbackDecision(body.decision.value)
        comment = body.comment.strip() if body.comment and body.comment.strip() else None
        existing = db.scalar(
            select(AnalysisFeedback).where(
                AnalysisFeedback.user_id == user.id,
                AnalysisFeedback.trace_id == trace_id,
            )
        )
        now = datetime.now(UTC)
        if existing is not None:
            existing.decision = decision.value
            existing.comment = comment
            existing.updated_at = now
            db.commit()
            db.refresh(existing)
            return existing
        row = AnalysisFeedback(
            user_id=user.id,
            trace_id=trace_id,
            decision=decision.value,
            comment=comment,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def feedback_public(row: AnalysisFeedback) -> AnalysisFeedbackPublic:
    return AnalysisFeedbackPublic.model_validate(row)
