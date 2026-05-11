from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import Sum

from apps.ledgers.models import Account, LedgerEntry


class ReportingRepository:
    @staticmethod
    def account_totals(as_of_date: date, branch: UUID | None = None) -> list[dict]:
        """Cumulative totals up to as_of_date — for balance sheet accounts."""
        queryset = LedgerEntry.objects.filter(date__lte=as_of_date).values(
            "account_id",
            "account__code",
            "account__name",
            "account__account_type",
            "account__category",
        )
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return list(
            queryset.annotate(
                debit_total=Sum("debit_base", default=Decimal("0.00")),
                credit_total=Sum("credit_base", default=Decimal("0.00")),
            )
        )

    @staticmethod
    def account_totals_for_period(
        start_date: date,
        end_date: date,
        branch: UUID | None = None,
    ) -> list[dict]:
        """Period-scoped totals — for income/expense accounts in P&L / income statement."""
        queryset = LedgerEntry.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
        ).values(
            "account_id",
            "account__code",
            "account__name",
            "account__account_type",
            "account__category",
        )
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return list(
            queryset.annotate(
                debit_total=Sum("debit_base", default=Decimal("0.00")),
                credit_total=Sum("credit_base", default=Decimal("0.00")),
            )
        )

    @staticmethod
    def accounts(branch: UUID | None = None):
        queryset = Account.objects.filter(is_active=True)
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by("code")
