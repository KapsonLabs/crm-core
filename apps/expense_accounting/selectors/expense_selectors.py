from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import Avg, Count, Q, Sum

from apps.expense_accounting.models import ExpenseBudget, ExpenseTransaction


def get_expense_summary(
    *,
    start_date: date,
    end_date: date,
    branch: UUID | None = None,
    department: str | None = None,
    project: str | None = None,
) -> dict:
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

    totals = qs.aggregate(
        total_net=Sum("base_amount"),
        total_tax=Sum("tax_base_amount"),
        count=Count("id"),
        avg_amount=Avg("base_amount"),
    )
    return {
        "total_net_ugx": totals["total_net"] or Decimal("0.00"),
        "total_tax_ugx": totals["total_tax"] or Decimal("0.00"),
        "total_gross_ugx": (totals["total_net"] or Decimal("0.00")) + (totals["total_tax"] or Decimal("0.00")),
        "count": totals["count"] or 0,
        "avg_amount_ugx": totals["avg_amount"] or Decimal("0.00"),
    }


def get_budget_utilization(
    *,
    fiscal_period_id: UUID,
    branch: UUID | None = None,
) -> list[dict]:
    qs = ExpenseBudget.objects.filter(fiscal_period_id=fiscal_period_id)
    if branch is not None:
        qs = qs.filter(branch=branch)
    results = []
    for budget in qs.select_related("expense_category"):
        remaining = max(budget.budget_amount - budget.consumed_amount, Decimal("0.00"))
        utilization_pct = (
            (budget.consumed_amount / budget.budget_amount * 100).quantize(Decimal("0.01"))
            if budget.budget_amount > 0
            else Decimal("0.00")
        )
        results.append(
            {
                "budget_id": str(budget.id),
                "department": budget.department,
                "project": budget.project,
                "branch": str(budget.branch) if budget.branch else None,
                "category": budget.expense_category.name if budget.expense_category else "All",
                "budget_amount": budget.budget_amount,
                "consumed_amount": budget.consumed_amount,
                "remaining_amount": remaining,
                "utilization_pct": utilization_pct,
                "is_over_budget": budget.consumed_amount > budget.budget_amount,
            }
        )
    return results


def get_aging_report(*, as_of_date: date, branch: UUID | None = None) -> list[dict]:
    qs = ExpenseTransaction.objects.filter(
        status=ExpenseTransaction.Status.POSTED,
        payment_status__in=[
            ExpenseTransaction.PaymentStatus.UNPAID,
            ExpenseTransaction.PaymentStatus.PARTIAL,
        ],
    )
    if branch is not None:
        qs = qs.filter(branch=branch)

    buckets: dict[str, Decimal] = {"0_30": Decimal("0.00"), "31_60": Decimal("0.00"), "61_90": Decimal("0.00"), "90_plus": Decimal("0.00")}
    rows = []
    for exp in qs.select_related("expense_category", "currency"):
        age = (as_of_date - exp.expense_date).days
        outstanding = exp.gross_base_amount
        if age <= 30:
            buckets["0_30"] += outstanding
        elif age <= 60:
            buckets["31_60"] += outstanding
        elif age <= 90:
            buckets["61_90"] += outstanding
        else:
            buckets["90_plus"] += outstanding
        rows.append(
            {
                "reference": exp.reference,
                "vendor": exp.vendor,
                "expense_date": str(exp.expense_date),
                "age_days": age,
                "outstanding_ugx": outstanding,
                "category": exp.expense_category.name,
            }
        )
    return {"buckets": buckets, "rows": rows}
