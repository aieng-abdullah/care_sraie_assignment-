"""Read-side business logic for the document results endpoint.

Fetches the extraction, line items, and unresolved validation issues for one
document and shapes them into the API response. Raises domain errors the route
translates into HTTP statuses (no HTTP objects in the service layer).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Document
from app.repositories import documents as documents_repo
from app.schemas.document import (
    ExtractionLineItem,
    ExtractionResponse,
    ValidationIssueItem,
)


class ExtractionNotReadyError(ValueError):
    """Raised when a document exists but has no extraction row yet."""


def get_results(session: Session, document: Document) -> ExtractionResponse:
    """Build the results response for an already-fetched document.

    Raises ExtractionNotReadyError when the document has not been extracted yet
    (still queued/processing/failed).
    """
    extraction = documents_repo.get_extraction(session, document.id)
    if extraction is None:
        raise ExtractionNotReadyError(
            f"extraction not available (document status: {document.status})"
        )

    line_items = documents_repo.get_line_items(session, extraction.id)
    issues = documents_repo.list_unresolved_issues(session, document.id)

    return ExtractionResponse(
        document_id=document.id,
        document_status=document.status,
        invoice_number=extraction.invoice_number,
        invoice_date=extraction.invoice_date,
        supplier_name=extraction.supplier_name,
        customer_name=extraction.customer_name,
        subtotal=extraction.subtotal,
        tax=extraction.tax,
        total=extraction.total,
        currency=extraction.currency,
        status=extraction.status or "ok",
        field_meta=extraction.field_meta,
        line_items=[
            ExtractionLineItem(
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                amount=item.amount,
            )
            for item in line_items
        ],
        validation_issues=[
            ValidationIssueItem(
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                context=issue.context,
            )
            for issue in issues
        ],
    )


def lookup_document(session: Session, document_id: uuid.UUID) -> Document:
    """Return the document or raise KeyError if the id does not exist."""
    document = documents_repo.get_document(session, document_id)
    if document is None:
        raise KeyError(f"document {document_id} not found")
    return document
