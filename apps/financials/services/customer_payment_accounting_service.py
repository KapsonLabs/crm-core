from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.services.helpers import get_configured_account
from apps.ledgers.services.journal_service import reverse_journal_entry
from apps.ledgers.services.receivable_service import allocate_customer_payment
from apps.ledgers.utils.currency import get_exchange_rate

logger = logging.getLogger(__name__)

PAYMENT_METHOD_ACCOUNT_MAP = {
    "cash": "cash_on_hand",
    "card": "cash_and_cash_equivalent_control",
    "mobile_money": "electronic_money_control",
    "bank_transfer": "cash_and_cash_equivalent_control",
    "other": "cash_and_cash_equivalent_control",
}


def _resolve_cash_account(method: str, branch: UUID | None):
    account_key = PAYMENT_METHOD_ACCOUNT_MAP.get(method, "cash_and_cash_equivalent_control")
    return get_configured_account(account_key, branch)


@transaction.atomic
def post_customer_payment(payment) -> object:
    invoice = payment.invoice
    customer = invoice.job.customer
    branch_id = invoice.branch_id
    currency = invoice.currency

    cash_account = _resolve_cash_account(payment.method, branch_id)

    original_foreign_amount = None
    original_exchange_rate = None

    if currency != DEFAULT_CURRENCY:
        original_foreign_amount = payment.amount
        original_exchange_rate = get_exchange_rate(
            from_currency_code=currency,
            to_currency_code=DEFAULT_CURRENCY,
            rate_date=invoice.issued_at,
        )

    posting_date = payment.paid_at
    if hasattr(posting_date, "date"):
        posting_date = posting_date.date()

    return allocate_customer_payment(
        payment_id=str(payment.id),
        posting_date=posting_date,
        amount=payment.amount,
        cash_account_id=cash_account.id,
        customer_id=str(customer.id),
        branch=branch_id,
        created_by_id=payment.recorded_by_id,
        currency=currency,
        original_foreign_amount=original_foreign_amount,
        original_exchange_rate=original_exchange_rate,
    )


@transaction.atomic
def reverse_customer_payment(
    payment,
    *,
    reversal_date: date,
    created_by_id: UUID | None = None,
    reason: str = "",
) -> object:
    from apps.ledgers.repositories.journal_repository import JournalRepository

    journal = JournalRepository.find_existing(
        source_module="receivables",
        source_id=str(payment.id),
        idempotency_key=f"receivable-payment:{payment.id}",
    )
    if not journal:
        raise ValueError(f"No posted journal found for payment {payment.id}.")

    return reverse_journal_entry(
        journal_entry_id=journal.id,
        reversal_date=reversal_date,
        created_by_id=created_by_id,
        reason=reason or f"Reversal of customer payment {payment.id}",
    )
