from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
from django.db.models import Max

User = get_user_model()


class Ticket(models.Model):
    """
    Support ticket model.
    
    Users can create tickets, tag other users, and have discussions.
    """
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    CATEGORY_CHOICES = [
        ('technical', 'Technical Support'),
        ('billing', 'Billing Issue'),
        ('feature_request', 'Feature Request'),
        ('bug', 'Bug Report'),
        ('account', 'Account Issue'),
        ('general', 'General Inquiry'),
        ('other', 'Other'),
    ]
    
    branch = models.ForeignKey(
        'organization.Branch',
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_tickets'
    )
    assigned_to = models.ManyToManyField(
        User, 
        related_name='assigned_tickets',
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='closed_tickets'
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['created_by']),
            models.Index(fields=['ticket_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.ticket_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            # Generate ticket number: TKT-YYYYMMDD-XXXX
            today = timezone.now().strftime('%Y%m%d')
            last_ticket = Ticket.objects.filter(
                ticket_number__startswith=f'TKT-{today}'
            ).aggregate(Max('ticket_number'))
            
            if last_ticket['ticket_number__max']:
                last_num = int(last_ticket['ticket_number__max'].split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.ticket_number = f'TKT-{today}-{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    def close(self, user):
        """Close the ticket"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.closed_by = user
        self.save()
    
    def resolve(self):
        """Mark ticket as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save()
    
    @property
    def assigned_users_list(self):
        """Get list of assigned users"""
        return list(self.assigned_to.all())


class TicketComment(models.Model):
    """
    Comments/Replies on tickets.
    
    Supports discussion-style format with multiple users responding.
    """
    
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ticket_comments'
    )
    comment = models.TextField()
    is_internal = models.BooleanField(default=False)
    attachments = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user.get_full_name()} on {self.ticket.ticket_number}"


class Notification(models.Model):
    """
    System notifications for users.
    
    Notifies users about ticket updates, assignments, mentions, etc.
    """
    
    NOTIFICATION_TYPES = [
        ('ticket_assigned', 'Ticket Assigned'),
        ('ticket_commented', 'New Comment on Ticket'),
        ('ticket_mentioned', 'Mentioned in Ticket'),
        ('ticket_status_changed', 'Ticket Status Changed'),
        ('ticket_closed', 'Ticket Closed'),
        ('message_received', 'New Message Received'),
        ('system', 'System Notification'),
        ('other', 'Other'),
    ]
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related Objects
    related_ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    action_url = models.CharField(max_length=500, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} - {self.user.get_full_name()}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class Message(models.Model):
    """
    Direct messaging between users.
    
    Supports one-to-one messaging with threading.
    """    
    # Sender and Recipient
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    
    subject = models.CharField(max_length=255)
    body = models.TextField()
    
    # Threading (reply to another message)
    parent_message = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    # Attachments
    attachments = models.JSONField(default=list, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Soft Delete
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_recipient = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', 'recipient']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Message from {self.sender.get_full_name()} to {self.recipient.get_full_name()}"
    
    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    @property
    def thread_messages(self):
        """Get all messages in this thread"""
        if self.parent_message:
            root = self.parent_message
            while root.parent_message:
                root = root.parent_message
            return Message.objects.filter(
                models.Q(id=root.id) | 
                models.Q(parent_message=root)
            ).order_by('created_at')
        else:
            return Message.objects.filter(
                models.Q(id=self.id) | 
                models.Q(parent_message=self)
            ).order_by('created_at')


class TicketAttachment(models.Model):
    """
    File attachments for tickets.
    """
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ticket_attachments'
    )
    
    file = models.FileField(upload_to='ticket_attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # in bytes
    file_type = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.file_name} - {self.ticket.ticket_number}"

