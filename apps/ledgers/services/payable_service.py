from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from apps.ledgers.models import JournalLine
from apps.ledgers.services.forex_service import (
    calculate_realized_forex_gain_loss,
    post_forex_adjustment,
)
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account


def create_supplier_invoice(*, invoice_id: str, posting_date: date, amount: Decimal, expense_account_id: UUID, supplier_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    payable = get_configured_account("accounts_payable", branch)
    return create_and_post_journal(
        reference=f"AP-{invoice_id}",
        journal_type="supplier_invoice",
        posting_date=posting_date,
        description=f"Supplier invoice {invoice_id}",
        source_module="payables",
        source_id=invoice_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"supplier-invoice:{invoice_id}",
        lines=build_two_line_entry(
            debit_account_id=expense_account_id,
            credit_account_id=payable.id,
            amount=amount,
            currency=currency,
            description=f"Supplier invoice {invoice_id}",
            branch=branch,
            party_type="supplier",
            party_id=supplier_id,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )


def allocate_supplier_payment(*, payment_id: str, posting_date: date, amount: Decimal, cash_account_id: UUID, supplier_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX", original_foreign_amount: Decimal | None = None, original_exchange_rate: Decimal | None = None, payable_account_id: UUID | None = None):
    payable = get_configured_account("accounts_payable", branch)
    if payable_account_id is None:
        payable_account_id = payable.id
    journal = create_and_post_journal(
        reference=f"APPAY-{payment_id}",
        journal_type="supplier_payment",
        posting_date=posting_date,
        description=f"Supplier payment {payment_id}",
        source_module="payables",
        source_id=payment_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"supplier-payment:{payment_id}",
        lines=build_two_line_entry(
            debit_account_id=payable_account_id,
            credit_account_id=cash_account_id,
            amount=amount,
            currency=currency,
            description=f"Supplier payment {payment_id}",
            branch=branch,
            party_type="supplier",
            party_id=supplier_id,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )
    if currency != "UGX" and original_foreign_amount is not None and original_exchange_rate is not None:
        from apps.ledgers.utils.currency import get_exchange_rate

        settlement_rate = get_exchange_rate(
            from_currency_code=currency,
            to_currency_code="UGX",
            rate_date=posting_date,
        )
        difference = calculate_realized_forex_gain_loss(
            original_foreign_amount=original_foreign_amount,
            original_exchange_rate=original_exchange_rate,
            settlement_exchange_rate=settlement_rate,
        )
        if difference != Decimal("0.00"):
            post_forex_adjustment(
                adjustment_id=f"payable:{payment_id}",
                posting_date=posting_date,
                amount_base=difference,
                revaluation_account_id=payable_account_id,
                branch=branch,
                created_by_id=created_by_id,
                is_realized=True,
            )
    return journal


def calculate_supplier_aging(*, as_of_date: date, branch: UUID | None = None) -> dict[str, Decimal]:
    buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    lines = JournalLine.objects.filter(
        journal_entry__status="posted",
        party_type="supplier",
        branch=branch,
        journal_entry__date__lte=as_of_date,
    ).select_related("journal_entry")
    for line in lines:
        # Use UGX base amounts — all reporting is in UGX regardless of transaction currency.
        outstanding = line.credit_base - line.debit_base
        if outstanding == Decimal("0.00"):
            continue
        age = (as_of_date - line.journal_entry.date).days
        if age <= 30:
            buckets["0_30"] += outstanding
        elif age <= 60:
            buckets["31_60"] += outstanding
        elif age <= 90:
            buckets["61_90"] += outstanding
        else:
            buckets["90_plus"] += outstanding
    return dict(buckets)


def post_expense_accrual(*, accrual_id: str, posting_date: date, amount: Decimal, expense_account_id: UUID, supplier_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    accrued_expense = get_configured_account("accrued_expenses", branch)
    return create_and_post_journal(
        reference=f"ACCR-{accrual_id}",
        journal_type="expense_accrual",
        posting_date=posting_date,
        description=f"Expense accrual {accrual_id}",
        source_module="payables",
        source_id=accrual_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"expense-accrual:{accrual_id}",
        lines=build_two_line_entry(
            debit_account_id=expense_account_id,
            credit_account_id=accrued_expense.id,
            amount=amount,
            currency=currency,
            description=f"Expense accrual {accrual_id}",
            branch=branch,
            party_type="supplier",
            party_id=supplier_id,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )
