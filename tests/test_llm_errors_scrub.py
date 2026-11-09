"""Sanitized LLM error responses (no secrets in client-facing text)."""

from __future__ import annotations

from forensics.api.llm_errors import http_exception_from_llm_error
from forensics.llm_client import LLMError
from forensics.secret_scrub import scrub_secrets_for_client


def test_scrub_secrets_for_client_redacts_api_key_patterns() -> None:
    raw = "failed: api_key=sk-abcdefghijklmnopqrstuvwxyz1234567890"
    out = scrub_secrets_for_client(raw)
    assert "sk-" not in out
    assert "[redacted]" in out


def test_http_exception_from_llm_error_402_sanitized() -> None:
    exc = LLMError("http 402: payment required", retryable=False, status=402)
    http_exc = http_exception_from_llm_error(exc)
    assert http_exc.status_code == 402
    assert "billing" in str(http_exc.detail).lower()
    assert "sk-" not in str(http_exc.detail)
