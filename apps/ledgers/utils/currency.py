from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.ledgers.constants import DEFAULT_CURRENCY, DEFAULT_EXCHANGE_RATE
from apps.ledgers.exceptions import PostingConfigurationError
from apps.ledgers.repositories.account_repository import AccountRepository


def quantize_currency(amount: Decimal, decimal_places: int = 2) -> Decimal:
    return amount.quantize(Decimal("1").scaleb(-decimal_places), rounding=ROUND_HALF_UP)


def get_exchange_rate(*, from_currency_code: str, to_currency_code: str = DEFAULT_CURRENCY, rate_date: date) -> Decimal:
    if from_currency_code == to_currency_code:
        return DEFAULT_EXCHANGE_RATE
    rate = AccountRepository.latest_exchange_rate(
        from_currency_code=from_currency_code,
        to_currency_code=to_currency_code,
        rate_date=rate_date,
    )
    if rate is None:
        raise PostingConfigurationError(
            f"No exchange rate found for {from_currency_code}/{to_currency_code} on or before {rate_date}."
        )
    return rate.rate


def convert_currency(*, amount: Decimal, exchange_rate: Decimal, decimal_places: int = 2) -> Decimal:
    return quantize_currency(amount * exchange_rate, decimal_places=decimal_places)


def convert_to_ugx(*, amount: Decimal, from_currency_code: str, rate_date: date) -> Decimal:
    rate = get_exchange_rate(
        from_currency_code=from_currency_code,
        to_currency_code=DEFAULT_CURRENCY,
        rate_date=rate_date,
    )
    return convert_currency(amount=amount, exchange_rate=rate, decimal_places=0 if DEFAULT_CURRENCY == "UGX" else 2)
