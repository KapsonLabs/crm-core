import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings

# Set Django settings module BEFORE importing anything that uses Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import WebSocket routing AFTER Django is initialized
# This is important because consumers.py imports get_user_model() which requires settings
from apps.crm.routing import websocket_urlpatterns

# application = ProtocolTypeRouter({
#     "http": django_asgi_app,
#     "websocket": AllowedHostsOriginValidator(
#         AuthMiddlewareStack(
#             URLRouter(
#                 websocket_urlpatterns
#             )
#         )
#     ),
# })

# Build WebSocket middleware stack
websocket_stack = AuthMiddlewareStack(
    URLRouter(
        websocket_urlpatterns
    )
)

# Only use AllowedHostsOriginValidator in production
# In DEBUG mode, skip origin validation for easier development and testing
if settings.DEBUG:
    # In development, skip origin validation for easier testing
    websocket_application = websocket_stack
else:
    # In production, validate origins
    websocket_application = AllowedHostsOriginValidator(websocket_stack)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": websocket_application,
})