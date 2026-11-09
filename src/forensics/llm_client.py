"""Async LLM client: OpenAI, Cloudflare Workers AI, and OpenCode Zen (Anthropic SDK)."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx
from anthropic import APIStatusError, APITimeoutError, AsyncAnthropic
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
)

ApiKind = Literal["openai", "cloudflare", "zen", "nvidia"]

_ZEN_JSON_SYSTEM_SUFFIX = "Respond with valid JSON only. Do not wrap the JSON in markdown."

# Anthropic SDK posts to relative path /v1/messages; base must not end with /v1.
_OPENCODE_ZEN_MESSAGES_PATH = "/messages"


def opencode_zen_messages_url(configured_base_url: str) -> str:
    """Full HTTP URL for OpenCode Zen Messages API (…/zen/v1/messages)."""
    return configured_base_url.rstrip("/") + _OPENCODE_ZEN_MESSAGES_PATH


def _opencode_zen_anthropic_sdk_base_url(configured_base_url: str) -> str:
    """Map configured …/zen/v1 base to SDK base …/zen (avoids …/v1/v1/messages)."""
    base = configured_base_url.rstrip("/")
    if base.endswith("/v1"):
        return base.removesuffix("/v1")
    return base


_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})
_NON_RETRYABLE_HTTP = frozenset({401, 402, 403})


@dataclass(slots=True, frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(slots=True, frozen=True)
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class LLMError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status: int | None = None,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.status = status
        self.retry_after_seconds = retry_after_seconds


class LLMQuotaExhaustedError(LLMError):
    """Non-retryable provider quota / daily allowance exhaustion (typically HTTP 429)."""

    def __init__(self, message: str, *, status: int | None = 429) -> None:
        super().__init__(message, retryable=False, status=status)


class _RetryableError(LLMError):
    pass


def _parse_retry_after(headers: httpx.Headers) -> float | None:
    raw = headers.get("Retry-After")
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return float(raw)
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delay = (dt - datetime.now(UTC)).total_seconds()
        return max(0.0, delay)
    except (TypeError, ValueError, OverflowError):
        return None


def _is_quota_exhausted(status: int, body_text: str) -> bool:
    if status != 429:
        return False
    lower = body_text.lower()
    if "resource_exhausted" in lower:
        return True
    if "quota" in lower and ("exceed" in lower or "exhaust" in lower):
        return True
    if "neuron" in lower and ("limit" in lower or "exhaust" in lower):
        return True
    if "daily" in lower and "limit" in lower:
        return True
    try:
        data = json.loads(body_text)
    except json.JSONDecodeError:
        return False
    errors = data.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if not isinstance(item, dict):
                continue
            msg = str(item.get("message", "")).lower()
            if "neuron" in msg or ("daily" in msg and "limit" in msg):
                return True
    err = data.get("error")
    if not isinstance(err, dict):
        return False
    if str(err.get("status", "")).upper() == "RESOURCE_EXHAUSTED":
        return True
    msg = str(err.get("message", "")).lower()
    return "quota" in msg and ("exceed" in msg or "exhaust" in msg)


def _http_error_snippet(status: int, body_text: str, *, limit: int = 200) -> str:
    snippet = body_text.strip().replace("\n", " ")[:limit]
    return f"http {status}: {snippet}" if snippet else f"http {status}"


def _raise_for_http_response(resp: httpx.Response) -> None:
    status = resp.status_code
    body = resp.text
    if status < 400:
        return
    retry_after = _parse_retry_after(resp.headers)
    snippet = _http_error_snippet(status, body)

    if status in _NON_RETRYABLE_HTTP:
        raise LLMError(snippet, retryable=False, status=status)

    if status == 429 and _is_quota_exhausted(status, body):
        raise LLMQuotaExhaustedError(snippet, status=status)

    if status in _RETRYABLE_HTTP:
        raise _RetryableError(
            snippet,
            status=status,
            retry_after_seconds=retry_after,
        )

    raise LLMError(snippet, retryable=False, status=status)


def _retry_wait_seconds(retry_state: object) -> float:
    """Bounded exponential backoff with jitter; honors Retry-After when set."""
    from tenacity import RetryCallState

    state: RetryCallState = retry_state  # type: ignore[assignment]
    exc = state.outcome.exception() if state.outcome is not None else None
    if isinstance(exc, _RetryableError) and exc.retry_after_seconds is not None:
        base = min(60.0, max(0.0, exc.retry_after_seconds))
    else:
        attempt = state.attempt_number
        base = min(8.0, 0.5 * (2 ** max(0, attempt - 1)))
    jitter = random.uniform(0.0, min(1.0, base * 0.1))
    return base + jitter


def _normalize_cloudflare_model(model: str) -> str:
    """Workers AI model IDs use literal @cf/... path segments (not percent-encoded)."""
    cleaned = model.strip()
    if cleaned.startswith("/"):
        cleaned = cleaned.lstrip("/")
    if not cleaned.startswith("@cf/"):
        msg = f"invalid Cloudflare model id {cleaned!r} (expected @cf/... prefix)"
        raise LLMError(msg, retryable=False, status=None)
    return cleaned


def _cloudflare_chat_completions_url(base_url: str, account_id: str) -> str:
    """OpenAI-compatible Workers AI: .../accounts/{id}/ai/v1/chat/completions."""
    base = base_url.rstrip("/")
    acct = account_id.strip()
    if not acct:
        raise LLMError("cloudflare account_id is empty", retryable=False, status=None)
    return f"{base}/accounts/{acct}/ai/v1/chat/completions"


class LLMClient:
    """OpenAI, Cloudflare, NVIDIA NIM, or OpenCode Zen chat APIs."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 60.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
        *,
        api_kind: ApiKind = "openai",
        supports_json_response_format: bool = True,
        account_id: str | None = None,
        anthropic_client: AsyncAnthropic | None = None,
        nvidia_temperature: float = 1.0,
        nvidia_top_p: float = 0.95,
        nvidia_output_token_floor: int = 1024,
        nvidia_output_token_ceiling: int = 8192,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._account_id = account_id
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self.api_kind = api_kind
        self.supports_json_response_format = supports_json_response_format
        self._nvidia_temperature = nvidia_temperature
        self._nvidia_top_p = nvidia_top_p
        self._nvidia_output_token_floor = nvidia_output_token_floor
        self._nvidia_output_token_ceiling = nvidia_output_token_ceiling
        self._anthropic = anthropic_client
        self._owns_anthropic = anthropic_client is None and api_kind == "zen"

        if api_kind == "zen":
            # Anthropic SDK manages its own HTTP client (httpx2); inject AsyncAnthropic in tests.
            self._client = client
            self._owns_client = client is not None
            if self._anthropic is None:
                self._anthropic = AsyncAnthropic(
                    api_key=api_key,
                    base_url=_opencode_zen_anthropic_sdk_base_url(self._base_url),
                    timeout=timeout_s,
                    max_retries=0,
                )
        else:
            self._client = client or httpx.AsyncClient(timeout=timeout_s)
            self._owns_client = client is None

    async def aclose(self) -> None:
        if self._anthropic is not None and self._owns_anthropic:
            await self._anthropic.close()
        if self._client is not None and self._owns_client:
            await self._client.aclose()

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        want_json = response_format is not None and self.supports_json_response_format

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries + 1),
            wait=_retry_wait_seconds,
            retry=retry_if_exception_type(_RetryableError),
            reraise=True,
        ):
            with attempt:
                if self.api_kind == "cloudflare":
                    return await self._do_cloudflare(
                        model,
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        want_json=want_json,
                    )
                if self.api_kind == "zen":
                    return await self._do_zen(
                        model,
                        messages,
                        max_tokens=max_tokens,
                        want_json=want_json,
                    )
                if self.api_kind == "nvidia":
                    return await self._do_nvidia(
                        model,
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                    )
                return await self._do_openai(
                    model,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
        raise RuntimeError("unreachable")  # pragma: no cover

    async def _do_openai(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, str] | None,
    ) -> LLMResponse:
        payload: dict[str, object] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None and self.supports_json_response_format:
            payload["response_format"] = response_format

        start = time.perf_counter()
        try:
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise _RetryableError(str(exc), status=None) from exc

        return self._parse_http_response(resp, model, start, provider="openai")

    def _nvidia_effective_max_tokens(self, requested: int) -> int:
        floor = min(self._nvidia_output_token_floor, self._nvidia_output_token_ceiling)
        ceiling = max(self._nvidia_output_token_floor, self._nvidia_output_token_ceiling)
        return min(ceiling, max(floor, requested))

    async def _do_nvidia(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, str] | None,
    ) -> LLMResponse:
        effective_max = self._nvidia_effective_max_tokens(max_tokens)
        payload: dict[str, object] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._nvidia_temperature if temperature == 0.0 else temperature,
            "top_p": self._nvidia_top_p,
            "max_tokens": effective_max,
            "stream": False,
        }
        if response_format is not None and self.supports_json_response_format:
            payload["response_format"] = response_format

        start = time.perf_counter()
        try:
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise _RetryableError(str(exc), status=None) from exc

        return self._parse_http_response(resp, model, start, provider="nvidia")

    async def _do_cloudflare(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float,
        max_tokens: int,
        want_json: bool,
    ) -> LLMResponse:
        if not self._account_id:
            raise LLMError(
                "cloudflare account_id is not configured",
                retryable=False,
                status=None,
            )

        model_id = _normalize_cloudflare_model(model)
        body: dict[str, object] = {
            "model": model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if want_json:
            body["response_format"] = {"type": "json_object"}

        url = _cloudflare_chat_completions_url(self._base_url, self._account_id)
        start = time.perf_counter()
        try:
            resp = await self._client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise _RetryableError(str(exc), status=None) from exc

        return self._parse_http_response(resp, model, start, provider="cloudflare")

    async def _do_zen(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        want_json: bool,
    ) -> LLMResponse:
        if self._anthropic is None:
            raise LLMError("zen anthropic client is not configured", retryable=False)

        system, api_messages = _split_anthropic_messages(messages)
        if want_json:
            system = (
                f"{system}\n\n{_ZEN_JSON_SYSTEM_SUFFIX}".strip()
                if system
                else _ZEN_JSON_SYSTEM_SUFFIX
            )

        start = time.perf_counter()
        try:
            response = await self._anthropic.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=api_messages,
                **({"system": system} if system else {}),
            )
        except APITimeoutError as exc:
            raise _RetryableError(str(exc), status=None) from exc
        except APIStatusError as exc:
            raise _anthropic_api_status_to_llm_error(exc) from exc

        return _parse_anthropic_message_response(response, model, start)

    def _parse_http_response(
        self,
        resp: httpx.Response,
        model: str,
        start: float,
        *,
        provider: ApiKind,
    ) -> LLMResponse:
        if resp.status_code >= 400:
            _raise_for_http_response(resp)

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise LLMError(
                "provider returned malformed JSON",
                retryable=False,
                status=resp.status_code,
            ) from exc

        if not isinstance(data, dict):
            raise LLMError(
                "provider returned unexpected JSON shape",
                retryable=False,
                status=resp.status_code,
            )

        if provider == "openai":
            return self._parse_openai_success(data, model, start)
        if provider == "nvidia":
            return self._parse_nvidia_success(data, model, start, http_status=resp.status_code)
        return self._parse_cloudflare_success(data, model, start, http_status=resp.status_code)

    def _parse_openai_success(
        self, data: dict[str, object], model: str, start: float
    ) -> LLMResponse:
        return _parse_chat_completion_success(
            data, model, start, provider_label="openai"
        )

    def _parse_nvidia_success(
        self,
        data: dict[str, object],
        model: str,
        start: float,
        *,
        http_status: int | None,
    ) -> LLMResponse:
        return _parse_chat_completion_success(
            data,
            model,
            start,
            provider_label="nvidia",
            http_status=http_status,
        )

    def _parse_cloudflare_success(
        self,
        data: dict[str, object],
        model: str,
        start: float,
        *,
        http_status: int,
    ) -> LLMResponse:
        if data.get("success") is False:
            errors = data.get("errors")
            messages = _format_cloudflare_errors(errors)
            combined = json.dumps(data)[:400]
            if _is_auth_cloudflare_errors(errors) or _is_auth_cloudflare_errors(messages):
                raise LLMError(
                    f"cloudflare authentication failed: {messages or combined}",
                    retryable=False,
                    status=401,
                )
            if _is_quota_exhausted(429, combined):
                raise LLMQuotaExhaustedError(
                    messages or combined,
                    status=429,
                )
            raise LLMError(
                messages or f"cloudflare request failed: {combined}",
                retryable=False,
                status=http_status,
            )

        return _parse_chat_completion_success(
            data, model, start, provider_label="cloudflare", http_status=http_status
        )


def _split_anthropic_messages(
    messages: list[ChatMessage],
) -> tuple[str | None, list[dict[str, str]]]:
    system_parts: list[str] = []
    api_messages: list[dict[str, str]] = []
    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
            continue
        api_messages.append({"role": msg.role, "content": msg.content})
    system = "\n\n".join(system_parts) if system_parts else None
    return system, api_messages


def _anthropic_api_status_to_llm_error(exc: APIStatusError) -> LLMError:
    status = exc.status_code
    body = exc.response.text if exc.response is not None else str(exc)
    snippet = _http_error_snippet(status, body)
    if status in _NON_RETRYABLE_HTTP:
        return LLMError(snippet, retryable=False, status=status)
    if status == 429 and _is_quota_exhausted(status, body):
        return LLMQuotaExhaustedError(snippet, status=status)
    headers = exc.response.headers if exc.response is not None else httpx.Headers()
    retry_after = _parse_retry_after(headers)
    if status in _RETRYABLE_HTTP:
        return _RetryableError(
            snippet,
            status=status,
            retry_after_seconds=retry_after,
        )
    return LLMError(snippet, retryable=False, status=status)


def _anthropic_content_blocks_to_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(str(block["text"]))
                continue
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
    return "".join(parts).strip()


def _anthropic_empty_diagnostics(response: Any) -> str:
    content = getattr(response, "content", None)
    block_types: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                block_types.append(str(block.get("type", "?")))
            else:
                block_types.append(str(getattr(block, "type", "?")))
    stop = getattr(response, "stop_reason", None)
    return f"stop_reason={stop!r}; block_types={block_types}"


def _parse_anthropic_message_response(
    response: Any, model: str, start: float
) -> LLMResponse:
    text = _anthropic_content_blocks_to_text(response.content)
    if not text:
        diag = _anthropic_empty_diagnostics(response)
        extra = ""
        if getattr(response, "stop_reason", None) == "max_tokens":
            extra = "; stop_reason=max_tokens (may have hit max_tokens)"
        raise LLMError(
            f"zen returned empty content ({diag}{extra})",
            retryable=False,
        )

    usage = getattr(response, "usage", None)
    prompt_tokens = _int_or_zero(getattr(usage, "input_tokens", 0) if usage else 0)
    completion_tokens = _int_or_zero(getattr(usage, "output_tokens", 0) if usage else 0)

    return LLMResponse(
        content=text,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )


def _extract_chat_message_answer(message: dict[str, object]) -> str:
    """Return assistant answer text; ignore reasoning-only fields (e.g. Muse Glimmer)."""
    content = _message_content_to_str(message.get("content"))
    if content:
        return content
    for key in ("text", "answer"):
        if key in message:
            text = _message_content_to_str(message[key])
            if text:
                return text
    return ""


def _message_content_to_str(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text") is not None:
                parts.append(str(item["text"]))
        return "".join(parts).strip()
    return str(content).strip()


def _empty_choice_diagnostics(choice: dict[str, object]) -> str:
    message = choice.get("message")
    msg_keys: list[str] = []
    reasoning_present = False
    if isinstance(message, dict):
        msg_keys = sorted(str(k) for k in message)
        rc = message.get("reasoning_content")
        reasoning_present = rc not in (None, "", [], {})
    choice_keys = sorted(str(k) for k in choice)
    finish = choice.get("finish_reason")
    return (
        f"choice_keys={choice_keys}; message_keys={msg_keys}; "
        f"finish_reason={finish!r}; reasoning_content_present={reasoning_present}"
    )


def _parse_chat_completion_success(
    data: dict[str, object],
    model: str,
    start: float,
    *,
    provider_label: str,
    http_status: int | None = None,
) -> LLMResponse:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMError(f"{provider_label} returned no choices", retryable=False)

    first = choices[0]
    if not isinstance(first, dict):
        raise LLMError(f"{provider_label} returned malformed choices", retryable=False)

    message = first.get("message")
    if not isinstance(message, dict):
        raise LLMError(f"{provider_label} returned empty message", retryable=False)

    content = _extract_chat_message_answer(message)
    if not content:
        diag = _empty_choice_diagnostics(first)
        extra = ""
        if first.get("finish_reason") == "length":
            extra = "; finish_reason=length (may have hit max_tokens)"
        raise LLMError(
            f"{provider_label} returned empty content ({diag}{extra})",
            retryable=False,
            status=http_status,
        )

    usage = data.get("usage")
    usage_dict = usage if isinstance(usage, dict) else {}
    prompt_tokens = _int_or_zero(usage_dict.get("prompt_tokens", 0))
    completion_tokens = _int_or_zero(usage_dict.get("completion_tokens", 0))

    return LLMResponse(
        content=content,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )


def _int_or_zero(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _format_cloudflare_errors(errors: object) -> str:
    if not isinstance(errors, list) or not errors:
        return ""
    parts: list[str] = []
    for item in errors:
        if isinstance(item, dict):
            msg = item.get("message") or item.get("code")
            if msg is not None:
                parts.append(str(msg))
        elif item is not None:
            parts.append(str(item))
    return "; ".join(parts)


def _is_auth_cloudflare_errors(errors: object) -> bool:
    text = _format_cloudflare_errors(errors).lower()
    if not text and isinstance(errors, str):
        text = errors.lower()
    return "auth" in text or "unauthorized" in text or "invalid api token" in text
