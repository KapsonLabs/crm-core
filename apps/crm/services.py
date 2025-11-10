import logging
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import Count, Q

from .models import Notification, Ticket, Message, TicketComment

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications"""
    
    @staticmethod
    def create_notification(
        user,
        notification_type,
        title,
        message,
        related_ticket=None,
        related_message=None,
        action_url='',
        metadata=None
    ):
        """Create a notification and send via WebSocket"""
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            related_ticket=related_ticket,
            related_message=related_message,
            action_url=action_url,
            metadata=metadata or {}
        )
        
        # Send notification via WebSocket
        NotificationService._send_websocket_notification(user, notification)
        
        return notification
    
    @staticmethod
    def _send_websocket_notification(user, notification):
        """Send notification to user via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                # Serialize notification data
                notification_data = {
                    'id': str(notification.id),
                    'type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'action_url': notification.action_url,
                    'is_read': notification.is_read,
                    'created_at': notification.created_at.isoformat(),
                }
                
                # Send to user's notification group
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{user.id}',
                    {
                        'type': 'notification_message',
                        'notification': notification_data
                    }
                )
        except Exception as e:
            # Log error but don't fail the notification creation
            logger.error(f"WebSocket notification failed: {str(e)}")
    
    @staticmethod
    def notify_ticket_assigned(ticket, users=None):
        """Notify users when assigned to a ticket"""
        if users is None:
            users = ticket.assigned_to.all()
        
        for user in users:
            NotificationService.create_notification(
                user=user,
                notification_type='ticket_assigned',
                title=f'Ticket Assigned: {ticket.title}',
                message=f'You have been assigned to ticket {ticket.ticket_number}: {ticket.title}',
                related_ticket=ticket,
                action_url=f'/crm/tickets/{ticket.id}/'
            )
    
    @staticmethod
    def notify_ticket_commented(ticket, comment):
        """Notify participants when a new comment is added"""
        # Get all participants (creator + assigned users)
        participants = set([ticket.created_by])
        participants.update(ticket.assigned_to.all())
        
        # Remove the comment author
        participants.discard(comment.user)
        
        for user in participants:
            # Skip internal comments for non-staff users
            if comment.is_internal and not user.is_staff:
                continue
            
            NotificationService.create_notification(
                user=user,
                notification_type='ticket_commented',
                title=f'New Comment on Ticket: {ticket.title}',
                message=f'{comment.user.get_full_name()} commented on ticket {ticket.ticket_number}',
                related_ticket=ticket,
                action_url=f'/crm/tickets/{ticket.id}/'
            )
    
    @staticmethod
    def notify_ticket_status_changed(ticket, old_status):
        """Notify participants when ticket status changes"""
        # Get all participants
        participants = set([ticket.created_by])
        participants.update(ticket.assigned_to.all())
        
        for user in participants:
            NotificationService.create_notification(
                user=user,
                notification_type='ticket_status_changed',
                title=f'Ticket Status Changed: {ticket.title}',
                message=f'Ticket {ticket.ticket_number} status changed from {old_status} to {ticket.status}',
                related_ticket=ticket,
                action_url=f'/crm/tickets/{ticket.id}/',
                metadata={
                    'old_status': old_status,
                    'new_status': ticket.status
                }
            )
    
    @staticmethod
    def notify_ticket_closed(ticket):
        """Notify participants when ticket is closed"""
        # Get all participants
        participants = set([ticket.created_by])
        participants.update(ticket.assigned_to.all())
        
        # Remove the person who closed it
        if ticket.closed_by:
            participants.discard(ticket.closed_by)
        
        for user in participants:
            NotificationService.create_notification(
                user=user,
                notification_type='ticket_closed',
                title=f'Ticket Closed: {ticket.title}',
                message=f'Ticket {ticket.ticket_number} has been closed by {ticket.closed_by.get_full_name() if ticket.closed_by else "system"}',
                related_ticket=ticket,
                action_url=f'/crm/tickets/{ticket.id}/'
            )
    
    @staticmethod
    def notify_message_received(message):
        """Notify recipient when they receive a message"""
        NotificationService.create_notification(
            user=message.recipient,
            notification_type='message_received',
            title=f'New Message from {message.sender.get_full_name()}',
            message=f'Subject: {message.subject}',
            related_message=message,
            action_url=f'/crm/messages/{message.id}/'
        )
    
    @staticmethod
    def notify_ticket_mentioned(ticket, mentioned_users, mentioner):
        """Notify users when mentioned in a ticket"""
        for user in mentioned_users:
            if user != mentioner:
                NotificationService.create_notification(
                    user=user,
                    notification_type='ticket_mentioned',
                    title=f'Mentioned in Ticket: {ticket.title}',
                    message=f'{mentioner.get_full_name()} mentioned you in ticket {ticket.ticket_number}',
                    related_ticket=ticket,
                    action_url=f'/crm/tickets/{ticket.id}/'
                )


class TicketService:
    """Service for ticket operations"""
    
    @staticmethod
    def get_user_tickets(user, status=None, assigned_only=False, created_only=False):
        """Get tickets for a user"""
        
        queryset = Ticket.objects.all()
        
        if not user.is_staff:
            queryset = queryset.filter(
                Q(created_by=user) | Q(assigned_to=user)
            ).distinct()
        
        if status:
            queryset = queryset.filter(status=status)
        
        if assigned_only:
            queryset = queryset.filter(assigned_to=user)
        
        if created_only:
            queryset = queryset.filter(created_by=user)
        
        return queryset.select_related('created_by', 'closed_by').prefetch_related('assigned_to')
    
    @staticmethod
    def get_ticket_statistics(user=None):
        """Get ticket statistics"""
        
        queryset = Ticket.objects.all()
        
        if user and not user.is_staff:
            queryset = queryset.filter(
                Q(created_by=user) | Q(assigned_to=user)
            ).distinct()
        
        stats = {
            'total': queryset.count(),
            'open': queryset.filter(status='open').count(),
            'in_progress': queryset.filter(status='in_progress').count(),
            'pending': queryset.filter(status='pending').count(),
            'resolved': queryset.filter(status='resolved').count(),
            'closed': queryset.filter(status='closed').count(),
            'by_priority': {
                'low': queryset.filter(priority='low').count(),
                'medium': queryset.filter(priority='medium').count(),
                'high': queryset.filter(priority='high').count(),
                'critical': queryset.filter(priority='critical').count(),
            },
            'by_category': {}
        }
        
        # Count by category
        categories = queryset.values('category').annotate(count=Count('id'))
        for cat in categories:
            stats['by_category'][cat['category']] = cat['count']
        
        return stats

