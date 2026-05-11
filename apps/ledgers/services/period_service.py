from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.ledgers.exceptions import JournalBalanceError
from apps.ledgers.models import FiscalPeriod
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.utils.ledger import calculate_trial_balance


@transaction.atomic
def close_period(*, period_id: UUID, performed_by_id: UUID | None = None) -> FiscalPeriod:
    period = FiscalPeriod.objects.select_for_update().get(pk=period_id)
    if period.is_closed:
        return period
    trial_balance = calculate_trial_balance(as_of_date=period.end_date, branch=period.branch)
    if trial_balance["difference"] != Decimal("0.00"):
        raise JournalBalanceError(
            f"Trial balance must be zero before closing. Difference={trial_balance['difference']}"
        )
    period.is_closed = True
    period.closed_at = timezone.now()
    period.closed_by_id = performed_by_id
    period.save(update_fields=["is_closed", "closed_at", "closed_by", "updated_at"])
    emit_audit_log(
        event_type="period.closed",
        entity_type="FiscalPeriod",
        entity_id=period.id,
        branch=period.branch,
        performed_by_id=performed_by_id,
        payload={"period_name": period.name},
    )
    return period


def reopen_period(*, period_id: UUID, performed_by_id: UUID | None = None) -> FiscalPeriod:
    period = FiscalPeriod.objects.get(pk=period_id)
    period.is_closed = False
    period.closed_at = None
    period.closed_by_id = None
    period.save(update_fields=["is_closed", "closed_at", "closed_by", "updated_at"])
    emit_audit_log(
        event_type="period.reopened",
        entity_type="FiscalPeriod",
        entity_id=period.id,
        branch=period.branch,
        performed_by_id=performed_by_id,
        payload={"period_name": period.name},
    )
    return period
