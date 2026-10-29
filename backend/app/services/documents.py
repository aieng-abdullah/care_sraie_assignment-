"""Upload ingestion: size caps, magic-byte checks, dedupe, storage, DB row."""

from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Document
from app.repositories import documents as documents_repo
from app.services.file_validation import (
    XLSX,
    UnsupportedFileTypeError,
    detect_content_type,
    sanitize_filename,
    verify_xlsx_archive,
)

logger = logging.getLogger(__name__)

_CHUNK_BYTES = 1024 * 1024
_HEAD_PROBE_BYTES = 65536


class FileTooLargeError(ValueError):
    """Raised when the upload exceeds MAX_UPLOAD_MB."""


@dataclass
class IngestOutcome:
    """Result of ingesting one file: the stored document plus duplicate flag."""

    document: Document
    duplicate: bool


def ingest_upload(
    session: Session,
    settings: Settings,
    *,
    filename: str,
    stream: BinaryIO,
) -> IngestOutcome:
    """Validate, store, and record one uploaded file; caller commits the session.

    Raises FileTooLargeError or UnsupportedFileTypeError before anything persists.
    Duplicate content (same sha256) returns the existing document instead.
    """
    display_name = sanitize_filename(filename)
    sha256, size, head = _hash_and_probe(stream, settings.max_upload_mb)

    if size == 0:
        raise UnsupportedFileTypeError("empty file")

    content_type = detect_content_type(display_name, head)

    existing = documents_repo.find_by_sha256(session, sha256)
    if existing is not None:
        return IngestOutcome(document=existing, duplicate=True)

    document_dir = settings.upload_dir / str(uuid.uuid4())
    document_dir.mkdir(parents=True, exist_ok=True)
    storage_path = document_dir / display_name
    _save_stream(stream, storage_path)

    if content_type == XLSX and not verify_xlsx_archive(str(storage_path)):
        shutil.rmtree(document_dir, ignore_errors=True)
        raise UnsupportedFileTypeError("file is not a valid xlsx workbook")

    document = documents_repo.create_document(
        session,
        filename=display_name,
        content_type=content_type,
        original_sha256=sha256,
        size_bytes=size,
        storage_path=str(storage_path),
    )
    session.flush()  # assign id before the event row
    documents_repo.add_event(
        session, document_id=document.id, event_type="uploaded", detail=content_type
    )
    try:
        session.commit()
    except IntegrityError:
        # Concurrent duplicate upload won the race; keep the stored file out.
        session.rollback()
        shutil.rmtree(document_dir, ignore_errors=True)
        winner = documents_repo.find_by_sha256(session, sha256)
        if winner is None:
            raise
        return IngestOutcome(document=winner, duplicate=True)

    logger.info(
        "document ingested",
        extra={"event": "document_uploaded", "document_id": str(document.id)},
    )
    return IngestOutcome(document=document, duplicate=False)


def _hash_and_probe(stream: BinaryIO, max_mb: int) -> tuple[str, int, bytes]:
    """Return (sha256, size, first 8 bytes), enforcing the size cap; rewinds stream."""
    max_bytes = max_mb * 1024 * 1024
    digest = hashlib.sha256()
    head = b""
    size = 0
    while True:
        chunk = stream.read(_CHUNK_BYTES)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise FileTooLargeError(f"file exceeds {max_mb} MB limit")
        digest.update(chunk)
        if len(head) < _HEAD_PROBE_BYTES:
            head = (head + chunk)[:_HEAD_PROBE_BYTES]
    stream.seek(0)
    return digest.hexdigest(), size, head


def _save_stream(stream: BinaryIO, storage_path: Path) -> None:
    """Write the rewound stream to the final storage path."""
    with open(storage_path, "wb") as out:
        shutil.copyfileobj(stream, out, length=_CHUNK_BYTES)
