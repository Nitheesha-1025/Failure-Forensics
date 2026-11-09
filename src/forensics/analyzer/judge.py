"""LLM-as-judge over a single span: did the input→output transformation succeed?"""

from __future__ import annotations

import json
import re
from typing import Final

from ..llm_client import ChatMessage, LLMClient
from ..models import SpanCritique, SpanRecord

_JSON_OBJ: Final[re.Pattern[str]] = re.compile(r"\{.*\}", re.DOTALL)

_JUDGE_SYSTEM = (
    "You are a strict senior engineer auditing a single step in an AI pipeline. "
    "Given a STEP NAME, INPUT, and OUTPUT, decide whether this step did its job: "
    "did the output faithfully and usefully follow from the input? "
    "Return JSON: {\"quality\": <float 0-1>, \"reason\": \"<short>\", "
    "\"is_root_cause_candidate\": <bool — true iff the step itself is clearly broken>}. "
    "Do NOT speculate about upstream steps you cannot see. Output ONLY JSON."
)

_JUDGE_USER = (
    "STEP NAME: {name}\n\n"
    "INPUT:\n{input}\n\n"
    "OUTPUT:\n{output}\n\n"
    "Return JSON now."
)


async def critique_span_async(
    *,
    client: LLMClient,
    judge_model: str,
    span: SpanRecord,
) -> SpanCritique:
    """Run the judge on one span. Falls back to a deterministic verdict on parse failure."""
    if span.status.value == "error":
        return SpanCritique(
            span_id=span.span_id,
            name=span.name,
            quality=0.0,
            reason=f"step raised: {span.error or 'unknown error'}",
            is_root_cause_candidate=True,
        )

    response = await client.chat(
        model=judge_model,
        messages=[
            ChatMessage(role="system", content=_JUDGE_SYSTEM),
            ChatMessage(
                role="user",
                content=_JUDGE_USER.format(
                    name=span.name,
                    input=json.dumps(span.input, ensure_ascii=False)[:4000],
                    output=json.dumps(span.output, ensure_ascii=False)[:4000],
                ),
            ),
        ],
        temperature=0.0,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    return _parse(response.content, span)


def _parse(raw: str, span: SpanRecord) -> SpanCritique:
    match = _JSON_OBJ.search(raw)
    if match is None:
        return SpanCritique(
            span_id=span.span_id,
            name=span.name,
            quality=0.5,
            reason=f"judge: parse error: {raw[:120]}",
            is_root_cause_candidate=False,
        )
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return SpanCritique(
            span_id=span.span_id,
            name=span.name,
            quality=0.5,
            reason=f"judge: parse error: {exc}",
            is_root_cause_candidate=False,
        )

    try:
        quality = float(data.get("quality", 0.5))
    except (TypeError, ValueError):
        quality = 0.5
    quality = max(0.0, min(1.0, quality))
    reason = str(data.get("reason", "")).strip() or "no reason given"
    candidate = bool(data.get("is_root_cause_candidate", False))
    return SpanCritique(
        span_id=span.span_id,
        name=span.name,
        quality=quality,
        reason=reason,
        is_root_cause_candidate=candidate,
    )
