"""Pydantic v2 contracts for the entire system.

Three concentric layers:

1. **Pipeline-step contracts** (`IntakeOutput`, `ExtractionOutput`,
   `ClassificationOutput`, `SummarizationOutput`). Strictly typed to forbid
   "untyped dicts between steps" — that's the design principle that makes the
   forensics layer possible at all.
2. **Trace contracts** (`SpanRecord`, `TraceRecord`). Versioned schema; the
   `schema_version` field is what lets old traces stay readable as the model
   evolves.
3. **Analysis contracts** (`SpanCritique`, `RootCauseAnalysis`,
   `FailureFlag`, `EvalCase`). The judge produces these; the feedback loop
   converts them into eval cases atomically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Pipeline-step contracts
# ---------------------------------------------------------------------------


class DocumentType(StrEnum):
    EMAIL = "email"
    INVOICE = "invoice"
    REPORT = "report"
    CONTRACT = "contract"
    OTHER = "other"


class IntakeOutput(BaseModel):
    """Raw text + minimal metadata. The intake step is deterministic."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    raw_text: str
    char_count: int = Field(ge=0)
    detected_type: DocumentType = DocumentType.OTHER


class ExtractionOutput(BaseModel):
    """Structured fields lifted out of the raw text by an LLM call."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    fields: dict[str, str]
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ClassificationOutput(BaseModel):
    """Top-level classification + confidence."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class SummarizationOutput(BaseModel):
    """Final user-facing summary plus the upstream artifacts it depends on."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


# ---------------------------------------------------------------------------
# Trace contracts
# ---------------------------------------------------------------------------


class StepStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class SpanRecord(BaseModel):
    """One step in a pipeline run. Designed to be JSON-serializable end-to-end."""

    model_config = ConfigDict(extra="forbid")

    span_id: str
    trace_id: str
    name: str
    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)
    status: StepStatus = StepStatus.OK
    error: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    input: dict[str, Any] = Field(default_factory=dict)
    # `output` is `Any` rather than `dict` because pipeline steps legitimately
    # return scalars / lists / Pydantic models. We serialize whatever the user
    # returns; the JSON file remains uniformly typed because Pydantic dumps it.
    output: Any = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceRecord(BaseModel):
    """A pipeline run, rooted at the intake step."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    trace_id: str
    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)
    status: StepStatus = StepStatus.OK
    spans: list[SpanRecord] = Field(default_factory=list)
    final_output: dict[str, Any] | None = None
    flagged: bool = False
    flag_reason: str | None = None

    @model_validator(mode="after")
    def _spans_belong_to_this_trace(self) -> Self:
        for span in self.spans:
            if span.trace_id != self.trace_id:
                raise ValueError(
                    f"span {span.span_id} has trace_id {span.trace_id}, "
                    f"expected {self.trace_id}"
                )
        return self


# ---------------------------------------------------------------------------
# Analysis contracts
# ---------------------------------------------------------------------------


class SpanCritique(BaseModel):
    """Per-span verdict from the judge: did this step do its job?"""

    model_config = ConfigDict(extra="forbid")

    span_id: str
    name: str
    quality: float = Field(ge=0.0, le=1.0)
    reason: str
    is_root_cause_candidate: bool = False


class RootCauseAnalysis(BaseModel):
    """Full backward-trace verdict for one trace."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    judge_model: str
    critiques: list[SpanCritique]
    root_cause_span_id: str | None = None
    root_cause_explanation: str = ""


class FailureFlag(BaseModel):
    """Human-supplied flag attached to a trace's final output."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    flagged_by: str | None = None
    reason: str
    expected_output: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvalCase(BaseModel):
    """A self-grown eval case: input → expected output, derived from a flagged trace."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    source_trace_id: str
    raw_text: str
    expected_label: str | None = None
    expected_summary: str | None = None
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
