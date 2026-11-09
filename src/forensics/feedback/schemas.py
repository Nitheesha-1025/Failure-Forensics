"""API schemas for analysis human review."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FeedbackDecisionPublic(StrEnum):
    confirmed = "confirmed"
    overridden = "overridden"


class SubmitAnalysisFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: FeedbackDecisionPublic
    comment: str | None = Field(default=None, max_length=2000)


class AnalysisFeedbackPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: str
    decision: str
    comment: str | None
    created_at: datetime
    updated_at: datetime
