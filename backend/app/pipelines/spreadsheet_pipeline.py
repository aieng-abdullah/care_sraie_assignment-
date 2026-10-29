"""Spreadsheet pipeline: multi-sheet XLS/XLSX and CSV parsed into sheet texts."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.pipelines.errors import CorruptedDocumentError

logger = logging.getLogger(__name__)

_CSV_ENCODING = "utf-8-sig"
_MAX_CSV_BYTES = 50 * 1024 * 1024


@dataclass
class SheetExtract:
    """One sheet (or CSV) serialized to CSV text for storage in the pages table."""

    name: str
    text: str
    row_count: int


def extract_sheets(path: str, content_type: str) -> list[SheetExtract]:
    """Parse a workbook (all sheets) or CSV; raises CorruptedDocumentError on bad data.

    Memory note: pandas loads the whole file — acceptable under MAX_UPLOAD_MB cap.
    """
    try:
        if content_type == "text/csv":
            return _extract_csv(path)
        return _extract_excel(path)
    except CorruptedDocumentError:
        raise
    except Exception:
        logger.warning("spreadsheet parse failed", extra={"event": "sheet_parse_failed"})
        raise CorruptedDocumentError("spreadsheet file could not be parsed") from None


def _extract_excel(path: str) -> list[SheetExtract]:
    """Read every sheet of an XLS/XLSX workbook into CSV-style text."""
    sheets: list[SheetExtract] = []
    book = pd.read_excel(path, sheet_name=None, engine=None)  # dict[name, DataFrame]
    if not book:
        raise CorruptedDocumentError("workbook contains no sheets")
    for name, frame in book.items():
        sheets.append(SheetExtract(name=str(name), text=_frame_to_csv(frame), row_count=len(frame)))
    return sheets


def _extract_csv(path: str) -> list[SheetExtract]:
    """Read a CSV with encoding fallbacks; non-text or malformed files raise."""
    file_path = Path(path)
    if file_path.stat().st_size > _MAX_CSV_BYTES:
        raise CorruptedDocumentError("CSV file is too large to parse")
    try:
        frame = pd.read_csv(io.StringIO(file_path.read_text(encoding=_CSV_ENCODING)))
    except UnicodeDecodeError as exc:
        raise CorruptedDocumentError("CSV file is not valid UTF-8 text") from exc
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
        raise CorruptedDocumentError("CSV file is malformed") from None
    return [SheetExtract(name="csv", text=_frame_to_csv(frame), row_count=len(frame))]


def _frame_to_csv(frame: pd.DataFrame) -> str:
    """Serialize a DataFrame to CSV text without the pandas index column."""
    return str(frame.to_csv(index=False))
