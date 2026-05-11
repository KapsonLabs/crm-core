from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import RecurringAccrual
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal


def _next_run_date(accrual: RecurringAccrual):
    if accrual.frequency == RecurringAccrual.Frequency.MONTHLY:
        return accrual.next_run_date + timedelta(days=30)
    if accrual.frequency == RecurringAccrual.Frequency.QUARTERLY:
        return accrual.next_run_date + timedelta(days=90)
    return accrual.next_run_date + timedelta(days=365)


def generate_accrual_schedule(*, name: str, source_module: str, source_id: str, accrual_account_id, offset_account_id, amount: Decimal, start_date, end_date, frequency: str, branch: UUID | None, metadata: dict | None = None):
    return RecurringAccrual.objects.create(
        name=name,
        source_module=source_module,
        source_id=source_id,
        accrual_account_id=accrual_account_id,
        offset_account_id=offset_account_id,
        amount=amount,
        start_date=start_date,
        end_date=end_date,
        next_run_date=start_date,
        frequency=frequency,
        branch=branch,
        metadata=metadata or {},
    )


@transaction.atomic
def run_monthly_accruals(*, run_date, created_by_id: UUID | None = None, branch: UUID | None = None) -> list[object]:
    journals = []
    accruals = RecurringAccrual.objects.filter(
        status=RecurringAccrual.Status.ACTIVE,
        next_run_date__lte=run_date,
    )
    if branch is not None:
        accruals = accruals.filter(branch=branch)
    for accrual in accruals.select_related("accrual_account", "offset_account"):
        journal = create_and_post_journal(
            reference=f"RACCR-{accrual.id}",
            journal_type="recurring_accrual",
            posting_date=run_date,
            description=accrual.name,
            source_module=accrual.source_module,
            source_id=f"{accrual.source_id}:{run_date.isoformat()}",
            branch=accrual.branch,
            created_by_id=created_by_id,
            idempotency_key=f"recurring-accrual:{accrual.id}:{run_date.isoformat()}",
            lines=build_two_line_entry(
                debit_account_id=accrual.accrual_account_id,
                credit_account_id=accrual.offset_account_id,
                amount=accrual.amount,
                currency=accrual.accrual_account.currency.code,
                description=accrual.name,
                branch=accrual.branch,
                rate_date=run_date,
            ),
        )
        accrual.next_run_date = _next_run_date(accrual)
        if accrual.next_run_date > accrual.end_date:
            accrual.status = RecurringAccrual.Status.COMPLETED
        accrual.save(update_fields=["next_run_date", "status", "updated_at"])
        journals.append(journal)
    return journals


@transaction.atomic
def reverse_accruals(*, recurring_accrual_id, reversal_date, created_by_id: UUID | None = None):
    from apps.ledgers.services.journal_service import reverse_journal_entry

    journals = []
    accrual = RecurringAccrual.objects.get(pk=recurring_accrual_id)
    posted = accrual.accrual_account.journal_lines.filter(
        journal_entry__source_module=accrual.source_module,
        journal_entry__source_id__startswith=accrual.source_id,
        journal_entry__status="posted",
    )
    for line in posted.select_related("journal_entry"):
        journals.append(
            reverse_journal_entry(
                journal_entry_id=line.journal_entry_id,
                reversal_date=reversal_date,
                created_by_id=created_by_id,
                reason=f"Accrual reversal for {accrual.name}",
            )
        )
    return journals
