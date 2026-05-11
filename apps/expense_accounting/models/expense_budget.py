from __future__ import annotations

import uuid

from django.db import models


class ExpenseBudget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fiscal_period_id = models.UUIDField(db_index=True, help_text="References ledgers.FiscalPeriod.id")
    department = models.CharField(max_length=120, blank=True, db_index=True)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    project = models.CharField(max_length=120, blank=True, db_index=True)
    expense_category = models.ForeignKey(
        "expense_accounting.ExpenseCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="budgets",
    )
    budget_amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="UGX budget allocation")
    consumed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="UGX consumed so far")
    created_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["fiscal_period_id", "department"]),
            models.Index(fields=["fiscal_period_id", "branch"]),
            models.Index(fields=["fiscal_period_id", "project"]),
        ]

    @property
    def remaining_amount(self):
        from apps.expense_accounting.constants import ZERO
        return max(self.budget_amount - self.consumed_amount, ZERO)

    def __str__(self) -> str:
        cat = self.expense_category.name if self.expense_category else "All"
        return f"Budget {cat} — dept:{self.department} branch:{self.branch} ({self.budget_amount} UGX)"
