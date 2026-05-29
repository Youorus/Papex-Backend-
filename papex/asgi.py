import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from api.websocket.middleware import JWTAuthMiddleware
from api.websocket.routing.urls import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
