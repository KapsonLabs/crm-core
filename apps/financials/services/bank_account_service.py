from __future__ import annotations

import logging
import re

from django.db import transaction

logger = logging.getLogger(__name__)


@transaction.atomic
def create_bank_account(
    *,
    branch_id,
    bank_name: str,
    account_name: str,
    account_number: str,
    currency: str = "UGX",
):
    from apps.financials.models import BankAccount
    from .payment_method_service import create_payment_method

    slug = re.sub(r"[^a-z0-9]+", "_", bank_name.lower()).strip("_")
    last4 = account_number[-4:] if len(account_number) >= 4 else account_number
    pm_code = f"{slug}_{last4}"[:50]
    display_name = f"{bank_name} — {account_name}"

    payment_method = create_payment_method(
        branch_id=branch_id,
        name=display_name,
        code=pm_code,
        account_type="bank",
        description=f"{bank_name}, {account_name}",
    )

    bank = BankAccount.objects.create(
        branch_id=branch_id,
        bank_name=bank_name,
        account_name=account_name,
        account_number=account_number,
        currency=currency,
        payment_method=payment_method,
    )
    logger.info("Created bank account %s (GL %s)", bank.id, payment_method.account.code)
    return bank
