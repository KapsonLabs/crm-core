from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .constants import DEBIT_NORMAL_ACCOUNT_TYPES, DEFAULT_CURRENCY


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Currency(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=3, unique=True, db_index=True)
    name = models.CharField(max_length=64)
    symbol = models.CharField(max_length=8, blank=True, default="")
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_base_currency = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_base_currency"],
                condition=Q(is_base_currency=True),
                name="ledgers_single_base_currency",
            ),
        ]

    def clean(self) -> None:
        if self.is_base_currency and self.code != DEFAULT_CURRENCY:
            raise ValidationError(f"The system base currency must be {DEFAULT_CURRENCY}.")

    def __str__(self) -> str:
        return self.code


class ExchangeRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="exchange_rates_from",
    )
    to_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="exchange_rates_to",
    )
    rate = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0.000001"))],
    )
    date = models.DateField(db_index=True)
    source = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_currency", "to_currency", "date", "source"],
                name="ledgers_exchange_rate_unique_daily_source",
            ),
            models.CheckConstraint(
                check=~Q(from_currency=models.F("to_currency")),
                name="ledgers_exchange_rate_distinct_currency_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["from_currency", "to_currency", "date"]),
        ]

    def save(self, *args, **kwargs):  # type: ignore[override]
        if self.pk and ExchangeRate.objects.filter(pk=self.pk).exists():
            raise ValidationError("Exchange rates are immutable. Create a new rate row instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[override]
        raise ValidationError("Exchange rates are immutable and cannot be deleted.")


class Account(TimeStampedModel):
    class AccountType(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    category = models.CharField(max_length=64, db_index=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    is_control_account = models.BooleanField(default=False)
    allows_manual_posting = models.BooleanField(default=True)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        indexes = [
            models.Index(fields=["branch", "code"]),
            models.Index(fields=["branch", "account_type"]),
            models.Index(fields=["parent", "is_active"]),
        ]

    def clean(self) -> None:
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError("An account cannot be its own parent.")
        if self.parent and self.parent.branch != self.branch:
            raise ValidationError("Parent account branch must match child branch.")

    @property
    def normal_balance(self) -> str:
        return "debit" if self.account_type in DEBIT_NORMAL_ACCOUNT_TYPES else "credit"

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ControlAccount(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    gl_account = models.OneToOneField(
        Account,
        on_delete=models.PROTECT,
        related_name="control_account_profile",
    )
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="control_accounts",
    )
    allows_manual_posting = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["code"]
        indexes = [models.Index(fields=["branch", "code"])]

    def clean(self) -> None:
        if not self.gl_account.is_control_account:
            raise ValidationError("ControlAccount must reference an Account marked as a control account.")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class SubLedgerAccount(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_code = models.CharField(max_length=64, unique=True, db_index=True)
    account_name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    ledger_purpose = models.CharField(max_length=64, default="primary", db_index=True)
    parent_control_account = models.ForeignKey(
        ControlAccount,
        on_delete=models.PROTECT,
        related_name="subledgers",
    )
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="subledger_accounts",
    )
    gl_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subledger_accounts",
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["account_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entity_type", "entity_id", "ledger_purpose", "parent_control_account"],
                name="ledgers_subledger_unique_per_entity_purpose_control",
            )
        ]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["branch", "ledger_purpose"]),
        ]

    def __str__(self) -> str:
        return f"{self.account_code} - {self.account_name}"


class FiscalPeriod(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64)
    start_date = models.DateField()
    end_date = models.DateField()
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="closed_fiscal_periods",
    )

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="ledgers_period_end_after_start",
            ),
        ]
        indexes = [models.Index(fields=["branch", "start_date", "end_date"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date} - {self.end_date})"


class AccountingConfiguration(TimeStampedModel):
    class CostingMethod(models.TextChoices):
        FIFO = "fifo", "FIFO"
        WEIGHTED_AVERAGE = "weighted_average", "Weighted Average"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.UUIDField(null=True, blank=True, unique=True)
    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="accounting_configurations",
    )
    inventory_costing_method = models.CharField(
        max_length=32,
        choices=CostingMethod.choices,
        default=CostingMethod.WEIGHTED_AVERAGE,
    )
    allow_manual_journal_posting = models.BooleanField(default=False)
    auto_post_subledgers = models.BooleanField(default=True)
    enable_multi_currency = models.BooleanField(default=True)
    default_accounts = models.JSONField(default=dict, blank=True)
    reporting_preferences = models.JSONField(default=dict, blank=True)

    def clean(self) -> None:
        if self.base_currency.code != DEFAULT_CURRENCY:
            raise ValidationError(f"Accounting configuration base currency must be {DEFAULT_CURRENCY}.")

    def __str__(self) -> str:
        return f"Accounting Configuration [{self.branch or 'global'}]"


class JournalEntry(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        REVERSED = "reversed", "Reversed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=64, db_index=True)
    journal_type = models.CharField(max_length=64, db_index=True)
    date = models.DateField(db_index=True)
    description = models.TextField(blank=True, default="")
    source_module = models.CharField(max_length=64, db_index=True)
    source_id = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    posted_at = models.DateTimeField(null=True, blank=True)
    reversed_entry = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal_of",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=128, blank=True, default="")
    extra_data = models.JSONField(default=dict, blank=True)
    transaction_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="transaction_journals",
    )
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=Decimal("1.000000"),
        validators=[MinValueValidator(Decimal("0.000001"))],
    )
    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="base_currency_journals",
    )

    class Meta:
        ordering = ["-date", "reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_module", "source_id", "idempotency_key"],
                name="ledgers_journal_idempotency_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["branch", "date"]),
            models.Index(fields=["source_module", "source_id"]),
        ]

    def mark_posted(self) -> None:
        self.status = self.Status.POSTED
        self.posted_at = timezone.now()

    def __str__(self) -> str:
        return self.reference


class JournalLine(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    description = models.CharField(max_length=255, blank=True, default="")
    party_type = models.CharField(max_length=32, blank=True, default="")
    party_id = models.CharField(max_length=64, blank=True, default="")
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=Decimal("1.000000"),
        validators=[MinValueValidator(Decimal("0.000001"))],
    )
    subledger_account = models.ForeignKey(
        SubLedgerAccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    debit_foreign = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_foreign = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    debit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    branch = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(debit_base__gt=0) & models.Q(credit_base=0))
                    | (models.Q(credit_base__gt=0) & models.Q(debit_base=0))
                ),
                name="ledgers_journal_line_single_sided",
            ),
        ]
        indexes = [models.Index(fields=["journal_entry", "account"])]

    def clean(self) -> None:
        if self.branch != self.journal_entry.branch:
            raise ValidationError("Journal line branch must match journal entry branch.")
        if self.debit != self.debit_base or self.credit != self.credit_base:
            raise ValidationError("Legacy debit/credit mirrors must equal base amounts in UGX.")
        if self.account.is_control_account and self.subledger_account_id is None and not self.account.allows_manual_posting:
            raise ValidationError("Posting to restricted control accounts requires a subledger account.")

    @property
    def amount(self) -> Decimal:
        return self.debit_base or self.credit_base


class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    journal_line = models.OneToOneField(
        JournalLine,
        on_delete=models.PROTECT,
        related_name="ledger_entry",
    )
    date = models.DateField(db_index=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=Decimal("1.000000"),
    )
    debit_foreign = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_foreign = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    debit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    subledger_account = models.ForeignKey(
        SubLedgerAccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    running_balance = models.DecimalField(max_digits=18, decimal_places=2)
    running_balance_base = models.DecimalField(max_digits=18, decimal_places=2)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "created_at", "id"]
        indexes = [
            models.Index(fields=["account", "branch", "date"]),
            models.Index(fields=["branch", "date"]),
        ]

    def save(self, *args, **kwargs):  # type: ignore[override]
        if self.pk and LedgerEntry.objects.filter(pk=self.pk).exists():
            raise ValidationError("Ledger entries are immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[override]
        raise ValidationError("Ledger entries are immutable and cannot be deleted.")


class RecurringAccrual(TimeStampedModel):
    class Frequency(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        YEARLY = "yearly", "Yearly"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    source_module = models.CharField(max_length=64)
    source_id = models.CharField(max_length=64)
    accrual_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="accrual_deferrals",
    )
    offset_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="accrual_offsets",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    next_run_date = models.DateField()
    frequency = models.CharField(max_length=16, choices=Frequency.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_run_date", "branch"])]


class AssetDepreciationSchedule(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        POSTED = "posted", "Posted"
        DISPOSED = "disposed", "Disposed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_reference = models.CharField(max_length=64, db_index=True)
    asset_name = models.CharField(max_length=255)
    asset_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="depreciating_assets",
    )
    accumulated_depreciation_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="asset_accumulated_depreciation",
    )
    depreciation_expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="asset_depreciation_expenses",
    )
    acquisition_cost = models.DecimalField(max_digits=18, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    useful_life_months = models.PositiveIntegerField()
    depreciation_start_date = models.DateField()
    depreciation_date = models.DateField(db_index=True)
    depreciation_amount = models.DecimalField(max_digits=18, decimal_places=2)
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    book_value = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    posted_journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="depreciation_schedules",
    )
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["asset_reference", "depreciation_date", "status"])]


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=64, db_index=True)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_audit_logs",
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event_type", "entity_type", "entity_id"])]

    def save(self, *args, **kwargs):  # type: ignore[override]
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit log entries are immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[override]
        raise ValidationError("Audit log entries are immutable and cannot be deleted.")


class InventoryValuationLayer(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item_id = models.UUIDField(db_index=True)
    warehouse_id = models.UUIDField(db_index=True)
    batch_id = models.CharField(max_length=64, blank=True, default="")
    serial_number = models.CharField(max_length=128, blank=True, default="")
    quantity_remaining = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="inventory_valuation_layers",
    )
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("1.000000"))
    base_unit_cost = models.DecimalField(max_digits=18, decimal_places=4)
    acquisition_date = models.DateField(db_index=True)
    source_transaction = models.CharField(max_length=128, db_index=True)
    costing_method = models.CharField(max_length=32, default="fifo")
    branch = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["acquisition_date", "created_at", "id"]
        indexes = [
            models.Index(fields=["inventory_item_id", "warehouse_id", "acquisition_date"]),
            models.Index(fields=["branch", "inventory_item_id", "warehouse_id"]),
        ]


class InventoryJournalEntry(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        REVERSED = "reversed", "Reversed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=64, db_index=True)
    journal_type = models.CharField(max_length=64, db_index=True)
    transaction_date = models.DateField(db_index=True)
    posting_date = models.DateField(db_index=True)
    source_module = models.CharField(max_length=64, db_index=True)
    source_id = models.CharField(max_length=64, db_index=True)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="inventory_journals",
    )
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("1.000000"))
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    description = models.TextField(blank=True, default="")
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-posting_date", "reference"]
        indexes = [
            models.Index(fields=["branch", "posting_date"]),
            models.Index(fields=["source_module", "source_id"]),
        ]


class InventoryJournalLine(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(
        InventoryJournalEntry,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="inventory_journal_lines",
    )
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    debit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="inventory_journal_lines",
    )
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("1.000000"))
    subledger_account = models.ForeignKey(
        SubLedgerAccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_journal_lines",
    )
    warehouse_id = models.UUIDField(null=True, blank=True, db_index=True)
    inventory_item_id = models.UUIDField(null=True, blank=True, db_index=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    description = models.CharField(max_length=255, blank=True, default="")
    branch = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                check=((models.Q(debit_base__gt=0) & models.Q(credit_base=0)) | (models.Q(credit_base__gt=0) & models.Q(debit_base=0))),
                name="ledgers_inventory_journal_line_single_sided",
            )
        ]


class InventoryLedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item_id = models.UUIDField(db_index=True)
    warehouse_id = models.UUIDField(db_index=True)
    quantity_in = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    quantity_out = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    running_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    inventory_value = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    inventory_value_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    valuation_layer = models.ForeignKey(
        InventoryValuationLayer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    journal_line = models.OneToOneField(
        InventoryJournalLine,
        on_delete=models.PROTECT,
        related_name="inventory_ledger_entry",
    )
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "created_at", "id"]
        indexes = [
            models.Index(fields=["inventory_item_id", "warehouse_id", "date"]),
            models.Index(fields=["branch", "warehouse_id", "date"]),
        ]

    def save(self, *args, **kwargs):  # type: ignore[override]
        if self.pk and InventoryLedgerEntry.objects.filter(pk=self.pk).exists():
            raise ValidationError("Inventory ledger entries are immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[override]
        raise ValidationError("Inventory ledger entries are immutable and cannot be deleted.")


class LandedCostAllocation(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment_reference = models.CharField(max_length=128, db_index=True)
    cost_type = models.CharField(max_length=64)
    allocation_method = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="landed_cost_allocations",
    )
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("1.000000"))
    allocated_at = models.DateTimeField()
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    allocation_basis = models.JSONField(default=dict, blank=True)


class InventoryWriteDown(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item_id = models.UUIDField(db_index=True)
    warehouse_id = models.UUIDField(db_index=True)
    original_value = models.DecimalField(max_digits=18, decimal_places=2)
    nrv_value = models.DecimalField(max_digits=18, decimal_places=2)
    write_down_amount = models.DecimalField(max_digits=18, decimal_places=2)
    reversal_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    assessment_date = models.DateField(db_index=True)
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="active")
    branch = models.UUIDField(null=True, blank=True, db_index=True)


class ManufacturingCostAllocation(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.CharField(max_length=128, db_index=True)
    direct_material_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    direct_labor_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    variable_overhead = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    fixed_overhead = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    unit_cost = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    output_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0.0000"))
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)


class InventoryAccrual(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVERSED = "reversed", "Reversed"
        SETTLED = "settled", "Settled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier_invoice_reference = models.CharField(max_length=128, db_index=True)
    inventory_item_id = models.UUIDField(null=True, blank=True, db_index=True)
    warehouse_id = models.UUIDField(null=True, blank=True, db_index=True)
    accrued_amount = models.DecimalField(max_digits=18, decimal_places=2)
    accrual_date = models.DateField(db_index=True)
    reversal_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)


class SubLedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subledger_account = models.ForeignKey(
        SubLedgerAccount,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    journal_line = models.ForeignKey(
        JournalLine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subledger_entries",
    )
    inventory_journal_line = models.ForeignKey(
        InventoryJournalLine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subledger_entries",
    )
    date = models.DateField(db_index=True)
    debit_foreign = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_foreign = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    debit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit_base = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    running_balance_base = models.DecimalField(max_digits=18, decimal_places=2)
    branch = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "created_at", "id"]
        indexes = [
            models.Index(fields=["subledger_account", "date"]),
            models.Index(fields=["branch", "date"]),
        ]

    def save(self, *args, **kwargs):  # type: ignore[override]
        if self.pk and SubLedgerEntry.objects.filter(pk=self.pk).exists():
            raise ValidationError("Subledger entries are immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[override]
        raise ValidationError("Subledger entries are immutable and cannot be deleted.")
