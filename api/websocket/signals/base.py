# api/websocket/signals/base.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging

logger = logging.getLogger(__name__)

def safe_payload(event: str, instance, serializer_class, extra: dict = None):
    return {
        "event": f"{instance.__class__.__name__.lower()}_{event}",
        "data": serializer_class(instance).data,
        "extra": extra or {},
    }

def broadcast(groups, payload: dict):
    channel_layer = get_channel_layer()
    text = json.dumps(payload)

    for group in groups:
        if not group:
            logger.warning("⚠️ Groupe WebSocket vide, message ignoré")
            continue
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": "send.event",  # doit correspondre à send_event dans BaseConsumer
                "text": text,
            },
        )
        logger.info(f"📢 WS Broadcast → {group} : {payload['event']}")