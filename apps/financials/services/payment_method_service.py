from __future__ import annotations

import logging

from django.db import transaction

from apps.ledgers.exceptions import PostingConfigurationError
from apps.ledgers.repositories.account_repository import AccountRepository

logger = logging.getLogger(__name__)

ACCOUNT_TYPE_CASH = "cash"
ACCOUNT_TYPE_BANK = "bank"
ACCOUNT_TYPE_CARD = "card"
ACCOUNT_TYPE_MOBILE_MONEY = "mobile_money"
ACCOUNT_TYPE_CHEQUE = "cheque"

# Code ranges reserved for dynamically created payment method GL accounts.
# Each payment method created via create_payment_method() occupies one slot.
ACCOUNT_TYPE_CODE_RANGE: dict[str, tuple[int, int] | None] = {
    ACCOUNT_TYPE_CASH: None,                  # reuses existing 1000 (Cash on Hand)
    ACCOUNT_TYPE_BANK: (1051, 1059),
    ACCOUNT_TYPE_CARD: (1061, 1069),
    ACCOUNT_TYPE_MOBILE_MONEY: (1071, 1079),
    ACCOUNT_TYPE_CHEQUE: (1081, 1089),
}

ACCOUNT_TYPE_CATEGORY = {
    ACCOUNT_TYPE_CASH: "cash_on_hand",
    ACCOUNT_TYPE_BANK: "bank_account",
    ACCOUNT_TYPE_CARD: "card_account",
    ACCOUNT_TYPE_MOBILE_MONEY: "mobile_money_account",
    ACCOUNT_TYPE_CHEQUE: "cheque_account",
}

# Parent GL account code that each payment-method type rolls up into.
# These parents are seeded as aggregation-only accounts (allows_manual_posting=False).
#   bank, card, cheque → 1001 (Cash and Cash Equivalent Control)
#   mobile_money       → 1010 (Electronic Money Control)
#   cash               → no parent (1000 is itself a leaf)
ACCOUNT_TYPE_PARENT_CODE = {
    ACCOUNT_TYPE_BANK: "1001",
    ACCOUNT_TYPE_CARD: "1001",
    ACCOUNT_TYPE_CHEQUE: "1001",
    ACCOUNT_TYPE_MOBILE_MONEY: "1010",
    ACCOUNT_TYPE_CASH: None,
}


def _next_payment_account_code(lo: int, hi: int) -> str:
    from apps.ledgers.models import Account

    existing = set(
        Account.objects.filter(code__gte=str(lo), code__lte=str(hi))
        .values_list("code", flat=True)
    )
    for n in range(lo, hi + 1):
        if str(n) not in existing:
            return str(n)
    raise PostingConfigurationError(
        f"Payment method GL account range {lo}–{hi} is exhausted. "
        "Contact your system administrator to expand the code range."
    )


@transaction.atomic
def create_payment_method(
    *,
    branch_id,
    name: str,
    code: str,
    account_type: str,
    description: str = "",
    is_active: bool = True,
):
    from apps.financials.models import PaymentMethod
    from apps.ledgers.models import Account

    if account_type not in ACCOUNT_TYPE_CODE_RANGE:
        raise ValueError(
            f"Unknown account_type '{account_type}'. "
            f"Choose from: {', '.join(ACCOUNT_TYPE_CODE_RANGE)}"
        )

    if account_type == ACCOUNT_TYPE_CASH:
        gl_account = AccountRepository.get_by_code("1000", branch=branch_id)
    else:
        lo, hi = ACCOUNT_TYPE_CODE_RANGE[account_type]
        next_code = _next_payment_account_code(lo, hi)
        base_currency = AccountRepository.get_base_currency()
        parent_code = ACCOUNT_TYPE_PARENT_CODE.get(account_type)
        parent_account = (
            AccountRepository.get_by_code(parent_code, branch=branch_id)
            if parent_code else None
        )
        gl_account = Account.objects.create(
            code=next_code,
            name=name,
            account_type="asset",
            category=ACCOUNT_TYPE_CATEGORY[account_type],
            currency=base_currency,
            branch=branch_id,
            parent=parent_account,
            allows_manual_posting=True,
            is_control_account=False,
        )
        logger.info(
            "Created GL account %s (%s) for payment method '%s'",
            next_code,
            name,
            code,
        )

    return PaymentMethod.objects.create(
        branch_id=branch_id,
        name=name,
        code=code,
        account_type=account_type,
        account=gl_account,
        description=description,
        is_active=is_active,
    )
