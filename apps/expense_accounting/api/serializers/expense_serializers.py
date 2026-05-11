from __future__ import annotations

from rest_framework import serializers

from apps.expense_accounting.models import (
    CorporateCardTransaction,
    ExpenseApproval,
    ExpenseBudget,
    ExpenseCategory,
    ExpenseLine,
    ExpenseTransaction,
    PrepaidExpenseSchedule,
)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = [
            "id", "name", "expense_type", "default_expense_account",
            "default_tax_account", "default_credit_account",
            "requires_approval", "is_capitalizable", "is_prepaid_eligible",
            "requires_project", "requires_department",
            "approval_required_above", "branch", "is_active",
        ]
        read_only_fields = ["id"]


class ExpenseLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseLine
        fields = [
            "id", "expense_account", "amount", "base_amount",
            "tax_amount", "tax_base_amount",
            "department", "project", "cost_center", "description", "order",
        ]
        read_only_fields = ["id", "base_amount", "tax_base_amount"]


class ExpenseApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseApproval
        fields = ["id", "approver", "approval_level", "status", "approved_at", "remarks", "created_at"]
        read_only_fields = ["id", "created_at"]


class ExpenseTransactionSerializer(serializers.ModelSerializer):
    lines = ExpenseLineSerializer(many=True, read_only=True)
    approvals = ExpenseApprovalSerializer(many=True, read_only=True)
    expense_category_name = serializers.CharField(source="expense_category.name", read_only=True)
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    gross_base_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = ExpenseTransaction
        fields = [
            "id", "reference", "expense_category", "expense_category_name",
            "vendor", "employee", "branch", "department", "project", "cost_center",
            "currency", "currency_code", "exchange_rate",
            "amount", "base_amount", "tax_amount", "tax_base_amount", "gross_base_amount",
            "description", "expense_date",
            "status", "approval_status", "payment_status",
            "created_by", "approved_by", "posted_at", "notes",
            "lines", "approvals",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "base_amount", "tax_base_amount", "exchange_rate",
            "approval_status", "status", "payment_status",
            "approved_by", "posted_at", "created_at", "updated_at",
        ]


class CreateExpenseSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)
    expense_category_id = serializers.UUIDField()
    vendor = serializers.CharField(max_length=255, default="")
    employee = serializers.UUIDField(allow_null=True, required=False)
    branch = serializers.UUIDField(allow_null=True, required=False)
    department = serializers.CharField(max_length=120, default="")
    project = serializers.CharField(max_length=120, default="")
    cost_center = serializers.CharField(max_length=120, default="")
    currency_code = serializers.CharField(max_length=8, default="UGX")
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=2, default=0)
    description = serializers.CharField()
    expense_date = serializers.DateField()
    notes = serializers.CharField(default="")
    lines = serializers.ListField(child=serializers.DictField(), required=False)


class PostExpenseSerializer(serializers.Serializer):
    credit_account_id = serializers.UUIDField(allow_null=True, required=False)
    fiscal_period_id = serializers.UUIDField(allow_null=True, required=False)
    enforce_budget = serializers.BooleanField(default=True)


class PayExpenseSerializer(serializers.Serializer):
    payment_date = serializers.DateField()
    cash_account_id = serializers.UUIDField()


class ApproveExpenseSerializer(serializers.Serializer):
    remarks = serializers.CharField(default="")


class ReverseExpenseSerializer(serializers.Serializer):
    reversal_date = serializers.DateField()
    reason = serializers.CharField(default="")
    fiscal_period_id = serializers.UUIDField(allow_null=True, required=False)


class PrepaidExpenseScheduleSerializer(serializers.ModelSerializer):
    expense_reference = serializers.CharField(source="expense_transaction.reference", read_only=True)

    class Meta:
        model = PrepaidExpenseSchedule
        fields = [
            "id", "expense_transaction", "expense_reference",
            "start_date", "end_date", "total_months",
            "monthly_amount", "monthly_base_amount",
            "remaining_balance", "remaining_base_balance",
            "next_run_date", "status", "amortizations_posted",
            "last_run_at", "created_at",
        ]
        read_only_fields = ["id", "total_months", "amortizations_posted", "last_run_at", "created_at"]


class ExpenseBudgetSerializer(serializers.ModelSerializer):
    remaining_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = ExpenseBudget
        fields = [
            "id", "fiscal_period_id", "department", "branch", "project",
            "expense_category", "budget_amount", "consumed_amount", "remaining_amount",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "consumed_amount", "remaining_amount", "created_at", "updated_at"]


class CorporateCardTransactionSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = CorporateCardTransaction
        fields = [
            "id", "card_reference", "employee", "expense_transaction",
            "transaction_date", "amount", "base_amount",
            "currency", "currency_code", "exchange_rate",
            "merchant", "reconciled", "reconciled_at", "branch", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
