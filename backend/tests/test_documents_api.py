"""Integration-style tests for the documents API against a per-test SQLite database."""

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import get_settings
from app.core.database import Base, get_engine, reset_engine

_REQUIRED_ENV = {
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_API_KEY": "test-key",
}

_PDF = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """TestClient wired to a fresh SQLite DB and temp upload dir per test."""
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    reset_engine()
    rate_limit._windows.clear()

    import app.models  # noqa: F401  # register tables

    Base.metadata.create_all(get_engine())

    from app.main import create_app

    fastapi_app: FastAPI = create_app()
    with TestClient(fastapi_app) as test_client:
        yield test_client

    reset_engine()
    get_settings.cache_clear()
    rate_limit._windows.clear()


def _upload(client: TestClient, files: list[tuple[str, bytes, str]]) -> httpx.Response:
    """POST multipart files to the upload endpoint."""
    response: httpx.Response = client.post(
        "/api/v1/documents",
        files=[("files", (name, data, content_type)) for name, data, content_type in files],
    )
    return response


def test_upload_accepts_pdf_and_returns_document_id(client: TestClient) -> None:
    """A valid PDF returns 201 with its assigned document id."""
    response = _upload(client, [("inv.pdf", _PDF, "application/pdf")])
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["error"] is None
    assert item["duplicate"] is False
    assert item["content_type"] == "application/pdf"


def test_upload_mixed_batch_reports_per_file_errors(client: TestClient) -> None:
    """Bad files fail per item; good ones still ingest (no batch rollback)."""
    response = _upload(
        client,
        [
            ("good.pdf", _PDF, "application/pdf"),
            ("junk.pdf", b"\x00\x01\x02\x03garbage", "application/pdf"),
        ],
    )
    assert response.status_code == 201
    items = response.json()["items"]
    assert items[0]["error"] is None
    assert items[1]["error"] is not None
    assert items[1]["document_id"] is None


def test_upload_all_invalid_returns_400(client: TestClient) -> None:
    """When nothing is accepted the whole request fails with 400 and reasons."""
    response = _upload(client, [("junk.pdf", b"not-a-real-file", "application/pdf")])
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["items"][0]["error"]


def test_upload_duplicate_content_is_idempotent(client: TestClient) -> None:
    """Same bytes twice return the original document with duplicate=True."""
    first = _upload(client, [("a.pdf", _PDF, "application/pdf")])
    second = _upload(client, [("b.pdf", _PDF, "application/pdf")])
    assert first.status_code == 201 and second.status_code == 201
    first_id = first.json()["items"][0]["document_id"]
    second_item = second.json()["items"][0]
    assert second_item["duplicate"] is True
    assert second_item["document_id"] == first_id

    listed = client.get("/api/v1/documents").json()
    assert listed["total"] == 1


def test_upload_rejects_oversized_file(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Files beyond MAX_UPLOAD_MB are rejected before storage."""
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    payload = b"x" * (1024 * 1024 + 1)
    response = _upload(client, [("big.pdf", payload, "application/pdf")])
    assert response.status_code == 400
    assert "exceeds" in str(response.json()["detail"])


def test_list_filters_by_status_and_filename(client: TestClient) -> None:
    """List supports status and keyword filters with pagination metadata."""
    _upload(client, [("alpha.pdf", _PDF, "application/pdf")])
    _upload(client, [("beta.pdf", _PDF + b"\n", "application/pdf")])

    all_docs = client.get("/api/v1/documents").json()
    assert all_docs["total"] == 2
    assert all_docs["page"] == 1

    filtered = client.get("/api/v1/documents", params={"q": "alpha"}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["filename"] == "alpha.pdf"

    by_status = client.get("/api/v1/documents", params={"status": "queued"}).json()
    assert by_status["total"] == 2
    none = client.get("/api/v1/documents", params={"status": "failed"}).json()
    assert none["total"] == 0


def test_status_endpoint_returns_progress_shape(client: TestClient) -> None:
    """Status returns queued state with page progress fields before processing."""
    uploaded = _upload(client, [("c.pdf", _PDF, "application/pdf")])
    doc_id = uploaded.json()["items"][0]["document_id"]
    response = client.get(f"/api/v1/documents/{doc_id}/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["pages_done"] == 0
    assert body["pages_total"] is None
    assert body["failure_reason"] is None


def test_status_endpoint_404_for_unknown_id(client: TestClient) -> None:
    """Unknown document ids return 404, not an empty shell."""
    response = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/status")
    assert response.status_code == 404


def test_upload_rate_limit_returns_429(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploads beyond the configured per-minute limit get 429 (NFR)."""
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_MINUTE", "3")
    get_settings.cache_clear()
    for i in range(3):
        accepted = _upload(client, [(f"r{i}.pdf", _PDF + str(i).encode(), "application/pdf")])
        assert accepted.status_code == 201
    limited = _upload(client, [("r3.pdf", _PDF + b"x", "application/pdf")])
    assert limited.status_code == 429
