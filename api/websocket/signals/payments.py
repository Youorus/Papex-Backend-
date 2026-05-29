import logging
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from api.payments.models import PaymentReceipt
from api.payments.serializers import PaymentReceiptSerializer
from api.websocket.signals.base import broadcast, safe_payload

logger = logging.getLogger(__name__)

def _send_payment_event(event: str, instance: PaymentReceipt):
    # On utilise PaymentReceipt pour l'événement "payment"
    payload = safe_payload(event, instance, PaymentReceiptSerializer)
    
    # On notifie :
    # 1. Le groupe général des clients
    # 2. Le groupe spécifique au client
    # 3. Le groupe spécifique au lead associé
    groups = ["clients", f"client-{instance.client_id}"]
    
    if instance.client and instance.client.lead_id:
        groups.append(f"leads_{instance.client.lead_id}")
        
    transaction.on_commit(lambda: broadcast(groups, payload))

@receiver(post_save, sender=PaymentReceipt)
def on_payment_saved(sender, instance: PaymentReceipt, created, **kwargs):
    logger.info("💸 post_save PaymentReceipt id=%s (created=%s)", instance.id, created)
    _send_payment_event("created" if created else "updated", instance)

@receiver(post_delete, sender=PaymentReceipt)
def on_payment_deleted(sender, instance: PaymentReceipt, **kwargs):
    logger.info("💸 post_delete PaymentReceipt id=%s", instance.id)
    _send_payment_event("deleted", instance)
