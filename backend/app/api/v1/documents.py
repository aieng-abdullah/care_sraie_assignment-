"""Document endpoints: upload (multi-file), paginated list, processing status."""

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models import Document
from app.repositories import documents as documents_repo
from app.schemas.document import (
    CorrectionCreate,
    CorrectionResponse,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentSummary,
    ExtractionResponse,
    UploadItem,
    UploadResponse,
)
from app.services import corrections as corrections_service
from app.services import documents as documents_service
from app.services import results as results_service
from app.services.file_validation import UnsupportedFileTypeError

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

logger = logging.getLogger(__name__)

_LIST_PAGE_SIZE_MAX = 100


def _rate_limit_uploads(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Apply the upload rate limit from settings (NFR: 429 under abuse)."""
    enforce_rate_limit(request, settings.rate_limit_uploads_per_minute)


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(_rate_limit_uploads),
) -> UploadResponse:
    """Ingest multiple files; each item reports accepted/duplicate/rejected."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no files provided")

    items: list[UploadItem] = []
    accepted = 0
    for upload in files:
        original_name = upload.filename or "upload"
        try:
            outcome = documents_service.ingest_upload(
                session,
                settings,
                filename=original_name,
                stream=upload.file,
            )
        except (UnsupportedFileTypeError, documents_service.FileTooLargeError) as exc:
            logger.warning(
                "upload rejected",
                extra={"event": "upload_rejected", "reason": str(exc)},
            )
            items.append(UploadItem(filename=original_name, error=str(exc)))
            continue
        accepted += 1
        items.append(
            UploadItem(
                filename=outcome.document.filename,
                document_id=outcome.document.id,
                content_type=outcome.document.content_type,
                duplicate=outcome.duplicate,
            )
        )

    if accepted == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "no file was accepted",
                "items": [item.model_dump(mode="json") for item in items],
            },
        )
    return UploadResponse(items=items)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    q: str | None = Query(default=None, max_length=256, description="filename contains"),
    doc_status: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=_LIST_PAGE_SIZE_MAX),
    session: Session = Depends(get_db),
) -> DocumentListResponse:
    """List documents newest-first with status/keyword filters and pagination."""
    rows, total = documents_repo.list_documents(
        session,
        status=doc_status,
        query=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return DocumentListResponse(
        items=[DocumentSummary.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def document_status(
    document_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> DocumentStatusResponse:
    """Return processing status and page progress for one document."""
    document: Document | None = documents_repo.get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    pages_done = documents_repo.count_pages_done(session, document_id)
    return DocumentStatusResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        pages_done=pages_done,
        pages_total=document.page_count,
        failure_reason=document.failure_reason,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/{document_id}/results", response_model=ExtractionResponse)
def document_results(
    document_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> ExtractionResponse:
    """Return one document's extraction, line items, and unresolved issues."""
    try:
        document = results_service.lookup_document(session, document_id)
        return results_service.get_results(session, document)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="document not found"
        ) from None
    except results_service.ExtractionNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.post(
    "/{document_id}/corrections",
    response_model=CorrectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_correction(
    document_id: uuid.UUID,
    payload: CorrectionCreate,
    session: Session = Depends(get_db),
) -> CorrectionResponse:
    """Apply a manual correction to one field, audit it, and re-validate."""
    try:
        document = results_service.lookup_document(session, document_id)
        return corrections_service.apply_correction(session, document, payload)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="document not found"
        ) from None
    except results_service.ExtractionNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except corrections_service.InvalidCorrectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
