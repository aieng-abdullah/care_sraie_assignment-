"""Tests for the /health and /ready probe endpoints."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings

_REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+psycopg://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_API_KEY": "test-key",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Return a TestClient with minimal valid env and a cleared settings cache."""
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    from app.main import create_app

    app: FastAPI = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health_returns_200(client: TestClient) -> None:
    """Liveness endpoint answers 200 without touching dependencies."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_dependencies_up(client: TestClient) -> None:
    """Readiness is ok when both database and Redis checks succeed."""
    with (
        patch("app.api.v1.health._check_database", return_value=True),
        patch("app.api.v1.health._check_redis", return_value=True),
    ):
        response = client.get("/ready")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": True, "redis": True}


def test_ready_returns_503_when_database_down(client: TestClient) -> None:
    """Readiness fails with 503 if the database check fails."""
    with (
        patch("app.api.v1.health._check_database", return_value=False),
        patch("app.api.v1.health._check_redis", return_value=True),
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    body: dict[str, Any] = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] is False


def test_ready_returns_503_when_redis_down(client: TestClient) -> None:
    """Readiness fails with 503 if the Redis check fails."""
    with (
        patch("app.api.v1.health._check_database", return_value=True),
        patch("app.api.v1.health._check_redis", return_value=False),
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    body: dict[str, Any] = response.json()
    assert body["checks"]["redis"] is False
