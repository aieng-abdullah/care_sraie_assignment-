"""Manual corrections: validate, apply, audit, and re-run validation rules.

A correction edits one header field of an existing extraction, appends an
export to the append-only corrections audit trail, then re-runs the shared
validation rules and refreshes the document status. Committed as a single
transaction (AGENTS: transactions on multi-step writes).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models import Document
from app.models.enums import DocumentStatus, IssueSeverity
from app.repositories import documents as documents_repo
from app.schemas.document import (
    CorrectionCreate,
    CorrectionResponse,
    ValidationIssueItem,
    correction_fields,
)
from app.services.results import ExtractionNotReadyError
from app.validation import rules

# Fields needing type-specific parsing of the incoming value string.
# Anything not listed here is treated as free text.
_MONEY_FIELDS = frozenset({"subtotal", "tax", "total"})
_DATE_FIELD = "invoice_date"
_CURRENCY_FIELD = "currency"

# Header fields a correction may target; anything else is rejected as 422.
ALLOWED_FIELDS = frozenset(correction_fields)

MONEY_QUANTUM = Decimal("0.01")


class InvalidCorrectionError(ValueError):
    """Raised when the field name is unknown or the new value fails checks."""


def _parse_field_value(field: str, new_value: str) -> str | Decimal | date | None:
    """Parse the raw request value to the type the extraction column expects.

    Raises InvalidCorrectionError on empty values for typed fields, malformed
    numbers/dates, or a non three-letter currency code.
    """
    value = new_value.strip()
    if field in _MONEY_FIELDS:
        try:
            return Decimal(value).quantize(MONEY_QUANTUM)
        except InvalidOperation as exc:
            raise InvalidCorrectionError(f"field {field} requires a decimal value") from exc
    if field == _DATE_FIELD:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise InvalidCorrectionError(
                f"field {field} requires an ISO date (YYYY-MM-DD)"
            ) from exc
    if field == _CURRENCY_FIELD:
        if len(value) != 3 or not value.isalpha():
            raise InvalidCorrectionError("field currency requires a 3-letter ISO code")
        return value.upper()
    return None if value == "" else value


def _format_old_value(extraction: object, field: str) -> str | None:
    """Render the previous column value as a string for the audit row."""
    old = getattr(extraction, field)
    if old is None:
        return None
    return str(old)


def apply_correction(
    session: Session,
    document: Document,
    payload: CorrectionCreate,
) -> CorrectionResponse:
    """Apply one validated correction, audit it, and re-run validation rules.

    Raises KeyError when the document is missing (route maps to 404),
    ExtractionNotReadyError when not yet extracted (409), and
    InvalidCorrectionError for unknown fields or malformed values (422).
    """
    extraction = documents_repo.get_extraction(session, document.id)
    if extraction is None:
        raise ExtractionNotReadyError(
            f"extraction not available (document status: {document.status})"
        )
    if payload.field not in ALLOWED_FIELDS:
        raise InvalidCorrectionError(
            f"unknown field {payload.field!r}; allowed: {', '.join(sorted(ALLOWED_FIELDS))}"
        )

    parsed = _parse_field_value(payload.field, payload.new_value)
    old_value = _format_old_value(extraction, payload.field)
    setattr(extraction, payload.field, parsed)

    documents_repo.add_correction(
        session,
        document_id=document.id,
        field=payload.field,
        old_value=old_value,
        new_value=payload.new_value.strip(),
        reason=payload.reason,
    )

    # Re-run rules from a clean slate: part issues may no longer apply.
    documents_repo.resolve_issues(session, document.id)

    issue_messages: list[tuple[str, str, str, dict[str, object] | None]] = []
    money_problem = rules.check_total_consistency(
        extraction.subtotal, extraction.tax, extraction.total
    )
    if money_problem is not None:
        issue_messages.append(
            ("total-mismatch", IssueSeverity.ERROR, money_problem, {"field": payload.field})
        )
    for required_field in sorted(
        {"invoice_number", "subtotal", "tax", "total", "currency"}
        & {f for f in ALLOWED_FIELDS if getattr(extraction, f) is None}
    ):
        issue_messages.append(
            (
                "missing-field",
                IssueSeverity.WARNING,
                f"field {required_field} has no value",
                {"field": required_field},
            )
        )
    for code, severity, message, context in issue_messages:
        documents_repo.add_issue(
            session,
            document_id=document.id,
            code=code,
            severity=severity,
            message=message,
            context=context,
        )

    if document.status in (DocumentStatus.OK, DocumentStatus.NEEDS_REVIEW):
        document.status = DocumentStatus.NEEDS_REVIEW if issue_messages else DocumentStatus.OK

    session.commit()
    return CorrectionResponse(
        document_id=document.id,
        field=payload.field,
        old_value=old_value,
        new_value=payload.new_value.strip(),
        reason=payload.reason,
        validation_issues=[
            ValidationIssueItem(code=code, severity=severity, message=message, context=context)
            for code, severity, message, context in issue_messages
        ],
    )
