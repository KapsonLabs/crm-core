from rest_framework import serializers

from apps.accounts.serializers import UserDetailsSerializer
from apps.organization.serializers import OrganizationShortDetailsSerializer

from .models import Customer, CustomerFeedback


class CustomerShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'first_name', 'last_name', 'phone_number', 'email']


class CustomerSerializer(serializers.ModelSerializer):
    organization = OrganizationShortDetailsSerializer(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'organization', 'first_name', 'last_name',
            'phone_number', 'email', 'is_active', 'created_at', 'updated_at',
        ]


class CustomerCreateWriteSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, default=True)


class CustomerPatchWriteSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    phone_number = serializers.CharField(max_length=20, required=False)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class CustomerFeedbackSerializer(serializers.ModelSerializer):
    customer = CustomerShortSerializer(read_only=True)
    submitted_by = UserDetailsSerializer(read_only=True)

    class Meta:
        model = CustomerFeedback
        fields = [
            'id', 'customer', 'submitted_by', 'subject', 'body',
            'rating', 'created_at', 'updated_at',
        ]


class CustomerFeedbackWriteSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)


class CustomerFeedbackPatchWriteSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255, required=False)
    body = serializers.CharField(required=False)
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
