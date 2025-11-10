"""
Utility functions for CRM notifications and permissions
"""

from django.contrib.auth import get_user_model

User = get_user_model()


def get_users_with_permission(permission_codename):
    """
    Get all users who have a specific permission.
    
    Args:
        permission_codename: The permission codename to check (e.g., 'members_approve')
        
    Returns:
        QuerySet of User objects who have the permission
    """
    # Get all active users with active roles that have the permission
    users_with_permission = User.objects.filter(
        is_active=True,
        role__is_active=True,
        role__permissions__codename=permission_codename,
        role__permissions__is_active=True
    ).distinct()
    
    return users_with_permission

