import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

PAYMENT_METHOD_ACCOUNT_TYPE_CHOICES = [
    ("cash", _("Cash")),
    ("bank", _("Bank / Direct Debit")),
    ("card", _("Card / POS")),
    ("mobile_money", _("Mobile Money")),
    ("cheque", _("Cheque")),
]


class PaymentMethod(models.Model):
    """
    Branch-level payment method configuration.

    Each payment method owns a dedicated GL Account created atomically by
    create_payment_method(). The account field is a direct FK — accounting
    services use payment.method.account rather than an account_key lookup.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_methods',
        help_text="Leave blank for system-wide defaults available to all branches.",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=50,
        help_text="Unique slug used in API calls, e.g. 'mobile_money'.",
    )
    account_type = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_ACCOUNT_TYPE_CHOICES,
        help_text="Determines which GL code range is used when the account is created.",
    )
    account = models.ForeignKey(
        'ledgers.Account',
        on_delete=models.PROTECT,
        related_name='payment_methods',
        null=True,
        blank=True,
        help_text="Dedicated GL account created atomically with this payment method.",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financials_payment_method'
        verbose_name = _('payment method')
        verbose_name_plural = _('payment methods')
        unique_together = [('branch', 'code')]
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Invoice(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_PARTIALLY_PAID = 'partially_paid'
    STATUS_PAID = 'paid'
    STATUS_VOID = 'void'
    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Draft')),
        (STATUS_SENT, _('Sent')),
        (STATUS_PARTIALLY_PAID, _('Partially paid')),
        (STATUS_PAID, _('Paid')),
        (STATUS_VOID, _('Void')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='invoices',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoices',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_created',
    )
    invoice_number = models.CharField(max_length=32)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    currency = models.CharField(max_length=10, default='UGX')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    issued_at = models.DateField()
    due_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financials_invoice'
        ordering = ['-issued_at', '-created_at']
        unique_together = [['organization', 'invoice_number']]
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['job']),
            models.Index(fields=['branch', 'status']),
        ]

    def __str__(self):
        return self.invoice_number


class InvoicePayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(auto_now_add=True)
    method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='invoice_payments',
    )
    reference = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_payments_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financials_invoice_payment'
        ordering = ['-paid_at']

    def __str__(self):
        return f'{self.invoice.invoice_number} {self.amount}'


class BankAccount(models.Model):
    """
    Represents a real-world bank account held by a branch.

    Creating a BankAccount atomically creates a PaymentMethod (account_type='bank')
    which in turn creates a dedicated GL Account in the 1051–1059 range.
    Use bank_account.payment_method.account to get the GL Account for postings
    and reconciliation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.CASCADE,
        related_name='bank_accounts',
    )
    bank_name = models.CharField(max_length=100, help_text="e.g. 'Stanbic Bank Uganda'")
    account_name = models.CharField(max_length=100, help_text="e.g. 'Main Operating Account'")
    account_number = models.CharField(max_length=50)
    currency = models.CharField(max_length=10, default='UGX')
    payment_method = models.OneToOneField(
        PaymentMethod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bank_account',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financials_bank_account'
        ordering = ['bank_name', 'account_name']

    def __str__(self) -> str:
        return f'{self.bank_name} — {self.account_name}'

    @property
    def masked_account_number(self) -> str:
        if len(self.account_number) <= 4:
            return self.account_number
        return f"****{self.account_number[-4:]}"


class Requisition(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Draft')),
        (STATUS_SUBMITTED, _('Submitted')),
        (STATUS_APPROVED, _('Approved')),
        (STATUS_REJECTED, _('Rejected')),
        (STATUS_FULFILLED, _('Fulfilled')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='requisitions',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='requisitions',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requisitions',
    )
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisitions',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='UGX')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financials_requisition'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['branch', 'status']),
        ]

    def __str__(self):
        return self.title
