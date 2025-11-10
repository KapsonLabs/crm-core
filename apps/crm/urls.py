from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    # Ticket URLs
    path('tickets/', views.TicketListView.as_view(), name='ticket-list'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket-detail'),
    path('tickets/<int:pk>/close/', views.TicketCloseView.as_view(), name='ticket-close'),
    path('tickets/<int:pk>/resolve/', views.TicketResolveView.as_view(), name='ticket-resolve'),
    path('tickets/<int:pk>/comments/', views.TicketCommentListView.as_view(), name='ticket-comments-list'),
    path('tickets/add-comment/', views.TicketCommentCreateView.as_view(), name='ticket-comment-create'),
    
    # Notification URLs (specific patterns first)
    path('notifications/mark-all-as-read/', views.NotificationMarkAllAsReadView.as_view(), name='notification-mark-all-as-read'),
    path('notifications/unread-count/', views.NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/mark-as-read/', views.NotificationMarkAsReadView.as_view(), name='notification-mark-as-read'),
    path('notifications/<int:pk>/', views.NotificationDetailView.as_view(), name='notification-detail'),
    
    # Message URLs (specific patterns first)
    path('messages/unread-count/', views.MessageUnreadCountView.as_view(), name='message-unread-count'),
    path('messages/conversations/', views.MessageConversationsView.as_view(), name='message-conversations'),
    path('messages/', views.MessageListView.as_view(), name='message-list'),
    path('messages/<int:pk>/mark-as-read/', views.MessageMarkAsReadView.as_view(), name='message-mark-as-read'),
    path('messages/<int:pk>/', views.MessageDetailView.as_view(), name='message-detail'),
]

