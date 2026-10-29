"""Tests for OCR engine factory, preprocessing, and the tesseract adapter."""

from pathlib import Path

import pytest
from PIL import Image

from app.pipelines.ocr_engine import (
    TesseractOcrEngine,
    get_ocr_engine,
    preprocess_for_ocr,
)


def test_factory_returns_tesseract() -> None:
    """Configured 'tesseract' resolves to the implemented engine."""
    assert isinstance(get_ocr_engine("tesseract"), TesseractOcrEngine)


def test_factory_rejects_unimplemented_backend() -> None:
    """Unknown backends raise loudly instead of silently degrading (AGENTS 6.2)."""
    with pytest.raises(NotImplementedError, match="not implemented"):
        get_ocr_engine("paddle")


def test_preprocess_grayscales_and_keeps_size() -> None:
    """Output stays single-channel at the input dimensions (OCR-ready)."""
    image = Image.new("RGB", (120, 80), "white")
    result = preprocess_for_ocr(image)
    assert result.size == (120, 80)
    assert result.mode in ("L", "1")


def test_preprocess_handles_skewed_text_like_image() -> None:
    """A rotated line does not crash preprocessing (deskew path executes)."""
    from PIL import ImageDraw

    image = Image.new("RGB", (300, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.line((20, 150, 280, 40), fill="black", width=6)
    result = preprocess_for_ocr(image.rotate(8, fillcolor="white", expand=False))
    assert result.size == (300, 200)


def test_tesseract_recognize_parses_word_confidences(monkeypatch: pytest.MonkeyPatch) -> None:
    """pytesseract output is mapped to text plus mean confidence in 0-1."""
    import pytesseract

    fake = {
        "text": ["INV-42", "", "TOTAL", "10.00"],
        "conf": ["95", "-1", "80", "70"],
    }
    monkeypatch.setattr(pytesseract, "image_to_data", lambda *a, **k: fake)
    engine = TesseractOcrEngine()
    result = engine.recognize(Image.new("RGB", (100, 40), "white"))
    assert result.text == "INV-42 TOTAL 10.00"
    # engine rounds the mean word confidence to 4 decimal places
    assert result.confidence == pytest.approx(round((95 + 80 + 70) / 3 / 100, 4))


def test_tesseract_recognize_empty_image_zero_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No recognized words means empty text and zero confidence, not a crash."""
    import pytesseract

    monkeypatch.setattr(pytesseract, "image_to_data", lambda *a, **k: {"text": [], "conf": []})
    engine = TesseractOcrEngine()
    result = engine.recognize(Image.new("RGB", (50, 20), "white"))
    assert result.text == ""
    assert result.confidence == 0.0


def test_recognize_missing_tesseract_binary_fails_as_corrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing system binary surfaces as a document failure, not a crash."""
    import pytesseract

    from app.pipelines import image_pipeline

    def _no_binary(*args: object, **kwargs: object) -> object:
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_data", _no_binary)
    image_path = tmp_path / "x.png"
    Image.new("RGB", (64, 64), "white").save(image_path)

    from app.pipelines.errors import CorruptedDocumentError

    with pytest.raises(CorruptedDocumentError):
        image_pipeline.extract_image(str(image_path), TesseractOcrEngine())
