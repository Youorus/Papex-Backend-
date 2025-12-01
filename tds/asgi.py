# tds/asgi.py
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from api.websocket.rootings.urls import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
# uvicorn tds.asgi:application --host 127.0.0.1 --port 8000 --reload
print("🚀 Chargement ASGI tds.asgi.application")  # <— DOIT s'afficher au boot

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
