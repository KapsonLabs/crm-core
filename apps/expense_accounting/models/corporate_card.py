from __future__ import annotations

import uuid

from django.db import models


class CorporateCardTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card_reference = models.CharField(max_length=64, db_index=True)
    employee = models.UUIDField(db_index=True)
    expense_transaction = models.ForeignKey(
        "expense_accounting.ExpenseTransaction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="card_transactions",
    )
    transaction_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    base_amount = models.DecimalField(max_digits=18, decimal_places=2, help_text="UGX equivalent")
    currency = models.ForeignKey(
        "ledgers.Currency",
        on_delete=models.PROTECT,
        related_name="card_transactions",
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6)
    merchant = models.CharField(max_length=255)
    reconciled = models.BooleanField(default=False, db_index=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        indexes = [
            models.Index(fields=["employee", "reconciled"]),
            models.Index(fields=["card_reference", "transaction_date"]),
        ]

    def __str__(self) -> str:
        return f"Card {self.card_reference} — {self.merchant} {self.amount} {self.currency_id}"
