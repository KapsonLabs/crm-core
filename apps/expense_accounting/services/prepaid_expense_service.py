from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.expense_accounting.constants import IK_PREPAID_AMORTIZATION, IK_PREPAID_INITIAL, SOURCE_MODULE, ZERO
from apps.expense_accounting.exceptions import ExpenseStatusError, PrepaidScheduleError
from apps.expense_accounting.models import ExpenseTransaction, PrepaidExpenseSchedule
from apps.expense_accounting.utils.expense_calculations import (
    add_months,
    compute_last_amortization_amount,
    compute_monthly_amount,
    count_months_between,
    round_currency,
)
from apps.ledgers.models import Account
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal
from apps.ledgers.utils.periods import ensure_date_in_open_period


@transaction.atomic
def create_prepaid_schedule(
    *,
    expense: ExpenseTransaction,
    start_date: date,
    end_date: date,
    prepaid_account: Account,
    credit_account: Account,
) -> PrepaidExpenseSchedule:
    """Create prepaid asset + amortization schedule. Called after expense is approved.

    Initial posting:
        DR Prepaid Expense (asset)
        CR AP / Cash
    """
    if expense.expense_category.expense_type != "prepaid":
        raise PrepaidScheduleError("Expense category must be of type 'prepaid'.")
    if hasattr(expense, "prepaid_schedule"):
        raise PrepaidScheduleError("Prepaid schedule already exists for this expense.")
    if end_date <= start_date:
        raise PrepaidScheduleError("end_date must be after start_date.")

    total_months = count_months_between(start_date, end_date)
    monthly_base = compute_monthly_amount(expense.base_amount, total_months)
    monthly_foreign = compute_monthly_amount(expense.amount, total_months)

    ensure_date_in_open_period(posting_date=expense.expense_date, branch=expense.branch)

    journal = create_and_post_journal(
        reference=f"PREPAID-{expense.reference}",
        journal_type="prepaid_expense_initial",
        posting_date=expense.expense_date,
        description=f"Prepaid expense initial posting — {expense.description}",
        source_module=SOURCE_MODULE,
        source_id=str(expense.id),
        branch=expense.branch,
        created_by_id=expense.created_by,
        idempotency_key=f"{IK_PREPAID_INITIAL}:{expense.id}",
        transaction_currency_code=expense.currency.code,
        lines=build_two_line_entry(
            debit_account_id=prepaid_account.id,
            credit_account_id=credit_account.id,
            amount=expense.amount,
            currency=expense.currency.code,
            description=f"Prepaid expense — {expense.description}",
            branch=expense.branch,
            party_type="supplier",
            party_id=expense.vendor,
            exchange_rate=expense.exchange_rate,
        ),
    )

    schedule = PrepaidExpenseSchedule.objects.create(
        expense_transaction=expense,
        start_date=start_date,
        end_date=end_date,
        total_months=total_months,
        monthly_amount=monthly_foreign,
        monthly_base_amount=monthly_base,
        remaining_balance=expense.amount,
        remaining_base_balance=expense.base_amount,
        next_run_date=start_date,
    )

    expense.journal_entry = journal
    expense.status = ExpenseTransaction.Status.POSTED
    expense.posted_at = timezone.now()
    expense.save(update_fields=["journal_entry", "status", "posted_at", "updated_at"])

    emit_audit_log(
        event_type="prepaid_expense.schedule_created",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=expense.created_by,
        payload={"schedule_id": str(schedule.id), "total_months": total_months},
    )
    return schedule


@transaction.atomic
def amortize_prepaid_expense(
    *,
    schedule: PrepaidExpenseSchedule,
    amortization_date: date,
    expense_account: Account,
    prepaid_account: Account,
    posted_by_id: UUID | None = None,
) -> dict:
    """Post one month's amortization entry.

    Monthly posting:
        DR Expense Account
        CR Prepaid Expense Asset
    """
    if schedule.status != PrepaidExpenseSchedule.Status.ACTIVE:
        raise PrepaidScheduleError("Schedule is not active.")

    expense = schedule.expense_transaction
    ensure_date_in_open_period(posting_date=amortization_date, branch=expense.branch)

    period_num = schedule.amortizations_posted + 1
    is_last = period_num == schedule.total_months

    if is_last:
        period_base = schedule.remaining_base_balance
        period_foreign = schedule.remaining_balance
    else:
        period_base = schedule.monthly_base_amount
        period_foreign = schedule.monthly_amount

    journal = create_and_post_journal(
        reference=f"AMORT-{expense.reference}-{period_num:02d}",
        journal_type="prepaid_amortization",
        posting_date=amortization_date,
        description=f"Prepaid amortization {period_num}/{schedule.total_months} — {expense.description}",
        source_module=SOURCE_MODULE,
        source_id=str(schedule.id),
        branch=expense.branch,
        created_by_id=posted_by_id,
        idempotency_key=f"{IK_PREPAID_AMORTIZATION}:{schedule.id}:{period_num}",
        transaction_currency_code=expense.currency.code,
        lines=build_two_line_entry(
            debit_account_id=expense_account.id,
            credit_account_id=prepaid_account.id,
            amount=period_foreign,
            currency=expense.currency.code,
            description=f"Prepaid amortization — {expense.description}",
            branch=expense.branch,
            exchange_rate=expense.exchange_rate,
        ),
    )

    schedule.remaining_balance = round_currency(schedule.remaining_balance - period_foreign)
    schedule.remaining_base_balance = round_currency(schedule.remaining_base_balance - period_base)
    schedule.amortizations_posted = period_num
    schedule.last_run_at = timezone.now()

    if is_last:
        schedule.status = PrepaidExpenseSchedule.Status.COMPLETED
        schedule.next_run_date = schedule.end_date
    else:
        schedule.next_run_date = add_months(amortization_date, 1)

    schedule.save(update_fields=[
        "remaining_balance", "remaining_base_balance", "amortizations_posted",
        "last_run_at", "status", "next_run_date", "updated_at",
    ])

    emit_audit_log(
        event_type="prepaid_expense.amortized",
        entity_type="PrepaidExpenseSchedule",
        entity_id=schedule.id,
        branch=expense.branch,
        performed_by_id=posted_by_id,
        payload={"period": period_num, "amount_ugx": str(period_base), "journal_id": str(journal.id)},
    )
    return {"journal_id": str(journal.id), "period": period_num, "amount_ugx": period_base}


@transaction.atomic
def reverse_prepaid_expense(
    *,
    schedule: PrepaidExpenseSchedule,
    reversal_date: date,
    prepaid_account: Account,
    credit_account: Account,
    reversed_by_id: UUID | None = None,
    reason: str = "",
) -> dict:
    """Cancel and reverse the remaining prepaid balance.

    Reversal posting:
        DR AP / Cash  (original credit side)
        CR Prepaid Expense Asset
    """
    if schedule.status != PrepaidExpenseSchedule.Status.ACTIVE:
        raise PrepaidScheduleError("Cannot reverse a schedule that is not active.")

    expense = schedule.expense_transaction
    remaining_base = schedule.remaining_base_balance
    remaining_foreign = schedule.remaining_balance

    if remaining_base <= ZERO:
        raise PrepaidScheduleError("No remaining balance to reverse.")

    ensure_date_in_open_period(posting_date=reversal_date, branch=expense.branch)

    journal = create_and_post_journal(
        reference=f"PREPAID-REV-{expense.reference}",
        journal_type="prepaid_expense_reversal",
        posting_date=reversal_date,
        description=f"Prepaid expense reversal — {expense.description}: {reason}",
        source_module=SOURCE_MODULE,
        source_id=str(schedule.id),
        branch=expense.branch,
        created_by_id=reversed_by_id,
        idempotency_key=f"prepaid-reversal:{schedule.id}",
        transaction_currency_code=expense.currency.code,
        lines=build_two_line_entry(
            debit_account_id=credit_account.id,
            credit_account_id=prepaid_account.id,
            amount=remaining_foreign,
            currency=expense.currency.code,
            description=f"Prepaid reversal — {reason or expense.description}",
            branch=expense.branch,
            exchange_rate=expense.exchange_rate,
        ),
    )

    schedule.remaining_balance = ZERO
    schedule.remaining_base_balance = ZERO
    schedule.status = PrepaidExpenseSchedule.Status.CANCELLED
    schedule.save(update_fields=["remaining_balance", "remaining_base_balance", "status", "updated_at"])

    expense.status = ExpenseTransaction.Status.REVERSED
    expense.reversal_journal_entry = journal
    expense.save(update_fields=["status", "reversal_journal_entry", "updated_at"])

    emit_audit_log(
        event_type="prepaid_expense.reversed",
        entity_type="PrepaidExpenseSchedule",
        entity_id=schedule.id,
        branch=expense.branch,
        performed_by_id=reversed_by_id,
        payload={"amount_ugx": str(remaining_base), "reason": reason},
    )
    return {"journal_id": str(journal.id), "reversed_amount_ugx": remaining_base}
