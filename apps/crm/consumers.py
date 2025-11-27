"""
WebSocket Consumers for CRM

Handles real-time notifications and messaging via WebSockets.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Notification, Message, Ticket, TicketComment
from .serializers import TicketCommentSerializer

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


class TicketCommentConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time ticket comment streaming.
    
    Enables conversation mode by streaming comments for a specific ticket
    in real-time to all connected users.
    """
    
    async def connect(self):
        """Accept connection and join ticket comment group"""
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # Get ticket_id from URL path
        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']
        
        # Check if user has permission to access this ticket
        has_permission = await self.check_ticket_permission()
        
        if not has_permission:
            await self.close(code=4003)  # Forbidden
            return
        
        # Create group name for this ticket's comments
        self.group_name = f'ticket_comments_{self.ticket_id}'
        
        # Join the ticket comment group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the WebSocket connection
        await self.accept()
        
        # Send connection confirmation with ticket info
        ticket_info = await self.get_ticket_info()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connected to ticket {ticket_info.get("ticket_number")} comment stream',
            'ticket_id': str(self.ticket_id),
            'ticket_number': ticket_info.get('ticket_number'),
            'ticket_title': ticket_info.get('title')
        }))
        
        # Optionally send recent comments on connect for conversation continuity
        await self.send_recent_comments()
    
    async def disconnect(self, close_code):
        """Remove from ticket comment group on disconnect"""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming messages from WebSocket"""
        try:
            data = json.loads(text_data)
            command = data.get('command')
            
            if command == 'ping':
                # Heartbeat/keepalive
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
            
            elif command == 'get_recent_comments':
                # Request recent comments
                await self.send_recent_comments()
            
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown command: {command}'
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
    
    async def comment_added(self, event):
        """
        Handle new comment messages from the channel layer.
        
        Called when a new comment is broadcast to this ticket's group.
        """
        comment_data = event.get('comment', {})
        
        # Check if user should see internal comments
        if comment_data.get('is_internal') and not await self.is_user_staff():
            return  # Don't send internal comments to non-staff users
        
        # Send comment to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_comment',
            'comment': comment_data
        }))
    
    async def comment_updated(self, event):
        """Handle comment update messages from the channel layer"""
        comment_data = event.get('comment', {})
        
        # Check if user should see internal comments
        if comment_data.get('is_internal') and not await self.is_user_staff():
            return
        
        await self.send(text_data=json.dumps({
            'type': 'comment_updated',
            'comment': comment_data
        }))
    
    @database_sync_to_async
    def check_ticket_permission(self):
        """Check if user has permission to access this ticket"""
        try:
            ticket = Ticket.objects.get(id=self.ticket_id)
            user = self.user
            
            # Staff users have access to all tickets
            if user.is_staff:
                return True
            
            # Creator or assigned users have access
            if ticket.created_by == user:
                return True
            
            if user in ticket.assigned_to.all():
                return True
            
            return False
        except Ticket.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_ticket_info(self):
        """Get basic ticket information"""
        try:
            ticket = Ticket.objects.get(id=self.ticket_id)
            return {
                'ticket_number': ticket.ticket_number,
                'title': ticket.title
            }
        except Ticket.DoesNotExist:
            return {}
    
    @database_sync_to_async
    def is_user_staff(self):
        """Check if user is staff"""
        return self.user.is_staff if self.user else False
    
    async def send_recent_comments(self, limit=50):
        """Send recent comments to the client for conversation continuity"""
        comments = await self.get_recent_comments(limit)
        
        await self.send(text_data=json.dumps({
            'type': 'recent_comments',
            'comments': comments,
            'count': len(comments)
        }))
    
    @database_sync_to_async
    def get_recent_comments(self, limit=50):
        """Get recent comments for the ticket"""
        try:
            ticket = Ticket.objects.get(id=self.ticket_id)
            comments_query = ticket.comments.all().order_by('-created_at')
            
            # Filter internal comments for non-staff users (must be done before slicing)
            if not self.user.is_staff:
                comments_query = comments_query.filter(is_internal=False)
            
            # Apply limit and convert to list
            comments = list(comments_query[:limit])
            
            # Reverse to get chronological order (oldest first)
            comments.reverse()
            
            # Serialize comments
            serializer = TicketCommentSerializer(comments, many=True)
            return serializer.data
        except Ticket.DoesNotExist:
            return []

