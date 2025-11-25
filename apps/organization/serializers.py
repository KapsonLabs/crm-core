from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Organization, OrganizationLicense, Branch, BranchSettings, BranchUser
from apps.accounts.models import Role

class RoleShortDetailsSerializer(serializers.ModelSerializer):
    """Short serializer for Role model."""
    class Meta:
        model = Role
        fields = ['id', 'name', 'slug']


class OrganizationSerializer(serializers.ModelSerializer):
    branch_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "description",
            "email",
            "phone_number",
            "website",
            "physical_address",
            "logo",
            "is_active",
            "branch_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "branch_count", "created_at", "updated_at"]


class OrganizationLicenseSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField()

    class Meta:
        model = OrganizationLicense
        fields = [
            "organization_id",
            "license_key",
            "plan",
            "status",
            "seats",
            "starts_on",
            "expires_on",
            "created_at",
            "updated_at",
            "is_active",
        ]
        read_only_fields = ["created_at", "updated_at", "is_active"]

    def validate(self, attrs):
        organization_id = attrs.get("organization_id")
        if not Organization.objects.filter(id=organization_id).exists():
            raise serializers.ValidationError({"organization_id": "Organization does not exist."})
        return attrs

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id")
        organization = Organization.objects.get(id=organization_id)
        instance, _ = OrganizationLicense.objects.update_or_create(
            organization=organization,
            defaults=validated_data,
        )
        return instance


class BranchSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "organization_id",
            "name",
            "code",
            "email",
            "phone_number",
            "address",
            "city",
            "country",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_organization_id(self, value):
        if not Organization.objects.filter(id=value).exists():
            raise serializers.ValidationError("Organization does not exist.")
        return value

    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id")
        organization = Organization.objects.get(id=organization_id)
        return Branch.objects.create(organization=organization, **validated_data)

    def update(self, instance, validated_data):
        # Prevent organization reassignment
        validated_data.pop("organization_id", None)
        return super().update(instance, validated_data)


class OrganizationShortDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name"]

class BranchShortDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name"]


class BranchSettingsSerializer(serializers.ModelSerializer):
    branch_id = serializers.UUIDField()

    class Meta:
        model = BranchSettings
        fields = [
            "branch_id",
            "timezone",
            "currency",
            "date_format",
            "language",
            "working_hours_start",
            "working_hours_end",
            "allow_weekend_operations",
            "notifications_email",
            "notifications_phone",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_branch_id(self, value):
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist.")
        return value

    def create(self, validated_data):
        branch_id = validated_data.pop("branch_id")
        branch = Branch.objects.get(id=branch_id)
        instance, _ = BranchSettings.objects.update_or_create(
            branch=branch,
            defaults=validated_data,
        )
        return instance

    def update(self, instance, validated_data):
        validated_data.pop("branch_id", None)
        return super().update(instance, validated_data)


class BranchUserSerializer(serializers.ModelSerializer):
    branch_id = serializers.UUIDField()
    user_id = serializers.UUIDField(source="user.id")
    role_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    role = RoleShortDetailsSerializer(read_only=True)

    class Meta:
        model = BranchUser
        fields = [
            "id",
            "branch_id",
            "user_id",
            "role_id",
            "role",
            "is_branch_admin",
            "is_active",
            "assigned_at",
            "assigned_by",
        ]
        read_only_fields = ["id", "role", "assigned_at", "assigned_by"]

    def validate_branch_id(self, value):
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist.")
        return value
    
    def validate_role_id(self, value):
        if value and not Role.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Role does not exist or is inactive.")
        return value

    def create(self, validated_data):
        branch_id = validated_data.pop("branch_id")
        role_id = validated_data.pop("role_id", None)
        user_data = validated_data.pop("user")
        branch = Branch.objects.get(id=branch_id)
        user_model = get_user_model()
        user = user_model.objects.get(id=user_data["id"])

        role = None
        if role_id:
            role = Role.objects.get(id=role_id)

        assigned_by = None
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            assigned_by = request.user

        branch_user, _ = BranchUser.objects.update_or_create(
            branch=branch,
            user=user,
            defaults={
                "role": role,
                "is_branch_admin": validated_data.get("is_branch_admin", False),
                "is_active": validated_data.get("is_active", True),
                "assigned_by": assigned_by,
            },
        )
        return branch_user

    def update(self, instance, validated_data):
        validated_data.pop("branch_id", None)
        role_id = validated_data.pop("role_id", None)

        if role_id is not None:
            if role_id:
                instance.role = Role.objects.get(id=role_id)
            else:
                instance.role = None

        for attr, value in validated_data.items():
            if attr == "user":
                continue
            setattr(instance, attr, value)
        instance.save()
        return instance

