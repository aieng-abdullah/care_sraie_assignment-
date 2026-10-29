"""Document processing pipelines: PDF text/OCR, images, spreadsheets.

Pure library functions: open files, extract text, raise typed errors.
Celery wiring lives in app.workers; LLM extraction is a later milestone.
"""

from app.pipelines.errors import (
    CorruptedDocumentError,
    PageLimitExceededError,
    PipelineError,
)
from app.pipelines.image_pipeline import extract_image
from app.pipelines.ocr_engine import OcrEngine, OcrResult, get_ocr_engine
from app.pipelines.pdf_pipeline import PageExtract, extract_page, get_page_count
from app.pipelines.spreadsheet_pipeline import SheetExtract, extract_sheets

__all__ = [
    "CorruptedDocumentError",
    "OcrEngine",
    "OcrResult",
    "PageExtract",
    "PageLimitExceededError",
    "PipelineError",
    "SheetExtract",
    "extract_image",
    "extract_page",
    "extract_sheets",
    "get_ocr_engine",
    "get_page_count",
]
