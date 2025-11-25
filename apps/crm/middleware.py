"""
Custom middleware for WebSocket authentication using Django sessions
"""

import logging

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session

User = get_user_model()
logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_session(session_key):
    """Get user from session key"""
    try:
        session = Session.objects.get(session_key=session_key)
        session_data = session.get_decoded()
        user_id = session_data.get('_auth_user_id')
        
        if user_id:
            user = User.objects.get(pk=user_id)
            if user.is_active:
                return user
            else:
                logger.warning(f"User {user.email} is inactive")
        else:
            logger.warning(f"No user_id found in session {session_key}")
    except Session.DoesNotExist:
        logger.warning(f"Session not found: {session_key}")
    except User.DoesNotExist:
        logger.warning(f"User not found for user_id in session {session_key}")
    except KeyError as e:
        logger.warning(f"KeyError in session data: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting user from session: {e}", exc_info=True)
    
    return AnonymousUser()


class SessionAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using Django sessions.
    
    Reads the sessionid cookie and loads the authenticated user from the database.
    """
    
    async def __call__(self, scope, receive, send):
        # Get session key from cookies
        headers = dict(scope.get('headers', []))
        
        # Try to get cookie header (ASGI headers are lowercase bytes)
        cookie_header = headers.get(b'cookie', b'').decode()
        
        # If not found, try case-insensitive search
        if not cookie_header:
            for key, value in headers.items():
                if isinstance(key, bytes) and key.lower() == b'cookie':
                    cookie_header = value.decode() if isinstance(value, bytes) else value
                    break
        
        # Parse cookies
        cookies = {}
        if cookie_header:
            for cookie in cookie_header.split(';'):
                cookie = cookie.strip()
                if '=' in cookie:
                    key, value = cookie.split('=', 1)
                    cookies[key.strip()] = value.strip()
        
        # Get session key
        session_key = cookies.get('sessionid')
        
        if session_key:
            # Load user from session
            user = await get_user_from_session(session_key)
            logger.info(f"WebSocket auth: session_key={session_key}, user={user}, authenticated={user.is_authenticated}")
            scope['user'] = user
        else:
            logger.warning("No sessionid found in WebSocket cookies")
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)

