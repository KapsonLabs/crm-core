from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import AssetDepreciationSchedule
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal
from apps.ledgers.services.types import JournalLineInput
from apps.ledgers.utils.money import round_currency


def _add_months(source: date, months: int) -> date:
    month = source.month - 1 + months
    year = source.year + month // 12
    month = month % 12 + 1
    day = min(source.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def generate_depreciation_schedule(
    *,
    asset_reference: str,
    asset_name: str,
    asset_account_id,
    accumulated_depreciation_account_id,
    depreciation_expense_account_id,
    acquisition_cost: Decimal,
    salvage_value: Decimal,
    useful_life_months: int,
    depreciation_start_date: date,
    branch: UUID | None,
    metadata: dict | None = None,
) -> list[AssetDepreciationSchedule]:
    depreciable_amount = acquisition_cost - salvage_value
    monthly_amount = round_currency(depreciable_amount / Decimal(useful_life_months))
    schedules = []
    accumulated = Decimal("0.00")
    for month in range(useful_life_months):
        # Last month absorbs any rounding difference to keep accumulated == depreciable_amount
        if month == useful_life_months - 1:
            period_amount = depreciable_amount - accumulated
        else:
            period_amount = monthly_amount
        accumulated += period_amount
        depreciation_date = _add_months(depreciation_start_date, month)
        schedules.append(
            AssetDepreciationSchedule.objects.create(
                asset_reference=asset_reference,
                asset_name=asset_name,
                asset_account_id=asset_account_id,
                accumulated_depreciation_account_id=accumulated_depreciation_account_id,
                depreciation_expense_account_id=depreciation_expense_account_id,
                acquisition_cost=acquisition_cost,
                salvage_value=salvage_value,
                useful_life_months=useful_life_months,
                depreciation_start_date=depreciation_start_date,
                depreciation_date=depreciation_date,
                depreciation_amount=period_amount,
                accumulated_depreciation=accumulated,
                book_value=acquisition_cost - accumulated,
                branch=branch,
                metadata=metadata or {},
            )
        )
    return schedules


@transaction.atomic
def post_monthly_depreciation(*, as_of_date: date, created_by_id: UUID | None = None, branch: UUID | None = None):
    journals = []
    schedules = AssetDepreciationSchedule.objects.filter(
        status=AssetDepreciationSchedule.Status.PENDING,
        depreciation_date__lte=as_of_date,
    )
    if branch is not None:
        schedules = schedules.filter(branch=branch)
    for schedule in schedules.select_related(
        "asset_account",
        "accumulated_depreciation_account",
        "depreciation_expense_account",
    ):
        journal = create_and_post_journal(
            reference=f"DEP-{schedule.asset_reference}-{schedule.depreciation_date.isoformat()}",
            journal_type="depreciation",
            posting_date=schedule.depreciation_date,
            description=f"Depreciation for {schedule.asset_name}",
            source_module="assets",
            source_id=f"{schedule.asset_reference}:{schedule.depreciation_date.isoformat()}",
            branch=schedule.branch,
            created_by_id=created_by_id,
            idempotency_key=f"depreciation:{schedule.id}",
            lines=build_two_line_entry(
                debit_account_id=schedule.depreciation_expense_account_id,
                credit_account_id=schedule.accumulated_depreciation_account_id,
                amount=schedule.depreciation_amount,
                currency=schedule.asset_account.currency.code,
                description=f"Depreciation for {schedule.asset_name}",
                branch=schedule.branch,
                rate_date=schedule.depreciation_date,
            ),
        )
        schedule.status = AssetDepreciationSchedule.Status.POSTED
        schedule.posted_journal_entry = journal
        schedule.save(update_fields=["status", "posted_journal_entry", "updated_at"])
        journals.append(journal)
    return journals


@transaction.atomic
def dispose_asset(
    *,
    asset_reference: str,
    disposal_date: date,
    proceeds: Decimal,
    cash_account_id: UUID,
    disposal_gain_loss_account_id: UUID,
    created_by_id: UUID | None = None,
    branch: UUID | None = None,
) -> object | None:
    schedules = AssetDepreciationSchedule.objects.filter(asset_reference=asset_reference).order_by("-depreciation_date")
    latest = schedules.select_related("asset_account", "accumulated_depreciation_account").first()
    if latest is None:
        return None
    currency_code = latest.asset_account.currency.code
    carrying_amount = latest.book_value
    gain_loss = proceeds - carrying_amount
    # IAS 16 disposal:
    #   DR  Cash / Proceeds             (debit proceeds received)
    #   DR  Accumulated Depreciation    (debit to clear accumulated dep)
    #   CR  Fixed Asset (cost)          (credit to remove original cost)
    #   CR  Gain on Disposal            (if gain)  OR
    #   DR  Loss on Disposal            (if loss)
    lines: list[JournalLineInput] = [
        JournalLineInput(
            account_id=cash_account_id,
            debit_foreign=proceeds,
            debit_base=proceeds,
            currency_code=currency_code,
            description=f"Asset disposal proceeds {asset_reference}",
            branch=branch,
        ),
        JournalLineInput(
            account_id=latest.accumulated_depreciation_account_id,
            debit_foreign=latest.accumulated_depreciation,
            debit_base=latest.accumulated_depreciation,
            currency_code=currency_code,
            description=f"Clear accumulated depreciation {asset_reference}",
            branch=branch,
        ),
        JournalLineInput(
            account_id=latest.asset_account_id,
            credit_foreign=latest.acquisition_cost,
            credit_base=latest.acquisition_cost,
            currency_code=currency_code,
            description=f"Remove asset cost {asset_reference}",
            branch=branch,
        ),
    ]
    if gain_loss > Decimal("0.00"):
        lines.append(
            JournalLineInput(
                account_id=disposal_gain_loss_account_id,
                credit_foreign=gain_loss,
                credit_base=gain_loss,
                currency_code=currency_code,
                description=f"Disposal gain {asset_reference}",
                branch=branch,
            )
        )
    elif gain_loss < Decimal("0.00"):
        lines.append(
            JournalLineInput(
                account_id=disposal_gain_loss_account_id,
                debit_foreign=abs(gain_loss),
                debit_base=abs(gain_loss),
                currency_code=currency_code,
                description=f"Disposal loss {asset_reference}",
                branch=branch,
            )
        )
    journal = create_and_post_journal(
        reference=f"DISP-{asset_reference}",
        journal_type="asset_disposal",
        posting_date=disposal_date,
        description=f"Asset disposal {asset_reference}",
        source_module="assets",
        source_id=f"{asset_reference}:disposal",
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"asset-disposal:{asset_reference}",
        lines=lines,
        transaction_currency_code=currency_code,
    )
    schedules.update(status=AssetDepreciationSchedule.Status.DISPOSED)
    return journal
