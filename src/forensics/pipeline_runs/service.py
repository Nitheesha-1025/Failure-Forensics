"""Execute the existing pipeline for user-owned documents; record runs in PostgreSQL."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import PipelineRun, ProcessingStatus, RunStatus, User
from ..documents.errors import DocumentParseError
from ..documents.service import DocumentService
from ..models import StepStatus, TraceRecord
from ..pipeline import Pipeline, run_pipeline
from ..secret_scrub import scrub_secrets_for_client
from ..storage import TraceStore
from .errors import PipelineRunAlreadyInProgressError, PipelineRunNotFoundError


def paginate_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return max(1, math.ceil(total / page_size))


def _safe_pipeline_error(trace: TraceRecord) -> str:
    for span in reversed(trace.spans):
        if span.error:
            return scrub_secrets_for_client(str(span.error))[:500]
    return "Pipeline execution failed"


class PipelineRunService:
    def __init__(self, document_service: DocumentService):
        self._documents = document_service

    async def execute_for_document(
        self,
        db: Session,
        *,
        user: User,
        document_id: str,
        pipeline: Pipeline,
        store: TraceStore,
    ) -> PipelineRun:
        doc = self._documents.get_owned_for_update(db, user=user, document_id=document_id)

        active_run = db.scalar(
            select(PipelineRun.id).where(
                PipelineRun.document_id == doc.id,
                PipelineRun.user_id == user.id,
                PipelineRun.status == RunStatus.RUNNING.value,
            )
        )
        if active_run is not None:
            raise PipelineRunAlreadyInProgressError()

        started_at = datetime.now(UTC)
        run = PipelineRun(
            id=str(uuid.uuid4()),
            user_id=user.id,
            document_id=doc.id,
            status=RunStatus.RUNNING.value,
            started_at=started_at,
        )
        doc.processing_status = ProcessingStatus.PROCESSING.value
        db.add(run)
        db.commit()
        db.refresh(run)

        started = started_at
        trace_id: str | None = None
        error_message: str | None = None
        status = RunStatus.FAILED.value

        try:
            raw_text = self._documents.extract_document_text(
                db, user=user, document_id=doc.id
            )
        except DocumentParseError as exc:
            error_message = str(exc)[:500]
            doc.processing_status = ProcessingStatus.FAILED.value
        else:
            try:
                final, trace = await run_pipeline(
                    pipeline,
                    document_id=doc.id,
                    raw_text=raw_text,
                )
                store.save_trace(trace)
                trace_id = trace.trace_id
                if final is not None and trace.status == StepStatus.OK:
                    status = RunStatus.COMPLETED.value
                    doc.processing_status = ProcessingStatus.COMPLETED.value
                else:
                    status = RunStatus.FAILED.value
                    doc.processing_status = ProcessingStatus.FAILED.value
                    error_message = _safe_pipeline_error(trace)
            except Exception:
                status = RunStatus.FAILED.value
                doc.processing_status = ProcessingStatus.FAILED.value
                error_message = "Pipeline execution failed"

        completed = datetime.now(UTC)
        run.trace_id = trace_id
        run.status = status
        run.error_message = error_message
        run.completed_at = completed
        run.duration_ms = int((completed - started).total_seconds() * 1000)
        db.commit()
        db.refresh(run)
        return run

    def list_for_document(
        self,
        db: Session,
        *,
        user: User,
        document_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[PipelineRun], int]:
        self._documents.get_owned(db, user=user, document_id=document_id)
        total = db.scalar(
            select(func.count())
            .select_from(PipelineRun)
            .where(
                PipelineRun.document_id == document_id,
                PipelineRun.user_id == user.id,
            )
        )
        total_int = int(total or 0)
        offset = (page - 1) * page_size
        rows = db.scalars(
            select(PipelineRun)
            .where(
                PipelineRun.document_id == document_id,
                PipelineRun.user_id == user.id,
            )
            .order_by(PipelineRun.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        return list(rows), total_int

    def get_owned(self, db: Session, *, user: User, run_id: str) -> PipelineRun:
        run = db.scalar(
            select(PipelineRun).where(
                PipelineRun.id == run_id,
                PipelineRun.user_id == user.id,
            )
        )
        if run is None:
            raise PipelineRunNotFoundError()
        return run
