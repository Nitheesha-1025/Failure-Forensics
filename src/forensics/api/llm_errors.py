"""Map LLM client failures to safe HTTP responses (no secrets)."""

from __future__ import annotations

from fastapi import HTTPException

from ..llm_client import LLMError, LLMQuotaExhaustedError, _RetryableError
from ..secret_scrub import scrub_secrets_for_client


def http_exception_from_llm_error(exc: LLMError) -> HTTPException:
    if exc.status == 402:
        return HTTPException(
            status_code=402,
            detail=(
                "The LLM provider rejected this request due to billing or plan limits. "
                "Check your provider account; credentials are configured only on the server."
            ),
        )
    if exc.status in (401, 403):
        return HTTPException(
            status_code=401,
            detail=(
                "LLM provider authentication failed. Verify API credentials "
                "in the server environment (e.g. NVIDIA_API_KEY, OPENCODE_ZEN_API_KEY, "
                "or Cloudflare tokens)."
            ),
        )
    if isinstance(exc, LLMQuotaExhaustedError):
        return HTTPException(
            status_code=429,
            detail=(
                "Cloudflare Workers AI daily allowance is exhausted (Free plan: "
                "10,000 Neurons/day). Wait until the next UTC day or reduce usage."
            ),
        )
    if isinstance(exc, _RetryableError):
        return HTTPException(
            status_code=429,
            detail=(
                "The AI provider rate-limited this analysis request. "
                "Wait a moment and click Retry."
            ),
        )
    if exc.status == 429:
        return HTTPException(
            status_code=429,
            detail=(
                "The AI provider rate-limited this analysis request. "
                "Wait a moment and click Retry."
            ),
        )
    if exc.status in (502, 503, 504):
        return HTTPException(
            status_code=503,
            detail=(
                "The AI provider is temporarily unavailable. "
                "Try again in a few moments."
            ),
        )
    safe = scrub_secrets_for_client(str(exc)).strip()
    if len(safe) > 240:
        safe = safe[:240] + "…"
    if not safe:
        safe = "Analysis failed due to an AI provider error."
    return HTTPException(status_code=502, detail=safe)
