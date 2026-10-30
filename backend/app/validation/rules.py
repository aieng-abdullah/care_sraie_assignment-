"""Validation rules that check extracted invoice totals and required fields.

Shared by the extraction pipeline and the corrections endpoint: the same rules
run after any manual edit so corrected values are validated identically.
"""

from __future__ import annotations

from decimal import Decimal

# Totals that must satisfy subtotal + tax = total (money is Decimal, AGENTS §2.9).
ROUNDING = Decimal("0.01")


def check_total_consistency(
    subtotal: Decimal | None,
    tax: Decimal | None,
    total: Decimal | None,
) -> str | None:
    """Return an error message when subtotal + tax != total, else None."""
    if subtotal is None or tax is None or total is None:
        return "subtotal+tax+total must all be present to verify the amount"
    expected = (subtotal + tax).quantize(ROUNDING)
    if expected != total.quantize(ROUNDING):
        return f"subtotal {subtotal} + tax {tax} does not equal total {total}"
    return None
