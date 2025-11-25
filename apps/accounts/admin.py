from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Permission, Module, Role


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """Admin configuration for Module model."""
    list_display = ('name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin configuration for Permission model."""
    
    list_display = ('name', 'codename', 'resource', 'action', 'is_active', 'created_at')
    list_filter = ('resource', 'action', 'is_active', 'created_at')
    search_fields = ('name', 'codename', 'description')
    ordering = ('resource', 'action')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('name', 'codename', 'description')}),
        ('Permission Details', {'fields': ('resource', 'action', 'is_active')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin configuration for Role model."""
    
    list_display = ('name', 'slug', 'organization', 'role_type', 'is_active', 'created_at')
    list_filter = ('role_type', 'is_active', 'organization', 'created_at')
    search_fields = ('name', 'slug', 'description')
    filter_horizontal = ('permissions',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('name',)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related for foreign keys."""
        qs = super().get_queryset(request)
        return qs.select_related('organization', 'created_by')
    
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'description', 'role_type')}),
        ('Organization', {'fields': ('organization',)}),
        ('Permissions', {'fields': ('permissions',)}),
        ('Status', {'fields': ('is_active',)}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for the custom User model."""
    
    list_display = ('email', 'username', 'first_name', 'last_name', 'organization', 'branch', 'role', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'role', 'organization', 'branch', 'created_at')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related for foreign keys."""
        qs = super().get_queryset(request)
        return qs.select_related('organization', 'branch', 'role')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username', 'first_name', 'last_name', 'phone_number', 'date_of_birth')}),
        ('Organization', {'fields': ('organization', 'branch')}),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )

