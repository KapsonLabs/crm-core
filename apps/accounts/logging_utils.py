"""
Logging utilities for the accounts module.

This module provides clean, reusable logging functions.
Note: This is a simplified version without db_logging dependency.
"""

# Placeholder for logging utilities
# In a production environment, you might want to integrate with a logging service


def get_client_ip(request):
    """Extract client IP address from request"""
    if not request:
        return None
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Extract user agent from request"""
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')


def get_session_id(request):
    """Extract session ID from request"""
    if not request:
        return ''
    if hasattr(request, 'session') and request.session:
        return request.session.session_key or ''
    return ''

