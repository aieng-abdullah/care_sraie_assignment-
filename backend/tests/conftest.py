"""Shared fixtures: per-test SQLite database with env and engine lifecycle."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Collection imports app.workers.celery_app, which reads settings at module
# load; provide harmless defaults here. Fixtures override per test.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LLM_API_KEY", "test-key")

from app.core.config import get_settings
from app.core.database import Base, get_engine, reset_engine

_REQUIRED_ENV = {
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_API_KEY": "test-key",
}


@pytest.fixture
def db_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Provide a fresh SQLite database file and empty uploads dir per test.

    Returns the temp directory so tests can place document files in it.
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    reset_engine()
    from app.core import rate_limit

    rate_limit._windows.clear()

    import app.models  # noqa: F401  # register tables on Base.metadata

    Base.metadata.create_all(get_engine())
    yield tmp_path
    reset_engine()
    get_settings.cache_clear()
    rate_limit._windows.clear()
