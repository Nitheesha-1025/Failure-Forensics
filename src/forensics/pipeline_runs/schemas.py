from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    trace_id: str | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
    created_at: datetime


class PipelineRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PipelineRunPublic]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
