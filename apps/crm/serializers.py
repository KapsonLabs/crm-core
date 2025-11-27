from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Ticket, TicketComment, Notification, Message, TicketAttachment
from apps.organization.serializers import BranchShortDetailsSerializer
from apps.organization.models import Branch

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user information for nested serialization"""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'first_name', 'last_name']
        read_only_fields = fields


class TicketCommentSerializer(serializers.ModelSerializer):
    """Serializer for ticket comments"""
    
    user = UserBasicSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = TicketComment
        fields = [
            'id', 'ticket', 'user', 'user_id', 'comment', 
            'is_internal', 'attachments', 'created_at', 'updated_at', 'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        # Set user from request context if not provided
        if 'user_id' not in validated_data:
            validated_data['user'] = self.context['request'].user
        else:
            user_id = validated_data.pop('user_id')
            validated_data['user'] = User.objects.get(id=user_id)
        
        return super().create(validated_data)


class TicketAttachmentSerializer(serializers.ModelSerializer):
    """Serializer for ticket attachments"""
    
    uploaded_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = TicketAttachment
        fields = [
            'id', 'ticket', 'uploaded_by', 'file', 'file_name',
            'file_size', 'file_type', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'uploaded_by']


class TicketListSerializer(serializers.ModelSerializer):
    """Serializer for ticket list view"""
    
    created_by = UserBasicSerializer(read_only=True)
    assigned_to = UserBasicSerializer(many=True, read_only=True)
    branch = BranchShortDetailsSerializer(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'title', 'category', 'priority', 
            'status', 'created_by', 'assigned_to', 'branch',
            'created_at', 'updated_at', 'comment_count'
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']


class TicketDetailSerializer(serializers.ModelSerializer):
    """Serializer for ticket detail view"""
    
    created_by = UserBasicSerializer(read_only=True)
    assigned_to = UserBasicSerializer(many=True, read_only=True)
    assigned_to_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    branch = BranchShortDetailsSerializer(read_only=True)
    branch_id = serializers.UUIDField(write_only=True, required=False)
    closed_by = UserBasicSerializer(read_only=True)
    comments = TicketCommentSerializer(many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'title', 'description', 'category',
            'priority', 'status', 'created_by', 'assigned_to', 'assigned_to_ids',
            'branch', 'branch_id', 'created_at', 'updated_at', 'resolved_at', 'closed_at',
            'closed_by', 'metadata', 'comments', 'attachments', 'comment_count'
        ]
        read_only_fields = [
            'id', 'ticket_number', 'created_at', 'updated_at', 
            'resolved_at', 'closed_at', 'closed_by'
        ]
    
    def create(self, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to_ids', [])
        branch_id = validated_data.pop('branch_id', None)
        user = self.context['request'].user
        
        validated_data['created_by'] = user
        
        # Set branch from branch_id if provided, otherwise use user's branch
        if branch_id:
            validated_data['branch'] = Branch.objects.get(id=branch_id)
        elif user.branch:
            validated_data['branch'] = user.branch
        else:
            raise serializers.ValidationError({
                'branch_id': 'Branch is required. Either provide branch_id or ensure your user has a branch assigned.'
            })
        
        ticket = Ticket.objects.create(**validated_data)
        
        # Assign users
        if assigned_to_ids:
            users = User.objects.filter(id__in=assigned_to_ids)
            ticket.assigned_to.set(users)
        
        return ticket
    
    def update(self, instance, validated_data):
        assigned_to_ids = validated_data.pop('assigned_to_ids', None)
        branch_id = validated_data.pop('branch_id', None)
        
        # Update branch if branch_id is provided
        if branch_id is not None:
            validated_data['branch'] = Branch.objects.get(id=branch_id)
        
        # Update ticket fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update assigned users if provided
        if assigned_to_ids is not None:
            users = User.objects.filter(id__in=assigned_to_ids)
            instance.assigned_to.set(users)
        
        return instance

class TicketCloseSerializer(serializers.ModelSerializer):
    """Serializer for ticket close"""
    
    class Meta:
        model = Ticket
        fields = ['id', 'status', 'closing_comment']
        read_only_fields = ['id', 'status']


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    
    user = UserBasicSerializer(read_only=True)
    related_ticket = TicketListSerializer(read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'notification_type', 'title', 'message',
            'related_ticket', 'related_message', 'action_url',
            'is_read', 'read_at', 'created_at', 'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'read_at']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages"""
    
    sender = UserBasicSerializer(read_only=True)
    recipient = UserBasicSerializer(read_only=True)
    recipient_id = serializers.UUIDField(write_only=True)
    parent_message_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'recipient', 'recipient_id', 'subject', 'body',
            'parent_message', 'parent_message_id', 'replies', 'attachments',
            'is_read', 'read_at', 'created_at', 'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'read_at', 'sender']
    
    def get_replies(self, obj):
        """Get replies to this message"""
        if hasattr(obj, 'replies'):
            replies = obj.replies.all()
            return MessageSerializer(replies, many=True, context=self.context).data
        return []
    
    def create(self, validated_data):
        recipient_id = validated_data.pop('recipient_id')
        parent_message_id = validated_data.pop('parent_message_id', None)
        
        validated_data['sender'] = self.context['request'].user
        validated_data['recipient'] = User.objects.get(id=recipient_id)
        
        if parent_message_id:
            validated_data['parent_message'] = Message.objects.get(id=parent_message_id)
        
        return super().create(validated_data)

