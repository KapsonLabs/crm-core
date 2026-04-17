from rest_framework import serializers

from apps.accounts.serializers import UserDetailsSerializer
from apps.customers.serializers import CustomerShortSerializer
from apps.organization.serializers import OrganizationShortDetailsSerializer, BranchShortDetailsSerializer

from .models import Job, JobAssignment, JobProduct, Product


class ProductSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'kind', 'name', 'price']


class ProductSerializer(serializers.ModelSerializer):
    organization = OrganizationShortDetailsSerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'organization', 'kind', 'name', 'description', 'price',
            'is_active', 'created_at', 'updated_at',
        ]


class ProductCreateWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Product.KIND_CHOICES)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, default=True)


class ProductPatchWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Product.KIND_CHOICES, required=False)
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class JobProductSerializer(serializers.ModelSerializer):
    product = ProductSummarySerializer(read_only=True)

    class Meta:
        model = JobProduct
        fields = ['id', 'product', 'quantity', 'unit_price', 'line_total', 'created_at', 'updated_at']


class JobAssignmentSerializer(serializers.ModelSerializer):
    user = UserDetailsSerializer(read_only=True)
    assigned_by = UserDetailsSerializer(read_only=True)

    class Meta:
        model = JobAssignment
        fields = ['id', 'job', 'user', 'assigned_by', 'assigned_at']
        read_only_fields = ['id', 'job', 'user', 'assigned_by', 'assigned_at']


class JobListSerializer(serializers.ModelSerializer):
    customer = CustomerShortSerializer(read_only=True)
    created_by = UserDetailsSerializer(read_only=True)
    assignee_count = serializers.IntegerField(read_only=True)
    job_products = JobProductSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'status', 'customer', 'created_by', 'assignee_count',
            'job_products',
            'created_at', 'updated_at',
        ]


class JobDetailSerializer(serializers.ModelSerializer):
    customer = CustomerShortSerializer(read_only=True)
    organization = OrganizationShortDetailsSerializer(read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)
    created_by = UserDetailsSerializer(read_only=True)
    completed_by = UserDetailsSerializer(read_only=True)
    closed_by = UserDetailsSerializer(read_only=True)
    assignments = JobAssignmentSerializer(many=True, read_only=True)
    job_products = JobProductSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'description', 'status',
            'customer', 'organization', 'branch',
            'created_by', 'assignments', 'job_products',
            'completed_at', 'completed_by', 'completion_notes',
            'closed_at', 'closed_by', 'closing_notes',
            'created_at', 'updated_at',
        ]


class JobProductLineWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        required=False,
    )
    unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )


class JobCreateWriteSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    status = serializers.ChoiceField(
        choices=Job.STATUS_CHOICES,
        required=False,
        default=Job.STATUS_OPEN,
    )
    job_products = JobProductLineWriteSerializer(many=True, required=False)


class JobPatchWriteSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField(required=False)
    branch_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Job.STATUS_CHOICES, required=False)


class JobAssignSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )


class JobCompleteSerializer(serializers.Serializer):
    completion_notes = serializers.CharField(required=False, allow_blank=True, default='')


class JobCloseSerializer(serializers.Serializer):
    closing_notes = serializers.CharField(required=False, allow_blank=True, default='')
