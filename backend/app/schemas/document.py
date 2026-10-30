"""Pydantic schemas for the documents endpoints (upload, list, status)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UploadItem(BaseModel):
    """Outcome for one uploaded file: accepted, duplicate, or rejected with reason."""

    filename: str
    document_id: uuid.UUID | None = None
    content_type: str | None = None
    duplicate: bool = False
    error: str | None = None


class UploadResponse(BaseModel):
    """Per-file results of a multi-file upload; errors are per item, not fatal."""

    items: list[UploadItem]


class DocumentSummary(BaseModel):
    """Row returned by the document list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: str
    page_count: int | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    items: list[DocumentSummary]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class DocumentStatusResponse(BaseModel):
    """Processing status for one document, with page progress for large PDFs."""

    id: uuid.UUID
    filename: str
    status: str
    pages_done: int
    pages_total: int | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ExtractionLineItem(BaseModel):
    """One invoice line item; money fields serialize as JSON strings (no floats)."""

    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class ValidationIssueItem(BaseModel):
    """One unresolved validation problem attached to a document."""

    code: str
    severity: str
    message: str
    context: dict[str, Any] | None = None


class ExtractionResponse(BaseModel):
    """Extraction result for one document plus unresolved validation issues.

    Absent or uncertain fields are null with detail in field_meta — the client
    must never guess values (AGENTS §2.4). Money fields are Decimal, serialized
    as JSON strings to avoid float artifacts.
    """

    document_id: uuid.UUID
    document_status: str
    invoice_number: str | None = None
    invoice_date: date | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None
    status: str
    field_meta: dict[str, Any] | None = None
    line_items: list[ExtractionLineItem] = Field(default_factory=list)
    validation_issues: list[ValidationIssueItem] = Field(default_factory=list)


correction_fields = (
    "invoice_number",
    "invoice_date",
    "supplier_name",
    "customer_name",
    "subtotal",
    "tax",
    "total",
    "currency",
)


class CorrectionCreate(BaseModel):
    """A user's manual fix for one extraction field, with optional reason."""

    field: str = Field(max_length=64)
    new_value: str = Field(max_length=512)
    reason: str | None = Field(default=None, max_length=512)


class CorrectionResponse(BaseModel):
    """Outcome of an accepted correction (append-only audit row + revalidation)."""

    document_id: uuid.UUID
    field: str
    old_value: str | None
    new_value: str
    reason: str | None = None
    validation_issues: list[ValidationIssueItem]
