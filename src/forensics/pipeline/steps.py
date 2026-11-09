"""Reference implementation of the 4-step pipeline.

The point of this module is *demonstrating* the contracts and the `@traced`
decorator. Real users would replace these step implementations with their own
domain logic; the trace layer doesn't care what the steps do as long as the
inputs and outputs are typed.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..llm_client import ChatMessage, LLMClient
from ..models import (
    ClassificationOutput,
    DocumentType,
    ExtractionOutput,
    IntakeOutput,
    SummarizationOutput,
)
from ..tracing import SpanContext, traced

_DOCTYPE_HINTS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.EMAIL: ("subject:", "from:", "to:", "dear "),
    DocumentType.INVOICE: ("invoice", "amount due", "total: $", "bill to"),
    DocumentType.REPORT: ("report", "summary", "introduction", "conclusion"),
    DocumentType.CONTRACT: ("agreement", "party", "shall", "whereas"),
}


@traced("intake")
def intake(document_id: str, raw_text: str) -> IntakeOutput:
    """Deterministic step: detect document type by simple heuristic."""
    lowered = raw_text.lower()
    doc_type = DocumentType.OTHER
    for candidate, hints in _DOCTYPE_HINTS.items():
        if any(h in lowered for h in hints):
            doc_type = candidate
            break
    return IntakeOutput(
        document_id=document_id,
        raw_text=raw_text,
        char_count=len(raw_text),
        detected_type=doc_type,
    )


@traced("extraction")
async def extract(
    intake_out: IntakeOutput,
    *,
    client: LLMClient,
    model: str,
    ctx: SpanContext | None = None,
) -> ExtractionOutput:
    """LLM-driven structured extraction. Returns whatever fields the LLM finds."""
    system = (
        "Extract the most useful structured fields from the document below. "
        "Return STRICT JSON: {\"fields\": {\"<key>\": \"<value>\"}, \"confidence\": <float 0-1>}. "
        "Use lowercase snake_case keys. Output ONLY JSON."
    )
    resp = await client.chat(
        model=model,
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=intake_out.raw_text),
        ],
        temperature=0.0,
        max_tokens=400,
        response_format={"type": "json_object"},
    )
    fields, confidence = _parse_extraction(resp.content)
    if ctx is not None:
        ctx.set_confidence(confidence)
        ctx.set_attribute("model", model)
    return ExtractionOutput(
        document_id=intake_out.document_id,
        fields=fields,
        confidence=confidence,
    )


@traced("classification")
async def classify(
    intake_out: IntakeOutput,
    extraction: ExtractionOutput,
    *,
    client: LLMClient,
    model: str,
    labels: list[str],
    ctx: SpanContext | None = None,
) -> ClassificationOutput:
    """Pick a label from `labels` given intake + extraction context."""
    system = (
        "You are a document classifier. Given the document text and extracted fields, "
        "choose EXACTLY ONE label from the candidates. "
        "Return JSON: {\"label\": \"<one of candidates>\", \"confidence\": <0-1>, \"rationale\": \"<one short sentence>\"}. "
        "Output ONLY JSON."
    )
    user = (
        f"Candidates: {', '.join(labels)}\n\n"
        f"Extracted fields: {json.dumps(extraction.fields)}\n\n"
        f"Document:\n{intake_out.raw_text}"
    )
    resp = await client.chat(
        model=model,
        messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
        temperature=0.0,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    label, confidence, rationale = _parse_classification(resp.content, labels)
    if ctx is not None:
        ctx.set_confidence(confidence)
        ctx.set_attribute("candidate_labels", labels)
    return ClassificationOutput(
        document_id=intake_out.document_id,
        label=label,
        confidence=confidence,
        rationale=rationale,
    )


@traced("summarization")
async def summarize(
    intake_out: IntakeOutput,
    extraction: ExtractionOutput,
    classification: ClassificationOutput,
    *,
    client: LLMClient,
    model: str,
    ctx: SpanContext | None = None,
) -> SummarizationOutput:
    system = (
        "Write a concise 1-2 sentence summary of the document. "
        "Reflect the document's class and any key extracted fields. Plain prose, no bullets."
    )
    user = (
        f"Class: {classification.label}\n"
        f"Fields: {json.dumps(extraction.fields)}\n\n"
        f"Document:\n{intake_out.raw_text}"
    )
    resp = await client.chat(
        model=model,
        messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
        temperature=0.2,
        max_tokens=200,
    )
    confidence = max(0.0, min(1.0, (extraction.confidence + classification.confidence) / 2))
    if ctx is not None:
        ctx.set_confidence(confidence)
    return SummarizationOutput(
        document_id=intake_out.document_id,
        summary=resp.content.strip(),
        confidence=confidence,
    )


_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def _parse_extraction(raw: str) -> tuple[dict[str, str], float]:
    obj = _safe_json(raw)
    fields_raw = obj.get("fields", {})
    if not isinstance(fields_raw, dict):
        fields_raw = {}
    fields: dict[str, str] = {str(k): str(v) for k, v in fields_raw.items()}
    confidence = _to_float(obj.get("confidence"))
    return fields, confidence


def _parse_classification(raw: str, labels: list[str]) -> tuple[str, float, str]:
    obj = _safe_json(raw)
    label = str(obj.get("label", "")).strip()
    if label not in labels:
        # Soft-clamp: pick the closest candidate by lowercase prefix match.
        norm = label.lower()
        match = next(
            (cand for cand in labels if cand.lower().startswith(norm) and norm),
            None,
        )
        label = match or labels[-1]
    confidence = _to_float(obj.get("confidence"))
    rationale = str(obj.get("rationale", "")).strip()
    return label, confidence, rationale


def _safe_json(raw: str) -> dict[str, Any]:
    match = _JSON_OBJ.search(raw or "")
    if match is None:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _to_float(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, f))
