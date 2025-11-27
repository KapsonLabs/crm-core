import logging
from typing import Any, Dict, Iterable, Optional, Sequence

from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import Count, Q
from django.utils import timezone

from .models import Notification, Ticket, Message, TicketComment
from .serializers import TicketCommentSerializer

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


class TicketCommentService:
    """Service for ticket comment operations including WebSocket broadcasting"""
    
    @staticmethod
    def broadcast_new_comment(comment):
        """Broadcast a new comment via WebSocket to all connected clients"""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured. Cannot broadcast comment.")
                return
            
            # Serialize comment data
            serializer = TicketCommentSerializer(comment)
            comment_data = serializer.data
            
            # Broadcast to ticket comment group
            group_name = f'ticket_comments_{comment.ticket.id}'
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'comment_added',
                    'comment': comment_data
                }
            )
            
            logger.info(f"Broadcasted new comment {comment.id} for ticket {comment.ticket.id}")
        except Exception as e:
            # Log error but don't fail the comment creation
            logger.error(f"WebSocket comment broadcast failed: {str(e)}")
    
    @staticmethod
    def broadcast_updated_comment(comment):
        """Broadcast an updated comment via WebSocket to all connected clients"""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured. Cannot broadcast comment update.")
                return
            
            # Serialize comment data
            serializer = TicketCommentSerializer(comment)
            comment_data = serializer.data
            
            # Broadcast to ticket comment group
            group_name = f'ticket_comments_{comment.ticket.id}'
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'comment_updated',
                    'comment': comment_data
                }
            )
            
            logger.info(f"Broadcasted updated comment {comment.id} for ticket {comment.ticket.id}")
        except Exception as e:
            logger.error(f"WebSocket comment update broadcast failed: {str(e)}")


class TicketActivityService:
    """Broadcast ticket lifecycle events via WebSockets."""

    @staticmethod
    def _broadcast_event(
        event_type: str,
        ticket: Ticket,
        triggered_by: User,
        metadata: Optional[Dict[str, Any]] = None,
        recipients: Optional[Iterable[User]] = None,
    ):
        """Send a structured event to all interested users."""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not configured. Cannot broadcast ticket activity.")
                return

            payload = {
                'type': event_type,
                'ticket': TicketService.serialize_ticket_summary(ticket),
                'triggered_by': {
                    'id': str(triggered_by.id),
                    'full_name': triggered_by.get_full_name() or triggered_by.email,
                    'email': triggered_by.email,
                },
                'timestamp': timezone.now().isoformat(),
                'metadata': metadata or {},
            }

            for user in recipients or TicketService.get_ticket_watchers(ticket):
                async_to_sync(channel_layer.group_send)(
                    f'tickets_{user.id}',
                    {
                        'type': 'ticket_event',
                        'payload': payload,
                    },
                )
        except Exception as exc:
            logger.error(f"Ticket activity broadcast failed: {exc}")

    @staticmethod
    def ticket_created(ticket: Ticket, triggered_by: User):
        TicketActivityService._broadcast_event('ticket_created', ticket, triggered_by)

    @staticmethod
    def ticket_updated(ticket: Ticket, triggered_by: User):
        TicketActivityService._broadcast_event('ticket_updated', ticket, triggered_by)

    @staticmethod
    def ticket_status_changed(ticket: Ticket, triggered_by: User, previous_status: str):
        TicketActivityService._broadcast_event(
            'ticket_status_changed',
            ticket,
            triggered_by,
            metadata={'previous_status': previous_status, 'current_status': ticket.status},
        )
    
    @staticmethod
    def notify_newly_assigned_users(ticket: Ticket, newly_assigned_users: Iterable[User], triggered_by: User):
        """
        Send ticket_created event to newly assigned users so the ticket appears in their list.
        
        When a user is assigned to a ticket they weren't previously part of,
        they receive a 'ticket_created' event so the ticket appears in their ticket list.
        """
        if not newly_assigned_users:
            return
        
        TicketActivityService._broadcast_event(
            'ticket_created',
            ticket,
            triggered_by,
            metadata={'reason': 'assigned', 'assigned_by': str(triggered_by.id)},
            recipients=list(newly_assigned_users),
        )
    
    @staticmethod
    def notify_removed_users(ticket: Ticket, removed_users: Iterable[User], triggered_by: User):
        """
        Send ticket_removed event to users who were removed from a ticket.
        
        When a user is unassigned/removed from a ticket, they receive a 'ticket_removed'
        event so the ticket can be removed from their ticket list.
        """
        if not removed_users:
            return
        
        TicketActivityService._broadcast_event(
            'ticket_removed',
            ticket,
            triggered_by,
            metadata={'reason': 'unassigned', 'removed_by': str(triggered_by.id)},
            recipients=list(removed_users),
        )


class TicketService:
    """Service for ticket operations and helpers."""

    LIST_SELECT_RELATED: Sequence[str] = ('created_by', 'closed_by', 'branch')
    LIST_PREFETCH_RELATED: Sequence[str] = ('assigned_to',)

    @classmethod
    def base_queryset(cls):
        return Ticket.objects.all().select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED)

    @classmethod
    def get_ticket_list_queryset(cls, user, params):
        """Build the ticket list queryset with all filters applied."""
        queryset = cls.base_queryset().annotate(comment_count=Count('comments'))
        queryset = cls._filter_by_user(queryset, user)
        queryset = cls._apply_filters(queryset, params, user)
        return queryset.order_by('-created_at', 'id')

    @staticmethod
    def _filter_by_user(queryset, user):
        if user.is_staff:
            return queryset
        return queryset.filter(Q(created_by=user) | Q(assigned_to=user)).distinct()

    @staticmethod
    def _apply_filters(queryset, params, user):
        status_filter = params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        priority = params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        category = params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        if params.get('assigned_to_me') == 'true':
            queryset = queryset.filter(assigned_to=user)

        if params.get('created_by_me') == 'true':
            queryset = queryset.filter(created_by=user)

        return queryset

    @classmethod
    def get_user_tickets(cls, user, status=None, assigned_only=False, created_only=False):
        """Backwards-compatible helper used by other parts of the codebase."""
        params = {}
        if status:
            params['status'] = status
        if assigned_only:
            params['assigned_to_me'] = 'true'
        if created_only:
            params['created_by_me'] = 'true'
        return cls.get_ticket_list_queryset(user, params)

    @classmethod
    def get_ticket_statistics(cls, user=None):
        """Get aggregated ticket statistics respecting permissions."""
        queryset = cls.base_queryset()
        if user:
            queryset = cls._filter_by_user(queryset, user)

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
            'by_category': {},
        }

        for cat in queryset.values('category').annotate(count=Count('id')):
            stats['by_category'][cat['category']] = cat['count']

        return stats

    @staticmethod
    def get_ticket_watchers(ticket: Ticket, include_staff: bool = True) -> Iterable[User]:
        """Return users who should receive ticket activity events."""
        participants = {ticket.created_by} if ticket.created_by else set()
        participants.update(ticket.assigned_to.all())

        if include_staff:
            participants.update(User.objects.filter(is_staff=True, is_active=True))

        return [user for user in participants if user]

    @staticmethod
    def serialize_ticket_summary(ticket: Ticket) -> Dict[str, Any]:
        """Lightweight representation for WebSocket payloads."""
        assigned_users = [
            {
                'id': str(user.id),
                'full_name': user.get_full_name() or user.email,
                'email': user.email,
            }
            for user in ticket.assigned_to.all()
        ]

        comment_count = getattr(ticket, 'comment_count', None)
        if comment_count is None:
            comment_count = ticket.comments.count()

        return {
            'id': str(ticket.id),
            'ticket_number': ticket.ticket_number,
            'title': ticket.title,
            'status': ticket.status,
            'priority': ticket.priority,
            'category': ticket.category,
            'branch': {
                'id': str(ticket.branch.id) if ticket.branch else None,
                'name': ticket.branch.name if ticket.branch else None,
            },
            'created_by': {
                'id': str(ticket.created_by.id),
                'full_name': ticket.created_by.get_full_name() or ticket.created_by.email,
                'email': ticket.created_by.email,
            } if ticket.created_by else None,
            'assigned_to': assigned_users,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
            'comment_count': comment_count,
        }

