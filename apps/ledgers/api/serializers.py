from __future__ import annotations

from rest_framework import serializers

from apps.ledgers.models import (
    Account,
    ControlAccount,
    Currency,
    ExchangeRate,
    FiscalPeriod,
    InventoryAccrual,
    InventoryJournalEntry,
    InventoryJournalLine,
    InventoryLedgerEntry,
    InventoryValuationLayer,
    InventoryWriteDown,
    JournalEntry,
    JournalLine,
    LandedCostAllocation,
    LedgerEntry,
    ManufacturingCostAllocation,
    SubLedgerAccount,
    SubLedgerEntry,
)


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = [
            "id",
            "code",
            "name",
            "symbol",
            "decimal_places",
            "is_base_currency",
            "is_active",
        ]


class ExchangeRateSerializer(serializers.ModelSerializer):
    from_currency_code = serializers.CharField(source="from_currency.code", read_only=True)
    to_currency_code = serializers.CharField(source="to_currency.code", read_only=True)

    class Meta:
        model = ExchangeRate
        fields = [
            "id",
            "from_currency",
            "from_currency_code",
            "to_currency",
            "to_currency_code",
            "rate",
            "date",
            "source",
            "created_at",
        ]


class AccountSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "code",
            "name",
            "account_type",
            "category",
            "parent",
            "is_control_account",
            "allows_manual_posting",
            "currency",
            "currency_code",
            "branch",
            "is_active",
        ]


class ControlAccountSerializer(serializers.ModelSerializer):
    gl_account_code = serializers.CharField(source="gl_account.code", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = ControlAccount
        fields = [
            "id",
            "code",
            "name",
            "gl_account",
            "gl_account_code",
            "branch",
            "currency",
            "currency_code",
            "allows_manual_posting",
            "is_active",
            "metadata",
        ]


class SubLedgerAccountSerializer(serializers.ModelSerializer):
    parent_control_account_code = serializers.CharField(source="parent_control_account.code", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    gl_account_code = serializers.CharField(source="gl_account.code", read_only=True)

    class Meta:
        model = SubLedgerAccount
        fields = [
            "id",
            "account_code",
            "account_name",
            "entity_type",
            "entity_id",
            "ledger_purpose",
            "parent_control_account",
            "parent_control_account_code",
            "branch",
            "currency",
            "currency_code",
            "gl_account",
            "gl_account_code",
            "is_active",
            "metadata",
        ]


class SubLedgerEntrySerializer(serializers.ModelSerializer):
    subledger_account_code = serializers.CharField(source="subledger_account.account_code", read_only=True)

    class Meta:
        model = SubLedgerEntry
        fields = "__all__"


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = JournalLine
        fields = [
            "id",
            "account",
            "account_code",
            "account_name",
            "debit",
            "credit",
            "debit_foreign",
            "credit_foreign",
            "debit_base",
            "credit_base",
            "description",
            "party_type",
            "party_id",
            "currency",
            "currency_code",
            "exchange_rate",
            "branch",
            "subledger_account",
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "reference",
            "journal_type",
            "date",
            "description",
            "source_module",
            "source_id",
            "status",
            "posted_at",
            "reversed_entry",
            "created_by",
            "branch",
            "idempotency_key",
            "extra_data",
            "transaction_currency",
            "exchange_rate",
            "base_currency",
            "lines",
        ]
        read_only_fields = ["status", "posted_at", "reversed_entry"]


class FiscalPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalPeriod
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "branch",
            "is_closed",
            "closed_at",
            "closed_by",
        ]
        read_only_fields = ["closed_at", "closed_by"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    journal_reference = serializers.CharField(source="journal_line.journal_entry.reference", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "account",
            "account_code",
            "journal_line",
            "journal_reference",
            "date",
            "debit",
            "credit",
            "debit_foreign",
            "credit_foreign",
            "debit_base",
            "credit_base",
            "currency",
            "currency_code",
            "exchange_rate",
            "running_balance",
            "running_balance_base",
            "branch",
            "created_at",
            "subledger_account",
        ]


class InventoryValuationLayerSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = InventoryValuationLayer
        fields = "__all__"


class InventoryJournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = InventoryJournalLine
        fields = "__all__"


class InventoryJournalEntrySerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    lines = InventoryJournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryJournalEntry
        fields = "__all__"


class InventoryLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLedgerEntry
        fields = "__all__"


class LandedCostAllocationSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = LandedCostAllocation
        fields = "__all__"


class InventoryWriteDownSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryWriteDown
        fields = "__all__"


class ManufacturingCostAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManufacturingCostAllocation
        fields = "__all__"


class InventoryAccrualSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryAccrual
        fields = "__all__"
