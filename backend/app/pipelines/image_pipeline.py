"""Image pipeline: EXIF-correct load, preprocessing, OCR for JPG/PNG/TIFF."""

from __future__ import annotations

import logging

from app.pipelines.errors import CorruptedDocumentError
from app.pipelines.ocr_engine import OcrEngine, preprocess_for_ocr

logger = logging.getLogger(__name__)

_MIN_IMAGE_PIXELS = 16


def extract_image(path: str, ocr_engine: OcrEngine) -> tuple[str, float]:
    """OCR one image; returns (text, confidence 0-1).

    Raises CorruptedDocumentError for unreadable or absurdly small images.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise CorruptedDocumentError("image file is corrupt or unreadable") from None

    if image.width < _MIN_IMAGE_PIXELS or image.height < _MIN_IMAGE_PIXELS:
        raise CorruptedDocumentError("image is too small to process")

    try:
        result = ocr_engine.recognize(preprocess_for_ocr(image.convert("RGB")))
    except CorruptedDocumentError:
        raise
    except Exception:
        # OCR engine crashed (e.g. missing binary): fail the document, not the worker.
        logger.warning("image OCR failed", extra={"event": "image_ocr_failed"})
        raise CorruptedDocumentError("OCR failed for this image") from None
    return result.text, result.confidence
