from __future__ import annotations

import uuid

from django.db import models


class ExpenseLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_transaction = models.ForeignKey(
        "expense_accounting.ExpenseTransaction",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    expense_account = models.ForeignKey(
        "ledgers.Account",
        on_delete=models.PROTECT,
        related_name="expense_lines",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="Transaction currency net amount")
    base_amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="UGX net amount")
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_base_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    department = models.CharField(max_length=120, blank=True)
    project = models.CharField(max_length=120, blank=True)
    cost_center = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=255, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"Line {self.order} — {self.expense_account.name}: {self.base_amount}"
