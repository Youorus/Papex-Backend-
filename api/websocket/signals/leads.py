import logging
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.websocket.signals.base import safe_payload, broadcast

logger = logging.getLogger(__name__)

def _send(event: str, instance: Lead):
    payload = safe_payload(event, instance, serializer_class=LeadSerializer)
    
    # On diffuse vers le groupe général ET le groupe spécifique au lead
    groups = ["leads", f"leads_{instance.id}"]
    
    transaction.on_commit(lambda: broadcast(groups, payload))

@receiver(post_save, sender=Lead)
def on_lead_saved(sender, instance: Lead, created, **kwargs):
    logger.info("🧲 post_save Lead id=%s (created=%s)", instance.id, created)
    _send("created" if created else "updated", instance)

@receiver(post_delete, sender=Lead)
def on_lead_deleted(sender, instance: Lead, **kwargs):
    logger.info("🧲 post_delete Lead id=%s", instance.id)
    _send("deleted", instance)