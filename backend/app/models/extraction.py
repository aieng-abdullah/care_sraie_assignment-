"""Extraction and line-item ORM models (structured invoice results)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Extraction(Base):
    """Exactly one current extraction per document; per-field meta in field_meta."""

    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True
    )
    invoice_number: Mapped[str | None] = mapped_column(String(128))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    supplier_name: Mapped[str | None] = mapped_column(String(512))
    customer_name: Mapped[str | None] = mapped_column(String(512))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str | None] = mapped_column(String(32))
    field_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    line_items: Mapped[list[LineItem]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
        order_by="LineItem.position",
    )

    __table_args__ = (
        Index("ix_extractions_invoice_number", "invoice_number"),
        Index("ix_extractions_supplier_name", "supplier_name"),
        Index("ix_extractions_invoice_date", "invoice_date"),
    )


class LineItem(Base):
    """One invoice line; money columns are NUMERIC(18,4), never float."""

    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extractions.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))

    extraction: Mapped[Extraction] = relationship(back_populates="line_items")

    __table_args__ = (Index("ix_line_items_extraction_position", "extraction_id", "position"),)
