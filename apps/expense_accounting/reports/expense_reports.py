from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import Avg, Count, Q, Sum

from apps.expense_accounting.models import CorporateCardTransaction, ExpenseTransaction, PrepaidExpenseSchedule
from apps.expense_accounting.selectors.expense_selectors import get_aging_report, get_budget_utilization


def generate_expense_analysis(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
    department: str | None = None,
    project: str | None = None,
) -> dict:
    """Expense analysis: totals by category and type."""
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    if department:
        qs = qs.filter(department=department)
    if project:
        qs = qs.filter(project=project)

    by_category = list(
        qs.values("expense_category__name", "expense_category__expense_type")
        .annotate(
            total_net_ugx=Sum("base_amount"),
            total_tax_ugx=Sum("tax_base_amount"),
            count=Count("id"),
        )
        .order_by("-total_net_ugx")
    )

    totals = qs.aggregate(
        total_net=Sum("base_amount"),
        total_tax=Sum("tax_base_amount"),
        count=Count("id"),
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "report_currency": "UGX",
        "by_category": by_category,
        "total_net_ugx": totals["total_net"] or Decimal("0.00"),
        "total_tax_ugx": totals["total_tax"] or Decimal("0.00"),
        "total_gross_ugx": (totals["total_net"] or Decimal("0.00")) + (totals["total_tax"] or Decimal("0.00")),
        "count": totals["count"] or 0,
    }


def generate_department_expense_report(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
) -> dict:
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
    )
    if branch is not None:
        qs = qs.filter(branch=branch)

    rows = list(
        qs.values("department")
        .annotate(
            total_net_ugx=Sum("base_amount"),
            total_tax_ugx=Sum("tax_base_amount"),
            count=Count("id"),
        )
        .order_by("-total_net_ugx")
    )
    return {"start_date": start_date, "end_date": end_date, "report_currency": "UGX", "rows": rows}


def generate_project_expense_report(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
) -> dict:
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
    )
    if branch is not None:
        qs = qs.filter(branch=branch)

    rows = list(
        qs.values("project")
        .annotate(total_net_ugx=Sum("base_amount"), total_tax_ugx=Sum("tax_base_amount"), count=Count("id"))
        .order_by("-total_net_ugx")
    )
    return {"start_date": start_date, "end_date": end_date, "report_currency": "UGX", "rows": rows}


def generate_branch_expense_report(
    *,
    start_date: date,
    end_date: date,
) -> dict:
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
    )
    rows = list(
        qs.values("branch")
        .annotate(total_net_ugx=Sum("base_amount"), total_tax_ugx=Sum("tax_base_amount"), count=Count("id"))
        .order_by("-total_net_ugx")
    )
    return {"start_date": start_date, "end_date": end_date, "report_currency": "UGX", "rows": rows}


def generate_budget_variance_report(*, fiscal_period_id: UUID, branch: UUID | None = None) -> dict:
    return {
        "fiscal_period_id": str(fiscal_period_id),
        "report_currency": "UGX",
        "rows": get_budget_utilization(fiscal_period_id=fiscal_period_id, branch=branch),
    }


def generate_prepaid_expense_report(*, as_of_date: date, branch: UUID | None = None) -> dict:
    qs = PrepaidExpenseSchedule.objects.filter(status=PrepaidExpenseSchedule.Status.ACTIVE)
    if branch is not None:
        qs = qs.filter(expense_transaction__branch=branch)
    rows = []
    for s in qs.select_related("expense_transaction__expense_category", "expense_transaction__currency"):
        rows.append(
            {
                "expense_reference": s.expense_transaction.reference,
                "description": s.expense_transaction.description,
                "start_date": str(s.start_date),
                "end_date": str(s.end_date),
                "total_months": s.total_months,
                "amortizations_posted": s.amortizations_posted,
                "monthly_base_amount_ugx": s.monthly_base_amount,
                "remaining_base_balance_ugx": s.remaining_base_balance,
                "next_run_date": str(s.next_run_date),
            }
        )
    return {"as_of_date": as_of_date, "report_currency": "UGX", "rows": rows}


def generate_expense_aging_report(*, as_of_date: date, branch: UUID | None = None) -> dict:
    return {"as_of_date": as_of_date, "report_currency": "UGX", **get_aging_report(as_of_date=as_of_date, branch=branch)}


def generate_employee_claims_report(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
) -> dict:
    qs = ExpenseTransaction.objects.filter(
        expense_category__expense_type="employee_reimbursement",
        expense_date__gte=start_date,
        expense_date__lte=end_date,
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    rows = list(
        qs.values("employee", "status", "payment_status")
        .annotate(total_ugx=Sum("base_amount"), count=Count("id"))
        .order_by("employee")
    )
    return {"start_date": start_date, "end_date": end_date, "report_currency": "UGX", "rows": rows}


def generate_expense_trend_report(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
) -> dict:
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    rows = list(
        qs.extra(select={"month": "DATE_TRUNC('month', expense_date)"})
        .values("month")
        .annotate(total_ugx=Sum("base_amount"), count=Count("id"))
        .order_by("month")
    )
    return {"start_date": start_date, "end_date": end_date, "report_currency": "UGX", "rows": rows}


def generate_corporate_card_report(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
) -> dict:
    qs = CorporateCardTransaction.objects.filter(
        transaction_date__gte=start_date,
        transaction_date__lte=end_date,
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    rows = list(
        qs.values("employee", "card_reference", "reconciled")
        .annotate(total_ugx=Sum("base_amount"), count=Count("id"))
        .order_by("employee", "card_reference")
    )
    return {"start_date": start_date, "end_date": end_date, "report_currency": "UGX", "rows": rows}


def generate_tax_deduction_report(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
) -> dict:
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
        tax_base_amount__gt=0,
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    rows = list(
        qs.values("expense_category__name")
        .annotate(total_tax_ugx=Sum("tax_base_amount"), total_net_ugx=Sum("base_amount"), count=Count("id"))
        .order_by("-total_tax_ugx")
    )
    totals = qs.aggregate(total_tax=Sum("tax_base_amount"), total_net=Sum("base_amount"))
    return {
        "start_date": start_date,
        "end_date": end_date,
        "report_currency": "UGX",
        "rows": rows,
        "total_tax_ugx": totals["total_tax"] or Decimal("0.00"),
        "total_net_ugx": totals["total_net"] or Decimal("0.00"),
    }
