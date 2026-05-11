from __future__ import annotations

from celery import shared_task

from apps.ledgers.services.accrual_service import run_monthly_accruals
from apps.ledgers.services.depreciation_service import post_monthly_depreciation
from apps.ledgers.services.impairment_service import create_inventory_provision
from apps.ledgers.utils.inventory_reporting import generate_inventory_valuation_report


@shared_task(name="ledgers.run_monthly_accruals")
def run_monthly_accruals_task(run_date_iso: str, branch_id: str | None = None) -> list[str]:
    from datetime import date
    from uuid import UUID

    run_date = date.fromisoformat(run_date_iso)
    branch = UUID(branch_id) if branch_id else None
    return [str(j.id) for j in run_monthly_accruals(run_date=run_date, branch=branch)]


@shared_task(name="ledgers.post_monthly_depreciation")
def post_monthly_depreciation_task(run_date_iso: str, branch_id: str | None = None) -> list[str]:
    from datetime import date
    from uuid import UUID

    run_date = date.fromisoformat(run_date_iso)
    branch = UUID(branch_id) if branch_id else None
    return [str(j.id) for j in post_monthly_depreciation(as_of_date=run_date, branch=branch)]


@shared_task(name="ledgers.run_inventory_valuation_report")
def run_inventory_valuation_report_task(run_date_iso: str, branch_id: str | None = None) -> dict:
    from datetime import date
    from uuid import UUID

    run_date = date.fromisoformat(run_date_iso)
    branch = UUID(branch_id) if branch_id else None
    report = generate_inventory_valuation_report(as_of_date=run_date, branch=branch)
    # Convert non-serializable types for Celery JSON transport
    report["as_of_date"] = str(report["as_of_date"])
    report["rows"] = [
        {
            k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            for k, v in row.items()
        }
        for row in report.get("rows", [])
    ]
    return report


@shared_task(name="ledgers.run_inventory_impairment_test")
def run_inventory_impairment_test_task(
    inventory_item_id: str,
    warehouse_id: str,
    carrying_value: str,
    nrv_value: str,
    assessment_date_iso: str,
    reason: str,
    branch_id: str | None = None,
) -> dict | None:
    from datetime import date
    from decimal import Decimal
    from uuid import UUID

    result = create_inventory_provision(
        inventory_item_id=UUID(inventory_item_id),
        warehouse_id=UUID(warehouse_id),
        carrying_value=Decimal(carrying_value),
        nrv_value=Decimal(nrv_value),
        assessment_date=date.fromisoformat(assessment_date_iso),
        reason=reason,
        branch=UUID(branch_id) if branch_id else None,
        created_by_id=None,
    )
    if result is None:
        return None
    return {
        "write_down_id": str(result["write_down"].id),
        "write_down_amount": str(result["write_down"].write_down_amount),
        "journal_id": str(result["journal"].id),
    }


@shared_task(name="ledgers.run_unrealized_forex_revaluation")
def run_unrealized_forex_revaluation_task(
    revaluation_date_iso: str,
    branch_id: str | None = None,
    performed_by_id: str | None = None,
) -> list[str]:
    """Revalue all open foreign-currency monetary items at month-end closing rate.

    This task iterates open SubLedgerEntry balances on foreign-currency accounts,
    computes the unrealized exchange difference versus the carrying rate, and posts
    an unrealized FX adjustment journal per account (IAS 21.28).

    Each adjustment is reversed at the start of the next period via the normal
    accrual reversal mechanism.
    """
    from datetime import date
    from decimal import Decimal
    from uuid import UUID

    from apps.ledgers.models import SubLedgerAccount, SubLedgerEntry
    from apps.ledgers.repositories.account_repository import AccountRepository
    from apps.ledgers.services.forex_service import (
        calculate_unrealized_forex_gain_loss,
        post_forex_adjustment,
    )
    from apps.ledgers.utils.currency import get_exchange_rate

    revaluation_date = date.fromisoformat(revaluation_date_iso)
    branch = UUID(branch_id) if branch_id else None
    performed_by = UUID(performed_by_id) if performed_by_id else None
    base_currency = AccountRepository.get_base_currency()
    posted_journal_ids: list[str] = []

    subledger_qs = SubLedgerAccount.objects.exclude(currency__code=base_currency.code).filter(is_active=True)
    if branch is not None:
        subledger_qs = subledger_qs.filter(branch=branch)

    for subledger in subledger_qs.select_related("currency", "parent_control_account__gl_account"):
        entries_qs = SubLedgerEntry.objects.filter(subledger_account=subledger)
        if branch is not None:
            entries_qs = entries_qs.filter(branch=branch)

        last_entry = entries_qs.order_by("-date", "-created_at", "-id").first()
        if last_entry is None:
            continue

        carrying_balance_foreign = last_entry.running_balance_base  # stored in foreign units
        if carrying_balance_foreign == Decimal("0.00"):
            continue

        try:
            closing_rate = get_exchange_rate(
                from_currency_code=subledger.currency.code,
                to_currency_code=base_currency.code,
                rate_date=revaluation_date,
            )
        except Exception:
            continue

        # We need the original carrying rate — use the exchange_rate from the
        # most recent journal line on this subledger.
        if last_entry.journal_line_id:
            carrying_rate = last_entry.journal_line.exchange_rate
        else:
            continue

        variance = calculate_unrealized_forex_gain_loss(
            foreign_balance=carrying_balance_foreign,
            carrying_exchange_rate=carrying_rate,
            closing_exchange_rate=closing_rate,
        )
        if variance == Decimal("0.00"):
            continue

        journal = post_forex_adjustment(
            adjustment_id=f"unrealized-{subledger.id}-{revaluation_date_iso}",
            posting_date=revaluation_date,
            amount_base=variance,
            revaluation_account_id=subledger.parent_control_account.gl_account_id,
            branch=branch,
            created_by_id=performed_by,
            is_realized=False,
        )
        if journal is not None:
            posted_journal_ids.append(str(journal.id))

    return posted_journal_ids
