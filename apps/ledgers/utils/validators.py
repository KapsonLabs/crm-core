from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from apps.ledgers.constants import ZERO
from apps.ledgers.exceptions import JournalBalanceError
from apps.ledgers.models import Account
from apps.ledgers.services.types import JournalLineInput


def validate_double_entry(lines: Iterable[JournalLineInput]) -> None:
    debit_total_base = ZERO
    credit_total_base = ZERO
    line_count = 0
    for line in lines:
        line_count += 1
        debit_total_base += line.debit_base
        credit_total_base += line.credit_base
    if line_count < 2 or debit_total_base != credit_total_base:
        raise JournalBalanceError(
            f"Journal is not balanced in UGX. Debits={debit_total_base} Credits={credit_total_base}"
        )


def validate_posting_period(period, posting_date: date) -> None:
    if period.start_date > posting_date or period.end_date < posting_date:
        raise JournalBalanceError("Posting date is outside the fiscal period.")
    if period.is_closed:
        raise JournalBalanceError("Fiscal period is closed.")


def validate_account_active(account: Account) -> None:
    if not account.is_active:
        raise JournalBalanceError(f"Account {account.code} is inactive.")


def validate_decimal_non_negative(amount: Decimal) -> None:
    if amount < ZERO:
        raise JournalBalanceError("Amounts must not be negative.")
