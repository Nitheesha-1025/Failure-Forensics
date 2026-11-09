from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateEvalCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(min_length=1, max_length=64)


class UserEvalCasePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: str
    feedback_id: str
    document_id: str | None
    pipeline_run_id: str | None
    raw_text: str
    human_decision: str
    human_comment: str | None
    expected_root_cause_span_id: str | None
    expected_root_cause_span_name: str | None
    created_at: datetime
    updated_at: datetime


class UserEvalCaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UserEvalCasePublic]
    total: int


class RegressionRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eval_case_id: str
    passed: bool | None
    human_decision: str
    expected_root_cause_span_id: str | None
    expected_root_cause_span_name: str | None
    actual_root_cause_span_id: str | None
    actual_root_cause_span_name: str | None
    message: str
