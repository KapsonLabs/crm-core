from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Ticket, TicketComment, Notification, Message, TicketAttachment
from .serializers import (
    TicketListSerializer,
    TicketDetailSerializer,
    TicketCommentSerializer,
    NotificationSerializer,
    MessageSerializer,
    TicketAttachmentSerializer,
    UserBasicSerializer,
    TicketCloseSerializer
)
from .services import NotificationService

User = get_user_model()


class TicketListView(APIView):
    """List all tickets or create a new ticket"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all tickets"""
        user = request.user
        queryset = Ticket.objects.all()
        
        # Filter by user's tickets (created or assigned)
        if not user.is_staff:
            queryset = queryset.filter(
                Q(created_by=user) | Q(assigned_to=user)
            ).distinct()
        
        # Annotate with comment count
        queryset = queryset.annotate(comment_count=Count('comments'))
        
        # Filter by status
        status_filter = request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by priority
        priority = request.query_params.get('priority', None)
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by category
        category = request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by assigned to me
        assigned_to_me = request.query_params.get('assigned_to_me', None)
        if assigned_to_me == 'true':
            queryset = queryset.filter(assigned_to=user)
        
        # Filter by created by me
        created_by_me = request.query_params.get('created_by_me', None)
        if created_by_me == 'true':
            queryset = queryset.filter(created_by=user)
        
        queryset = queryset.select_related('created_by', 'closed_by').prefetch_related('assigned_to')
        
        serializer = TicketListSerializer(queryset, many=True)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create a new ticket"""
        serializer = TicketDetailSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            ticket = serializer.save()
            
            # Send notifications to assigned users
            NotificationService.notify_ticket_assigned(ticket)
            
            return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TicketDetailView(APIView):
    """Retrieve, update or delete a ticket"""
    
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        """Get ticket object with permission check"""
        try:
            ticket = Ticket.objects.annotate(comment_count=Count('comments')).get(pk=pk)
            
            # Check permissions
            if not user.is_staff:
                if ticket.created_by != user and user not in ticket.assigned_to.all():
                    return None
            
            return ticket
        except Ticket.DoesNotExist:
            return None
    
    def get(self, request, pk):
        """Get ticket details"""
        ticket = self.get_object(pk, request.user)
        if not ticket:
            return Response(
                {'error': 'Ticket not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TicketDetailSerializer(ticket)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        """Update ticket"""
        ticket = self.get_object(pk, request.user)
        if not ticket:
            return Response(
                {'error': 'Ticket not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        old_status = ticket.status
        old_assigned = set(ticket.assigned_to.all())
        
        serializer = TicketDetailSerializer(ticket, data=request.data, context={'request': request})
        if serializer.is_valid():
            ticket = serializer.save()
            
            # Send notification if status changed
            if old_status != ticket.status:
                NotificationService.notify_ticket_status_changed(ticket, old_status)
            
            # Send notification if new users assigned
            new_assigned = set(ticket.assigned_to.all())
            newly_assigned = new_assigned - old_assigned
            if newly_assigned:
                NotificationService.notify_ticket_assigned(ticket, list(newly_assigned))
            
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        """Partially update ticket"""
        ticket = self.get_object(pk, request.user)
        if not ticket:
            return Response(
                {'error': 'Ticket not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        old_status = ticket.status
        old_assigned = set(ticket.assigned_to.all())
        
        serializer = TicketDetailSerializer(ticket, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            ticket = serializer.save()
            
            # Send notification if status changed
            if old_status != ticket.status:
                NotificationService.notify_ticket_status_changed(ticket, old_status)
            
            # Send notification if new users assigned
            new_assigned = set(ticket.assigned_to.all())
            newly_assigned = new_assigned - old_assigned
            if newly_assigned:
                NotificationService.notify_ticket_assigned(ticket, list(newly_assigned))
            
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete ticket"""
        ticket = self.get_object(pk, request.user)
        if not ticket:
            return Response(
                {'error': 'Ticket not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        ticket.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TicketCloseView(APIView):
    """Close a ticket"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Close the ticket"""
        try:
            ticket = Ticket.objects.get(pk=pk)
            
            # Check permissions
            user = request.user
            if not user.is_staff:
                if ticket.created_by != user and user not in ticket.assigned_to.all():
                    return Response(
                        {'error': 'Access denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            ticket.close(request.user)
            
            # Notify all participants
            NotificationService.notify_ticket_closed(ticket)
            
            serializer = TicketCloseSerializer(ticket)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TicketResolveView(APIView):
    """Resolve a ticket"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Mark ticket as resolved"""
        try:
            ticket = Ticket.objects.get(pk=pk)
            
            # Check permissions
            user = request.user
            if not user.is_staff:
                if ticket.created_by != user and user not in ticket.assigned_to.all():
                    return Response(
                        {'error': 'Access denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            ticket.resolve()
            
            # Notify participants
            NotificationService.notify_ticket_status_changed(ticket, 'resolved')
            
            serializer = TicketCloseSerializer(ticket)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TicketCommentListView(APIView):
    """List comments for a ticket"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get all comments for the ticket"""
        try:
            ticket = Ticket.objects.get(pk=pk)
            
            # Check permissions
            user = request.user
            if not user.is_staff:
                if ticket.created_by != user and user not in ticket.assigned_to.all():
                    return Response(
                        {'error': 'Access denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            comments = ticket.comments.all()
            
            # Hide internal comments from non-staff users
            if not user.is_staff:
                comments = comments.filter(is_internal=False)
            
            serializer = TicketCommentSerializer(comments, many=True)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TicketCommentCreateView(APIView):
    """Add a comment to a ticket"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Add a comment to the ticket"""
        try:
            ticket = Ticket.objects.get(pk=request.data.get('ticket'))
            
            # Check permissions
            user = request.user
            if not user.is_staff:
                if ticket.created_by != user and user not in ticket.assigned_to.all():
                    return Response(
                        {'error': 'Access denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            serializer = TicketCommentSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                comment = serializer.save(ticket=ticket, user=request.user)
                
                # Notify all participants
                NotificationService.notify_ticket_commented(ticket, comment)
                
                return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class NotificationListView(APIView):
    """List all notifications for the current user"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List notifications"""
        user = request.user
        queryset = Notification.objects.filter(user=user)
        
        # Filter by read status
        is_read = request.query_params.get('is_read', None)
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        # Filter by type
        notification_type = request.query_params.get('type', None)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        queryset = queryset.select_related('user', 'related_ticket', 'related_message')
        
        serializer = NotificationSerializer(queryset, many=True)
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)


class NotificationDetailView(APIView):
    """Retrieve a notification"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get notification details"""
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            serializer = NotificationSerializer(notification)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class NotificationMarkAsReadView(APIView):
    """Mark a notification as read"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Mark notification as read"""
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            notification.mark_as_read()
            
            serializer = NotificationSerializer(notification)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class NotificationMarkAllAsReadView(APIView):
    """Mark all notifications as read"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Mark all unread notifications as read"""
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        count = notifications.count()
        
        for notification in notifications:
            notification.mark_as_read()
        
        return Response({
            'message': f'{count} notifications marked as read',
            'count': count
        })


class NotificationUnreadCountView(APIView):
    """Get count of unread notifications"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get count of unread notifications"""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        
        return Response({
            'unread_count': count
        })


class MessageListView(APIView):
    """List all messages or send a new message"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List messages"""
        user = request.user
        queryset = Message.objects.filter(
            Q(sender=user, is_deleted_by_sender=False) |
            Q(recipient=user, is_deleted_by_recipient=False)
        )
        
        # Filter by conversation partner
        partner_id = request.query_params.get('partner_id', None)
        if partner_id:
            queryset = queryset.filter(
                Q(sender=user, recipient_id=partner_id) |
                Q(sender_id=partner_id, recipient=user)
            )
        
        # Filter by sent/received
        message_type = request.query_params.get('type', None)
        if message_type == 'sent':
            queryset = queryset.filter(sender=user)
        elif message_type == 'received':
            queryset = queryset.filter(recipient=user)
        
        # Filter by read status
        is_read = request.query_params.get('is_read', None)
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        queryset = queryset.select_related('sender', 'recipient', 'parent_message')
        
        serializer = MessageSerializer(queryset, many=True, context={'request': request})
        return Response({'data': serializer.data}, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Send a new message"""
        serializer = MessageSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            message = serializer.save()
            
            # Send notification to recipient
            NotificationService.notify_message_received(message)
            
            return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MessageDetailView(APIView):
    """Retrieve or delete a message"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """Get message details"""
        try:
            user = request.user
            message = Message.objects.get(pk=pk)
            
            # Check permissions
            if message.sender != user and message.recipient != user:
                return Response(
                    {'error': 'Access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check soft delete
            if (message.sender == user and message.is_deleted_by_sender) or \
               (message.recipient == user and message.is_deleted_by_recipient):
                return Response(
                    {'error': 'Message not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = MessageSerializer(message, context={'request': request})
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, pk):
        """Soft delete a message"""
        try:
            user = request.user
            message = Message.objects.get(pk=pk)
            
            # Check permissions
            if message.sender != user and message.recipient != user:
                return Response(
                    {'error': 'Access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if message.sender == user:
                message.is_deleted_by_sender = True
            if message.recipient == user:
                message.is_deleted_by_recipient = True
            
            message.save()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class MessageMarkAsReadView(APIView):
    """Mark a message as read"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """Mark message as read"""
        try:
            message = Message.objects.get(pk=pk)
            
            # Only recipient can mark as read
            if message.recipient != request.user:
                return Response(
                    {'error': 'Only recipient can mark message as read'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            message.mark_as_read()
            
            serializer = MessageSerializer(message, context={'request': request})
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class MessageUnreadCountView(APIView):
    """Get count of unread messages"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get count of unread messages"""
        count = Message.objects.filter(
            recipient=request.user,
            is_read=False,
            is_deleted_by_recipient=False
        ).count()
        
        return Response({
            'unread_count': count
        })


class MessageConversationsView(APIView):
    """Get list of conversations"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get list of conversations"""
        user = request.user
        
        # Get unique conversation partners
        sent_to = Message.objects.filter(
            sender=user,
            is_deleted_by_sender=False
        ).values_list('recipient_id', flat=True).distinct()
        
        received_from = Message.objects.filter(
            recipient=user,
            is_deleted_by_recipient=False
        ).values_list('sender_id', flat=True).distinct()
        
        partner_ids = set(list(sent_to) + list(received_from))
        
        partners = User.objects.filter(id__in=partner_ids)
        
        # Get last message for each partner
        conversations = []
        for partner in partners:
            last_message = Message.objects.filter(
                Q(sender=user, recipient=partner, is_deleted_by_sender=False) |
                Q(sender=partner, recipient=user, is_deleted_by_recipient=False)
            ).order_by('-created_at').first()
            
            unread_count = Message.objects.filter(
                sender=partner,
                recipient=user,
                is_read=False,
                is_deleted_by_recipient=False
            ).count()
            
            conversations.append({
                'partner': UserBasicSerializer(partner).data,
                'last_message': MessageSerializer(last_message, context={'request': request}).data if last_message else None,
                'unread_count': unread_count
            })
        
        # Sort by last message timestamp
        conversations.sort(
            key=lambda x: x['last_message']['created_at'] if x['last_message'] else '',
            reverse=True
        )
        
        return Response({'data': conversations}, status=status.HTTP_200_OK)

