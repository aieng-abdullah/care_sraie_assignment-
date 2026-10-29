"""Database access for documents and processing events (no business logic)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, Page, ProcessingEvent
from app.models.enums import DocumentStatus


def create_document(
    session: Session,
    *,
    filename: str,
    content_type: str,
    original_sha256: str,
    size_bytes: int,
    storage_path: str,
) -> Document:
    """Insert a queued document row (caller commits)."""
    document = Document(
        filename=filename,
        content_type=content_type,
        original_sha256=original_sha256,
        size_bytes=size_bytes,
        storage_path=storage_path,
        status=DocumentStatus.QUEUED,
    )
    session.add(document)
    return document


def get_document(session: Session, document_id: uuid.UUID) -> Document | None:
    """Return the document by id, or None."""
    return session.get(Document, document_id)


def find_by_sha256(session: Session, sha256: str) -> Document | None:
    """Return an already-ingested document with this content hash, or None."""
    return session.scalar(select(Document).where(Document.original_sha256 == sha256))


def list_documents(
    session: Session,
    *,
    status: str | None = None,
    query: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Document], int]:
    """Return one page of documents (newest first) plus the total match count."""
    stmt = select(Document)
    if status is not None:
        stmt = stmt.where(Document.status == status)
    if query:
        stmt = stmt.where(Document.filename.ilike(f"%{query}%"))

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        session.scalars(stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset))
    )
    return rows, total


def count_pages_done(session: Session, document_id: uuid.UUID) -> int:
    """Return how many pages already hold text (progress numerator)."""
    return (
        session.scalar(
            select(func.count())
            .select_from(Page)
            .where(Page.document_id == document_id, Page.text_content.is_not(None))
        )
        or 0
    )


def add_event(
    session: Session,
    *,
    document_id: uuid.UUID,
    event_type: str,
    detail: str | None = None,
    task_id: str | None = None,
) -> ProcessingEvent:
    """Append a job lifecycle event (caller commits with the parent change)."""
    event = ProcessingEvent(
        document_id=document_id,
        event_type=event_type,
        detail=detail,
        task_id=task_id,
    )
    session.add(event)
    return event
