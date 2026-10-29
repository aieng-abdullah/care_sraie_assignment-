"""Pydantic schemas for the documents endpoints (upload, list, status)."""

import uuid
from datetime import datetime

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
