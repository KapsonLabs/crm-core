from __future__ import annotations

import uuid

from django.db import models


class ExpenseTransaction(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        POSTED = "posted", "Posted"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        REVERSED = "reversed", "Reversed"

    class ApprovalStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not Required"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    expense_category = models.ForeignKey(
        "expense_accounting.ExpenseCategory",
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    vendor = models.CharField(max_length=255, blank=True)
    employee = models.UUIDField(null=True, blank=True, db_index=True)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    department = models.CharField(max_length=120, blank=True, db_index=True)
    project = models.CharField(max_length=120, blank=True, db_index=True)
    cost_center = models.CharField(max_length=120, blank=True, db_index=True)
    currency = models.ForeignKey(
        "ledgers.Currency",
        on_delete=models.PROTECT,
        related_name="expense_transactions",
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6)
    amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="Transaction currency amount (before tax)")
    base_amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="UGX equivalent of amount")
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_base_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, help_text="UGX equivalent of tax_amount")
    description = models.TextField()
    expense_date = models.DateField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    approval_status = models.CharField(
        max_length=16, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    payment_status = models.CharField(
        max_length=8, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    created_by = models.UUIDField()
    approved_by = models.UUIDField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    journal_entry = models.ForeignKey(
        "ledgers.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="expense_transactions",
    )
    reversal_journal_entry = models.ForeignKey(
        "ledgers.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="expense_reversals",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["status", "expense_date"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["department", "expense_date"]),
            models.Index(fields=["project", "expense_date"]),
            models.Index(fields=["employee", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.expense_category.name} ({self.status})"

    @property
    def gross_amount(self):
        return self.amount + self.tax_amount

    @property
    def gross_base_amount(self):
        return self.base_amount + self.tax_base_amount
