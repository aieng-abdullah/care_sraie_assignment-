"""Content-type detection from magic bytes; client headers and names never trusted."""

from __future__ import annotations

import zipfile
from pathlib import Path

# Signatures (first bytes) for binary formats the assignment accepts.
_PDF_MAGIC = b"%PDF-"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_TIFF_LE_MAGIC = b"II*\x00"
_TIFF_BE_MAGIC = b"MM\x00*"
_XLS_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_MAGIC = b"PK\x03\x04"

# Canonical content types the system accepts.
PDF = "application/pdf"
JPEG = "image/jpeg"
PNG = "image/png"
TIFF = "image/tiff"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLS = "application/vnd.ms-excel"
CSV = "text/csv"

ALLOWED_TYPES = frozenset({PDF, JPEG, PNG, TIFF, XLSX, XLS, CSV})

_EXTENSIONS: dict[str, str] = {
    ".pdf": PDF,
    ".jpg": JPEG,
    ".jpeg": JPEG,
    ".png": PNG,
    ".tif": TIFF,
    ".tiff": TIFF,
    ".xlsx": XLSX,
    ".xls": XLS,
    ".csv": CSV,
}

_SNIFF_BYTES = 8
_CSV_SAMPLE_BYTES = 65536


class UnsupportedFileTypeError(ValueError):
    """Raised when file content does not match any accepted format."""


def extension_for(filename: str) -> str:
    """Return the lowercased suffix of the filename ('' when absent)."""
    return Path(filename).suffix.lower()


def detect_content_type(filename: str, head: bytes) -> str:
    """Return the content type derived from magic bytes (and extension for xlsx/csv).

    Zip-based .xlsx is accepted on magic+extension here; the caller must follow up
    with verify_xlsx_archive() on the saved server-side path before accepting it.
    Raises UnsupportedFileTypeError when content matches no accepted format.
    """
    ext = extension_for(filename)

    if head.startswith(_PDF_MAGIC):
        return PDF
    if head.startswith(_JPEG_MAGIC):
        return JPEG
    if head.startswith(_PNG_MAGIC):
        return PNG
    if head.startswith(_TIFF_LE_MAGIC) or head.startswith(_TIFF_BE_MAGIC):
        return TIFF
    if head.startswith(_XLS_OLE_MAGIC):
        return XLS
    if head.startswith(_ZIP_MAGIC) and ext == ".xlsx":
        return XLSX
    if ext == ".csv" and _looks_like_csv(head):
        return CSV

    raise UnsupportedFileTypeError("content does not match any accepted file format")


def verify_xlsx_archive(storage_path: str) -> bool:
    """Confirm a saved zip actually contains [Content_Types].xml (a real workbook)."""
    try:
        with zipfile.ZipFile(storage_path) as archive:
            return "[Content_Types].xml" in archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def _looks_like_csv(head: bytes) -> bool:
    """CSV has no magic bytes: require UTF-8(-BOM) decodability of a sample.

    Trims up to 4 trailing bytes first so a multibyte character split by the
    sample boundary does not reject an otherwise valid text file.
    """
    sample = head[:_CSV_SAMPLE_BYTES]
    if not sample:
        return False
    for trim in range(5):
        chunk = sample[: len(sample) - trim] if trim else sample
        try:
            chunk.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        return True
    return False


def sanitize_filename(filename: str) -> str:
    """Strip directories and dangerous characters; never trust a client path."""
    name = Path(filename.replace("\\", "/")).name
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in "._- ()").strip()
    cleaned = cleaned.lstrip(".")
    return cleaned[:512] or "upload"
