from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RootCauseCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_name: str
    count: int = Field(ge=0)


class AnalyticsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_documents: int = Field(ge=0)
    total_runs: int = Field(ge=0)
    completed_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    analyzed_traces: int = Field(ge=0)
    feedback_confirmed: int = Field(ge=0)
    feedback_overridden: int = Field(ge=0)
    evaluation_cases: int = Field(ge=0)
    top_root_causes: list[RootCauseCount]
