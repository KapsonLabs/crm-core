from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import Sum

from apps.ledgers.models import Account, LedgerEntry
from apps.ledgers.repositories.journal_repository import JournalRepository


def calculate_account_balance(
    account: Account,
    as_of_date: date | None = None,
    branch: UUID | None = None,
) -> Decimal:
    queryset = LedgerEntry.objects.filter(account=account)
    if as_of_date is not None:
        queryset = queryset.filter(date__lte=as_of_date)
    if branch is not None:
        queryset = queryset.filter(branch=branch)
    totals = queryset.aggregate(
        debit_total=Sum("debit_base", default=Decimal("0.00")),
        credit_total=Sum("credit_base", default=Decimal("0.00")),
    )
    if account.normal_balance == "debit":
        return totals["debit_total"] - totals["credit_total"]
    return totals["credit_total"] - totals["debit_total"]


def calculate_trial_balance(as_of_date: date, branch: UUID | None = None) -> dict[str, Decimal]:
    queryset = LedgerEntry.objects.filter(date__lte=as_of_date)
    if branch is not None:
        queryset = queryset.filter(branch=branch)
    totals = queryset.aggregate(
        total_debits=Sum("debit_base", default=Decimal("0.00")),
        total_credits=Sum("credit_base", default=Decimal("0.00")),
    )
    return {
        "total_debits": totals["total_debits"],
        "total_credits": totals["total_credits"],
        "difference": totals["total_debits"] - totals["total_credits"],
    }


def generate_general_ledger(
    *,
    account_id: UUID,
    branch: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[LedgerEntry]:
    queryset = JournalRepository.ledger_for_account(account_id=account_id, branch=branch)
    if start_date is not None:
        queryset = queryset.filter(date__gte=start_date)
    if end_date is not None:
        queryset = queryset.filter(date__lte=end_date)
    return list(queryset)
