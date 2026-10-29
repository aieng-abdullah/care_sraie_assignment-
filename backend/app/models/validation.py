"""Validation-issue and correction ORM models (review/audit side of the schema)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import IssueSeverity


class ValidationIssue(Base):
    """A validation problem raised against a document or reconciliation."""

    __tablename__ = "validation_issues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    reconciliation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reconciliations.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default=IssueSeverity.WARNING)
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_validation_issues_document", "document_id"),
        Index("ix_validation_issues_code", "code"),
        Index(
            "ix_validation_issues_unresolved",
            "document_id",
            postgresql_where=text("NOT resolved"),
            sqlite_where=text("NOT resolved"),
        ),
    )


class Correction(Base):
    """Append-only audit trail for manual edits; never updated or deleted."""

    __tablename__ = "corrections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    field: Mapped[str] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_corrections_document_created", "document_id", "created_at"),)
