"""Swappable OCR engine abstraction; Tesseract implemented, others raise loudly."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import numpy as np
    from PIL import Image

logger = logging.getLogger(__name__)

_TESSERACT_CONF_EMPTY = -1


@dataclass
class OcrResult:
    """Recognized text plus mean word confidence scaled to 0-1."""

    text: str
    confidence: float


class OcrEngine(Protocol):
    """Interface every OCR backend must satisfy (swappable per AGENTS 6.2)."""

    def recognize(self, image: Image.Image) -> OcrResult:
        """Return recognized text and confidence for one preprocessed image."""
        ...


class TesseractOcrEngine:
    """Tesseract via pytesseract; confidence from word-level data."""

    def __init__(self, lang: str = "eng") -> None:
        """Use the given tesseract language pack (must exist on the host)."""
        self._lang = lang

    def recognize(self, image: Image.Image) -> OcrResult:
        """Run OCR and average the confidences of recognized words."""
        import pytesseract

        data = pytesseract.image_to_data(
            image, lang=self._lang, output_type=pytesseract.Output.DICT
        )
        words: list[str] = []
        confidences: list[int] = []
        for text, conf in zip(data["text"], data["conf"], strict=True):
            cleaned = str(text).strip()
            if not cleaned:
                continue
            words.append(cleaned)
            value = int(float(str(conf)))
            if value > _TESSERACT_CONF_EMPTY:
                confidences.append(value)
        mean_conf = sum(confidences) / len(confidences) / 100 if confidences else 0.0
        return OcrResult(text=" ".join(words), confidence=round(mean_conf, 4))


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Grayscale + Otsu threshold + light deskew so poor scans recognize better."""
    import cv2
    import numpy as np
    from PIL import Image

    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    angle = _estimate_skew(binary)
    if angle:
        rotated = _rotate(binary, angle)
        return Image.fromarray(rotated)
    return Image.fromarray(binary)


def _estimate_skew(binary: np.ndarray) -> float:
    """Return the dominant skew angle in degrees (-15..15), or 0.0 if unsure."""
    import cv2
    import numpy as np

    edges = cv2.Canny(binary, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=50, maxLineGap=10)
    if lines is None:
        return 0.0
    angles: list[float] = []
    # OpenCV 4.x returns (N,1,4); 5.x returns (N,4) — reshape to a flat segment list.
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        if x2 == x1:
            continue
        angles.append(float(np.degrees(np.arctan2(y2 - y1, x2 - x1))))
    if not angles:
        return 0.0
    median = float(np.median(angles))
    if abs(median) > 15.0:  # likely near-vertical table rules, not page skew
        return 0.0
    return median


def _rotate(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate a numpy image around its center by angle degrees."""
    import cv2

    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )


def get_ocr_engine(engine_name: str) -> OcrEngine:
    """Return the OCR engine for the configured name; unknown backends raise."""
    if engine_name == "tesseract":
        return TesseractOcrEngine()
    raise NotImplementedError(
        f"OCR engine '{engine_name}' is not implemented; only 'tesseract' is available"
    )
