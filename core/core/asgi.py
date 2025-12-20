"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# HTTP application (doesn't need django.setup immediately)
http_application = get_asgi_application()

def get_websocket_application():
    """Lazy load WebSocket components after Django is setup"""
    import django
    django.setup()  # Setup Django here
    
    from channels.routing import URLRouter
    from chat.ws_jwt import JwtAuthMiddleware
    import chat.routing
    
    return JwtAuthMiddleware(
        URLRouter(chat.routing.websocket_urlpatterns)
    )

from channels.routing import ProtocolTypeRouter

application = ProtocolTypeRouter({
    "http": http_application,
    "websocket": get_websocket_application(),
})