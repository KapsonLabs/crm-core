from rest_framework import serializers

from apps.accounts.serializers import UserDetailsSerializer
from apps.customers.serializers import CustomerShortSerializer
from apps.jobs.models import Job
from apps.organization.serializers import (
    OrganizationShortDetailsSerializer,
    BranchShortDetailsSerializer,
)

from . import services
from .models import (
    BankAccount,
    Invoice,
    InvoicePayment,
    PAYMENT_METHOD_ACCOUNT_TYPE_CHOICES,
    PaymentMethod,
    Requisition,
)


class PaymentMethodAccountSerializer(serializers.Serializer):
    """Minimal GL account info embedded in PaymentMethod responses."""
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()


class PaymentMethodSerializer(serializers.ModelSerializer):
    branch = BranchShortDetailsSerializer(read_only=True)
    account = PaymentMethodAccountSerializer(read_only=True)

    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'branch', 'name', 'code', 'account_type', 'account',
            'description', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'branch', 'account', 'created_at', 'updated_at']


class PaymentMethodWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=100)
    code = serializers.CharField(max_length=50)
    account_type = serializers.ChoiceField(choices=PAYMENT_METHOD_ACCOUNT_TYPE_CHOICES)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    is_active = serializers.BooleanField(required=False, default=True)


class BankAccountSerializer(serializers.ModelSerializer):
    branch = BranchShortDetailsSerializer(read_only=True)
    payment_method = PaymentMethodSerializer(read_only=True)
    account_number = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            'id', 'branch', 'bank_name', 'account_name', 'account_number',
            'currency', 'payment_method', 'is_active', 'created_at', 'updated_at',
        ]

    def get_account_number(self, obj):
        return obj.masked_account_number


class BankAccountWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    bank_name = serializers.CharField(max_length=100)
    account_name = serializers.CharField(max_length=100)
    account_number = serializers.CharField(max_length=50)
    currency = serializers.CharField(max_length=10, required=False, default='UGX')


class JobOnInvoiceSerializer(serializers.ModelSerializer):
    customer = CustomerShortSerializer(read_only=True)

    class Meta:
        model = Job
        fields = ['id', 'title', 'customer']


class InvoicePaymentSerializer(serializers.ModelSerializer):
    recorded_by = UserDetailsSerializer(read_only=True)
    method = PaymentMethodSerializer(read_only=True)

    class Meta:
        model = InvoicePayment
        fields = [
            'id', 'amount', 'paid_at', 'method', 'reference',
            'recorded_by', 'created_at', 'updated_at',
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    job = JobOnInvoiceSerializer(read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'status', 'job', 'branch', 'currency',
            'total', 'balance_due', 'issued_at', 'due_at', 'created_at',
        ]

    def get_balance_due(self, obj):
        return str(services.invoice_balance_due(obj))


class InvoiceDetailSerializer(serializers.ModelSerializer):
    job = JobOnInvoiceSerializer(read_only=True)
    organization = OrganizationShortDetailsSerializer(read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)
    created_by = UserDetailsSerializer(read_only=True)
    payments = InvoicePaymentSerializer(many=True, read_only=True)
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'status', 'job', 'organization', 'branch',
            'currency', 'subtotal', 'tax_amount', 'total', 'balance_due',
            'issued_at', 'due_at', 'notes', 'payments',
            'created_by', 'created_at', 'updated_at',
        ]

    def get_balance_due(self, obj):
        return str(services.invoice_balance_due(obj))


class InvoiceForJobSerializer(serializers.ModelSerializer):
    """
    Invoice embedded in job detail. Omits nested job (parent context is the job).
    Uses the latest invoice by created_at when a job has void + replacement history.
    """

    organization = OrganizationShortDetailsSerializer(read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)
    created_by = UserDetailsSerializer(read_only=True)
    payments = InvoicePaymentSerializer(many=True, read_only=True)
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'status', 'organization', 'branch',
            'currency', 'subtotal', 'tax_amount', 'total', 'balance_due',
            'issued_at', 'due_at', 'notes', 'payments',
            'created_by', 'created_at', 'updated_at',
        ]

    def get_balance_due(self, obj):
        return str(services.invoice_balance_due(obj))


class InvoiceCreateWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=10, required=False, default='UGX')
    issued_at = serializers.DateField(required=False, allow_null=True)
    due_at = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class InvoicePatchWriteSerializer(serializers.Serializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=10, required=False)
    status = serializers.ChoiceField(choices=Invoice.STATUS_CHOICES, required=False)
    issued_at = serializers.DateField(required=False, allow_null=True)
    due_at = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class InvoicePaymentWriteSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method_id = serializers.UUIDField()
    reference = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_payment_method_id(self, value):
        if not PaymentMethod.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Payment method not found or inactive.")
        return value


class RequisitionSerializer(serializers.ModelSerializer):
    organization = OrganizationShortDetailsSerializer(read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)
    requested_by = UserDetailsSerializer(read_only=True)
    job = JobOnInvoiceSerializer(read_only=True)

    class Meta:
        model = Requisition
        fields = [
            'id', 'organization', 'branch', 'requested_by', 'job', 'title', 'description',
            'amount', 'currency', 'status', 'submitted_at', 'resolved_at',
            'created_at', 'updated_at',
        ]


class RequisitionCreateWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    job_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=10, required=False, default='UGX')
    status = serializers.ChoiceField(choices=Requisition.STATUS_CHOICES, required=False)


class RequisitionPatchWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    job_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(max_length=10, required=False)
    status = serializers.ChoiceField(choices=Requisition.STATUS_CHOICES, required=False)
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)
    resolved_at = serializers.DateTimeField(required=False, allow_null=True)
