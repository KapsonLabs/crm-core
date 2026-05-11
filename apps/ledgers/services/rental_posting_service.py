from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account


@transaction.atomic
def post_rent_invoice(*, invoice_id: str, posting_date: date, amount: Decimal, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    receivable = get_configured_account("rental_receivables", branch)
    income = get_configured_account("rental_income", branch)
    return create_and_post_journal(
        reference=f"RINV-{invoice_id}",
        journal_type="rental_invoice",
        posting_date=posting_date,
        description=f"Rental invoice {invoice_id}",
        source_module="rental",
        source_id=invoice_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"rent-invoice:{invoice_id}",
        lines=build_two_line_entry(
            debit_account_id=receivable.id,
            credit_account_id=income.id,
            amount=amount,
            currency=currency,
            description=f"Rental invoice {invoice_id}",
            branch=branch,
        ),
    )


@transaction.atomic
def post_rent_payment(*, payment_id: str, posting_date: date, amount: Decimal, cash_account_id: UUID, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    receivable = get_configured_account("rental_receivables", branch)
    return create_and_post_journal(
        reference=f"RPAY-{payment_id}",
        journal_type="rental_payment",
        posting_date=posting_date,
        description=f"Rental payment {payment_id}",
        source_module="rental",
        source_id=payment_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"rent-payment:{payment_id}",
        lines=build_two_line_entry(
            debit_account_id=cash_account_id,
            credit_account_id=receivable.id,
            amount=amount,
            currency=currency,
            description=f"Rental payment {payment_id}",
            branch=branch,
        ),
    )


@transaction.atomic
def post_security_deposit(*, deposit_id: str, posting_date: date, amount: Decimal, cash_account_id: UUID, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    liability = get_configured_account("security_deposit_liability", branch)
    return create_and_post_journal(
        reference=f"RDEP-{deposit_id}",
        journal_type="security_deposit",
        posting_date=posting_date,
        description=f"Security deposit {deposit_id}",
        source_module="rental",
        source_id=deposit_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"security-deposit:{deposit_id}",
        lines=build_two_line_entry(
            debit_account_id=cash_account_id,
            credit_account_id=liability.id,
            amount=amount,
            currency=currency,
            description=f"Security deposit {deposit_id}",
            branch=branch,
        ),
    )


@transaction.atomic
def post_rent_accrual(*, accrual_id: str, posting_date: date, amount: Decimal, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX", deferred: bool = True):
    receivable = get_configured_account("rental_receivables", branch)
    income = get_configured_account("deferred_rental_income" if deferred else "rental_income", branch)
    return create_and_post_journal(
        reference=f"RACC-{accrual_id}",
        journal_type="rental_accrual",
        posting_date=posting_date,
        description=f"Rental accrual {accrual_id}",
        source_module="rental",
        source_id=accrual_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"rent-accrual:{accrual_id}",
        lines=build_two_line_entry(
            debit_account_id=receivable.id,
            credit_account_id=income.id,
            amount=amount,
            currency=currency,
            description=f"Rental accrual {accrual_id}",
            branch=branch,
        ),
    )
