"""PDF pipeline: page count, text-layer extraction, OCR fallback for scans."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pymupdf
from PIL import Image

from app.models.enums import PageSource
from app.pipelines.errors import CorruptedDocumentError
from app.pipelines.ocr_engine import OcrEngine, preprocess_for_ocr

logger = logging.getLogger(__name__)

_RENDER_DPI = 200
_MIN_LAYER_CHARS = 40


@dataclass
class PageExtract:
    """Text extracted for one page: content, origin, and OCR confidence."""

    text: str
    source: PageSource
    confidence: float | None = None


def open_pdf(path: str) -> pymupdf.Document:
    """Open a PDF, raising CorruptedDocumentError for unreadable files."""
    try:
        document = pymupdf.open(path)
    except (pymupdf.FileDataError, RuntimeError, OSError) as exc:
        raise CorruptedDocumentError("file cannot be opened as a PDF") from exc
    if document.needs_pass:
        document.close()
        raise CorruptedDocumentError("PDF is password protected")
    return document


def get_page_count(path: str) -> int:
    """Return the number of pages; raises CorruptedDocumentError when unreadable."""
    document = open_pdf(path)
    try:
        return int(document.page_count)
    finally:
        document.close()


def extract_page(path: str, page_no: int, ocr_engine: OcrEngine) -> PageExtract:
    """Extract one page (0-based) via text layer, falling back to OCR on scans.

    Raises CorruptedDocumentError when the file or page cannot be read.
    """
    document = open_pdf(path)
    try:
        if page_no >= document.page_count:
            raise CorruptedDocumentError("page number out of range")
        page = document.load_page(page_no)
        layer_text = page.get_text("text").strip()
        if len(layer_text) >= _MIN_LAYER_CHARS:
            return PageExtract(text=layer_text, source=PageSource.TEXT_LAYER)

        pixmap = page.get_pixmap(dpi=_RENDER_DPI, alpha=False)
        image = _pixmap_to_image(pixmap)
        result = ocr_engine.recognize(preprocess_for_ocr(image))
        return PageExtract(text=result.text, source=PageSource.OCR, confidence=result.confidence)
    except CorruptedDocumentError:
        raise
    except Exception:
        # Corrupted internals must fail the document, not crash the worker (AGENTS 10).
        logger.warning("page extraction failed", extra={"event": "page_extract_failed"})
        raise CorruptedDocumentError("page could not be processed") from None
    finally:
        document.close()


def _pixmap_to_image(pixmap: pymupdf.Pixmap) -> Image.Image:
    """Convert a PyMuPDF pixmap to a PIL image without touching the disk."""
    mode = "RGB" if pixmap.n >= 3 else "L"
    return Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
