from __future__ import annotations

from celery import shared_task


@shared_task(name="expense_accounting.run_prepaid_amortization")
def run_prepaid_amortization_task(run_date_iso: str, branch_id: str | None = None) -> list[dict]:
    """Amortize all active prepaid schedules due on or before run_date.

    Returns a list of {schedule_id, journal_id, period, amount_ugx}.
    """
    from datetime import date
    from uuid import UUID

    from apps.ledgers.models import Account

    from apps.expense_accounting.repositories.expense_repository import ExpenseRepository
    from apps.expense_accounting.services.prepaid_expense_service import amortize_prepaid_expense

    run_date = date.fromisoformat(run_date_iso)
    schedules = ExpenseRepository.get_active_prepaid_schedules(as_of_date=run_date)
    if branch_id:
        schedules = schedules.filter(expense_transaction__branch=UUID(branch_id))

    results = []
    for schedule in schedules:
        expense = schedule.expense_transaction
        category = expense.expense_category
        try:
            expense_account = category.default_expense_account
            prepaid_account = Account.objects.get(category="prepaid_expenses", branch=expense.branch)
            result = amortize_prepaid_expense(
                schedule=schedule,
                amortization_date=run_date,
                expense_account=expense_account,
                prepaid_account=prepaid_account,
            )
            results.append({"schedule_id": str(schedule.id), **result})
        except Exception as exc:
            results.append({"schedule_id": str(schedule.id), "error": str(exc)})
    return results


@shared_task(name="expense_accounting.run_accrual_reversals")
def run_accrual_reversals_task(reversal_date_iso: str, branch_id: str | None = None) -> list[str]:
    """Reverse all posted accrual-type expenses at the start of the new period.

    Returns list of reversed expense IDs.
    """
    from datetime import date
    from uuid import UUID

    from apps.expense_accounting.models import ExpenseTransaction
    from apps.expense_accounting.services.expense_posting_service import reverse_expense

    reversal_date = date.fromisoformat(reversal_date_iso)
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        expense_category__expense_type="accrual",
    )
    if branch_id:
        qs = qs.filter(branch=UUID(branch_id))

    reversed_ids = []
    for expense in qs:
        try:
            reverse_expense(
                expense_id=expense.id,
                reversal_date=reversal_date,
                reason="Automatic accrual reversal at period start",
            )
            reversed_ids.append(str(expense.id))
        except Exception:
            pass
    return reversed_ids


@shared_task(name="expense_accounting.escalate_pending_approvals")
def escalate_pending_approvals_task() -> list[str]:
    """Escalate approval records that have been pending longer than ESCALATION_DAYS.

    Returns list of escalated approval IDs.
    """
    from datetime import datetime, timedelta, timezone

    from apps.expense_accounting.constants import ESCALATION_DAYS
    from apps.expense_accounting.repositories.expense_repository import ExpenseRepository
    from apps.expense_accounting.services.expense_approval_service import escalate_pending_approval

    overdue_before = datetime.now(tz=timezone.utc) - timedelta(days=ESCALATION_DAYS)
    pending = ExpenseRepository.expenses_pending_escalation(overdue_before=overdue_before)
    escalated = []
    for approval in pending:
        result = escalate_pending_approval(expense_id=approval.expense_transaction_id)
        if result:
            escalated.append(str(result.id))
    return escalated


@shared_task(name="expense_accounting.run_budget_monitoring")
def run_budget_monitoring_task(fiscal_period_id_str: str) -> list[dict]:
    """Return all over-budget allocations for the given fiscal period."""
    from uuid import UUID

    from apps.expense_accounting.services.expense_budget_service import generate_budget_variance

    fiscal_period_id = UUID(fiscal_period_id_str)
    variances = generate_budget_variance(fiscal_period_id=fiscal_period_id)
    return [v for v in variances if v["is_over_budget"]]


@shared_task(name="expense_accounting.send_reimbursement_reminders")
def send_reimbursement_reminders_task() -> list[str]:
    """Return IDs of unpaid reimbursement expenses older than 7 days (for notification layer)."""
    from datetime import date, timedelta

    from apps.expense_accounting.models import ExpenseTransaction

    cutoff = date.today() - timedelta(days=7)
    unpaid = ExpenseTransaction.objects.filter(
        expense_category__expense_type="employee_reimbursement",
        status=ExpenseTransaction.Status.POSTED,
        payment_status=ExpenseTransaction.PaymentStatus.UNPAID,
        expense_date__lte=cutoff,
    ).values_list("id", flat=True)
    return [str(eid) for eid in unpaid]
