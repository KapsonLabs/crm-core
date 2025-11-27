from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/crm/notifications/', consumers.NotificationConsumer.as_asgi()),
    path('ws/crm/messages/', consumers.MessageConsumer.as_asgi()),
    path('ws/crm/tickets/<int:ticket_id>/comments/', consumers.TicketCommentConsumer.as_asgi()),
]