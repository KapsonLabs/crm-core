from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import User


@shared_task
def send_welcome_email(user_id):
    """
    Send a welcome email to a newly created user.
    
    Args:
        user_id (str): The UUID of the user
    """
    try:
        user = User.objects.get(id=user_id)
        subject = "Welcome!"
        message = f"""
        Hello {user.first_name or user.username},
        
        Welcome! Your account has been successfully created.
        
        You can now log in using your email address: {user.email}
        
        Best regards,
        The Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return f"Welcome email sent to {user.email}"
    except User.DoesNotExist:
        return f"User with ID {user_id} not found"
    except Exception as e:
        return f"Failed to send welcome email: {str(e)}"


@shared_task
def send_account_activation_email(user_id):
    """
    Send an account activation email to a user.
    
    Args:
        user_id (str): The UUID of the user
    """
    try:
        user = User.objects.get(id=user_id)
        subject = "Your Account Has Been Activated"
        message = f"""
        Hello {user.first_name or user.username},
        
        Your account has been activated successfully.
        You can now log in and start using our services.
        
        Best regards,
        The Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return f"Activation email sent to {user.email}"
    except User.DoesNotExist:
        return f"User with ID {user_id} not found"
    except Exception as e:
        return f"Failed to send activation email: {str(e)}"

