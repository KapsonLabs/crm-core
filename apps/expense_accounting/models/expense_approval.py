from __future__ import annotations

import uuid

from django.db import models


class ExpenseApproval(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ESCALATED = "escalated", "Escalated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_transaction = models.ForeignKey(
        "expense_accounting.ExpenseTransaction",
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    approver = models.UUIDField(null=True, blank=True, db_index=True)
    approval_level = models.PositiveSmallIntegerField(
        help_text="1=manager, 2=finance, 3=CFO"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["approval_level", "created_at"]
        indexes = [
            models.Index(fields=["expense_transaction", "status"]),
            models.Index(fields=["approver", "status"]),
        ]

    def __str__(self) -> str:
        return f"Level {self.approval_level} approval — {self.expense_transaction.reference} ({self.status})"
