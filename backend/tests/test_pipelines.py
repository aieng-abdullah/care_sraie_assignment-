"""Tests for PDF, image, and spreadsheet pipelines (real files, mocked OCR)."""

from pathlib import Path

import pymupdf
import pytest

from app.models.enums import PageSource
from app.pipelines import (
    CorruptedDocumentError,
    OcrResult,
    extract_image,
    extract_page,
    extract_sheets,
    get_page_count,
)

_LONG_TEXT = (
    "Invoice INV-001 for widgets and services rendered during the billing period. "
    "Subtotal 100.00, tax 10.00, total 110.00. Thank you for your business. "
)


class FakeOcrEngine:
    """OCR double: returns fixed text and confidence without any binary."""

    def __init__(self, text: str = "OCR TEXT", confidence: float = 0.9) -> None:
        """Configure what this fake recognizes."""
        self._result = OcrResult(text=text, confidence=confidence)
        self.calls = 0

    def recognize(self, image: "object") -> OcrResult:
        """Count the call and return the canned result."""
        self.calls += 1
        return self._result


def _make_text_pdf(path: Path, pages: int = 1) -> Path:
    """Write a real PDF with a usable text layer on every page."""
    document = pymupdf.open()
    for _ in range(pages):
        page = document.new_page()
        page.insert_text((72, 72), _LONG_TEXT, fontsize=11)
    document.save(path)
    document.close()
    return path


def _make_blank_pdf(path: Path) -> Path:
    """Write a real scan-like PDF with no text layer."""
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()
    return path


def test_page_count_of_real_pdf(tmp_path: Path) -> None:
    """Page count comes from the file, not the client."""
    assert get_page_count(str(_make_text_pdf(tmp_path / "a.pdf", pages=3))) == 3


def test_corrupted_pdf_raises(tmp_path: Path) -> None:
    """Garbage bytes fail as CorruptedDocumentError instead of crashing."""
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"definitely not a pdf")
    with pytest.raises(CorruptedDocumentError):
        get_page_count(str(path))


def test_text_layer_page_skips_ocr(tmp_path: Path) -> None:
    """Digital PDFs use the text layer; the OCR engine is never touched."""
    path = _make_text_pdf(tmp_path / "t.pdf")
    engine = FakeOcrEngine()
    extract = extract_page(str(path), 0, engine)
    assert extract.source == PageSource.TEXT_LAYER
    assert "Invoice INV-001" in extract.text
    assert extract.confidence is None
    assert engine.calls == 0


def test_scanned_page_falls_back_to_ocr(tmp_path: Path) -> None:
    """Pages without a text layer are rendered and OCR'd with confidence stored."""
    path = _make_blank_pdf(tmp_path / "scan.pdf")
    engine = FakeOcrEngine(text="SCANNED INVOICE 42", confidence=0.87)
    extract = extract_page(str(path), 0, engine)
    assert extract.source == PageSource.OCR
    assert extract.text == "SCANNED INVOICE 42"
    assert extract.confidence == 0.87
    assert engine.calls == 1


def test_page_out_of_range_raises(tmp_path: Path) -> None:
    """Asking for a nonexistent page is a document error, not an IndexError leak."""
    path = _make_text_pdf(tmp_path / "t.pdf")
    with pytest.raises(CorruptedDocumentError):
        extract_page(str(path), 5, FakeOcrEngine())


def test_image_ocr_returns_text_and_confidence(tmp_path: Path) -> None:
    """PNG loads, gets preprocessed, and returns OCR text with confidence."""
    from PIL import Image

    path = tmp_path / "img.png"
    Image.new("RGB", (200, 100), "white").save(path)
    engine = FakeOcrEngine(text="PO NUMBER 7781", confidence=0.72)
    text, confidence = extract_image(str(path), engine)
    assert text == "PO NUMBER 7781"
    assert confidence == 0.72
    assert engine.calls == 1


def test_corrupt_image_raises(tmp_path: Path) -> None:
    """A .png name with garbage content fails gracefully."""
    path = tmp_path / "broken.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nnot-really-a-png")
    with pytest.raises(CorruptedDocumentError):
        extract_image(str(path), FakeOcrEngine())


def test_tiny_image_rejected(tmp_path: Path) -> None:
    """Absurdly small images cannot contain text and are rejected."""
    from PIL import Image

    path = tmp_path / "dot.png"
    Image.new("RGB", (4, 4), "white").save(path)
    with pytest.raises(CorruptedDocumentError):
        extract_image(str(path), FakeOcrEngine())


def test_xlsx_multi_sheet_extraction(tmp_path: Path) -> None:
    """Every sheet becomes CSV text in workbook order."""
    from openpyxl import Workbook

    path = tmp_path / "book.xlsx"
    book = Workbook()
    first = book.active
    first.title = "Invoices"
    first.append(["invoice_no", "total"])
    first.append(["INV-1", 100])
    second = book.create_sheet("Lines")
    second.append(["description", "amount"])
    second.append(["Widget", 100])
    book.save(path)

    sheets = extract_sheets(
        str(path),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert [sheet.name for sheet in sheets] == ["Invoices", "Lines"]
    assert "INV-1" in sheets[0].text
    assert "Widget" in sheets[1].text
    assert sheets[0].row_count == 1


def test_csv_extraction(tmp_path: Path) -> None:
    """CSV parses to a single sheet with rows preserved."""
    path = tmp_path / "rows.csv"
    path.write_text("invoice_no,total\nINV-9,250\n", encoding="utf-8")
    sheets = extract_sheets(str(path), "text/csv")
    assert len(sheets) == 1
    assert sheets[0].row_count == 1
    assert "INV-9" in sheets[0].text


def test_corrupt_xlsx_raises(tmp_path: Path) -> None:
    """Zip-with-xlsx-name that is not a workbook fails as corrupted."""
    path = tmp_path / "fake.xlsx"
    path.write_bytes(b"PK\x03\x04 definitely not a zip central directory")
    with pytest.raises(CorruptedDocumentError):
        extract_sheets(
            str(path),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def test_binary_junk_csv_raises(tmp_path: Path) -> None:
    """CSV containing undecodable bytes is reported, not guessed."""
    path = tmp_path / "junk.csv"
    path.write_bytes(b"\xff\xfe\x00\x01\x02\x80\x81\x82")
    with pytest.raises(CorruptedDocumentError):
        extract_sheets(str(path), "text/csv")
