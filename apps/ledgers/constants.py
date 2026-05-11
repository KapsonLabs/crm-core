from __future__ import annotations

from decimal import Decimal


ZERO = Decimal("0.00")
DEFAULT_CURRENCY = "UGX"
DEFAULT_EXCHANGE_RATE = Decimal("1.000000")
DECIMAL_PLACES = Decimal("0.01")


class AccountTypes:
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


DEBIT_NORMAL_ACCOUNT_TYPES = {AccountTypes.ASSET, AccountTypes.EXPENSE}
