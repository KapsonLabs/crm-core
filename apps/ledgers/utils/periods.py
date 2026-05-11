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
        queryset = queryset.filter(branch__isnull=True)
    else:
        queryset = queryset.filter(branch__isnull=True)
    period = queryset.first()
    if period is None:
        raise FiscalPeriodClosedError("No open fiscal period available for posting date.")
    return period


def ensure_date_in_open_period(posting_date: date, branch: UUID | None = None) -> FiscalPeriod:
    return get_open_period(posting_date=posting_date, branch=branch)
