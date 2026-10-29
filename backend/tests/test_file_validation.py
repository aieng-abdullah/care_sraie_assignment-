"""Tests for magic-byte detection, filename sanitization, and xlsx verification."""

import io
import zipfile
from pathlib import Path

import pytest

from app.services.file_validation import (
    CSV,
    JPEG,
    PDF,
    PNG,
    TIFF,
    XLS,
    XLSX,
    UnsupportedFileTypeError,
    detect_content_type,
    sanitize_filename,
    verify_xlsx_archive,
)

PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
TIFF_LE_BYTES = b"II*\x00"
TIFF_BE_BYTES = b"MM\x00*"
OLE_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 8
ZIP_BYTES = b"PK\x03\x04"


def _detect(name: str, head: bytes) -> str:
    """Shorthand for detect_content_type."""
    return detect_content_type(name, head)


def test_detects_pdf_regardless_of_name() -> None:
    """PDF magic wins even when the client lies about the extension."""
    assert _detect("report.pdf", PDF_BYTES) == PDF


def test_detects_jpeg_png_tiff() -> None:
    """Image formats resolve by their magic bytes."""
    assert _detect("a.jpg", JPEG_BYTES) == JPEG
    assert _detect("a.png", PNG_BYTES) == PNG
    assert _detect("a.tiff", TIFF_LE_BYTES) == TIFF
    assert _detect("a.tiff", TIFF_BE_BYTES) == TIFF


def test_detects_xls_by_ole_magic() -> None:
    """Legacy .xls is recognized by the OLE compound-file signature."""
    assert _detect("old.xls", OLE_BYTES) == XLS


def test_zip_with_xlsx_extension_accepted_magic_only() -> None:
    """Zip content plus .xlsx name passes detection; archive verified later."""
    assert _detect("book.xlsx", ZIP_BYTES) == XLSX


def test_zip_with_other_extension_rejected() -> None:
    """A zip named .pdf or .csv is not an accepted format."""
    with pytest.raises(UnsupportedFileTypeError):
        _detect("data.pdf", ZIP_BYTES)


def test_csv_requires_decodable_utf8() -> None:
    """CSV is accepted when the sample decodes as UTF-8; binary junk is rejected."""
    assert _detect("rows.csv", b"a,b,c\n1,2,3\n") == CSV
    with pytest.raises(UnsupportedFileTypeError):
        _detect("rows.csv", b"\xff\xfe\x00\x01binary\x80\x81")


def test_garbage_rejected() -> None:
    """Unrecognized bytes raise UnsupportedFileTypeError instead of guessing."""
    with pytest.raises(UnsupportedFileTypeError):
        _detect("mystery.bin", b"\x00\x01\x02\x03\x04\x05\x06\x07")


def test_sanitize_filename_strips_traversal_and_controls() -> None:
    """Path components and dangerous characters never reach storage paths."""
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\boot.ini") == "boot.ini"
    assert sanitize_filename("in;voice$!.pdf") == "invoice.pdf"


def test_sanitize_filename_never_returns_empty() -> None:
    """Hostile input degrades to a placeholder instead of an empty path."""
    assert sanitize_filename("....") == "upload"
    assert sanitize_filename("") == "upload"


def test_verify_xlsx_archive_accepts_real_workbook(tmp_path: Path) -> None:
    """A minimal zip containing [Content_Types].xml verifies as xlsx."""
    path = tmp_path / "ok.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    assert verify_xlsx_archive(str(path)) is True


def test_verify_xlsx_archive_rejects_plain_zip(tmp_path: Path) -> None:
    """A zip without workbook structure fails verification."""
    path = tmp_path / "fake.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("hello.txt", "hi")
    assert verify_xlsx_archive(str(path)) is False


def test_verify_xlsx_archive_rejects_non_zip(tmp_path: Path) -> None:
    """Non-zip bytes raise internally and return False, never crash the upload."""
    path = tmp_path / "broken.xlsx"
    path.write_bytes(io.BytesIO(PDF_BYTES).getvalue())
    assert verify_xlsx_archive(str(path)) is False
