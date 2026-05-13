from __future__ import annotations

from datetime import date
from uuid import UUID

from apps.ledgers.exceptions import FiscalPeriodClosedError
from apps.ledgers.models import FiscalPeriod


def get_open_period(posting_date: date, branch: UUID | None = None) -> FiscalPeriod:
    queryset = FiscalPeriod.objects.filter(
        start_date__lte=posting_date,
        end_date__gte=posting_date,
        is_closed=False,
    )
    if branch is not None:
        period = queryset.filter(branch=branch).first()
        if period:
            return period
        global_period = queryset.filter(branch__isnull=True).first()
        if global_period:
            return global_period
        raise FiscalPeriodClosedError(
            f"No open fiscal period found for {posting_date} on this branch. "
            "Please open or create a fiscal period that covers this date before posting."
        )
    period = queryset.filter(branch__isnull=True).first()
    if period is None:
        raise FiscalPeriodClosedError(
            f"No open fiscal period found for {posting_date}. "
            "Please open or create a fiscal period that covers this date before posting."
        )
    return period


def ensure_date_in_open_period(posting_date: date, branch: UUID | None = None) -> FiscalPeriod:
    return get_open_period(posting_date=posting_date, branch=branch)
