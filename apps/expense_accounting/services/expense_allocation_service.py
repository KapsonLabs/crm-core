from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.expense_accounting.constants import ZERO
from apps.expense_accounting.exceptions import AllocationError
from apps.expense_accounting.models import ExpenseLine, ExpenseTransaction
from apps.expense_accounting.utils.expense_calculations import round_currency


def _validate_percentages(percentages: dict[str, Decimal]) -> None:
    total = sum(percentages.values(), ZERO)
    if abs(total - Decimal("100")) > Decimal("0.01"):
        raise AllocationError(f"Allocation percentages must sum to 100. Got {total}.")


def split_expense_by_percentage(
    *,
    expense: ExpenseTransaction,
    allocations: list[dict],
) -> list[dict]:
    """Split an expense across dimensions by percentage.

    Args:
        allocations: List of dicts with keys:
            - account_id (UUID)
            - percentage (Decimal, must sum to 100)
            - department (str, optional)
            - project (str, optional)
            - cost_center (str, optional)
            - description (str, optional)

    Returns:
        List of computed allocation dicts with resolved amounts.
    """
    percentages = {str(a.get("account_id", i)): Decimal(str(a["percentage"])) for i, a in enumerate(allocations)}
    _validate_percentages(percentages)

    total_base = expense.base_amount
    result = []
    accumulated = ZERO
    for i, alloc in enumerate(allocations):
        pct = Decimal(str(alloc["percentage"])) / Decimal("100")
        if i == len(allocations) - 1:
            alloc_base = round_currency(total_base - accumulated)
        else:
            alloc_base = round_currency(total_base * pct)
            accumulated += alloc_base
        result.append({**alloc, "base_amount": alloc_base})
    return result


@transaction.atomic
def allocate_expense(
    *,
    expense: ExpenseTransaction,
    allocations: list[dict],
) -> list[ExpenseLine]:
    """Replace all expense lines with freshly computed allocations."""
    computed = split_expense_by_percentage(expense=expense, allocations=allocations)
    expense.lines.all().delete()
    lines = []
    for i, alloc in enumerate(computed):
        from apps.ledgers.models import Account
        line = ExpenseLine.objects.create(
            expense_transaction=expense,
            expense_account_id=alloc["account_id"],
            amount=round_currency(expense.amount * Decimal(str(alloc["percentage"])) / Decimal("100")),
            base_amount=alloc["base_amount"],
            tax_amount=ZERO,
            tax_base_amount=ZERO,
            department=alloc.get("department", expense.department),
            project=alloc.get("project", expense.project),
            cost_center=alloc.get("cost_center", expense.cost_center),
            description=alloc.get("description", expense.description),
            order=i,
        )
        lines.append(line)
    return lines


def allocate_to_project(
    *,
    expense: ExpenseTransaction,
    project_id: str,
    percentage: Decimal = Decimal("100"),
) -> list[dict]:
    """Convenience wrapper — allocate a percentage of the expense to a project."""
    return split_expense_by_percentage(
        expense=expense,
        allocations=[
            {
                "account_id": str(expense.expense_category.default_expense_account_id),
                "percentage": percentage,
                "project": project_id,
                "department": expense.department,
                "cost_center": expense.cost_center,
                "description": expense.description,
            }
        ],
    )


def allocate_to_departments(
    *,
    expense: ExpenseTransaction,
    dept_percentages: dict[str, Decimal],
) -> list[dict]:
    """Allocate expense across multiple departments.

    Args:
        dept_percentages: {department_name: percentage}
    """
    allocations = [
        {
            "account_id": str(expense.expense_category.default_expense_account_id),
            "percentage": pct,
            "department": dept,
            "project": expense.project,
            "cost_center": expense.cost_center,
            "description": f"{expense.description} ({dept})",
        }
        for dept, pct in dept_percentages.items()
    ]
    return split_expense_by_percentage(expense=expense, allocations=allocations)


def allocate_to_branches(
    *,
    expense: ExpenseTransaction,
    branch_percentages: dict[str, Decimal],
) -> list[dict]:
    """Allocate expense across multiple branches.

    Args:
        branch_percentages: {branch_uuid_str: percentage}
    """
    allocations = [
        {
            "account_id": str(expense.expense_category.default_expense_account_id),
            "percentage": pct,
            "department": expense.department,
            "project": expense.project,
            "cost_center": expense.cost_center,
            "description": f"{expense.description} (branch {branch})",
        }
        for branch, pct in branch_percentages.items()
    ]
    return split_expense_by_percentage(expense=expense, allocations=allocations)
