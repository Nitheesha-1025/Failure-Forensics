"""Runtime configuration (env-driven)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_SECRETS = frozenset(
    {
        "change-me",
        "change-me-to-a-long-random-string",
        "secret",
        "changeme",
        "jwt-secret",
        "dev",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FORENSICS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(
        default="",
        validation_alias=AliasChoices("DATABASE_URL", "FORENSICS_DATABASE_URL"),
    )
    jwt_secret: str = Field(
        default="",
        validation_alias=AliasChoices("JWT_SECRET", "FORENSICS_JWT_SECRET"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        min_length=3,
        validation_alias=AliasChoices("JWT_ALGORITHM", "FORENSICS_JWT_ALGORITHM"),
    )
    jwt_access_token_expire_minutes: int = Field(
        default=60,
        ge=5,
        le=10_080,
        validation_alias=AliasChoices(
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
            "FORENSICS_JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )
    application_secret: str = Field(
        default="",
        validation_alias=AliasChoices("APPLICATION_SECRET", "FORENSICS_APPLICATION_SECRET"),
    )

    upload_dir: Path = Field(
        default=Path("./uploads"),
        validation_alias=AliasChoices("UPLOAD_DIR", "FORENSICS_UPLOAD_DIR"),
    )
    max_upload_size_mb: int = Field(
        default=25,
        ge=1,
        le=512,
        validation_alias=AliasChoices(
            "MAX_UPLOAD_SIZE_MB",
            "FORENSICS_MAX_UPLOAD_SIZE_MB",
        ),
    )

    llm_provider: str = Field(
        default="auto",
        validation_alias=AliasChoices("FORENSICS_LLM_PROVIDER", "LLM_PROVIDER"),
    )
    cloudflare_account_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "CLOUDFLARE_ACCOUNT_ID",
            "FORENSICS_CLOUDFLARE_ACCOUNT_ID",
        ),
    )
    cloudflare_api_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "CLOUDFLARE_API_TOKEN",
            "FORENSICS_CLOUDFLARE_API_TOKEN",
        ),
    )
    cloudflare_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "CLOUDFLARE_MODEL",
            "FORENSICS_CLOUDFLARE_MODEL",
        ),
    )
    cloudflare_extraction_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_CLOUDFLARE_EXTRACTION_MODEL",
            "CLOUDFLARE_EXTRACTION_MODEL",
        ),
    )
    cloudflare_classification_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_CLOUDFLARE_CLASSIFICATION_MODEL",
            "CLOUDFLARE_CLASSIFICATION_MODEL",
        ),
    )
    cloudflare_summarization_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_CLOUDFLARE_SUMMARIZATION_MODEL",
            "CLOUDFLARE_SUMMARIZATION_MODEL",
        ),
    )
    cloudflare_judge_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_CLOUDFLARE_JUDGE_MODEL",
            "CLOUDFLARE_JUDGE_MODEL",
        ),
    )

    opencode_zen_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENCODE_ZEN_API_KEY",
            "FORENSICS_OPENCODE_ZEN_API_KEY",
            "ANTHROPIC_API_KEY",
        ),
    )
    opencode_zen_base_url: str = Field(
        default="https://opencode.ai/zen/v1",
        validation_alias=AliasChoices(
            "OPENCODE_ZEN_BASE_URL",
            "FORENSICS_OPENCODE_ZEN_BASE_URL",
        ),
    )
    opencode_zen_model: str = Field(
        default="claude-fable-5-1",
        validation_alias=AliasChoices(
            "OPENCODE_ZEN_MODEL",
            "FORENSICS_OPENCODE_ZEN_MODEL",
        ),
    )
    opencode_zen_extraction_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_OPENCODE_ZEN_EXTRACTION_MODEL",
            "OPENCODE_ZEN_EXTRACTION_MODEL",
        ),
    )
    opencode_zen_classification_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_OPENCODE_ZEN_CLASSIFICATION_MODEL",
            "OPENCODE_ZEN_CLASSIFICATION_MODEL",
        ),
    )
    opencode_zen_summarization_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_OPENCODE_ZEN_SUMMARIZATION_MODEL",
            "OPENCODE_ZEN_SUMMARIZATION_MODEL",
        ),
    )
    opencode_zen_judge_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_OPENCODE_ZEN_JUDGE_MODEL",
            "OPENCODE_ZEN_JUDGE_MODEL",
        ),
    )

    nvidia_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "NVIDIA_API_KEY",
            "FORENSICS_NVIDIA_API_KEY",
        ),
    )
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        validation_alias=AliasChoices(
            "NVIDIA_BASE_URL",
            "FORENSICS_NVIDIA_BASE_URL",
        ),
    )
    nvidia_model: str = Field(
        default="meta/muse-glimmer-30b",
        validation_alias=AliasChoices(
            "NVIDIA_MODEL",
            "FORENSICS_NVIDIA_MODEL",
        ),
    )
    nvidia_extraction_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_NVIDIA_EXTRACTION_MODEL",
            "NVIDIA_EXTRACTION_MODEL",
        ),
    )
    nvidia_classification_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_NVIDIA_CLASSIFICATION_MODEL",
            "NVIDIA_CLASSIFICATION_MODEL",
        ),
    )
    nvidia_summarization_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_NVIDIA_SUMMARIZATION_MODEL",
            "NVIDIA_SUMMARIZATION_MODEL",
        ),
    )
    nvidia_judge_model: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FORENSICS_NVIDIA_JUDGE_MODEL",
            "NVIDIA_JUDGE_MODEL",
        ),
    )
    nvidia_temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        validation_alias=AliasChoices(
            "NVIDIA_TEMPERATURE",
            "FORENSICS_NVIDIA_TEMPERATURE",
        ),
    )
    nvidia_top_p: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices(
            "NVIDIA_TOP_P",
            "FORENSICS_NVIDIA_TOP_P",
        ),
    )
    nvidia_output_token_floor: int = Field(
        default=1024,
        ge=64,
        le=8192,
        validation_alias=AliasChoices(
            "NVIDIA_OUTPUT_TOKEN_FLOOR",
            "FORENSICS_NVIDIA_OUTPUT_TOKEN_FLOOR",
        ),
    )
    nvidia_output_token_ceiling: int = Field(
        default=8192,
        ge=256,
        le=8192,
        validation_alias=AliasChoices(
            "NVIDIA_OUTPUT_TOKEN_CEILING",
            "FORENSICS_NVIDIA_OUTPUT_TOKEN_CEILING",
        ),
    )

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    extraction_model: str = "gpt-4o-mini"
    classification_model: str = "gpt-4o-mini"
    summarization_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o"

    db_path: Path = Path("./forensics.sqlite3")
    traces_dir: Path = Path("./traces")
    eval_set_path: Path = Path("./eval/cases.jsonl")

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8090, ge=1, le=65535)
    cors_origins: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "FORENSICS_CORS_ORIGINS"),
    )

    judge_concurrency: int = Field(
        default=1,
        ge=1,
        le=32,
        validation_alias=AliasChoices(
            "JUDGE_CONCURRENCY",
            "FORENSICS_JUDGE_CONCURRENCY",
        ),
    )

    request_timeout_s: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _require_strong_jwt_when_database_configured(self) -> Settings:
        if not self.database_url.strip():
            return self
        secret = self.jwt_secret.strip()
        if len(secret) < 32:
            msg = "JWT_SECRET must be at least 32 characters when DATABASE_URL is set"
            raise ValueError(msg)
        if secret.lower() in _INSECURE_JWT_SECRETS:
            msg = "JWT_SECRET must not use a default placeholder when DATABASE_URL is set"
            raise ValueError(msg)
        return self


def load_settings(**overrides: Any) -> Settings:
    return Settings(**overrides)
