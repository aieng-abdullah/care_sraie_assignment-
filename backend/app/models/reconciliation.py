"""Reconciliation ORM model (cross-document PDF/Excel verification results)."""

import uuid
from typing import Any
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ReconciliationStatus, ReconciliationCheckType


class Reconciliation(Base):
    """Result of comparing two documents (PDF-PDF or PDF-Excel)."""

    __tablename__ = "reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    left_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    right_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    check_type: Mapped[str] = mapped_column(String(32), default=ReconciliationCheckType.PDF_PDF)
    status: Mapped[str] = mapped_column(String(32), default=ReconciliationStatus.INCOMPLETE)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_reconciliations_left", "left_document_id"),
        Index("ix_reconciliations_right", "right_document_id"),
        Index(
            "uq_reconciliations_pair",
            "left_document_id",
            "right_document_id",
            "check_type",
            unique=True,
        ),
    )
