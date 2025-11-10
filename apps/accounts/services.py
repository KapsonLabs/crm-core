from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User


def create_user(user_data):
    """
    Create a new user with validated data.
    
    Args:
        user_data (dict): User data including username, email, password, etc.
    
    Returns:
        User: The created user instance
    
    Raises:
        ValidationError: If password validation fails
    """
    # Validate password
    password = user_data.get('password')
    if password:
        validate_password(password)
    
    # Create user
    user = User.objects.create_user(
        username=user_data['username'],
        email=user_data['email'],
        password=password,
        first_name=user_data.get('first_name', ''),
        last_name=user_data.get('last_name', ''),
        phone_number=user_data.get('phone_number'),
        date_of_birth=user_data.get('date_of_birth')
    )
    
    return user


def authenticate_user(email, password):
    """
    Authenticate a user with email and password.
    
    Args:
        email (str): User's email address
        password (str): User's password
    
    Returns:
        User or None: Authenticated user or None if authentication fails
    """
    return authenticate(username=email, password=password)


def get_user_by_id(user_id):
    """
    Get a user by their ID.
    
    Args:
        user_id (str): User's UUID
    
    Returns:
        User or None: User instance or None if not found
    """
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def update_user(user, user_data):
    """
    Update user information.
    
    Args:
        user (User): User instance to update
        user_data (dict): New user data
    
    Returns:
        User: Updated user instance
    """
    for field, value in user_data.items():
        if hasattr(user, field) and field != 'password':
            setattr(user, field, value)
    
    user.save()
    return user


def deactivate_user(user):
    """
    Deactivate a user account.
    
    Args:
        user (User): User instance to deactivate
    
    Returns:
        User: Deactivated user instance
    """
    user.is_active = False
    user.save()
    return user


def activate_user(user):
    """
    Activate a user account.
    
    Args:
        user (User): User instance to activate
    
    Returns:
        User: Activated user instance
    """
    user.is_active = True
    user.save()
    return user

