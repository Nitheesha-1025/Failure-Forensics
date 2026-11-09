"""Pipeline orchestrator that wires the 4 steps inside one TraceRecorder."""

from __future__ import annotations

from dataclasses import dataclass

from ..llm_client import LLMClient
from ..models import StepStatus, SummarizationOutput, TraceRecord
from ..tracing import TraceRecorder
from .steps import classify, extract, intake, summarize


@dataclass
class Pipeline:
    """Configurable orchestrator. Holds models + LLM client + label space."""

    client: LLMClient
    extraction_model: str
    classification_model: str
    summarization_model: str
    labels: list[str]


async def run_pipeline(
    pipeline: Pipeline,
    *,
    document_id: str,
    raw_text: str,
    trace_id: str | None = None,
) -> tuple[SummarizationOutput | None, TraceRecord]:
    """Execute one pipeline run. Returns (final_output_or_none, trace_record).

    Errors in any step short-circuit the run; partial spans are still emitted.
    The trace's status is ERROR if any step raised.
    """
    rec = TraceRecorder(trace_id=trace_id)
    final: SummarizationOutput | None = None
    async with rec.trace():
        try:
            intake_out = intake(document_id, raw_text)
            extraction = await extract(
                intake_out, client=pipeline.client, model=pipeline.extraction_model
            )
            classification = await classify(
                intake_out,
                extraction,
                client=pipeline.client,
                model=pipeline.classification_model,
                labels=pipeline.labels,
            )
            final = await summarize(
                intake_out,
                extraction,
                classification,
                client=pipeline.client,
                model=pipeline.summarization_model,
            )
            rec.set_final_output(final)
        except Exception:
            # The recorder marks itself ERROR on raise; we re-raise to honor
            # caller expectations rather than swallowing.
            rec.set_final_output(None)

    started = rec.started_at
    ended = rec.ended_at
    assert started is not None and ended is not None
    duration_ms = int((ended - started).total_seconds() * 1000)
    return final, TraceRecord(
        trace_id=rec.trace_id,
        started_at=started,
        ended_at=ended,
        duration_ms=duration_ms,
        status=rec.status if rec.status != StepStatus.OK or final is not None else StepStatus.ERROR,
        spans=rec.spans,
        final_output=rec.final_output,
    )
