"""Tests for environment settings: fail-fast validation, defaults, and secret handling."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings

REQUIRED = {
    "database_url": "postgresql+psycopg://u:p@localhost/db",
    "redis_url": "redis://localhost:6379/0",
    "llm_api_key": "test-key",
}


def make_settings(**overrides: Any) -> Settings:
    """Build Settings from required test values plus overrides, ignoring any .env file."""
    return Settings.model_validate({**REQUIRED, **overrides})


def test_missing_required_env_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent required variables raise a validation error instead of starting half-configured."""
    for key in ("DATABASE_URL", "REDIS_URL", "LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError) as excinfo:
        Settings.model_validate({})
    missing = {error["loc"][0] for error in excinfo.value.errors()}
    assert {"database_url", "redis_url", "llm_api_key"} <= missing


def test_defaults_match_documented_env_example() -> None:
    """Optional settings default to the values documented in .env.example."""
    settings = make_settings()
    assert settings.llm_base_url == "https://api.openai.com/v1"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.max_upload_mb == 20
    assert settings.max_pdf_pages == 1000
    assert settings.ocr_engine == "tesseract"
    assert settings.embedding_dim == 1536


def test_secrets_never_appear_in_repr() -> None:
    """SecretStr keeps the LLM API key out of repr/str output (no secret logging)."""
    settings = make_settings()
    assert "test-key" not in repr(settings)
    assert "test-key" not in str(settings.model_dump())


def test_invalid_ocr_engine_rejected() -> None:
    """Unknown OCR engine fails at startup rather than at first scanned document."""
    with pytest.raises(ValidationError):
        make_settings(ocr_engine="easyocr")


def test_upload_dir_is_absolute() -> None:
    """Upload path resolves absolute so API and workers agree regardless of cwd."""
    assert make_settings(upload_dir="data/uploads").upload_dir.is_absolute()


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings load once per process; repeated calls return the same object."""
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key.upper(), value)
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
