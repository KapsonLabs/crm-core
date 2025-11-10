"""
Custom permission classes and decorators for role-based access control.
"""

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from functools import wraps


class HasPermission(permissions.BasePermission):
    """
    Custom permission class to check if user has a specific permission through their role.
    
    Usage in views:
        permission_classes = [IsAuthenticated, HasPermission]
        required_permission = 'products_create'
    """
    
    def has_permission(self, request, view):
        """Check if user has the required permission."""
        # Get the required permission from the view
        required_permission = getattr(view, 'required_permission', None)
        
        if not required_permission:
            # If no permission is specified, deny access
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check if user has the permission through their role
        return request.user.has_perm(required_permission)


class HasAnyPermission(permissions.BasePermission):
    """
    Custom permission class to check if user has ANY of the specified permissions.
    
    Usage in views:
        permission_classes = [IsAuthenticated, HasAnyPermission]
        required_permissions = ['products_create', 'products_update']
    """
    
    def has_permission(self, request, view):
        """Check if user has any of the required permissions."""
        # Get the required permissions from the view
        required_permissions = getattr(view, 'required_permissions', [])
        
        if not required_permissions:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check if user has any of the permissions
        for permission in required_permissions:
            if request.user.has_perm(permission):
                return True
        
        return False


class HasAllPermissions(permissions.BasePermission):
    """
    Custom permission class to check if user has ALL of the specified permissions.
    
    Usage in views:
        permission_classes = [IsAuthenticated, HasAllPermissions]
        required_permissions = ['products_create', 'products_approve']
    """
    
    def has_permission(self, request, view):
        """Check if user has all of the required permissions."""
        # Get the required permissions from the view
        required_permissions = getattr(view, 'required_permissions', [])
        
        if not required_permissions:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check if user has all of the permissions
        for permission in required_permissions:
            if not request.user.has_perm(permission):
                return False
        
        return True


def require_permission(permission_codename):
    """
    Decorator to require a specific permission for a view method.
    
    Usage:
        @require_permission('products_create')
        def post(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Superusers always have access
            if request.user.is_superuser:
                return func(self, request, *args, **kwargs)
            
            # Check if user has the permission
            if not request.user.has_perm(permission_codename):
                raise PermissionDenied(
                    f"You do not have permission to perform this action. "
                    f"Required permission: {permission_codename}"
                )
            
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(*permission_codenames):
    """
    Decorator to require ANY of the specified permissions for a view method.
    
    Usage:
        @require_any_permission('products_create', 'products_update')
        def post(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Superusers always have access
            if request.user.is_superuser:
                return func(self, request, *args, **kwargs)
            
            # Check if user has any of the permissions
            for permission in permission_codenames:
                if request.user.has_perm(permission):
                    return func(self, request, *args, **kwargs)
            
            raise PermissionDenied(
                f"You do not have permission to perform this action. "
                f"Required permissions (any): {', '.join(permission_codenames)}"
            )
        return wrapper
    return decorator


def require_all_permissions(*permission_codenames):
    """
    Decorator to require ALL of the specified permissions for a view method.
    
    Usage:
        @require_all_permissions('products_create', 'products_approve')
        def post(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Superusers always have access
            if request.user.is_superuser:
                return func(self, request, *args, **kwargs)
            
            # Check if user has all of the permissions
            missing_permissions = []
            for permission in permission_codenames:
                if not request.user.has_perm(permission):
                    missing_permissions.append(permission)
            
            if missing_permissions:
                raise PermissionDenied(
                    f"You do not have all required permissions. "
                    f"Missing: {', '.join(missing_permissions)}"
                )
            
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


class IsRoleType(permissions.BasePermission):
    """
    Permission class to check if user has a specific role type.
    
    Usage in views:
        permission_classes = [IsAuthenticated, IsRoleType]
        required_role_type = 'system'
    """
    
    def has_permission(self, request, view):
        """Check if user's role matches the required role type."""
        required_role_type = getattr(view, 'required_role_type', None)
        
        if not required_role_type:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check if user has a role and it matches the required type
        if request.user.role and request.user.role.is_active:
            return request.user.role.role_type == required_role_type
        
        return False

