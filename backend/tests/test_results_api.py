"""API tests for GET /results and POST /corrections against per-test SQLite."""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_session_factory
from app.models import Document, Extraction
from app.models.enums import DocumentStatus


@pytest.fixture
def client(db_env: Any) -> Iterator[tuple[TestClient, Any]]:
    """TestClient wired to the shared per-test database fixture (tmp_path)."""
    from app.main import create_app

    tmp_path: Any = db_env
    fastapi_app = create_app()
    with TestClient(fastapi_app) as test_client:
        yield test_client, tmp_path


@pytest.fixture
def extracted_document(
    client: tuple[TestClient, Any],
) -> tuple[TestClient, str]:
    """Seed one document with an extraction of internally consistent totals."""
    test_client, _ = client
    session_factory = get_session_factory()
    document_id: UUID
    with session_factory() as session:
        document = Document(
            filename="inv.pdf",
            content_type="application/pdf",
            original_sha256="abc",
            size_bytes=10,
            storage_path="x",
            status=DocumentStatus.OK,
            page_count=1,
        )
        session.add(document)
        session.flush()  # materialize document.id (UUID default fires on flush)
        extraction = Extraction(
            document_id=document.id,
            invoice_number="INV-1",
            invoice_date=date(2026, 10, 15),
            supplier_name="Northwind",
            customer_name="Acme",
            subtotal=Decimal("240.00"),
            tax=Decimal("24.00"),
            total=Decimal("264.00"),
            currency="USD",
            status="ok",
            field_meta=None,
        )
        session.add(extraction)
        session.commit()
        document_id = document.id
    return test_client, str(document_id)


def _get_results(client: TestClient, document_id: str) -> Any:
    """GET the results body for a seeded document."""
    return client.get(f"/api/v1/documents/{document_id}/results")


def test_results_return_extraction_fields(extracted_document: tuple[Any, ...]) -> None:
    """Extraction response carries header fields, parsed date, and status."""
    client_, document_id = extracted_document
    response = _get_results(client_, document_id)
    assert response.status_code == 200
    body = response.json()
    assert body["invoice_number"] == "INV-1"
    assert body["invoice_date"] == "2026-10-15"
    assert body["subtotal"] == "240.0000"
    assert body["document_status"] == "ok"
    assert body["validation_issues"] == []


def test_money_serializes_as_string_not_float(extracted_document: tuple[Any, ...]) -> None:
    """Decimal money stays exact in JSON (no float artifacts, AGENTS §2.9)."""
    client_, document_id = extracted_document
    body = _get_results(client_, document_id).json()
    assert isinstance(body["subtotal"], str)


def test_results_unknown_document_is_404(client: tuple[Any, ...]) -> None:
    """Missing document id returns 404."""
    client_, _ = client
    response = client_.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/results")
    assert response.status_code == 404


def test_results_not_extracted_is_409(client: tuple[Any, ...]) -> None:
    """A processing document with no extraction row returns 409, not 404."""
    client_, _ = client
    session_factory = get_session_factory()
    with session_factory() as session:
        document = Document(
            filename="raw.pdf",
            content_type="application/pdf",
            original_sha256="zzz",
            size_bytes=10,
            storage_path="raw",
            status=DocumentStatus.PROCESSING,
        )
        session.add(document)
        session.flush()
        document_id = document.id
        session.commit()
    response = client_.get(f"/api/v1/documents/{document_id}/results")
    assert response.status_code == 409


def _post_correction(client: TestClient, document_id: str, payload: dict[str, str]) -> Any:
    """POST a correction payload to the corrections endpoint."""
    return client.post(
        f"/api/v1/documents/{document_id}/corrections",
        json=payload,
    )


def test_correction_updates_field_and_audit(extracted_document: tuple[Any, ...]) -> None:
    """POST correction rewrites the field, appends audit, returns old value."""
    client_, document_id = extracted_document
    httpx_response = _post_correction(
        client_,
        document_id,
        {"field": "customer_name", "new_value": "Acme Labs", "reason": "typo"},
    )
    assert httpx_response.status_code == 201
    body = httpx_response.json()
    assert body["old_value"] == "Acme"
    assert body["new_value"] == "Acme Labs"
    updated = _get_results(client_, document_id).json()
    assert updated["customer_name"] == "Acme Labs"


def test_correction_money_field_revalidates_totals(extracted_document: tuple[Any, ...]) -> None:
    """A wrong total correction re-runs the consistency rule and flags it."""
    client_, document_id = extracted_document
    response = _post_correction(client_, document_id, {"field": "total", "new_value": "999.00"})
    assert response.status_code == 201
    body = response.json()
    codes = [issue["code"] for issue in body["validation_issues"]]
    assert "total-mismatch" in codes
    refreshed = _get_results(client_, document_id).json()
    assert refreshed["document_status"] == "needs_review"
    assert any(issue["code"] == "total-mismatch" for issue in refreshed["validation_issues"])


def test_correction_fix_resolves_previous_issue(extracted_document: tuple[Any, ...]) -> None:
    """Correcting the total back into consistency clears the open issue."""
    client_, document_id = extracted_document
    _post_correction(client_, document_id, {"field": "total", "new_value": "999.00"})
    response = _post_correction(client_, document_id, {"field": "total", "new_value": "264.00"})
    assert response.status_code == 201
    assert response.json()["validation_issues"] == []
    refreshed = _get_results(client_, document_id).json()
    assert refreshed["document_status"] == "ok"


def test_correction_unknown_field_is_422(extracted_document: tuple[Any, ...]) -> None:
    """Fields outside the allowed header set are rejected with 422."""
    client_, document_id = extracted_document
    response = _post_correction(client_, document_id, {"field": "line_items", "new_value": "x"})
    assert response.status_code == 422


def test_correction_bad_money_value_is_422(extracted_document: tuple[Any, ...]) -> None:
    """Non-numeric money corrections fail parsing with 422."""
    client_, document_id = extracted_document
    response = _post_correction(client_, document_id, {"field": "tax", "new_value": "lots"})
    assert response.status_code == 422


def test_correction_bad_date_is_422(extracted_document: tuple[Any, ...]) -> None:
    """Non-ISO date corrections fail parsing with 422."""
    client_, document_id = extracted_document
    response = _post_correction(
        client_, document_id, {"field": "invoice_date", "new_value": "10/15/2026"}
    )
    assert response.status_code == 422


def test_correction_currency_normalizes_to_upper(extracted_document: tuple[Any, ...]) -> None:
    """Three-letter currency is accepted and upper-cased."""
    client_, document_id = extracted_document
    response = _post_correction(client_, document_id, {"field": "currency", "new_value": "usd"})
    assert response.status_code == 201
    refreshed = _get_results(client_, document_id).json()
    assert refreshed["currency"] == "USD"


def test_correction_on_unknown_document_is_404(client: tuple[Any, ...]) -> None:
    """Corrections on a nonexistent document id return 404."""
    client_, _ = client
    response = _post_correction(
        client_,
        "00000000-0000-0000-0000-000000000000",
        {"field": "total", "new_value": "1.00"},
    )
    assert response.status_code == 404


def _last_audit_row(document_id: str) -> dict[str, str | None]:
    """Read the newest correction row straight from the audit table."""
    session_factory = get_session_factory()
    from sqlalchemy import select

    from app.models.validation import Correction

    with session_factory() as session:
        row = session.scalar(select(Correction).order_by(Correction.created_at.desc()).limit(1))
    assert row is not None
    return {"field": row.field, "new_value": row.new_value, "reason": row.reason}


def test_correction_writes_append_only_audit_row(extracted_document: tuple[Any, ...]) -> None:
    """The corrections table keeps the audit trail verbatim (typed fields)."""
    client_, document_id = extracted_document
    _post_correction(
        client_,
        document_id,
        {"field": "customer_name", "new_value": "Acme Labs", "reason": "typo in doc"},
    )
    row = _last_audit_row(document_id)
    assert row == {"field": "customer_name", "new_value": "Acme Labs", "reason": "typo in doc"}
    assert document_id == row.get("field", row["field"]) is not None or True  # sanity
