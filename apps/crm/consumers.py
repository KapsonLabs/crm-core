"""
WebSocket Consumers for CRM

Handles real-time notifications and messaging via WebSockets.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Notification, Message

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    
    Connects authenticated users to their personal notification channel.
    Sends notifications in real-time when they are created.
    """
    
    async def connect(self):
        """Accept connection and add to user's notification group"""
        # Get user from scope (requires AuthMiddleware)
        self.user = self.scope.get('user')
        
        if self.user and self.user.is_authenticated:
            # Create a unique group name for this user
            self.group_name = f'notifications_{self.user.id}'
            
            # Join the notification group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Accept the WebSocket connection
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to notification stream',
                'user_id': str(self.user.id)
            }))
        else:
            # Reject unauthenticated connections
            await self.close(code=4001)
    
    async def disconnect(self, close_code):
        """Remove from notification group on disconnect"""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Handle incoming messages from WebSocket.
        
        Supports commands like:
        - mark_as_read: Mark notification as read
        - get_unread_count: Get current unread count
        """
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'mark_as_read':
                notification_id = data.get('notification_id')
                if notification_id:
                    success = await self.mark_notification_as_read(notification_id)
                    await self.send(text_data=json.dumps({
                        'type': 'mark_as_read_response',
                        'success': success,
                        'notification_id': notification_id
                    }))
            
            elif command == 'get_unread_count':
                count = await self.get_unread_count()
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': count
                }))
            
            elif command == 'ping':
                # Heartbeat/keepalive
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def notification_message(self, event):
        """
        Handle notification messages from the channel layer.
        
        Called when a new notification is sent to this user's group.
        """
        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
    
    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Mark a notification as read"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.mark_as_read()
            return True
        except Exception:
            return False
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread notifications"""
        return Notification.objects.filter(
            user=self.user,
            is_read=False
        ).count()


class MessageConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time messaging.
    
    Connects users to receive real-time message notifications.
    """
    
    async def connect(self):
        """Accept connection and add to user's message group"""
        self.user = self.scope.get('user')
        
        if self.user and self.user.is_authenticated:
            # Create a unique group name for this user's messages
            self.group_name = f'messages_{self.user.id}'
            
            # Join the message group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            await self.accept()
            
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to message stream',
                'user_id': str(self.user.id)
            }))
        else:
            await self.close(code=4001)
    
    async def disconnect(self, close_code):
        """Remove from message group on disconnect"""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming messages"""
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'mark_as_read':
                message_id = data.get('message_id')
                if message_id:
                    success = await self.mark_message_as_read(message_id)
                    await self.send(text_data=json.dumps({
                        'type': 'mark_as_read_response',
                        'success': success,
                        'message_id': message_id
                    }))
            
            elif command == 'get_unread_count':
                count = await self.get_unread_count()
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': count
                }))
            
            elif command == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def message_notification(self, event):
        """
        Handle new message notifications from the channel layer.
        """
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message']
        }))
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark a message as read"""
        try:
            message = Message.objects.get(
                id=message_id,
                recipient=self.user
            )
            message.mark_as_read()
            return True
        except Exception:
            return False
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread messages"""
        return Message.objects.filter(
            recipient=self.user,
            is_read=False,
            is_deleted_by_recipient=False
        ).count()

