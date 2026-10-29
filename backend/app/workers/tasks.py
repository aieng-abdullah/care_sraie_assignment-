"""Celery tasks: parent dispatch, per-page extraction, idempotent finalization.

Jobs are idempotent (page rows overwritten on retry); only transient errors
retry with backoff+jitter, pipeline errors fail the document gracefully.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from celery import group
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import Document, Page, ProcessingEvent
from app.models.enums import DocumentStatus, PageSource
from app.pipelines import (
    PageLimitExceededError,
    PipelineError,
    SheetExtract,
    extract_image,
    extract_page,
    extract_sheets,
    get_ocr_engine,
    get_page_count,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_POLICY = {
    "autoretry_for": (OperationalError, OSError),
    "retry_backoff": True,
    "retry_jitter": True,
    "retry_kwargs": {"max_retries": 3},
}

_FAILED_EVENT = "failed"
_DONE_EVENT = "done"


def _open_session() -> Session:
    """Return a fresh worker-scoped session (never the request session)."""
    return get_session_factory()()


def _record_event(
    session: Session, document_id: UUID, event_type: str, detail: str | None = None
) -> None:
    """Append a lifecycle event (caller commits)."""
    session.add(ProcessingEvent(document_id=document_id, event_type=event_type, detail=detail))


def _fail_document(session: Session, document: Document, reason: str) -> None:
    """Mark a document failed with a UI-safe reason (no stack traces)."""
    document.status = DocumentStatus.FAILED
    document.failure_reason = reason[:512]
    _record_event(session, document.id, _FAILED_EVENT, reason[:512])


@celery_app.task(name="app.workers.tasks.process_document", bind=True, **_RETRY_POLICY)
def process_document(self: object, document_id: str) -> str:
    """Parent job: validate limits, create page rows, fan out page work."""
    del self
    doc_uuid = UUID(document_id)
    session = _open_session()
    try:
        document = session.get(Document, doc_uuid)
        if document is None:
            return "missing"
        if document.status not in (DocumentStatus.QUEUED, DocumentStatus.PROCESSING):
            return "skipped"  # already terminal or reprocessing elsewhere
        document.status = DocumentStatus.PROCESSING
        document.failure_reason = None
        _record_event(session, doc_uuid, "started")
        session.commit()

        if document.content_type == "application/pdf":
            return _dispatch_pdf(session, document)
        _dispatch_single(session, document)
        return "single"
    except Exception:
        logger.exception(
            "parent task crashed", extra={"event": "parent_crashed", "document_id": document_id}
        )
        session.rollback()
        document = session.get(Document, doc_uuid)
        if document is not None:
            _fail_document(session, document, "internal processing error")
            session.commit()
        return "crashed"
    finally:
        session.close()


def _dispatch_pdf(session: Session, document: Document) -> str:
    """Check page cap, upsert empty page rows, fan out per-page tasks."""
    settings = get_settings()
    try:
        page_count = get_page_count(document.storage_path)
    except PipelineError as exc:
        _fail_document(session, document, str(exc))
        session.commit()
        return "failed"

    if page_count > settings.max_pdf_pages:
        error = PageLimitExceededError(
            f"PDF has {page_count} pages; limit is {settings.max_pdf_pages}"
        )
        _fail_document(session, document, str(error))
        session.commit()
        return "failed"

    document.page_count = page_count
    _upsert_blank_pages(session, document.id, page_count)
    session.commit()

    doc_id = str(document.id)
    tasks = [process_page.s(doc_id, page_no) for page_no in range(page_count)]
    if not tasks:
        finalize.s(doc_id).apply_async()
        return "empty_pdf"
    group(*tasks).apply_async()
    return f"fanout:{page_count}"


def _dispatch_single(session: Session, document: Document) -> str:
    """Queue one task for images and spreadsheets (no page fan-out needed)."""
    process_single.s(str(document.id)).apply_async()
    session.commit()
    return "single"


def _upsert_blank_pages(session: Session, document_id: UUID, page_count: int) -> None:
    """Ensure page rows 1..page_count exist (idempotent; progress denominator)."""
    existing = {
        page.page_no
        for page in session.scalars(select(Page).where(Page.document_id == document_id))
    }
    for page_no in range(page_count):
        if page_no + 1 not in existing:
            session.add(Page(document_id=document_id, page_no=page_no + 1))


@celery_app.task(name="app.workers.tasks.process_page", bind=True, **_RETRY_POLICY)
def process_page(self: object, document_id: str, page_no: int) -> str:
    """Extract one PDF page (0-based index) and store it; overwrites on retry."""
    del self
    doc_uuid = UUID(document_id)
    session = _open_session()
    try:
        document = session.get(Document, doc_uuid)
        if document is None:
            return "missing"
        settings = get_settings()
        ocr_engine = get_ocr_engine(settings.ocr_engine)
        extract = extract_page(document.storage_path, page_no, ocr_engine)

        existing = session.scalar(
            select(Page).where(Page.document_id == doc_uuid, Page.page_no == page_no + 1)
        )
        if existing is None:
            existing = Page(document_id=doc_uuid, page_no=page_no + 1)
            session.add(existing)
        existing.text_content = extract.text
        existing.source = extract.source
        existing.confidence = (
            Decimal(str(extract.confidence)) if extract.confidence is not None else None
        )
        _record_event(session, doc_uuid, "page_done", f"page {page_no + 1}")
        session.commit()
        _maybe_finalize(session, doc_uuid)
        return "ok"
    except PipelineError as exc:
        session.rollback()
        document = session.get(Document, doc_uuid)
        if document is not None:
            _fail_document(session, document, str(exc))
            session.commit()
        return "failed"
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.process_single", bind=True, **_RETRY_POLICY)
def process_single(self: object, document_id: str) -> str:
    """Extract an image (one OCR page) or spreadsheet (one page per sheet)."""
    del self
    doc_uuid = UUID(document_id)
    session = _open_session()
    try:
        document = session.get(Document, doc_uuid)
        if document is None:
            return "missing"
        settings = get_settings()

        if document.content_type == "text/csv" or document.content_type.endswith(
            ("spreadsheetml.sheet", "ms-excel")
        ):
            sheets = extract_sheets(document.storage_path, document.content_type)
            _store_sheets(session, doc_uuid, sheets)
        else:
            ocr_engine = get_ocr_engine(settings.ocr_engine)
            text, confidence = extract_image(document.storage_path, ocr_engine)
            _store_pages(session, doc_uuid, [(text, confidence)])

        _record_event(session, doc_uuid, "single_done")
        session.commit()
        _maybe_finalize(session, doc_uuid)
        return "ok"
    except PipelineError as exc:
        session.rollback()
        document = session.get(Document, doc_uuid)
        if document is not None:
            _fail_document(session, document, str(exc))
            session.commit()
        return "failed"
    finally:
        session.close()


def _store_sheets(session: Session, document_id: UUID, sheets: list[SheetExtract]) -> None:
    """Store each sheet as one page row (page order = workbook order)."""
    _clear_pages(session, document_id)
    for index, sheet in enumerate(sheets, start=1):
        session.add(
            Page(
                document_id=document_id,
                page_no=index,
                text_content=sheet.text,
                source=PageSource.TEXT_LAYER,
            )
        )


def _store_pages(session: Session, document_id: UUID, rows: list[tuple[str, float | None]]) -> None:
    """Store single-content page rows (images: exactly one page)."""
    _clear_pages(session, document_id)
    for index, (text, confidence) in enumerate(rows, start=1):
        session.add(
            Page(
                document_id=document_id,
                page_no=index,
                text_content=text,
                source=PageSource.OCR,
                confidence=Decimal(str(confidence)) if confidence is not None else None,
            )
        )


def _clear_pages(session: Session, document_id: UUID) -> None:
    """Delete existing page rows so single-content extraction is idempotent."""
    for page in session.scalars(select(Page).where(Page.document_id == document_id)):
        session.delete(page)


@celery_app.task(name="app.workers.tasks.finalize", bind=True, **_RETRY_POLICY)
def finalize(self: object, document_id: str) -> str:
    """Mark processing done once every page holds text; idempotent under races."""
    del self
    doc_uuid = UUID(document_id)
    session = _open_session()
    try:
        document = session.get(Document, doc_uuid)
        if document is None:
            return "missing"
        if document.status in (
            DocumentStatus.OK,
            DocumentStatus.FAILED,
            DocumentStatus.NEEDS_REVIEW,
        ):
            return "already-terminal"

        done = _count_pages_done(session, doc_uuid)
        total = document.page_count or done
        if done < total:
            return f"pending:{done}/{total}"

        document.status = DocumentStatus.OK
        document.failure_reason = None
        _record_event(session, doc_uuid, _DONE_EVENT, f"{done} pages")
        session.commit()
        return "ok"
    finally:
        session.close()


def _count_pages_done(session: Session, document_id: UUID) -> int:
    """Count pages whose text extraction finished."""
    return (
        session.scalar(
            select(func.count())
            .select_from(Page)
            .where(Page.document_id == document_id, Page.text_content.is_not(None))
        )
        or 0
    )


def _maybe_finalize(session: Session, document_id: UUID) -> None:
    """Enqueue finalize when the last outstanding page completes (idempotent)."""
    document = session.get(Document, document_id)
    if document is None:
        return
    if document.status == DocumentStatus.FAILED:
        return
    done = _count_pages_done(session, document_id)
    total = document.page_count or 1
    if done >= total:
        finalize.apply_async(args=[str(document_id)])
