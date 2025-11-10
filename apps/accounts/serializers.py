from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from .models import User, Permission, Module, Role


class ModuleSerializer(serializers.ModelSerializer):
    """Serializer for Module model."""
    permissions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Module
        fields = ['id', 'name', 'description', 'is_active', 'permissions_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_permissions_count(self, obj):
        """Get the number of permissions for this module."""
        return obj.permissions.filter(is_active=True).count()


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model."""
    resource_name = serializers.CharField(source='resource.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = Permission
        fields = [
            'id', 'name', 'codename', 'description', 'resource', 'resource_name',
            'action', 'action_display', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PermissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating permissions."""
    
    class Meta:
        model = Permission
        fields = ['name', 'codename', 'description', 'resource', 'action', 'is_active']
    
    def validate(self, data):
        """Validate that the resource and action combination is unique."""
        resource = data.get('resource')
        action = data.get('action')
        
        if resource and action:
            # Check if combination already exists (for create)
            if not self.instance and Permission.objects.filter(resource=resource, action=action).exists():
                raise serializers.ValidationError(
                    f"Permission with resource '{resource}' and action '{action}' already exists."
                )
        
        return data


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model."""
    permissions = PermissionSerializer(many=True, read_only=True)
    permissions_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    permissions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'slug', 'description', 'role_type', 'permissions',
            'permissions_ids', 'permissions_count', 'is_active', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_permissions_count(self, obj):
        """Get the number of permissions for this role."""
        return obj.permissions.filter(is_active=True).count()
    
    def create(self, validated_data):
        permissions_ids = validated_data.pop('permissions_ids', [])
        role = Role.objects.create(**validated_data)
        
        if permissions_ids:
            permissions = Permission.objects.filter(id__in=permissions_ids)
            role.permissions.set(permissions)
        
        return role
    
    def update(self, instance, validated_data):
        permissions_ids = validated_data.pop('permissions_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if permissions_ids is not None:
            permissions = Permission.objects.filter(id__in=permissions_ids)
            instance.permissions.set(permissions)
        
        return instance


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    role = RoleSerializer(read_only=True)
    role_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'phone_number', 'date_of_birth', 'role', 'role_id', 'permissions',
            'is_active', 'is_staff', 'is_superuser', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_permissions(self, obj):
        """Get all permissions for this user through their role."""
        if obj.role and obj.role.is_active:
            return obj.role.get_permissions_list()
        return []
    
    def update(self, instance, validated_data):
        role_id = validated_data.pop('role_id', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if role_id is not None:
            try:
                role = Role.objects.get(id=role_id)
                instance.role = role
            except Role.DoesNotExist:
                pass
        
        instance.save()
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users."""
    password = serializers.CharField(write_only=True, required=True)
    role_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'first_name', 'last_name', 
            'phone_number', 'date_of_birth', 'role_id', 'is_active', 'is_staff'
        ]
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        role_id = validated_data.pop('role_id', None)
        user = User(**validated_data)
        user.set_password(password)
        
        if role_id:
            try:
                role = Role.objects.get(id=role_id)
                user.role = role
            except Role.DoesNotExist:
                pass
        
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating users."""
    role_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 
            'phone_number', 'date_of_birth', 'role_id', 'is_active', 'is_staff'
        ]
    
    def update(self, instance, validated_data):
        role_id = validated_data.pop('role_id', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if role_id is not None:
            try:
                role = Role.objects.get(id=role_id)
                instance.role = role
            except Role.DoesNotExist:
                instance.role = None
        
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, data):
        """Validate password change request."""
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        if data['new_password'] == data['old_password']:
            raise serializers.ValidationError({"new_password": "New password must be different from old password."})
        
        return data
    
    def validate_old_password(self, value):
        """Validate that old password is correct."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer that includes user data and uses email for authentication."""
    username_field = 'email'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Replace username field with email field
        self.fields['email'] = self.fields.pop('username')
    
    def validate(self, attrs):
        # Rename email back to username for parent validation
        if 'email' in attrs:
            attrs['username'] = attrs.pop('email')
        
        data = super().validate(attrs)
        
        # Add user data to response
        user_serializer = UserSerializer(self.user)
        data['user'] = user_serializer.data
        
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone_number', 'date_of_birth'
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'phone_number': {'required': False},
            'date_of_birth': {'required': False},
        }
    
    def validate(self, attrs):
        """Validate that passwords match."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "Password fields didn't match."
            })
        return attrs
    
    def create(self, validated_data):
        """Create a new user."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        """Validate user credentials."""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'email': 'Invalid email or password.'
                })
            
            if not user.check_password(password):
                raise serializers.ValidationError({
                    'email': 'Invalid email or password.'
                })
            
            if not user.is_active:
                raise serializers.ValidationError({
                    'email': 'User account is disabled.'
                })
            
            attrs['user'] = user
        else:
            raise serializers.ValidationError({
                'email': 'Must include "email" and "password".'
            })
        
        return attrs

