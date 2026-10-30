"""Environment-driven application settings, validated at startup (fail fast)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
OcrEngine = Literal["tesseract", "paddle"]


class Settings(BaseSettings):
    """All runtime configuration; sourced from environment variables, never hard-coded."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    environment: Literal["development", "test", "production"] = "development"

    # Required: startup fails with a clear validation error if any are missing.
    database_url: str
    redis_url: str
    llm_api_key: SecretStr  # Groq: gsk_...  or OpenAI: sk-...

    # LLM (OpenAI-compatible endpoint; set base_url/model for other providers).
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    # Embeddings (OpenAI); required from the semantic-search milestone onward.
    openai_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = Field(default=1536, gt=0)

    # Limits (NFR hard gates: size/page caps, rate limits).
    max_upload_mb: int = Field(default=20, gt=0, le=500)
    max_pdf_pages: int = Field(default=1000, gt=1, le=5000)
    rate_limit_uploads_per_minute: int = Field(default=60, gt=0)
    # Storage and OCR.
    upload_dir: Path = Path("data/uploads")
    ocr_engine: OcrEngine = "tesseract"

    # Logging.
    log_level: LogLevel = "INFO"
    service_name: str = "docintel-backend"

    @field_validator("upload_dir", mode="after")
    @classmethod
    def _absolute_upload_dir(cls, value: Path) -> Path:
        """Store uploads under an absolute path so workers share one location."""
        return value.expanduser().resolve()

    @field_validator("llm_base_url")
    @classmethod
    def _strip_base_url_slash(cls, value: str) -> str:
        """Drop trailing slash so SDK path joining never doubles it."""
        return value.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings; raises ValidationError at first call if env is incomplete."""
    return Settings()
