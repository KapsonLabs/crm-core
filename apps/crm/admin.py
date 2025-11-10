from django.contrib import admin
from .models import Ticket, TicketComment, Notification, Message, TicketAttachment

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'title', 'category', 'priority', 
        'status', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['ticket_number', 'title', 'description']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at', 'closed_at', 'resolved_at']
    filter_horizontal = ['assigned_to']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('ticket_number', 'title', 'description', 'category', 'priority')
        }),
        ('Status', {
            'fields': ('status', 'resolved_at', 'closed_at', 'closed_by')
        }),
        ('Assignment', {
            'fields': ('created_by', 'assigned_to')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'user', 'is_internal', 'created_at']
    list_filter = ['is_internal', 'created_at']
    search_fields = ['ticket__ticket_number', 'comment', 'user__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'notification_type', 'title', 
        'is_read', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'title', 'message']
    readonly_fields = ['created_at', 'read_at']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'sender', 'recipient', 'subject', 
        'is_read', 'created_at'
    ]
    list_filter = ['is_read', 'created_at']
    search_fields = ['sender__email', 'recipient__email', 'subject', 'body']
    readonly_fields = ['created_at', 'read_at']


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'file_name', 'uploaded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['ticket__ticket_number', 'file_name']
    readonly_fields = ['created_at']

