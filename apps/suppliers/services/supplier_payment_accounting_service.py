from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.services.helpers import get_configured_account
from apps.ledgers.services.journal_service import reverse_journal_entry
from apps.ledgers.services.payable_service import allocate_supplier_payment
from apps.ledgers.utils.currency import get_exchange_rate

logger = logging.getLogger(__name__)


@transaction.atomic
def post_supplier_payment(
    *,
    payment_id: str,
    supplier,
    amount: Decimal,
    payment_date: date,
    payment_method: str,
    branch_id: UUID | None,
    created_by_id: UUID | None,
    currency: str = DEFAULT_CURRENCY,
    invoice_date: date | None = None,
) -> object:
    cash_account = _resolve_cash_account(payment_method, branch_id)

    original_foreign_amount = None
    original_exchange_rate = None

    if currency != DEFAULT_CURRENCY and invoice_date is not None:
        original_foreign_amount = amount
        original_exchange_rate = get_exchange_rate(
            from_currency_code=currency,
            to_currency_code=DEFAULT_CURRENCY,
            rate_date=invoice_date,
        )

    return allocate_supplier_payment(
        payment_id=payment_id,
        posting_date=payment_date,
        amount=amount,
        cash_account_id=cash_account.id,
        supplier_id=str(supplier.id),
        branch=branch_id,
        created_by_id=created_by_id,
        currency=currency,
        original_foreign_amount=original_foreign_amount,
        original_exchange_rate=original_exchange_rate,
    )


PAYMENT_METHOD_ACCOUNT_MAP = {
    "cash": "cash_on_hand",
    "card": "cash_and_cash_equivalent_control",
    "mobile_money": "electronic_money_control",
    "bank_transfer": "cash_and_cash_equivalent_control",
    "cheque": "cash_and_cash_equivalent_control",
    "other": "cash_and_cash_equivalent_control",
}


def _resolve_cash_account(method: str, branch: UUID | None):
    account_key = PAYMENT_METHOD_ACCOUNT_MAP.get(method, "cash_and_cash_equivalent_control")
    return get_configured_account(account_key, branch)


@transaction.atomic
def reverse_supplier_payment(
    *,
    payment_id: str,
    reversal_date: date,
    created_by_id: UUID | None = None,
    reason: str = "",
) -> object:
    from apps.ledgers.repositories.journal_repository import JournalRepository

    journal = JournalRepository.find_existing(
        source_module="payables",
        source_id=payment_id,
        idempotency_key=f"supplier-payment:{payment_id}",
    )
    if not journal:
        raise ValueError(f"No posted journal found for supplier payment {payment_id}.")

    return reverse_journal_entry(
        journal_entry_id=journal.id,
        reversal_date=reversal_date,
        created_by_id=created_by_id,
        reason=reason or f"Reversal of supplier payment {payment_id}",
    )
