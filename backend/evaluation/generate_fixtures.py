"""Fixture generator for upload/extraction testing of the DocIntel app.

Run from backend/: `uv run python evaluation/generate_fixtures.py`.
Produces one invoice fixture on each accepted format in evaluation/fixtures/:
PDF (text layer, no OCR needed), PNG (OCR path), XLSX and CSV. All fixtures
share the same invented-but-internally-consistent invoice values below, so
validation rules (subtotal + tax = total) see clean data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import fitz
from openpyxl import Workbook
from PIL import Image, ImageDraw


@dataclass(frozen=True)
class InvoiceFixture:
    """Ground-truth invoice values shared by every fixture file; totals must stay consistent."""

    invoice_number: str
    invoice_date: str
    supplier_name: str
    customer_name: str
    currency: str
    line_items: tuple[tuple[str, int, float, float], ...]  # (description, qty, unit, amount)
    subtotal: float
    tax: float
    total: float


GROUND_TRUTH = InvoiceFixture(
    invoice_number="INV-2026-0042",
    invoice_date="2026-10-15",
    supplier_name="Northwind Print Supplies",
    customer_name="Acme Labs",
    currency="USD",
    line_items=(
        ("Toner cartridge", 10, 14.00, 140.00),
        ("A4 paper case", 5, 20.00, 100.00),
    ),
    subtotal=240.00,
    tax=24.00,
    total=264.00,
)

FIXTURES_DIR = "evaluation/fixtures"

LINE_WIDTH = 1240
LINE_HEIGHT = 900
FONT_SIZE_PDF = 11
MARGIN_PDF = 72
FONT_SIZE_PNG = 28
LINE_SPACING_PNG = 42


def _header_lines() -> list[str]:
    """Return the invoice header as plain text lines shared by PDF and PNG."""
    qtys = [item[1] for item in GROUND_TRUTH.line_items]
    return [
        GROUND_TRUTH.supplier_name,
        f"Invoice {GROUND_TRUTH.invoice_number}",
        f"Date: {GROUND_TRUTH.invoice_date}",
        f"Bill to: {GROUND_TRUTH.customer_name}",
        f"Currency: {GROUND_TRUTH.currency}",
        f"Items: {len(GROUND_TRUTH.line_items)} (first quantity {qtys[0]})",
        f"Subtotal: {GROUND_TRUTH.subtotal:.2f}",
        f"Tax: {GROUND_TRUTH.tax:.2f}",
        f"Total: {GROUND_TRUTH.total:.2f} {GROUND_TRUTH.currency}",
    ]


def _line_lines() -> list[str]:
    """Return line items as transcribable text rows shared by PDF and PNG."""
    return [
        f"{desc}: Qty {qty} x {unit:.2f} = {amount:.2f}"
        for desc, qty, unit, amount in GROUND_TRUTH.line_items
    ]


def generate_text_pdf(out_path: str) -> None:
    """Create a one-page PDF with the invoice as a real text layer."""
    doc = fitz.open()
    page = doc.new_page()
    text = "\n".join(_header_lines() + _line_lines())
    page.insert_text((MARGIN_PDF, MARGIN_PDF), text, fontsize=FONT_SIZE_PDF)
    doc.save(out_path)
    doc.close()


def generate_ocr_png(out_path: str) -> None:
    """Render the invoice text into a PNG image, exercising the OCR pipeline."""
    img = Image.new("RGB", (LINE_WIDTH, LINE_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    y = 60
    for line in _header_lines() + _line_lines():
        draw.text((60, y), line, fill="black", font_size=FONT_SIZE_PNG)
        y += LINE_SPACING_PNG
    img.save(out_path)


def generate_xlsx(out_path: str) -> None:
    """Write an .xlsx workbook: header/values on 'Invoice', items on 'Line items'."""
    wb = Workbook()
    summary = wb.active
    assert summary is not None  # a new Workbook always has one active sheet
    summary.title = "Invoice"
    summary.append(["Field", "Value"])
    for field in ("invoice_number", "invoice_date", "supplier_name", "customer_name", "currency"):
        summary.append([field, getattr(GROUND_TRUTH, field)])
    for field in ("subtotal", "tax", "total"):
        summary.append([field, f"{getattr(GROUND_TRUTH, field):.2f}"])
    lines = wb.create_sheet("Line items")
    lines.append(["description", "quantity", "unit_price", "amount"])
    for row in GROUND_TRUTH.line_items:
        lines.append(list(row))
    wb.save(out_path)


def generate_csv(out_path: str) -> None:
    """Write a line-item CSV ending with subtotal/tax/total rows."""
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("description,quantity,unit_price,amount\n")
        for desc, qty, unit, amount in GROUND_TRUTH.line_items:
            fh.write(f"{desc},{qty},{unit:.2f},{amount:.2f}\n")
        fh.write(f"Subtotal,,,{GROUND_TRUTH.subtotal:.2f}\n")
        fh.write(f"Tax,,,{GROUND_TRUTH.tax:.2f}\n")
        fh.write(f"Total,,,{GROUND_TRUTH.total:.2f}\n")


def generate_all() -> None:
    """Generate every fixture and print each written path."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    for creator, filename in (
        (generate_text_pdf, "invoice_text.pdf"),
        (generate_ocr_png, "invoice_scan.png"),
        (generate_xlsx, "invoice.xlsx"),
        (generate_csv, "invoice.csv"),
    ):
        out = os.path.join(FIXTURES_DIR, filename)
        creator(out)
        print(f"wrote {out}")


if __name__ == "__main__":
    generate_all()
