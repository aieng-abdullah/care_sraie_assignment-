"""Typed errors raised by processing pipelines; workers map them to document failure."""


class PipelineError(Exception):
    """Base class for document processing failures (message is safe for users)."""


class CorruptedDocumentError(PipelineError):
    """File cannot be opened or parsed as its content type claims."""


class PageLimitExceededError(PipelineError):
    """PDF has more pages than MAX_PDF_PAGES allows (NFR hard cap)."""
