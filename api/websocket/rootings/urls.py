from django.urls import re_path
from api.websocket.consumers.leads import LeadConsumer
from api.websocket.consumers.clients import ClientRoomConsumer
from api.websocket.consumers.health import HealthCheckConsumer

websocket_urlpatterns = [
    # 🔥 Health ping/pong
    re_path(r"^ws/health/?$", HealthCheckConsumer.as_asgi()),

    # 🔥 Lead rooms
    re_path(r"^ws/leads/$", LeadConsumer.as_asgi()),
    re_path(r"^ws/leads/(?P<lead_id>\d+)/?$", LeadConsumer.as_asgi()),

    # 🔥 Client rooms
    re_path(r"^ws/client/(?P<client_id>\d+)/?$", ClientRoomConsumer.as_asgi()),
]
