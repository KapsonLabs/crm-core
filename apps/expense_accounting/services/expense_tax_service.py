from __future__ import annotations

from decimal import Decimal

from apps.expense_accounting.constants import ZERO
from apps.expense_accounting.exceptions import ExpenseConfigurationError
from apps.expense_accounting.utils.expense_calculations import round_currency, split_exclusive_tax, split_inclusive_tax


def calculate_input_vat(*, net_amount: Decimal, vat_rate: Decimal) -> Decimal:
    """Return the VAT amount on a net (tax-exclusive) expense amount."""
    _, vat = split_exclusive_tax(net_amount, vat_rate)
    return vat


def calculate_withholding_tax(*, gross_amount: Decimal, wht_rate: Decimal) -> Decimal:
    """Return withholding tax deducted from the gross payable amount."""
    if wht_rate < ZERO or wht_rate > Decimal("1"):
        raise ExpenseConfigurationError("Withholding tax rate must be between 0 and 1.")
    return round_currency(gross_amount * wht_rate)


def split_tax_amounts(
    *,
    amount: Decimal,
    tax_rate: Decimal,
    tax_inclusive: bool = False,
) -> tuple[Decimal, Decimal]:
    """Return (net_amount, tax_amount) based on whether the amount is tax-inclusive.

    Args:
        amount: The expense amount (gross if inclusive, net if exclusive).
        tax_rate: Fractional rate, e.g. Decimal("0.18") for 18% VAT.
        tax_inclusive: If True the amount already includes tax.

    Returns:
        Tuple of (net_amount, tax_amount), both rounded to 2 dp.
    """
    if tax_rate == ZERO:
        return amount, ZERO
    if tax_inclusive:
        return split_inclusive_tax(amount, tax_rate)
    return split_exclusive_tax(amount, tax_rate)
