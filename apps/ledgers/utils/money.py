from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.ledgers.constants import DECIMAL_PLACES


def round_currency(amount: Decimal, places: Decimal = DECIMAL_PLACES) -> Decimal:
    return amount.quantize(places, rounding=ROUND_HALF_UP)


def convert_currency(amount: Decimal, exchange_rate: Decimal) -> Decimal:
    return round_currency(amount * exchange_rate)
