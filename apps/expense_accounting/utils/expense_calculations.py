from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from apps.expense_accounting.constants import TWO_DP, ZERO


def round_currency(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_DP)


def convert_to_base(amount: Decimal, exchange_rate: Decimal) -> Decimal:
    if exchange_rate <= ZERO:
        raise ValueError("Exchange rate must be positive.")
    return round_currency(amount * exchange_rate)


def add_months(source: date, months: int) -> date:
    month = source.month - 1 + months
    year = source.year + month // 12
    month = month % 12 + 1
    day = min(source.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def compute_monthly_amount(total: Decimal, months: int) -> Decimal:
    if months <= 0:
        raise ValueError("months must be positive.")
    return round_currency(total / Decimal(months))


def compute_last_amortization_amount(
    total: Decimal,
    monthly_amount: Decimal,
    months: int,
) -> Decimal:
    """Return total minus all prior months' amounts to absorb rounding."""
    return round_currency(total - monthly_amount * Decimal(months - 1))


def count_months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def split_inclusive_tax(gross_amount: Decimal, tax_rate: Decimal) -> tuple[Decimal, Decimal]:
    """Split a tax-inclusive gross amount into (net, tax).

    Returns (net_amount, tax_amount).
    """
    if tax_rate < ZERO or tax_rate >= Decimal("1"):
        raise ValueError("tax_rate must be in [0, 1).")
    net = round_currency(gross_amount / (1 + tax_rate))
    tax = round_currency(gross_amount - net)
    return net, tax


def split_exclusive_tax(net_amount: Decimal, tax_rate: Decimal) -> tuple[Decimal, Decimal]:
    """Compute tax on a net amount.

    Returns (net_amount, tax_amount).
    """
    tax = round_currency(net_amount * tax_rate)
    return net_amount, tax
