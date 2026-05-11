from __future__ import annotations

import uuid

from django.db import models


class PrepaidExpenseSchedule(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_transaction = models.OneToOneField(
        "expense_accounting.ExpenseTransaction",
        on_delete=models.PROTECT,
        related_name="prepaid_schedule",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    total_months = models.PositiveSmallIntegerField()
    monthly_amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="Transaction currency")
    monthly_base_amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="UGX")
    remaining_balance = models.DecimalField(max_digits=18, decimal_places=2)
    remaining_base_balance = models.DecimalField(max_digits=18, decimal_places=2)
    next_run_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    last_run_at = models.DateTimeField(null=True, blank=True)
    amortizations_posted = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_run_date"]),
        ]

    def __str__(self) -> str:
        return f"Prepaid schedule — {self.expense_transaction.reference} ({self.status})"
