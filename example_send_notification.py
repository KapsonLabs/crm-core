#!/usr/bin/env python3
"""
Example script to send a test notification via the channel layer

This script demonstrates how to send a notification to a user via WebSocket
by using the Django channel layer.

Usage:
    python example_send_notification.py <user_id>
    
Example:
    python example_send_notification.py 123e4567-e89b-12d3-a456-426614174000
"""

import os
import sys
from pathlib import Path

# Find project root (directory containing manage.py)
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent  # Go up from crm/ to crm-core/

# Add project root to Python path if not already there
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Change to project root directory
os.chdir(project_root)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

# Import and setup Django
import django
django.setup()

# Now import Django models and channels
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.crm.models import Notification
from apps.accounts.models import User


def send_test_notification(user_id):
    """Send a test notification to a user via WebSocket"""
    try:
        user = User.objects.get(id=user_id)
        print(f"📤 Sending test notification to user: {user.email} ({user.id})")
        
        # Create a notification in the database
        notification = Notification.objects.create(
            user=user,
            notification_type='info',
            title='Test Notification',
            message='This is a test notification sent via WebSocket',
            metadata={'test': True}
        )
        
        print(f"✅ Created notification: {notification.id}")
        
        # Get channel layer
        channel_layer = get_channel_layer()
        
        # Send notification to user's WebSocket group
        group_name = f'notifications_{user.id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': {
                    'id': str(notification.id),
                    'title': notification.title,
                    'message': notification.message,
                    'notification_type': notification.notification_type,
                    'is_read': notification.is_read,
                    'created_at': notification.created_at.isoformat(),
                    'metadata': notification.metadata,
                }
            }
        )
        
        print(f"✅ Notification sent to WebSocket group: {group_name}")
        print(f"   If the user is connected via WebSocket, they should receive it now!")
        
    except User.DoesNotExist:
        print(f"❌ User with ID {user_id} not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python example_send_notification.py <user_id>")
        sys.exit(1)
    
    user_id = sys.argv[1]
    send_test_notification(user_id)
