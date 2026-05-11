from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.expense_accounting.constants import ZERO
from apps.expense_accounting.exceptions import BudgetExceededError, BudgetNotFoundError
from apps.expense_accounting.models import ExpenseBudget
from apps.expense_accounting.repositories.expense_repository import ExpenseRepository


def check_budget_availability(
    *,
    fiscal_period_id: UUID,
    amount_ugx: Decimal,
    department: str = "",
    branch: UUID | None = None,
    project: str = "",
    expense_category_id: UUID | None = None,
    raise_on_exceeded: bool = True,
) -> dict:
    """Check whether budget is available. Returns a status dict.

    Args:
        raise_on_exceeded: If True raises BudgetExceededError when over budget.
    """
    budget = ExpenseRepository.get_budget(
        fiscal_period_id=fiscal_period_id,
        department=department,
        branch=branch,
        project=project,
        expense_category_id=expense_category_id,
    )
    if budget is None:
        return {"has_budget": False, "available": None, "amount": amount_ugx}

    available = budget.remaining_amount
    if raise_on_exceeded and amount_ugx > available:
        raise BudgetExceededError(
            f"Budget exceeded: requested {amount_ugx} UGX but only {available} UGX remaining "
            f"(dept={department!r}, branch={branch}, project={project!r})."
        )
    return {
        "has_budget": True,
        "available": available,
        "amount": amount_ugx,
        "budget_id": budget.id,
        "will_exceed": amount_ugx > available,
    }


@transaction.atomic
def consume_budget(
    *,
    fiscal_period_id: UUID,
    amount_ugx: Decimal,
    department: str = "",
    branch: UUID | None = None,
    project: str = "",
    expense_category_id: UUID | None = None,
) -> None:
    """Atomically consume budget. Locks the row with select_for_update."""
    budget = ExpenseRepository.get_budget(
        fiscal_period_id=fiscal_period_id,
        department=department,
        branch=branch,
        project=project,
        expense_category_id=expense_category_id,
    )
    if budget is None:
        return  # no budget configured — allow posting without budget enforcement
    budget.consumed_amount += amount_ugx
    budget.save(update_fields=["consumed_amount", "updated_at"])


@transaction.atomic
def release_budget(
    *,
    fiscal_period_id: UUID,
    amount_ugx: Decimal,
    department: str = "",
    branch: UUID | None = None,
    project: str = "",
    expense_category_id: UUID | None = None,
) -> None:
    """Release previously consumed budget (on reversal)."""
    budget = ExpenseRepository.get_budget(
        fiscal_period_id=fiscal_period_id,
        department=department,
        branch=branch,
        project=project,
        expense_category_id=expense_category_id,
    )
    if budget is None:
        return
    budget.consumed_amount = max(ZERO, budget.consumed_amount - amount_ugx)
    budget.save(update_fields=["consumed_amount", "updated_at"])


def generate_budget_variance(
    *,
    fiscal_period_id: UUID,
    branch: UUID | None = None,
) -> list[dict]:
    qs = ExpenseBudget.objects.filter(fiscal_period_id=fiscal_period_id)
    if branch is not None:
        qs = qs.filter(branch=branch)
    results = []
    for b in qs.select_related("expense_category"):
        variance = b.budget_amount - b.consumed_amount
        results.append(
            {
                "budget_id": str(b.id),
                "department": b.department,
                "project": b.project,
                "branch": str(b.branch) if b.branch else None,
                "category": b.expense_category.name if b.expense_category else "All",
                "budget_amount": b.budget_amount,
                "consumed_amount": b.consumed_amount,
                "remaining_amount": b.remaining_amount,
                "variance": variance,
                "is_over_budget": variance < ZERO,
            }
        )
    return results
