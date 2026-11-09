"""User-owned evaluation cases derived from human feedback (Phase 10)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UserEvalCase(Base):
    __tablename__ = "user_eval_cases"
    __table_args__ = (UniqueConstraint("user_id", "trace_id", name="uq_user_eval_cases_user_trace"),)

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feedback_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_feedback.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pipeline_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    human_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    human_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_root_cause_span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_root_cause_span_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
