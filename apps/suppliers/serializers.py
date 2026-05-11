from decimal import Decimal

from rest_framework import serializers

from apps.accounts.serializers import UserDetailsSerializer
from apps.jobs.serializers import ProductSummarySerializer
from apps.organization.serializers import (
    BranchShortDetailsSerializer,
    OrganizationShortDetailsSerializer,
)

from .models import LocalPurchaseOrder, LocalPurchaseOrderItem, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    organization = OrganizationShortDetailsSerializer(read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id',
            'organization',
            'branch',
            'name',
            'contact_name',
            'email',
            'phone_number',
            'physical_address',
            'tax_id',
            'payment_terms',
            'notes',
            'is_active',
            'created_at',
            'updated_at',
        ]


class SupplierCreateWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=255)
    contact_name = serializers.CharField(required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, default='')
    physical_address = serializers.CharField(required=False, allow_blank=True, default='')
    tax_id = serializers.CharField(required=False, allow_blank=True, default='')
    payment_terms = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    is_active = serializers.BooleanField(required=False, default=True)


class SupplierPatchWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=255, required=False)
    contact_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    physical_address = serializers.CharField(required=False, allow_blank=True)
    tax_id = serializers.CharField(required=False, allow_blank=True)
    payment_terms = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class LocalPurchaseOrderItemSerializer(serializers.ModelSerializer):
    product = ProductSummarySerializer(read_only=True)

    class Meta:
        model = LocalPurchaseOrderItem
        fields = [
            'id',
            'product',
            'description',
            'quantity',
            'quantity_received',
            'unit_price',
            'line_total',
            'deleted_status',
            'delivered_status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'product',
            'description',
            'quantity',
            'quantity_received',
            'unit_price',
            'line_total',
            'deleted_status',
            'delivered_status',
            'created_at',
            'updated_at',
        ]


class LocalPurchaseOrderItemWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal('0.0001'))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))


class LocalPurchaseOrderItemPatchWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=4, required=False, min_value=Decimal('0.0001'),
    )
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal('0'),
    )


class LocalPurchaseOrderLineUpsertPatchSerializer(serializers.Serializer):
    """Create when ``item_id`` omitted; patch existing line when ``item_id`` present."""

    item_id = serializers.UUIDField(required=False, allow_null=True)
    product_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=4, required=False, allow_null=True, min_value=Decimal('0.0001'),
    )
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=Decimal('0'),
    )

    def validate(self, attrs):
        iid = attrs.get('item_id')
        if iid:
            return attrs
        if attrs.get('quantity') is None or attrs.get('unit_price') is None:
            raise serializers.ValidationError(
                'quantity and unit_price are required when creating a line (no item_id).'
            )
        return attrs


class SupplierShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'phone_number', 'email']


class LocalPurchaseOrderSerializer(serializers.ModelSerializer):
    # organization = OrganizationShortDetailsSerializer(read_only=True)
    # branch = BranchShortDetailsSerializer(read_only=True)
    supplier = SupplierShortSerializer(read_only=True)
    created_by = UserDetailsSerializer(read_only=True)
    approved_by = UserDetailsSerializer(read_only=True)
    items = LocalPurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = LocalPurchaseOrder
        fields = [
            'id',
            'organization',
            'branch',
            'supplier',
            'job_id',
            'requisition_id',
            'lpo_number',
            'currency',
            'status',
            'subtotal',
            'total',
            'notes',
            'expected_delivery_date',
            'issued_at',
            'delivered_at',
            'created_by',
            'approved_by',
            'items',
            'created_at',
            'updated_at',
        ]


class LocalPurchaseOrderCreateWriteSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    job_id = serializers.UUIDField(required=False, allow_null=True)
    requisition_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, default='UGX', max_length=10)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    items = LocalPurchaseOrderItemWriteSerializer(many=True, min_length=1)


class LocalPurchaseOrderPatchWriteSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField(required=False)
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    job_id = serializers.UUIDField(required=False, allow_null=True)
    requisition_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, max_length=10)
    notes = serializers.CharField(required=False, allow_blank=True)
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    item_ids_to_delete = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
    )
    items = LocalPurchaseOrderLineUpsertPatchSerializer(many=True, required=False)


class LocalPurchaseOrderTransitionWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LocalPurchaseOrder.STATUS_CHOICES)


class ReceiveLineWriteSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity_received = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal('0'))


class LocalPurchaseOrderReceiveWriteSerializer(serializers.Serializer):
    lines = ReceiveLineWriteSerializer(many=True)
