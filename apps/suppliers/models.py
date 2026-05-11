import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='suppliers',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='suppliers',
    )
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True)
    physical_address = models.CharField(max_length=500, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    payment_terms = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers_supplier'
        ordering = ['name']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['branch', 'name']),
        ]

    def __str__(self):
        return self.name


class LocalPurchaseOrder(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_ISSUED = 'issued'
    STATUS_IN_TRANSIT = 'in_transit'
    STATUS_PARTIALLY_RECEIVED = 'partially_received'
    STATUS_RECEIVED = 'received'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Draft')),
        (STATUS_ISSUED, _('Issued')),
        (STATUS_IN_TRANSIT, _('In transit')),
        (STATUS_PARTIALLY_RECEIVED, _('Partially received')),
        (STATUS_RECEIVED, _('Received')),
        (STATUS_CANCELLED, _('Cancelled')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'organization.Organization',
        on_delete=models.CASCADE,
        related_name='local_purchase_orders',
    )
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='local_purchase_orders',
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='local_purchase_orders',
    )
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_purchase_orders',
    )
    requisition = models.ForeignKey(
        'financials.Requisition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_purchase_orders',
    )
    lpo_number = models.CharField(max_length=64, blank=True, null=True)
    currency = models.CharField(max_length=10, default='UGX')
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_purchase_orders_created',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_purchase_orders_approved',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers_local_purchase_order'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['supplier', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'lpo_number'],
                condition=models.Q(lpo_number__isnull=False),
                name='suppliers_lpo_org_number_uniq_when_set',
            ),
        ]

    def __str__(self):
        label = self.lpo_number or str(self.pk)[:8]
        return f'LPO {label}'


class LocalPurchaseOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lpo = models.ForeignKey(
        LocalPurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'jobs.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='lpo_lines',
    )
    description = models.CharField(max_length=512, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('1'))
    quantity_received = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deleted_status = models.BooleanField(default=False)
    delivered_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers_local_purchase_order_item'
        ordering = ['lpo', 'created_at']

    def clean(self):
        errors = {}
        if self.quantity <= 0:
            errors['quantity'] = _('Quantity must be greater than zero.')
        if self.quantity_received < 0:
            errors['quantity_received'] = _('Quantity received cannot be negative.')
        if self.quantity_received > self.quantity:
            errors['quantity_received'] = _(
                'Quantity received cannot exceed quantity ordered.'
            )
        has_product = self.product_id is not None
        if not has_product and not (self.description and self.description.strip()):
            errors['description'] = _('Description is required when no product is linked.')
        if self.delivered_status and self.quantity_received < self.quantity:
            errors['delivered_status'] = _(
                'Delivered status requires quantity received to be at least the ordered quantity.'
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Item {self.pk} on {self.lpo_id}'
