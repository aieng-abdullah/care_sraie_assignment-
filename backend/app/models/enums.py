"""Status and type constants shared by models, services, and API schemas."""

from enum import StrEnum


class DocumentStatus(StrEnum):
    """Lifecycle states of a document; terminal states are ok/needs_review/failed."""

    QUEUED = "queued"
    PROCESSING = "processing"
    OK = "ok"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class PageSource(StrEnum):
    """Where page text came from: text layer, OCR, or not yet processed."""

    TEXT_LAYER = "text_layer"
    OCR = "ocr"


class IssueSeverity(StrEnum):
    """Severity of a validation issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReconciliationCheckType(StrEnum):
    """Kinds of cross-document verification."""

    PDF_PDF = "pdf_pdf"
    PDF_EXCEL = "pdf_excel"


class ReconciliationStatus(StrEnum):
    """Outcome of a cross-document verification."""

    MATCH = "match"
    MISMATCH = "mismatch"
    INCOMPLETE = "incomplete"
