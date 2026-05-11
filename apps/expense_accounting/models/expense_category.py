from __future__ import annotations

import uuid

from django.db import models


class ExpenseCategory(models.Model):
    class ExpenseType(models.TextChoices):
        OPERATIONAL = "operational", "Operational"
        SUPPLIER = "supplier", "Supplier Invoice"
        EMPLOYEE = "employee_reimbursement", "Employee Reimbursement"
        PREPAID = "prepaid", "Prepaid Expense"
        ACCRUAL = "accrual", "Accrued Expense"
        CAPITAL = "capital", "Capitalizable Expense"
        DEFERRED = "deferred", "Deferred Expense"
        CORPORATE_CARD = "corporate_card", "Corporate Card"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    expense_type = models.CharField(max_length=32, choices=ExpenseType.choices)
    default_expense_account = models.ForeignKey(
        "ledgers.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expense_categories_expense",
    )
    default_tax_account = models.ForeignKey(
        "ledgers.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expense_categories_tax",
    )
    default_credit_account = models.ForeignKey(
        "ledgers.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expense_categories_credit",
        help_text="Default AP or cash account for the credit side of the journal.",
    )
    requires_approval = models.BooleanField(default=True)
    is_capitalizable = models.BooleanField(default=False)
    is_prepaid_eligible = models.BooleanField(default=False)
    requires_project = models.BooleanField(default=False)
    requires_department = models.BooleanField(default=False)
    approval_required_above = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="UGX threshold above which approval is required. NULL means always required.",
    )
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["expense_type", "is_active"]),
            models.Index(fields=["branch", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_expense_type_display()})"
