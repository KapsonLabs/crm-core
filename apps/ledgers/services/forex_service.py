from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.services.helpers import create_and_post_journal, get_configured_account
from apps.ledgers.services.types import JournalLineInput
from apps.ledgers.utils.currency import convert_currency, get_exchange_rate, quantize_currency


def convert_to_base_currency(*, amount: Decimal, from_currency_code: str, rate_date: date) -> Decimal:
    rate = get_exchange_rate(
        from_currency_code=from_currency_code,
        to_currency_code=DEFAULT_CURRENCY,
        rate_date=rate_date,
    )
    return convert_currency(amount=amount, exchange_rate=rate, decimal_places=0)


def calculate_realized_forex_gain_loss(
    *,
    original_foreign_amount: Decimal,
    original_exchange_rate: Decimal,
    settlement_exchange_rate: Decimal,
) -> Decimal:
    original_base = quantize_currency(original_foreign_amount * original_exchange_rate, 0)
    settlement_base = quantize_currency(original_foreign_amount * settlement_exchange_rate, 0)
    return settlement_base - original_base


def calculate_unrealized_forex_gain_loss(
    *,
    foreign_balance: Decimal,
    carrying_exchange_rate: Decimal,
    closing_exchange_rate: Decimal,
) -> Decimal:
    carrying_base = quantize_currency(foreign_balance * carrying_exchange_rate, 0)
    closing_base = quantize_currency(foreign_balance * closing_exchange_rate, 0)
    return closing_base - carrying_base


def post_forex_adjustment(
    *,
    adjustment_id: str,
    posting_date: date,
    amount_base: Decimal,
    revaluation_account_id: UUID,
    branch: UUID | None,
    created_by_id: UUID | None,
    is_realized: bool,
) -> object | None:
    gain_account = get_configured_account(
        "forex_gain" if is_realized else "unrealized_forex_gain",
        branch,
    )
    loss_account = get_configured_account(
        "forex_loss" if is_realized else "unrealized_forex_loss",
        branch,
    )
    if amount_base > Decimal("0.00"):
        # Forex GAIN (IAS 21): the monetary item increased in base currency value.
        # DR  Revaluation account (e.g. AR — asset increases)
        # CR  Forex Gain (income)
        lines = [
            JournalLineInput(
                account_id=revaluation_account_id,
                debit_base=amount_base,
                debit_foreign=amount_base,
                currency_code=DEFAULT_CURRENCY,
            ),
            JournalLineInput(
                account_id=gain_account.id,
                credit_base=amount_base,
                credit_foreign=amount_base,
                currency_code=DEFAULT_CURRENCY,
            ),
        ]
    elif amount_base < Decimal("0.00"):
        # Forex LOSS (IAS 21): the monetary item decreased in base currency value.
        # DR  Forex Loss (expense)
        # CR  Revaluation account (e.g. AR — asset decreases)
        absolute_amount = abs(amount_base)
        lines = [
            JournalLineInput(
                account_id=loss_account.id,
                debit_base=absolute_amount,
                debit_foreign=absolute_amount,
                currency_code=DEFAULT_CURRENCY,
            ),
            JournalLineInput(
                account_id=revaluation_account_id,
                credit_base=absolute_amount,
                credit_foreign=absolute_amount,
                currency_code=DEFAULT_CURRENCY,
            ),
        ]
    else:
        return None
    return create_and_post_journal(
        reference=f"FX-{adjustment_id}",
        journal_type="realized_forex_adjustment" if is_realized else "unrealized_forex_adjustment",
        posting_date=posting_date,
        description=f"Forex adjustment {adjustment_id}",
        source_module="forex",
        source_id=adjustment_id,
        branch=branch,
        created_by_id=created_by_id,
        lines=lines,
        idempotency_key=f"forex-adjustment:{adjustment_id}",
        transaction_currency_code=DEFAULT_CURRENCY,
    )
