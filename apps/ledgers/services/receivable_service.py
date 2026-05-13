from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from apps.ledgers.exceptions import PostingConfigurationError
from apps.ledgers.models import JournalLine, SubLedgerAccount
from apps.ledgers.services.forex_service import (
    calculate_realized_forex_gain_loss,
    post_forex_adjustment,
)
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account


def _get_ar_subledger(customer_id: str, branch) -> SubLedgerAccount:
    subledger = SubLedgerAccount.objects.filter(
        entity_type="customer",
        entity_id=customer_id,
        ledger_purpose="Customer Receivable Ledger",
    ).first()
    if subledger is None:
        raise PostingConfigurationError(
            f"No AR subledger found for customer {customer_id}. "
            "Ensure the customer was created with accounting enabled."
        )
    return subledger


def create_receivable_invoice(*, invoice_id: str, posting_date: date, amount: Decimal, revenue_account_id: UUID, customer_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    receivable = get_configured_account("accounts_receivable", branch)
    ar_subledger = _get_ar_subledger(customer_id, branch)
    return create_and_post_journal(
        reference=f"AR-{invoice_id}",
        journal_type="receivable_invoice",
        posting_date=posting_date,
        description=f"Customer invoice {invoice_id}",
        source_module="receivables",
        source_id=invoice_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"receivable-invoice:{invoice_id}",
        lines=build_two_line_entry(
            debit_account_id=receivable.id,
            credit_account_id=revenue_account_id,
            amount=amount,
            currency=currency,
            description=f"Customer invoice {invoice_id}",
            branch=branch,
            party_type="customer",
            party_id=customer_id,
            rate_date=posting_date,
            debit_subledger_account_id=ar_subledger.id,
        ),
        transaction_currency_code=currency,
    )


def allocate_customer_payment(*, payment_id: str, posting_date: date, amount: Decimal, cash_account_id: UUID, customer_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX", original_foreign_amount: Decimal | None = None, original_exchange_rate: Decimal | None = None, receivable_account_id: UUID | None = None):
    receivable = get_configured_account("accounts_receivable", branch)
    if receivable_account_id is None:
        receivable_account_id = receivable.id
    ar_subledger = _get_ar_subledger(customer_id, branch)
    journal = create_and_post_journal(
        reference=f"ARPAY-{payment_id}",
        journal_type="receivable_payment",
        posting_date=posting_date,
        description=f"Customer payment {payment_id}",
        source_module="receivables",
        source_id=payment_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"receivable-payment:{payment_id}",
        lines=build_two_line_entry(
            debit_account_id=cash_account_id,
            credit_account_id=receivable_account_id,
            amount=amount,
            currency=currency,
            description=f"Customer payment {payment_id}",
            branch=branch,
            party_type="customer",
            party_id=customer_id,
            rate_date=posting_date,
            credit_subledger_account_id=ar_subledger.id,
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
                adjustment_id=f"receivable:{payment_id}",
                posting_date=posting_date,
                amount_base=difference,
                revaluation_account_id=receivable_account_id,
                branch=branch,
                created_by_id=created_by_id,
                is_realized=True,
            )  # amount_base == 0 returns None, handled upstream
    return journal


def calculate_customer_aging(*, as_of_date: date, branch: UUID | None = None) -> dict[str, Decimal]:
    buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    lines = JournalLine.objects.filter(
        journal_entry__status="posted",
        party_type="customer",
        branch=branch,
        journal_entry__date__lte=as_of_date,
    ).select_related("journal_entry")
    for line in lines:
        # Use UGX base amounts — all reporting is in UGX regardless of transaction currency.
        outstanding = line.debit_base - line.credit_base
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


def post_bad_debt(*, debt_id: str, posting_date: date, amount: Decimal, customer_id: str, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    expense = get_configured_account("bad_debt_expense", branch)
    allowance = get_configured_account("allowance_for_doubtful_accounts", branch)
    return create_and_post_journal(
        reference=f"BD-{debt_id}",
        journal_type="bad_debt",
        posting_date=posting_date,
        description=f"Bad debt provision {debt_id}",
        source_module="receivables",
        source_id=debt_id,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"bad-debt:{debt_id}",
        lines=build_two_line_entry(
            debit_account_id=expense.id,
            credit_account_id=allowance.id,
            amount=amount,
            currency=currency,
            description=f"Bad debt provision {debt_id}",
            branch=branch,
            party_type="customer",
            party_id=customer_id,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )
