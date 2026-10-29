"""Initial schema: documents, pages, extractions, line_items, issues, corrections.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all core tables and indexes."""
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("original_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])

    op.create_table(
        "pages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("uq_pages_document_page", "pages", ["document_id", "page_no"], unique=True)

    op.create_table(
        "reconciliations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "left_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "right_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_reconciliations_left", "reconciliations", ["left_document_id"])
    op.create_index("ix_reconciliations_right", "reconciliations", ["right_document_id"])
    op.create_index(
        "uq_reconciliations_pair",
        "reconciliations",
        ["left_document_id", "right_document_id", "check_type"],
        unique=True,
    )

    op.create_table(
        "extractions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("invoice_number", sa.String(128), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("supplier_name", sa.String(512), nullable=True),
        sa.Column("customer_name", sa.String(512), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=True),
        sa.Column("tax", sa.Numeric(18, 4), nullable=True),
        sa.Column("total", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("field_meta", sa.JSON(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_extractions_invoice_number", "extractions", ["invoice_number"])
    op.create_index("ix_extractions_supplier_name", "extractions", ["supplier_name"])
    op.create_index("ix_extractions_invoice_date", "extractions", ["invoice_date"])

    op.create_table(
        "line_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "extraction_id",
            sa.Uuid(),
            sa.ForeignKey("extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=True),
    )
    op.create_index(
        "ix_line_items_extraction_position", "line_items", ["extraction_id", "position"]
    )

    op.create_table(
        "validation_issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_id",
            sa.Uuid(),
            sa.ForeignKey("reconciliations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_validation_issues_document", "validation_issues", ["document_id"])
    op.create_index("ix_validation_issues_code", "validation_issues", ["code"])
    op.create_index(
        "ix_validation_issues_unresolved",
        "validation_issues",
        ["document_id"],
        postgresql_where=sa.text("NOT resolved"),
    )

    op.create_table(
        "corrections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field", sa.String(64), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_corrections_document_created", "corrections", ["document_id", "created_at"])

    op.create_table(
        "processing_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_processing_events_document_created",
        "processing_events",
        ["document_id", "created_at"],
    )


def downgrade() -> None:
    """Drop every table created by upgrade (reverse order)."""
    op.drop_table("processing_events")
    op.drop_table("corrections")
    op.drop_table("validation_issues")
    op.drop_table("line_items")
    op.drop_table("extractions")
    op.drop_table("reconciliations")
    op.drop_table("pages")
    op.drop_table("documents")
