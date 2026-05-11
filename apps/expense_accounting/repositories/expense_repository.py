from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import QuerySet, Sum

from apps.expense_accounting.models import (
    CorporateCardTransaction,
    ExpenseApproval,
    ExpenseBudget,
    ExpenseTransaction,
    PrepaidExpenseSchedule,
)


class ExpenseRepository:
    @staticmethod
    def get_by_id(expense_id: UUID) -> ExpenseTransaction:
        return ExpenseTransaction.objects.select_related(
            "expense_category", "currency", "journal_entry"
        ).get(id=expense_id)

    @staticmethod
    def get_by_reference(reference: str) -> ExpenseTransaction:
        return ExpenseTransaction.objects.select_related(
            "expense_category", "currency"
        ).get(reference=reference)

    @staticmethod
    def filter_posted(
        *,
        branch: UUID | None = None,
        department: str | None = None,
        project: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> QuerySet[ExpenseTransaction]:
        qs = ExpenseTransaction.objects.filter(status=ExpenseTransaction.Status.POSTED)
        if branch is not None:
            qs = qs.filter(branch=branch)
        if department:
            qs = qs.filter(department=department)
        if project:
            qs = qs.filter(project=project)
        if start_date:
            qs = qs.filter(expense_date__gte=start_date)
        if end_date:
            qs = qs.filter(expense_date__lte=end_date)
        return qs.select_related("expense_category", "currency")

    @staticmethod
    def get_pending_approval(expense_id: UUID) -> ExpenseApproval:
        return ExpenseApproval.objects.get(
            expense_transaction_id=expense_id,
            status=ExpenseApproval.Status.PENDING,
        )

    @staticmethod
    def get_active_prepaid_schedules(as_of_date: date) -> QuerySet[PrepaidExpenseSchedule]:
        return PrepaidExpenseSchedule.objects.filter(
            status=PrepaidExpenseSchedule.Status.ACTIVE,
            next_run_date__lte=as_of_date,
        ).select_related("expense_transaction__expense_category", "expense_transaction__currency")

    @staticmethod
    def get_budget(
        *,
        fiscal_period_id: UUID,
        department: str = "",
        branch: UUID | None = None,
        project: str = "",
        expense_category_id: UUID | None = None,
    ) -> ExpenseBudget | None:
        try:
            return ExpenseBudget.objects.select_for_update().get(
                fiscal_period_id=fiscal_period_id,
                department=department,
                branch=branch,
                project=project,
                expense_category_id=expense_category_id,
            )
        except ExpenseBudget.DoesNotExist:
            return None

    @staticmethod
    def total_posted_by_employee(employee_id: UUID) -> Decimal:
        result = ExpenseTransaction.objects.filter(
            employee=employee_id,
            status=ExpenseTransaction.Status.POSTED,
        ).aggregate(total=Sum("base_amount"))
        return result["total"] or Decimal("0.00")

    @staticmethod
    def unreconciled_card_transactions(employee_id: UUID) -> QuerySet[CorporateCardTransaction]:
        return CorporateCardTransaction.objects.filter(
            employee=employee_id,
            reconciled=False,
        ).select_related("currency")

    @staticmethod
    def expenses_pending_escalation(overdue_before) -> QuerySet[ExpenseApproval]:
        return ExpenseApproval.objects.filter(
            status=ExpenseApproval.Status.PENDING,
            created_at__lt=overdue_before,
        ).select_related("expense_transaction")
