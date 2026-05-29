import logging
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from api.contracts.models import Contract
from api.contracts.serializer import ContractSerializer
from api.websocket.signals.base import broadcast, safe_payload

logger = logging.getLogger(__name__)

def _send_contract_event(event: str, instance: Contract):
    payload = safe_payload(event, instance, ContractSerializer)
    
    # On notifie :
    # 1. Le groupe général des clients
    # 2. Le groupe spécifique au client
    # 3. Le groupe spécifique au lead associé
    groups = ["clients", f"client-{instance.client_id}"]
    
    if instance.client and instance.client.lead_id:
        groups.append(f"leads_{instance.client.lead_id}")
        
    transaction.on_commit(lambda: broadcast(groups, payload))

@receiver(post_save, sender=Contract)
def on_contract_saved(sender, instance: Contract, created, **kwargs):
    logger.info("📜 post_save Contract id=%s (created=%s)", instance.id, created)
    _send_contract_event("created" if created else "updated", instance)

@receiver(post_delete, sender=Contract)
def on_contract_deleted(sender, instance: Contract, **kwargs):
    logger.info("📜 post_delete Contract id=%s", instance.id)
    _send_contract_event("deleted", instance)
