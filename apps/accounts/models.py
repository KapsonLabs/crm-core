from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
import uuid


class Module(models.Model):
    """
    Module model to define modules in the system.
    Modules are the main areas of the system.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Module name (e.g., 'Products')")
    description = models.TextField(blank=True, help_text="Description of this module")
    is_active = models.BooleanField(default=True, help_text="Whether this module is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('module')
        verbose_name_plural = _('modules')
        db_table = 'accounts_module'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Permission(models.Model):
    """
    Permission model to define granular permissions in the system.
    Permissions are actions that can be performed on resources.
    """
    
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('export', 'Export'),
        ('import', 'Import'),
    ]
    
    name = models.CharField(max_length=100, unique=True, help_text="Unique permission name (e.g., 'create_product')")
    codename = models.CharField(max_length=100, unique=True, help_text="Machine-readable permission code")
    description = models.TextField(blank=True, help_text="Description of what this permission allows")
    resource = models.ForeignKey(Module, on_delete=models.PROTECT, related_name="permissions")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, help_text="The action this permission allows")
    is_active = models.BooleanField(default=True, help_text="Whether this permission is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
        db_table = 'accounts_permission'
        ordering = ['created_at']
        unique_together = [['resource', 'action']]
    
    def __str__(self):
        return f"{self.name} ({self.resource}.{self.action})"
    
    def save(self, *args, **kwargs):
        # Auto-generate codename if not provided
        if not self.codename:
            self.codename = f"{self.resource.name.lower()}_{self.action}"
        # Auto-generate name if not provided
        if not self.name:
            self.name = f"{self.action.title()} {self.resource.name}"
        super().save(*args, **kwargs)


class Role(models.Model):
    """
    Role model for access control.
    Roles have permissions that determine what users can do.
    """
    ROLE_TYPE_CHOICES = [
        ('system', 'System Role'),
        ('custom', 'Custom Role'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text="Role name (e.g., 'Admin', 'Manager')")
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-friendly role identifier")
    description = models.TextField(blank=True, help_text="Description of this role")
    role_type = models.CharField(
        max_length=20, 
        choices=ROLE_TYPE_CHOICES, 
        default='custom',
        help_text="System roles cannot be deleted"
    )
    permissions = models.ManyToManyField(
        'Permission',
        related_name='roles',
        blank=True,
        help_text="Permissions assigned to this role"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this role is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_roles',
        help_text="User who created this role"
    )
    
    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        db_table = 'accounts_role'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def has_permission(self, permission_codename):
        """Check if this role has a specific permission"""
        return self.permissions.filter(
            codename=permission_codename,
            is_active=True
        ).exists()
    
    def get_permissions_list(self):
        """Get list of all permission codenames for this role"""
        return list(self.permissions.filter(is_active=True).values_list('codename', flat=True))


class User(AbstractUser):
    """
    Custom User model for the accounts app.
    Extends Django's AbstractUser with additional fields.
    Users have a role that determines their permissions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="Role assigned to this user"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        db_table = 'accounts_user'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def has_perm(self, perm, obj=None):
        """
        Check if user has a specific permission through their role.
        Superusers always have all permissions.
        """
        if self.is_superuser:
            return True
        
        if not self.is_active:
            return False
        
        # Check if user has a role and the role has the permission
        if self.role and self.role.is_active:
            return self.role.has_permission(perm)
        
        return False
    
    def get_all_permissions(self, obj=None):
        """
        Get all permissions for this user through their role.
        Returns a set of all permissions from the user's role.
        """
        if self.is_superuser:
            return set(Permission.objects.values_list('codename', flat=True))
        
        # Get permissions from user's role
        if self.role and self.role.is_active:
            return set(self.role.get_permissions_list())
        
        return set()
    
    def has_module_perms(self, app_label):
        """
        Check if user has any permissions for a specific app/module.
        """
        if self.is_superuser:
            return True
        
        if not self.is_active:
            return False
        
        # Check if user's role has any permissions for this module
        if self.role and self.role.is_active:
            # Check if role has any permissions for this resource
            if self.role.permissions.filter(
                resource__name=app_label,
                is_active=True
            ).exists():
                return True
        
        return False

