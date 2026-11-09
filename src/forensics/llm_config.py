"""Resolve LLM provider credentials and model IDs from settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Settings
from .llm_client import LLMClient

# https://developers.cloudflare.com/workers-ai/get-started/rest-api/
CLOUDFLARE_API_BASE_URL = "https://api.cloudflare.com/client/v4"
CLOUDFLARE_DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct"

# OpenCode Zen (Anthropic Messages API compatible)
OPENCODE_ZEN_BASE_URL = "https://opencode.ai/zen/v1"
OPENCODE_ZEN_DEFAULT_MODEL = "claude-fable-5-1"

# NVIDIA NIM (OpenAI-compatible chat/completions)
NVIDIA_API_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_DEFAULT_MODEL = "meta/muse-glimmer-30b"

LLMProvider = Literal["openai", "cloudflare", "zen", "nvidia"]


@dataclass(frozen=True, slots=True)
class ResolvedLLMSettings:
    provider: LLMProvider
    api_key: str
    base_url: str
    account_id: str
    extraction_model: str
    classification_model: str
    summarization_model: str
    judge_model: str
    supports_json_response_format: bool


class LLMConfigurationError(Exception):
    pass


def _normalize_provider(raw: str) -> str:
    return raw.strip().lower()


def _cloudflare_configured(settings: Settings) -> bool:
    return bool(
        settings.cloudflare_account_id.strip()
        and settings.cloudflare_api_token.strip()
    )


def _zen_configured(settings: Settings) -> bool:
    return bool(settings.opencode_zen_api_key.strip())


def resolve_llm_settings(settings: Settings) -> ResolvedLLMSettings:
    """Pick OpenCode Zen, Cloudflare Workers AI, or OpenAI from env."""
    openai_key = settings.openai_api_key.strip()
    raw_provider = _normalize_provider(settings.llm_provider or "auto")

    allowed = {"auto", "openai", "cloudflare", "zen", "nvidia", "anthropic", "opencode"}
    if raw_provider not in allowed:
        msg = (
            f"Unknown FORENSICS_LLM_PROVIDER={raw_provider!r} "
            "(use auto, zen, cloudflare, nvidia, or openai)"
        )
        raise LLMConfigurationError(msg)

    if raw_provider in {"anthropic", "opencode"}:
        raw_provider = "zen"

    provider: LLMProvider
    if raw_provider == "zen":
        provider = "zen"
    elif raw_provider == "openai":
        provider = "openai"
    elif raw_provider == "cloudflare":
        provider = "cloudflare"
    elif raw_provider == "nvidia":
        provider = "nvidia"
    elif _zen_configured(settings):
        provider = "zen"
    elif _cloudflare_configured(settings):
        provider = "cloudflare"
    elif openai_key:
        provider = "openai"
    else:
        provider = "zen"

    if provider == "zen":
        api_key = settings.opencode_zen_api_key.strip()
        if not api_key:
            raise LLMConfigurationError(
                "OPENCODE_ZEN_API_KEY is required when FORENSICS_LLM_PROVIDER=zen "
                "(or auto with no Cloudflare/OpenAI credentials)"
            )
        base = settings.opencode_zen_base_url.strip() or OPENCODE_ZEN_BASE_URL
        default_model = settings.opencode_zen_model.strip() or OPENCODE_ZEN_DEFAULT_MODEL
        return ResolvedLLMSettings(
            provider="zen",
            api_key=api_key,
            base_url=base.rstrip("/"),
            account_id="",
            extraction_model=settings.opencode_zen_extraction_model or default_model,
            classification_model=settings.opencode_zen_classification_model or default_model,
            summarization_model=settings.opencode_zen_summarization_model or default_model,
            judge_model=settings.opencode_zen_judge_model or default_model,
            supports_json_response_format=True,
        )

    if provider == "cloudflare":
        account_id = settings.cloudflare_account_id.strip()
        token = settings.cloudflare_api_token.strip()
        if not account_id or not token:
            raise LLMConfigurationError(
                "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required when "
                "FORENSICS_LLM_PROVIDER=cloudflare"
            )
        default_model = settings.cloudflare_model.strip() or CLOUDFLARE_DEFAULT_MODEL
        return ResolvedLLMSettings(
            provider="cloudflare",
            api_key=token,
            base_url=CLOUDFLARE_API_BASE_URL,
            account_id=account_id,
            extraction_model=settings.cloudflare_extraction_model or default_model,
            classification_model=settings.cloudflare_classification_model or default_model,
            summarization_model=settings.cloudflare_summarization_model or default_model,
            judge_model=settings.cloudflare_judge_model or default_model,
            supports_json_response_format=True,
        )

    if provider == "nvidia":
        api_key = settings.nvidia_api_key.strip()
        if not api_key:
            raise LLMConfigurationError(
                "NVIDIA_API_KEY is required when FORENSICS_LLM_PROVIDER=nvidia"
            )
        base = settings.nvidia_base_url.strip() or NVIDIA_API_BASE_URL
        default_model = settings.nvidia_model.strip() or NVIDIA_DEFAULT_MODEL
        return ResolvedLLMSettings(
            provider="nvidia",
            api_key=api_key,
            base_url=base.rstrip("/"),
            account_id="",
            extraction_model=settings.nvidia_extraction_model or default_model,
            classification_model=settings.nvidia_classification_model or default_model,
            summarization_model=settings.nvidia_summarization_model or default_model,
            judge_model=settings.nvidia_judge_model or default_model,
            supports_json_response_format=True,
        )

    if not openai_key:
        raise LLMConfigurationError(
            "FORENSICS_OPENAI_API_KEY is required when using OpenAI "
            "(set OPENCODE_ZEN_API_KEY or Cloudflare credentials for other providers)"
        )
    return ResolvedLLMSettings(
        provider="openai",
        api_key=openai_key,
        base_url=settings.openai_base_url.rstrip("/"),
        account_id="",
        extraction_model=settings.extraction_model,
        classification_model=settings.classification_model,
        summarization_model=settings.summarization_model,
        judge_model=settings.judge_model,
        supports_json_response_format=True,
    )


def build_llm_client(resolved: ResolvedLLMSettings, *, settings: Settings) -> LLMClient:
    nvidia_kwargs: dict[str, float | int] = {}
    if resolved.provider == "nvidia":
        nvidia_kwargs = {
            "nvidia_temperature": settings.nvidia_temperature,
            "nvidia_top_p": settings.nvidia_top_p,
            "nvidia_output_token_floor": settings.nvidia_output_token_floor,
            "nvidia_output_token_ceiling": settings.nvidia_output_token_ceiling,
        }
    return LLMClient(
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        account_id=resolved.account_id or None,
        timeout_s=settings.request_timeout_s,
        max_retries=settings.max_retries,
        api_kind=resolved.provider,
        supports_json_response_format=resolved.supports_json_response_format,
        **nvidia_kwargs,
    )
