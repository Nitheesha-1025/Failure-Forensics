from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Document, PipelineRun, User
from ..db.models.analysis_feedback import AnalysisFeedback, FeedbackDecision
from ..db.models.pipeline_run import RunStatus
from ..db.models.user_eval_case import UserEvalCase
from ..storage import TraceStore
from .schemas import AnalyticsSummary, RootCauseCount


class AnalyticsService:
    def summary_for_user(
        self,
        db: Session,
        *,
        user: User,
        store: TraceStore,
    ) -> AnalyticsSummary:
        total_documents = int(
            db.scalar(
                select(func.count()).select_from(Document).where(Document.user_id == user.id)
            )
            or 0
        )
        runs = db.scalars(
            select(PipelineRun).where(PipelineRun.user_id == user.id)
        ).all()
        total_runs = len(runs)
        completed_runs = sum(1 for r in runs if r.status == RunStatus.COMPLETED.value)
        failed_runs = sum(1 for r in runs if r.status == RunStatus.FAILED.value)
        trace_ids = [r.trace_id for r in runs if r.trace_id]
        analyzed_traces = sum(1 for tid in trace_ids if store.get_analysis(tid) is not None)
        feedback_confirmed = int(
            db.scalar(
                select(func.count())
                .select_from(AnalysisFeedback)
                .where(
                    AnalysisFeedback.user_id == user.id,
                    AnalysisFeedback.decision == FeedbackDecision.CONFIRMED.value,
                )
            )
            or 0
        )
        feedback_overridden = int(
            db.scalar(
                select(func.count())
                .select_from(AnalysisFeedback)
                .where(
                    AnalysisFeedback.user_id == user.id,
                    AnalysisFeedback.decision == FeedbackDecision.OVERRIDDEN.value,
                )
            )
            or 0
        )
        evaluation_cases = int(
            db.scalar(
                select(func.count())
                .select_from(UserEvalCase)
                .where(UserEvalCase.user_id == user.id)
            )
            or 0
        )
        names = db.scalars(
            select(UserEvalCase.expected_root_cause_span_name).where(
                UserEvalCase.user_id == user.id,
                UserEvalCase.expected_root_cause_span_name.is_not(None),
            )
        ).all()
        counter = Counter(n for n in names if n)
        top_root_causes = [
            RootCauseCount(span_name=name, count=count)
            for name, count in counter.most_common(5)
        ]
        return AnalyticsSummary(
            total_documents=total_documents,
            total_runs=total_runs,
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            analyzed_traces=analyzed_traces,
            feedback_confirmed=feedback_confirmed,
            feedback_overridden=feedback_overridden,
            evaluation_cases=evaluation_cases,
            top_root_causes=top_root_causes,
        )
