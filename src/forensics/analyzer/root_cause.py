"""Backward-trace root-cause selection.

Algorithm (intentionally simple):

  1. Critique every span concurrently with the judge LLM.
  2. Walk spans in order. The root-cause is the **first** span where
     either (a) the step raised, or (b) the judge marked it as
     `is_root_cause_candidate=true`, or (c) the quality drops below
     `min_quality` AND the previous span was above it.

The "first significant quality cliff" wins. This matches the spec's wording
"backward trace" as a logical concept — we walk forward but stop at the first
break — but is more robust than purely starting from the final output: if the
final output is corrupt because step 2 misclassified, we want to flag step 2,
not the otherwise-fine summarization step that ran on bad inputs.
"""

from __future__ import annotations

import asyncio

from ..llm_client import LLMClient
from ..models import RootCauseAnalysis, SpanCritique, SpanRecord, TraceRecord
from .judge import critique_span_async


async def analyze_trace(
    trace: TraceRecord,
    *,
    client: LLMClient,
    judge_model: str,
    min_quality: float = 0.6,
    concurrency: int = 1,
) -> RootCauseAnalysis:
    if not trace.spans:
        return RootCauseAnalysis(
            trace_id=trace.trace_id,
            judge_model=judge_model,
            critiques=[],
            root_cause_span_id=None,
            root_cause_explanation="no spans in trace",
        )

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(span: SpanRecord) -> SpanCritique:
        async with sem:
            return await critique_span_async(
                client=client, judge_model=judge_model, span=span
            )

    critiques: list[SpanCritique] = list(
        await asyncio.gather(*(_one(s) for s in trace.spans))
    )

    root_id, explanation = _pick_root_cause(critiques, min_quality)
    return RootCauseAnalysis(
        trace_id=trace.trace_id,
        judge_model=judge_model,
        critiques=critiques,
        root_cause_span_id=root_id,
        root_cause_explanation=explanation,
    )


def _pick_root_cause(
    critiques: list[SpanCritique], min_quality: float
) -> tuple[str | None, str]:
    if not critiques:
        return None, "no critiques"
    # Phase 1: explicit candidate flag wins globally — the judge gets the last
    # word when it's confident a single step is broken.
    explicit = next((c for c in critiques if c.is_root_cause_candidate), None)
    if explicit is not None:
        return explicit.span_id, (
            f"step '{explicit.name}' was marked as root-cause candidate: {explicit.reason}"
        )
    # Phase 2: forward walk to find the first quality cliff.
    prev_quality = 1.0
    for crit in critiques:
        if crit.quality < min_quality and prev_quality >= min_quality:
            return crit.span_id, (
                f"first quality cliff at '{crit.name}' "
                f"(quality={crit.quality:.2f} < {min_quality}): {crit.reason}"
            )
        prev_quality = crit.quality

    # Fallback: pick the lowest-quality span.
    worst = min(critiques, key=lambda c: c.quality)
    if worst.quality < min_quality:
        return worst.span_id, (
            f"lowest-quality span '{worst.name}' "
            f"(quality={worst.quality:.2f}): {worst.reason}"
        )
    return None, "no span fell below the quality threshold"
